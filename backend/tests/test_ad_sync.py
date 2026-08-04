"""AD 동기화 테스트 (A-US-01, backend-design §3.3).

가장 중요한 건 **AD 조회 실패를 삭제로 오인하지 않는 것**이다.
"""

from app.clients.ad.client import AdUser
from tests.conftest import auth_headers


def test_sync_creates_missing_users(client, db, admin_token, ad_client):
    from app.models import User

    resp = client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    # opadmin은 부트스트랩에서 이미 생성됨 → 나머지 2명이 신규
    assert body["created"] == 2
    assert db.query(User).count() == 3


def test_sync_soft_deletes_users_absent_from_ad(client, db, admin_token, ad_client):
    from app.models import User

    client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))

    ad_client.users = [u for u in ad_client.users if u.username != "seonsj"]
    resp = client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))
    assert resp.json()["deactivated"] == 1

    db.expire_all()
    gone = db.get(User, "guid-other")
    assert gone.is_active is False
    assert gone.deleted_at is not None  # hard delete가 아니다


def test_ad_outage_does_not_deactivate_anyone(client, db, admin_token, ad_client):
    """네트워크 장애를 '전원 퇴사'로 처리하면 안 된다."""
    from app.models import User

    client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))
    assert db.query(User).filter(User.deleted_at.is_(None)).count() == 3

    ad_client.fail = True
    resp = client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["deactivated"] == 0

    db.expire_all()
    assert db.query(User).filter(User.deleted_at.is_(None)).count() == 3


def test_sync_restores_returning_user(client, db, admin_token, ad_client):
    from app.models import User

    client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))
    removed = [u for u in ad_client.users if u.username != "seonsj"]
    ad_client.users = removed
    client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))

    # 오탐이었다면 AD에 다시 나타나고, soft delete라서 복구가 가능하다.
    ad_client.users = removed + [AdUser("guid-other", "seonsj", "선수진", "sj@corp.com")]
    client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))

    db.expire_all()
    restored = db.get(User, "guid-other")
    assert restored.is_active is True
    assert restored.deleted_at is None


def test_ad_connection_response_hides_bind_password(client, admin_token):
    resp = client.get("/api/v1/ad/connection", headers=auth_headers(admin_token))
    body = resp.json()
    assert body["bind_secret_configured"] is True
    assert "bind_password" not in body
    assert "bind_secret_ref" not in body
    assert "bind-pw" not in resp.text


def test_sync_records_audit_and_timestamp(client, db, admin_token):
    from app.models import AdConnection, AuditLog

    client.post("/api/v1/ad/sync", headers=auth_headers(admin_token))
    assert db.query(AuditLog).filter_by(action="AD_SYNC").count() == 1
    conn = db.query(AdConnection).one()
    assert conn.last_sync_at is not None
    assert "신규" in conn.last_sync_result


def test_sync_is_admin_only(client, user_token):
    assert client.post("/api/v1/ad/sync", headers=auth_headers(user_token)).status_code == 403
