"""테스트 픽스처 — SQLite in-memory + 외부의존 fake 주입."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.clients.ad.client import AdUser
from app.core.config import Settings
from app.core.deps import get_client_factory, get_secret_store
from app.core.redis_client import PermissionCache, RefreshTokenStore, SessionStore
from app.core.secrets import EnvSecretStore
from app.db import session as db_session
from app.main import create_app
from app.models import Base, Cluster, ClusterCredential, Permission, Role, RolePermission
from tests.fakes import FakeAdClient, FakeClientFactory, FakeRedis, FakeSlurmClient

SETUP_TOKEN = "test-setup-token"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret="test-secret",
        setup_token=SETUP_TOKEN,
        scheduler_enabled=False,
        # TestClient는 http로 부른다 — Secure 쿠키는 그때 저장되지 않는다.
        # 운영은 HTTPS이므로 기본값(True)을 그대로 쓴다.
        cookie_secure=False,
    )


@pytest.fixture
def engine(settings):
    # StaticPool을 써야 in-memory DB가 커넥션 간에 공유된다.
    from sqlalchemy.pool import StaticPool

    engine = db_session.init_engine(settings.database_url, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    yield engine
    db_session.dispose_engine()


@pytest.fixture
def db(engine):
    session = db_session.get_session_factory()()
    _seed_rbac(session)
    yield session
    session.close()


def _seed_rbac(session) -> None:
    """마이그레이션 0002와 동일한 초기 seed."""
    user_role = Role(code="USER", name="일반 사용자")
    admin_role = Role(code="ADMIN", name="관리자")
    perm = Permission(code="admin:access", description="ADMIN 접근")
    session.add_all([user_role, admin_role, perm])
    session.flush()
    session.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
    session.commit()


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def ad_client() -> FakeAdClient:
    return FakeAdClient(
        users=[
            AdUser("guid-admin", "opadmin", "운영관리자", "op@corp.com"),
            AdUser("guid-user", "jrpark", "박정록", "jr@corp.com"),
            AdUser("guid-other", "seonsj", "선수진", "sj@corp.com"),
        ],
        passwords={"opadmin": "pw-admin", "jrpark": "pw-user", "seonsj": "pw-other"},
    )


@pytest.fixture
def slurm_client() -> FakeSlurmClient:
    return FakeSlurmClient(
        jobs=[
            {"job_id": 45812, "name": "llm-finetune", "user_name": "jrpark", "job_state": "RUNNING", "partition": "gpu"},
            {"job_id": 45813, "name": "cfd-solve", "user_name": "seonsj", "job_state": "PENDING", "partition": "cpu"},
        ]
    )


@pytest.fixture
def secret_store(settings) -> EnvSecretStore:
    return EnvSecretStore(settings)


@pytest.fixture
def app(settings, engine, redis, secret_store, slurm_client, ad_client, monkeypatch):
    """앱 조립 — lifespan의 외부 자원 초기화를 fake로 대체한다."""

    def fake_bootstrap(app_, settings_):
        app_.state.redis = redis
        app_.state.session_store = SessionStore(redis, settings_.session_ttl_seconds)
        app_.state.refresh_token_store = RefreshTokenStore(
            redis, settings_.refresh_token_ttl_seconds
        )
        app_.state.permission_cache = PermissionCache(redis, settings_.permission_cache_ttl_seconds)
        app_.state.secret_store = secret_store
        app_.state.client_factory = FakeClientFactory(slurm_client)

    monkeypatch.setattr("app.main.bootstrap_state", fake_bootstrap)
    monkeypatch.setattr("app.main.init_engine", lambda url, **kw: engine)
    monkeypatch.setattr("app.main.dispose_engine", lambda: None)
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    application = create_app(settings)
    application.dependency_overrides[get_secret_store] = lambda: secret_store
    application.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(slurm_client)

    # AD client는 AuthService 내부에서 만들어지므로 팩토리 훅을 갈아끼운다.
    import app.services.auth as auth_module

    original_init = auth_module.AuthService.__init__

    def patched_init(self, session, settings_, *, ad_client_factory=None, **kwargs):
        # 인자를 나열하지 않고 그대로 넘긴다 — 서비스에 인자가 늘어도 여기가 깨지지 않는다.
        original_init(
            self,
            session,
            settings_,
            ad_client_factory=ad_client_factory or (lambda conn, password=None: ad_client),
            **kwargs,
        )

    monkeypatch.setattr(auth_module.AuthService, "__init__", patched_init)

    from app.core.deps import get_app_settings

    application.dependency_overrides[get_app_settings] = lambda: settings
    return application


@pytest.fixture
def client(app, db) -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bootstrapped(client, ad_client) -> dict:
    """seed ADMIN까지 마친 상태를 만든다."""
    resp = client.post(
        "/api/v1/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "ldaps_url": "ldaps://ad.corp.com",
            "base_dn": "dc=corp,dc=com",
            "bind_account": "svc-portal",
            "bind_password": "bind-pw",
            "allowed_group": "cn=HPC-Users,dc=corp,dc=com",
            "id_attribute": "sAMAccountName",
            "seed_admin_username": "opadmin",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def login(client: TestClient, username: str, password: str) -> str:
    """Bearer 토큰을 하나 얻는다. **세션 쿠키는 남기지 않는다.**

    로그인은 토큰과 쿠키를 함께 발급한다(브라우저용). 그런데 `TestClient`는 쿠키를
    들고 다니므로, 이 헬퍼가 쿠키를 남기면 **이후의 "자격증명 없는" 요청이 실제로는
    인증된 요청이 된다.** 그러면 401을 기대하는 권한 테스트가 조용히 통과하거나
    엉뚱한 코드로 실패한다 — 실제로 `test_settings_require_admin`이 그렇게 깨졌다.

    쿠키 자체를 검증하는 테스트는 이 헬퍼를 쓰지 않고 엔드포인트를 직접 부른다
    (`tests/test_auth_cookies.py`).
    """
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    client.cookies.clear()
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_token(client, bootstrapped) -> str:
    return login(client, "opadmin", "pw-admin")


@pytest.fixture
def user_token(client, bootstrapped) -> str:
    return login(client, "jrpark", "pw-user")


@pytest.fixture
def cluster(db, secret_store) -> Cluster:
    """등록된 클러스터 + JWT 자격증명."""
    c = Cluster(
        name="seoul-hpc",
        slurmrestd_url="http://slurmrestd.local:6820",
        api_version="v0.0.43",
        auth_method="jwt",
        is_default=True,
        is_active=True,
    )
    db.add(c)
    db.flush()
    secret_ref = f"cluster/{c.id}/SLURM_JWT"
    secret_store.put(secret_ref, "fake.jwt.token")
    db.add(ClusterCredential(cluster_id=c.id, kind="SLURM_JWT", secret_ref=secret_ref))
    db.commit()
    return c


class _AllImagesPresent:
    """이미지 디렉터리에 **카탈로그가 가리키는 SIF가 다 있다**고 보는 가짜 SSH.

    제출 경로가 이제 "이 클러스터에 이미지가 있는가"를 본다(T-06). 그게 주제가 아닌
    테스트까지 전부 SSH를 흉내 내게 만들면 배보다 배꼽이 커진다. 목록은 **부를 때**
    계산한다 — `monkeypatch.setattr(B, "APPS", ...)`로 카탈로그를 갈아 끼우는
    테스트가 많아서, 미리 굳혀 두면 그쪽이 조용히 깨진다.

    이미지가 **없는** 상태는 `test_app_images.py`가 따로 고정한다.
    """

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def list_dir(self, user, path, **kw):
        from app.clients.ssh.client import FileEntry
        from app.services import batch_apps, session_apps

        names = {a.image for a in session_apps.APPS if a.image}
        names |= {a.image for a in batch_apps.APPS if a.image}
        entries = [
            FileEntry(name=n, is_dir=False, size=1, mtime=None, mode="-rw-r--r--", uid=0, gid=0)
            for n in sorted(names)
        ]
        return path, entries


@pytest.fixture(autouse=True)
def images_present(monkeypatch):
    """기본값: 카탈로그의 이미지가 클러스터에 다 있다. 자세한 근거는 `_AllImagesPresent`."""
    monkeypatch.setattr(
        "app.services.app_images.AppImageService._connect",
        lambda self, cluster: _AllImagesPresent(),
    )
