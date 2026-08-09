"""기반 계층 단위 테스트 — client·Secret·모델 경계."""

import httpx
import pytest

from app.clients.base_http import BaseHttpClient
from app.clients.slurm.client import SlurmrestdClient
from app.core.errors import ExternalServiceError, NotFound, SecretNotFound, SlurmUnauthorized
from app.core.redis_client import redis_lock
from app.core.secrets import EnvSecretStore
from tests.fakes import FakeRedis


def _transport(handler):
    return httpx.MockTransport(handler)


def test_slurm_headers_carry_token_and_impersonation():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"jobs": []})

    client = SlurmrestdClient(
        "http://slurm:6820",
        token_provider=lambda: "jwt-abc",
        api_version="v0.0.43",
        transport=_transport(handler),
    )
    client.get_jobs(as_user="jrpark")
    assert seen["x-slurm-user-token"] == "jwt-abc"
    assert seen["x-slurm-user-name"] == "jrpark"


def test_slurm_omits_impersonation_when_not_user_scoped():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json={})

    client = SlurmrestdClient(
        "http://slurm:6820", token_provider=lambda: "t", transport=_transport(handler)
    )
    client.ping()
    assert "x-slurm-user-name" not in seen


def test_slurm_401_maps_to_token_reregistration():
    client = SlurmrestdClient(
        "http://slurm:6820",
        token_provider=lambda: "expired",
        transport=_transport(lambda r: httpx.Response(401, json={"error": "invalid token"})),
    )
    with pytest.raises(SlurmUnauthorized) as exc:
        client.ping()
    assert "재등록" in exc.value.message


def test_api_version_is_pinned_in_path():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={})

    client = SlurmrestdClient(
        "http://slurm:6820",
        token_provider=lambda: "t",
        api_version="v0.0.43",
        transport=_transport(handler),
    )
    client.ping()
    client.get_accounting_jobs()
    assert paths == ["/slurm/v0.0.43/ping", "/slurmdb/v0.0.43/jobs"]


def test_retry_only_for_idempotent_methods():
    calls = {"GET": 0, "POST": 0}

    def handler(request):
        calls[request.method] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = BaseHttpClient("http://x", max_retries=2, transport=_transport(handler))
    with pytest.raises(ExternalServiceError):
        client.request("GET", "/a")
    with pytest.raises(ExternalServiceError):
        client.request("POST", "/a")
    assert calls["GET"] == 3  # 최초 + 재시도 2
    assert calls["POST"] == 1  # 중복 제출 방지 — 재시도하지 않는다


def test_4xx_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, json={})

    client = BaseHttpClient("http://x", max_retries=3, transport=_transport(handler))
    with pytest.raises(NotFound):
        client.request("GET", "/missing")
    assert len(calls) == 1


def test_secret_store_roundtrip_and_missing(settings):
    store = EnvSecretStore(settings)
    store.put("cluster/1/SLURM_JWT", "value")
    assert store.get("cluster/1/SLURM_JWT") == "value"
    with pytest.raises(SecretNotFound):
        store.get("cluster/9/SLURM_JWT")


def test_redis_lock_prevents_concurrent_batch():
    redis = FakeRedis()
    with redis_lock(redis, "sync:lock:ad") as first:
        assert first is True
        with redis_lock(redis, "sync:lock:ad") as second:
            assert second is False  # 다른 replica는 건너뛴다
    with redis_lock(redis, "sync:lock:ad") as third:
        assert third is True  # 해제 후 재획득 가능


def test_client_factory_survives_detached_cluster(db, settings, secret_store):
    """풀에 캐시된 client가 요청 단위 세션의 ORM 객체를 붙잡으면 안 된다.

    실환경에서 발견된 결함: 한 요청이 오류로 rollback되면 ORM 속성이 만료되고 세션이
    닫히는데, 캐시된 client의 token_provider가 그 인스턴스를 참조하고 있어 **그 클러스터의
    이후 모든 요청이 500(DetachedInstanceError)** 이 됐다. 앱 재시작 전까지 복구되지 않는다.
    """
    from app.clients.factory import ClusterClientFactory
    from app.clients.token_provider import SlurmTokenProvider
    from app.models import Cluster

    cluster = Cluster(name="c1", slurmrestd_url="http://slurm:6820", api_version="v0.0.43")
    db.add(cluster)
    db.commit()
    secret_store.put("cluster/1/SLURM_JWT", "jwt-value")

    factory = ClusterClientFactory(
        settings,
        SlurmTokenProvider(secret_store),
        transport_factory=lambda: _transport(lambda r: httpx.Response(200, json={"ok": True})),
    )
    client = factory.slurm(cluster, "cluster/1/SLURM_JWT")

    # 오류 경로 재현: session_scope의 rollback은 열린 트랜잭션의 ORM 속성을 **만료**시키고,
    # 이어서 세션이 닫히면 인스턴스가 detached가 된다. 그 상태를 그대로 만든다.
    db.expire_all()
    db.close()

    assert client.ping() == {"ok": True}


