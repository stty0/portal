"""고위험 구간 회귀 테스트 (C-01·C-02·C-05).

plan.md §4에 따라 인증·인가·감사·Secret을 별도로 재검증한다.
"""

from app.clients.ad.client import AdUser
from app.core.security import create_session_token
from tests.conftest import auth_headers, login


def test_stale_token_cannot_ride_username_reuse(client, db, settings, ad_client, bootstrapped):
    """세션 키가 username이라 재사용 시 옛 JWT가 남의 세션에 올라탈 수 있었다.

    토큰의 objectGUID를 현재 사용자와 대조해 막는다.
    """
    ad_client.users.append(AdUser("guid-first", "shared", "최초 사용자"))
    ad_client.passwords["shared"] = "pw1"
    stale_token = login(client, "shared", "pw1")
    assert client.get("/api/v1/auth/me", headers=auth_headers(stale_token)).status_code == 200

    # 같은 sAMAccountName을 다른 사람(GUID 다름)이 물려받고 로그인 → 세션 키가 겹친다.
    ad_client.users = [u for u in ad_client.users if u.username != "shared"]
    ad_client.users.append(AdUser("guid-second", "shared", "후임자"))
    ad_client.passwords["shared"] = "pw2"
    login(client, "shared", "pw2")

    # 옛 소유자의 JWT는 서명도 유효하고 세션도 존재하지만 거부돼야 한다.
    resp = client.get("/api/v1/auth/me", headers=auth_headers(stale_token))
    assert resp.status_code == 401


def test_token_with_unknown_sid_is_rejected(client, settings, user_token):
    """서명이 유효해도 세션 레코드가 없으면 거부된다 — sid는 추측 불가한 난수다."""
    forged = create_session_token(
        settings, sid="made-up-session-id", username="opadmin", guid="guid-admin", role="ADMIN"
    )
    assert client.get("/api/v1/auth/me", headers=auth_headers(forged)).status_code == 401


def test_identity_comes_from_session_not_jwt_claims(client, db, redis, settings, user_token):
    """JWT의 sub/guid/role을 조작해도 신원·권한은 세션 레코드와 DB가 정한다."""
    from app.core.redis_client import SessionStore
    from jose import jwt as jose_jwt

    sid = jose_jwt.get_unverified_claims(user_token)["sid"]
    store = SessionStore(redis, settings.session_ttl_seconds)
    assert store.get(sid).username == "jrpark"

    # 같은 sid에 남의 신원·ADMIN role을 실어 재서명한다.
    escalated = create_session_token(
        settings, sid=sid, username="opadmin", guid="guid-admin", role="ADMIN"
    )
    me = client.get("/api/v1/auth/me", headers=auth_headers(escalated))
    assert me.status_code == 200
    assert me.json()["username"] == "jrpark"  # 클레임이 아니라 세션의 guid로 조회
    assert me.json()["role"] == "USER"
    assert client.get("/api/v1/users", headers=auth_headers(escalated)).status_code == 403


def test_logout_ends_only_that_session(client, bootstrapped):
    """세션이 sid 단위라 한 기기에서 로그아웃해도 다른 기기는 유지된다."""
    laptop = login(client, "jrpark", "pw-user")
    phone = login(client, "jrpark", "pw-user")
    assert laptop != phone

    assert client.post("/api/v1/auth/logout", headers=auth_headers(laptop)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth_headers(laptop)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth_headers(phone)).status_code == 200


def test_revoke_all_ends_every_session(client, redis, settings, bootstrapped):
    from app.core.redis_client import SessionStore

    tokens = [login(client, "jrpark", "pw-user") for _ in range(3)]
    store = SessionStore(redis, settings.session_ttl_seconds)
    assert store.revoke_all("guid-user") == 3
    for token in tokens:
        assert client.get("/api/v1/auth/me", headers=auth_headers(token)).status_code == 401


def test_setup_token_comparison_is_constant_time():
    """setup 토큰 비교는 상수시간이어야 한다 — 길이별 시간차로 한 글자씩 추측당한다."""
    import inspect

    from app.services import auth

    # 검증은 setup/probe 공통 진입점 한 곳에 모여 있다.
    assert "compare_digest" in inspect.getsource(auth.AuthService._assert_setup_allowed)


def test_secret_values_never_appear_in_audit_log(client, db, cluster, admin_token):
    from app.models import AuditLog

    client.put(
        f"/api/v1/clusters/{cluster.id}/credentials",
        json={"kind": "SSH_KEY", "value": "-----BEGIN OPENSSH PRIVATE KEY-----abc"},
        headers=auth_headers(admin_token),
    )
    for entry in db.query(AuditLog).all():
        assert "BEGIN OPENSSH" not in (entry.detail or "")
        assert "BEGIN OPENSSH" not in (entry.target or "")


def test_control_actions_are_all_audited(client, db, cluster, admin_token, user_token):
    from app.models import AuditLog

    client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={"name": "j", "script": "srun true"},
        headers=auth_headers(user_token),
    )
    client.delete(f"/api/v1/clusters/{cluster.id}/jobs/45812", headers=auth_headers(user_token))
    client.patch(
        f"/api/v1/clusters/{cluster.id}/jobs/45812",
        json={"action": "hold"},
        headers=auth_headers(admin_token),
    )

    actions = {a for (a,) in db.query(AuditLog.action).all()}
    assert {"JOB_SUBMIT", "JOB_CANCEL", "JOB_HOLD"} <= actions


def test_read_only_calls_are_not_audited(client, db, cluster, user_token):
    """감사 로그가 조회로 가득 차면 제어 이력이 묻힌다(C-05는 제어성 액션 대상)."""
    from app.models import AuditLog

    before = db.query(AuditLog).count()
    client.get(f"/api/v1/clusters/{cluster.id}/jobs", headers=auth_headers(user_token))
    client.get(f"/api/v1/clusters/{cluster.id}/jobs/45812", headers=auth_headers(user_token))
    assert db.query(AuditLog).count() == before


def test_internal_error_does_not_leak_details(app, db, cluster, user_token, monkeypatch):
    """예기치 못한 예외의 내부 메시지가 응답으로 새면 안 된다."""
    from fastapi.testclient import TestClient

    def boom(*args, **kwargs):
        raise RuntimeError("db password is hunter2")

    monkeypatch.setattr("app.services.job.JobService.list_jobs", boom)
    # 실제 서버처럼 동작시키려면 예외 재발생을 꺼야 핸들러 응답을 볼 수 있다.
    with TestClient(app, raise_server_exceptions=False) as raw:
        resp = raw.get(
            f"/api/v1/clusters/{cluster.id}/jobs", headers=auth_headers(user_token)
        )
    assert resp.status_code == 500
    assert "hunter2" not in resp.text
    assert resp.json()["code"] == "INTERNAL_ERROR"
