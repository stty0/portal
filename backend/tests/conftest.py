"""테스트 픽스처 — SQLite in-memory + 외부의존 fake 주입."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.clients.ad.client import AdUser
from app.core.config import Settings
from app.core.deps import get_client_factory, get_secret_store
from app.core.redis_client import PermissionCache, SessionStore
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

    def patched_init(self, session, settings_, *, secrets, sessions, ad_client_factory=None):
        original_init(
            self,
            session,
            settings_,
            secrets=secrets,
            sessions=sessions,
            ad_client_factory=ad_client_factory or (lambda conn, password=None: ad_client),
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
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
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
        api_version="v0.0.41",
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
