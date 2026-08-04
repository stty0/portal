"""인가 테스트 (C-02, backend-design §3.4·§3.5).

라우터가 `require_permission` 문법을 쓰므로, permission이 세분화돼도 이 테스트의
의미는 유지된다.
"""

import pytest

from tests.conftest import auth_headers

ADMIN_ONLY_GET = ["/api/v1/users", "/api/v1/ad/connection"]


@pytest.mark.parametrize("path", ADMIN_ONLY_GET)
def test_user_cannot_access_admin_endpoints(client, user_token, path):
    resp = client.get(path, headers=auth_headers(user_token))
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"
    assert resp.json()["detail"]["required"] == "admin:access"


@pytest.mark.parametrize("path", ADMIN_ONLY_GET)
def test_anonymous_is_rejected_before_permission_check(client, bootstrapped, path):
    assert client.get(path).status_code == 401


def test_admin_can_list_users(client, admin_token):
    resp = client.get("/api/v1/users", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_forced_logout_invalidates_valid_jwt(client, redis, settings, admin_token):
    from app.core.redis_client import SessionStore

    headers = auth_headers(admin_token)
    assert client.get("/api/v1/users", headers=headers).status_code == 200
    # 관리자가 이 사용자의 모든 세션을 강제 종료 — JWT는 그대로지만 즉시 막혀야 한다.
    store = SessionStore(redis, settings.session_ttl_seconds)
    assert store.revoke_all("guid-admin") == 1
    assert client.get("/api/v1/users", headers=headers).status_code == 401


def test_deactivated_user_is_blocked(client, db, admin_token, user_token):
    """비활성화는 세션까지 끊는다 — 401(세션 없음)로 즉시 차단된다."""
    from app.models import User

    resp = client.get("/api/v1/auth/me", headers=auth_headers(user_token))
    assert resp.status_code == 200

    guid = db.query(User).filter_by(username="jrpark").one().ad_object_guid
    patch = client.patch(
        f"/api/v1/users/{guid}", json={"is_active": False}, headers=auth_headers(admin_token)
    )
    assert patch.status_code == 200

    assert client.get("/api/v1/auth/me", headers=auth_headers(user_token)).status_code == 401


def test_role_change_takes_effect(client, db, admin_token, user_token):
    from app.models import User

    guid = db.query(User).filter_by(username="jrpark").one().ad_object_guid
    resp = client.patch(
        f"/api/v1/users/{guid}", json={"role": "ADMIN"}, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "ADMIN"
    # 권한 캐시는 role 단위라 사용자 role 변경은 즉시 반영된다.
    assert client.get("/api/v1/users", headers=auth_headers(user_token)).status_code == 200


def test_cannot_demote_last_admin(client, db, admin_token):
    from app.models import User

    guid = db.query(User).filter_by(username="opadmin").one().ad_object_guid
    resp = client.patch(
        f"/api/v1/users/{guid}", json={"role": "USER"}, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CONFLICT"


def test_ad_identity_fields_are_not_updatable(client, db, admin_token, user_token):
    """AD 소유 필드는 스키마에 없으므로 무시된다(정의서 §1.2)."""
    from app.models import User

    guid = db.query(User).filter_by(username="jrpark").one().ad_object_guid
    resp = client.patch(
        f"/api/v1/users/{guid}",
        json={"username": "hacked", "display_name": "hacked", "email": "x@y.z"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "jrpark"