def test_models_match_erd_entity_count():
    """db-erd.md의 엔티티 수와 일치해야 한다.

    22 = 초기 21개 - `user_ssh_key`(U-AC-03, 0005) - `job_template`(U-JB-03/A-OP-02, 0012)
    + `api_token`(C-01 기계 자격증명, 0013) + `app_access`(앱별 허용 계정, 0014)
    + `app_catalog`(A-OP-02 앱 정보, 0015).
    """
    from app.models import Base

    assert len(Base.metadata.tables) == 22


def test_slurm_owned_entities_are_not_portal_tables():
    """account·QOS·association은 slurmdbd 소유 — Portal DB에 있으면 경계 위반."""
    from app.models import Base

    names = set(Base.metadata.tables)
    assert not names & {"account", "qos", "association", "slurm_user"}


# --- slurmrestd 숫자 어댑터 ------------------------------------------------
# 같은 필드를 서비스마다 따로 풀다가 답이 갈린 적이 있다: 한쪽은 맨 숫자를 그대로 받고
# 다른 쪽은 None(=한도 없음)으로 접어, QOS 한도가 판본에 따라 "무제한"으로 뒤집혔다.


def test_number_adapter_accepts_both_shapes():
    from app.clients.slurm.adapters import number

    # 래퍼
    assert number({"set": True, "infinite": False, "number": 5}) == 5
    # 맨 숫자 — 이걸 None으로 접으면 "5개 제한"이 "무제한"으로 뒤집힌다
    assert number(5) == 5
    assert number(0) == 0
    # 무제한·미설정은 None이다. 0으로 접으면 "0 제한"으로 오해된다.
    assert number({"set": True, "infinite": True, "number": 0}) is None
    assert number({"set": False, "infinite": False, "number": 7}) is None
    assert number(None) is None
    assert number("8") is None
    # bool은 숫자가 아니다 — isinstance(True, int)가 참이라 걸러내지 않으면 1로 샌다
    assert number(True) is None


def test_int_or_folds_missing_to_zero():
    """한도(무제한=None)와 달리 "노드의 CPU 수"는 모르면 세지 않는 편이 맞다."""
    from app.clients.slurm.adapters import int_or

    assert int_or({"set": True, "infinite": False, "number": 8}) == 8
    assert int_or(8) == 8
    assert int_or(None) == 0
    assert int_or({"set": False}) == 0


def test_qos_limits_read_plain_numbers_too():
    """account 서비스도 같은 어댑터를 쓴다 — 맨 숫자를 "무제한"으로 뒤집지 않는다."""
    from app.services.account import _qos_limits

    limits = _qos_limits(
        {
            "name": "normal",
            "priority": 10,  # 래퍼가 아니라 맨 숫자로 오는 경우
            "limits": {"max": {"jobs": {"active_jobs": {"per": {"user": 5}}}}},
        }
    )
    assert limits["priority"] == 10
    assert limits["max_jobs_per_user"] == 5


