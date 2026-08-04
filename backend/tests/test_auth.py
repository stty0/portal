"""인증·부트스트랩 테스트 (C-01·C-02, A-US-01)."""

from app.clients.ad.client import AdUser
from tests.conftest import SETUP_TOKEN, auth_headers, login


def test_setup_status_before_bootstrap(client):
    resp = client.get("/api/v1/auth/setup-status")
    assert resp.status_code == 200
    assert resp.json()["bootstrap_required"] is True


def test_setup_seeds_admin_and_locks(client, bootstrapped):
    assert client.get("/api/v1/auth/setup-status").json()["bootstrap_required"] is False

    # 1회용 — 두 번째 호출은 서버가 하드 거부한다.
    resp = client.post(
        "/api/v1/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "ldaps_url": "ldaps://evil",
            "base_dn": "dc=corp,dc=com",
            "bind_account": "x",
            "bind_password": "y",
            "seed_admin_username": "jrpark",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "BOOTSTRAP_LOCKED"


def test_setup_rejects_wrong_token(client):
    resp = client.post(
        "/api/v1/auth/setup",
        json={
            "setup_token": "wrong",
            "ldaps_url": "ldaps://ad",
            "base_dn": "dc=corp,dc=com",
            "bind_account": "svc",
            "bind_password": "pw",
            "seed_admin_username": "opadmin",
        },
    )
    assert resp.status_code == 403


def test_setup_rejects_unknown_ad_user(client):
    resp = client.post(
        "/api/v1/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "ldaps_url": "ldaps://ad",
            "base_dn": "dc=corp,dc=com",
            "bind_account": "svc",
            "bind_password": "pw",
            "seed_admin_username": "nobody",
        },
    )
    assert resp.status_code == 422


def test_login_jit_provisions_user(client, bootstrapped):
    token = login(client, "jrpark", "pw-user")
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["username"] == "jrpark"
    assert me["role"] == "USER"
    assert me["permissions"] == []  # USER는 admin:access 미보유


def test_admin_has_permission(client, admin_token):
    me = client.get("/api/v1/auth/me", headers=auth_headers(admin_token)).json()
    assert me["role"] == "ADMIN"
    assert me["permissions"] == ["admin:access"]


def test_login_wrong_password_is_generic(client, bootstrapped):
    resp = client.post(
        "/api/v1/auth/login", json={"username": "jrpark", "password": "nope"}
    )
    assert resp.status_code == 401
    # 계정 존재 여부가 새어 나가면 안 된다.
    assert resp.json()["detail"] is None


def test_logout_revokes_session_immediately(client, user_token):
    headers = auth_headers(user_token)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    # JWT 자체는 아직 유효하지만 Redis 세션이 없으므로 거부돼야 한다.
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_rename_keeps_role(client, db, admin_token, ad_client, bootstrapped):
    """username이 바뀌어도 objectGUID가 같으면 동일인 — role을 유지한다."""
    from app.models import User

    user = db.get(User, "guid-admin")
    assert user.role.code == "ADMIN"

    ad_client.users = [AdUser("guid-admin", "opadmin2", "운영관리자", "op@corp.com")]
    ad_client.passwords = {"opadmin2": "pw-admin"}
    login(client, "opadmin2", "pw-admin")

    db.expire_all()
    renamed = db.get(User, "guid-admin")
    assert renamed.username == "opadmin2"
    assert renamed.role.code == "ADMIN"  # 개명이 권한을 바꾸지 않는다