def test_tables_without_code_are_the_documented_ones():
    """쓰는 코드가 없는 표 목록이 **문서와 일치**해야 한다.

    2026-08-07에 `job_template`을 지운 이유가 "쓰는 사람이 없는 표"였다. 그 상태를
    금지하지는 않는다 — 정의서에 있는 기능의 선행 스키마는 남길 이유가 있다. 다만
    **모르는 채로 늘어나는 것**은 막는다. 새 표를 만들고 서비스를 안 붙였거나, 반대로
    기능을 붙였는데 `models/ops.py`의 목록을 안 고치면 여기서 걸린다.
    """
    import pathlib
    import re

    from app.models import Base

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    sources = "\n".join(
        p.read_text(encoding="utf-8")
        for group in ("services", "routers", "repositories")
        for p in (app_dir / group).rglob("*.py")
    )
    classes = {
        m.group(2): m.group(1)  # 테이블명 → 클래스명
        for text in [(app_dir / "models").rglob("*.py")]
        for p in text
        for m in re.finditer(
            r'class (\w+)\(Base\):.*?__tablename__ = "(\w+)"',
            p.read_text(encoding="utf-8"),
            re.DOTALL,
        )
    }
    assert set(classes) == set(Base.metadata.tables), "모델 스캔이 테이블 전체를 못 찾았다"

    unused = {t for t, cls in classes.items() if not re.search(rf"\b{cls}\b", sources)}
    assert unused == {
        "license_server",            # A-LM-01 (SCR-17) 미구현
        "license_feature_snapshot",  # A-LM-02·05 미구현
        "ticket",                    # A-OP-05 · U-AC-04 미구현
        "report_schedule",           # A-RP-04 미구현
        "chargeback_rate",           # A-RP-05 미구현
        "billing_snapshot",          # A-BL-03·04 수집 이력 미구현
    }, f"쓰이지 않는 표 목록이 바뀌었다: {sorted(unused)} — models/ops.py 머리말도 함께 고칠 것"


# --- A-OP-02 앱 카탈로그 -----------------------------------------------------
def _app_body(**overrides):
    return {
        "kind": "interactive",
        "app_id": "jupyter",
        "name": "JupyterLab",
        "vendor": "Project Jupyter",
        "version": "4.2",
        "image_location": "docker://reg.dt-hpc.net/hpc/jupyter:4.2",
        "icon_file": "jupyter.svg",
        "description": "노트북 세션",
        **overrides,
    }