def test_guid_reuse_provisions_new_user(client, db, ad_client, bootstrapped):
    """sAMAccountName 재사용 — GUID가 다르면 전임자의 role을 물려받지 않는다."""
    from app.models import Role, User

    admin_role = db.query(Role).filter_by(code="ADMIN").one()
    db.add(
        User(ad_object_guid="guid-old", username="reused", display_name="전임자", role_id=admin_role.id)
    )
    db.commit()

    ad_client.users.append(AdUser("guid-new", "reused", "신규 입사자", "new@corp.com"))
    ad_client.passwords["reused"] = "pw-new"
    login(client, "reused", "pw-new")

    db.expire_all()
    new_user = db.get(User, "guid-new")
    assert new_user.role.code == "USER"  # ADMIN을 상속하지 않는다
    old_user = db.get(User, "guid-old")
    assert old_user.deleted_at is not None and old_user.is_active is False


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_setup_probe_lists_ad_candidates(client, ad_client):
    """부트스트랩 1단계 — bind만 검증하고 seed ADMIN 후보를 돌려준다."""
    resp = client.post(
        "/api/v1/auth/setup/probe",
        json={
            "setup_token": SETUP_TOKEN,
            "ldaps_url": "ldaps://ad.corp.com",
            "base_dn": "dc=corp,dc=com",
            "bind_account": "svc-portal",
            "bind_password": "bind-pw",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert {u["username"] for u in body["users"]} == {"opadmin", "jrpark", "seonsj"}


def test_setup_probe_writes_nothing(client, db, ad_client):
    """검증 전용이다 — 실패든 성공이든 DB에 흔적을 남기면 안 된다."""
    from app.models import AdConnection, User

    client.post(
        "/api/v1/auth/setup/probe",
        json={
            "setup_token": SETUP_TOKEN, "ldaps_url": "ldaps://ad", "base_dn": "dc=corp,dc=com",
            "bind_account": "svc", "bind_password": "pw",
        },
    )
    assert db.query(AdConnection).count() == 0
    assert db.query(User).count() == 0


def test_setup_probe_rejects_wrong_token(client):
    resp = client.post(
        "/api/v1/auth/setup/probe",
        json={
            "setup_token": "wrong", "ldaps_url": "ldaps://ad", "base_dn": "dc=corp,dc=com",
            "bind_account": "svc", "bind_password": "pw",
        },
    )
    assert resp.status_code == 403


def test_setup_probe_locked_after_bootstrap(client, bootstrapped):
    """부트스트랩 후에는 후보 조회조차 막는다 — AD 계정 목록이 새어 나가면 안 된다."""
    resp = client.post(
        "/api/v1/auth/setup/probe",
        json={
            "setup_token": SETUP_TOKEN, "ldaps_url": "ldaps://ad", "base_dn": "dc=corp,dc=com",
            "bind_account": "svc", "bind_password": "pw",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "BOOTSTRAP_LOCKED"


def test_setup_promotes_existing_user_to_admin(client, db, ad_client):
    """이미 USER로 등록된 계정을 seed ADMIN으로 지정해도 반드시 승격돼야 한다.

    provision()은 개명이 권한을 바꾸지 않도록 기존 role을 보존하는데, 부트스트랩은
    "이 계정을 관리자로 만든다"가 목적이라 그 규칙을 그대로 두면 **관리자 없는 포털**이 된다.
    """
    from app.models import Role, User

    user_role = db.query(Role).filter_by(code="USER").one()
    db.add(User(ad_object_guid="guid-admin", username="opadmin", role_id=user_role.id))
    db.commit()

    resp = client.post(
        "/api/v1/auth/setup",
        json={
            "setup_token": SETUP_TOKEN,
            "ldaps_url": "ldaps://ad.corp.com",
            "base_dn": "dc=corp,dc=com",
            "bind_account": "svc-portal",
            "bind_password": "bind-pw",
            "seed_admin_username": "opadmin",
        },
    )
    assert resp.status_code == 200, resp.text

    db.expire_all()
    seeded = db.get(User, "guid-admin")
    assert seeded.role.code == "ADMIN"
    assert seeded.is_active is True

    # 실제로 관리자 권한이 동작하는지까지 확인한다.
    token = login(client, "opadmin", "pw-admin")
    assert client.get("/api/v1/users", headers=auth_headers(token)).status_code == 200