def test_app_catalog_crud_is_admin_only(client, admin_token, user_token):
    from tests.conftest import auth_headers

    # 읽기는 인증 사용자에게 열려 있다 — 사용자 화면이 아이콘·벤더를 읽는다.
    assert client.get("/api/v1/apps", headers=auth_headers(user_token)).status_code == 200
    assert client.post(
        "/api/v1/apps", json=_app_body(), headers=auth_headers(user_token)
    ).status_code == 403

    created = client.post("/api/v1/apps", json=_app_body(), headers=auth_headers(admin_token))
    assert created.status_code == 201
    pk = created.json()["id"]

    patched = client.patch(
        f"/api/v1/apps/{pk}", json={"version": "4.3"}, headers=auth_headers(admin_token)
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == "4.3"
    assert patched.json()["vendor"] == "Project Jupyter"  # 부분 수정이 다른 값을 지우지 않는다

    assert client.delete(f"/api/v1/apps/{pk}", headers=auth_headers(admin_token)).status_code == 200
    # 등록을 지워도 코드 카탈로그의 앱은 목록에 남는다 — 사라지는 것은 등록 정보뿐이다.
    after = _find_app(client, admin_token, "interactive", "jupyter")
    assert after["id"] is None
    assert after["vendor"] is None


def test_app_catalog_rejects_duplicate_and_unknown_kind(client, admin_token):
    from tests.conftest import auth_headers

    assert client.post(
        "/api/v1/apps", json=_app_body(), headers=auth_headers(admin_token)
    ).status_code == 201
    # 같은 (kind, app_id)는 코드 카탈로그로 가는 연결 키라 하나여야 한다.
    assert client.post(
        "/api/v1/apps", json=_app_body(), headers=auth_headers(admin_token)
    ).status_code == 409
    # kind가 다르면 같은 app_id를 써도 다른 앱이다.
    assert client.post(
        "/api/v1/apps", json=_app_body(kind="batch"), headers=auth_headers(admin_token)
    ).status_code == 201
    assert client.post(
        "/api/v1/apps", json=_app_body(kind="desktop"), headers=auth_headers(admin_token)
    ).status_code == 422


def test_app_catalog_changes_are_audited_by_reference_only(client, db, admin_token):
    from app.models import AuditLog
    from tests.conftest import auth_headers

    client.post("/api/v1/apps", json=_app_body(), headers=auth_headers(admin_token))
    entry = db.query(AuditLog).filter_by(action="APP_CREATE").one()
    assert entry.target == "JupyterLab"
    assert entry.detail == "interactive/jupyter"


def test_icon_url_is_derived_from_stored_filename(client, admin_token):
    """DB에는 파일명만 남고 주소는 서버가 만든다 — 배포 위치가 DB로 새지 않는다."""
    from app.models import AppCatalog
    from tests.conftest import auth_headers

    created = client.post(
        "/api/v1/apps", json=_app_body(), headers=auth_headers(admin_token)
    ).json()
    assert created["icon_file"] == "jupyter.svg"
    assert created["icon_url"] == "/api/v1/app-icons/jupyter.svg"
    assert not hasattr(AppCatalog, "icon_url")  # 컬럼이 아니라 파생값이다


def test_app_icon_serving_rejects_traversal_and_unknown_types(client, admin_token, tmp_path):
    """아이콘 디렉터리 밖은 어떤 형태로도 읽히면 안 된다."""
    from app.core.config import get_settings
    from tests.conftest import auth_headers

    (tmp_path / "ok.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (tmp_path / "secret.env").write_text("PORTAL_JWT_SECRET=leak")
    outside = tmp_path.parent / "outside.svg"
    outside.write_text("<svg/>")
    (tmp_path / "link.svg").symlink_to(outside)

    settings = get_settings()
    original = settings.app_icon_dir
    object.__setattr__(settings, "app_icon_dir", str(tmp_path))
    try:
        h = auth_headers(admin_token)
        ok = client.get("/api/v1/app-icons/ok.svg", headers=h)
        assert ok.status_code == 200
        assert ok.headers["content-type"].startswith("image/svg+xml")
        # SVG를 직접 열어도 스크립트가 돌지 않게 잠근다
        assert ok.headers["content-security-policy"] == "default-src 'none'; style-src 'unsafe-inline'"
        assert ok.headers["x-content-type-options"] == "nosniff"

        for bad in ("../secret.env", "..%2Fsecret.env", "secret.env", ".hidden.svg", "link.svg"):
            assert client.get(f"/api/v1/app-icons/{bad}", headers=h).status_code in (307, 404)

        assert client.get("/api/v1/app-icons", headers=h).json() == ["ok.svg"]
    finally:
        object.__setattr__(settings, "app_icon_dir", original)


def _find_app(client, token, kind, app_id):
    from tests.conftest import auth_headers

    rows = client.get("/api/v1/apps", headers=auth_headers(token)).json()
    return next(r for r in rows if r["kind"] == kind and r["app_id"] == app_id)


def test_app_list_includes_code_catalog_apps_without_registration(client, admin_token):
    """등록이 0건이어도 코드 카탈로그의 앱은 보여야 한다.

    등록된 것만 주면 아직 등록하지 않은 앱이 관리 화면에서 존재하지 않는 것이 된다.
    """
    from tests.conftest import auth_headers

    rows = client.get("/api/v1/apps", headers=auth_headers(admin_token)).json()
    keys = {(r["kind"], r["app_id"]) for r in rows}
    assert ("interactive", "desktop") in keys
    assert ("interactive", "paraview") in keys
    assert ("batch", "openfoam") in keys

    desktop = _find_app(client, admin_token, "interactive", "desktop")
    assert desktop["id"] is None  # 아직 등록 안 함 → 등록 대상
    assert desktop["in_code"] is True
    assert desktop["name"]  # 이름·설명은 코드 카탈로그 값이 쓰인다
    assert desktop["vendor"] is None


def test_registered_metadata_overlays_code_catalog(client, admin_token):
    from tests.conftest import auth_headers

    client.post(
        "/api/v1/apps",
        json=_app_body(app_id="desktop", name="원격 데스크톱 (사내)", vendor="MATE"),
        headers=auth_headers(admin_token),
    )
    row = _find_app(client, admin_token, "interactive", "desktop")
    assert row["id"] is not None
    assert row["in_code"] is True
    assert row["name"] == "원격 데스크톱 (사내)"  # 등록 이름이 코드 이름을 덮는다
    assert row["vendor"] == "MATE"


def test_registration_for_app_not_in_code_is_kept(client, admin_token):
    """도입 예정 앱을 미리 등록할 수 있다 — 코드에 없다고 목록에서 빠지면 안 된다."""
    from tests.conftest import auth_headers

    client.post(
        "/api/v1/apps",
        json=_app_body(app_id="ansys-fluent", name="Ansys Fluent"),
        headers=auth_headers(admin_token),
    )
    row = _find_app(client, admin_token, "interactive", "ansys-fluent")
    assert row["in_code"] is False
    assert row["id"] is not None
