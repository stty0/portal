"""사용자별 API 토큰 (C-01).

자동화는 브라우저 쿠키도, 30분짜리 액세스 토큰도, AD 비밀번호도 쓸 수 없다.
그래서 세 번째 자격증명을 둔다 — 장수명이고 폐기 가능하다.
"""

from tests.conftest import auth_headers

API = "/api/v1"


def _create(client, token, **kw):
    body = {"name": "렌더 파이프라인", **kw}
    return client.post(f"{API}/me/api-tokens", json=body, headers=auth_headers(token))


def test_raw_token_is_returned_once_and_never_again(client, user_token):
    created = _create(client, user_token)
    assert created.status_code == 201, created.text
    raw = created.json()["token"]
    assert raw.startswith("hpcp_")

    # 목록에는 원문이 없다 — 서버에 해시만 있으므로 애초에 돌려줄 수 없다.
    listed = client.get(f"{API}/me/api-tokens", headers=auth_headers(user_token)).json()
    assert len(listed) == 1
    assert "token" not in listed[0]
    assert listed[0]["prefix"] == raw[: len("hpcp_") + 6]


def test_token_authenticates_like_a_session(client, user_token):
    raw = _create(client, user_token).json()["token"]
    me = client.get(f"{API}/auth/me", headers=auth_headers(raw))
    assert me.status_code == 200
    assert me.json()["username"] == "jrpark"


def test_token_is_exempt_from_csrf(client, user_token):
    """Bearer는 브라우저가 자동으로 붙이지 않는다 — CSRF가 성립하지 않는다."""
    raw = _create(client, user_token).json()["token"]
    # 상태를 바꾸는 요청인데 CSRF 헤더가 없다.
    resp = client.post(
        f"{API}/me/api-tokens", json={"name": "두번째"}, headers=auth_headers(raw)
    )
    assert resp.status_code == 201


def test_revoked_token_stops_working_immediately(client, user_token):
    created = _create(client, user_token).json()
    raw = created["token"]
    assert client.get(f"{API}/auth/me", headers=auth_headers(raw)).status_code == 200

    client.delete(f"{API}/me/api-tokens/{created['id']}", headers=auth_headers(user_token))
    # 만료를 기다리지 않는다 — 조회할 때마다 폐기 여부를 본다.
    assert client.get(f"{API}/auth/me", headers=auth_headers(raw)).status_code == 401


def test_expired_token_is_rejected(client, db, user_token):
    from datetime import datetime, timedelta

    from app.models import ApiToken

    raw = _create(client, user_token, expires_in_days=1).json()["token"]
    record = db.query(ApiToken).one()
    record.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    assert client.get(f"{API}/auth/me", headers=auth_headers(raw)).status_code == 401


def test_no_expiry_is_allowed_but_not_the_default(client, user_token):
    assert _create(client, user_token).json()["expires_at"] is not None  # 기본 90일
    forever = _create(client, user_token, name="상시", expires_in_days=None).json()
    assert forever["expires_at"] is None


def test_others_tokens_are_invisible_and_unrevokable(client, user_token, admin_token):
    mine = _create(client, user_token).json()

    # 남의 목록에는 안 보인다.
    assert client.get(f"{API}/me/api-tokens", headers=auth_headers(admin_token)).json() == []
    # 존재 여부조차 알리지 않는다 — 403이 아니라 404다.
    resp = client.delete(f"{API}/me/api-tokens/{mine['id']}", headers=auth_headers(admin_token))
    assert resp.status_code == 404
    # 그리고 실제로 살아 있다.
    assert client.get(f"{API}/auth/me", headers=auth_headers(mine["token"])).status_code == 200


def test_token_inherits_owner_permissions_not_more(client, user_token, admin_token):
    """토큰은 소유자의 역할을 그대로 따른다 — 권한이 늘지 않는다."""
    user_raw = _create(client, user_token).json()["token"]
    assert client.get(f"{API}/settings", headers=auth_headers(user_raw)).status_code == 403

    admin_raw = _create(client, admin_token, name="관리자 토큰").json()["token"]
    assert client.get(f"{API}/settings", headers=auth_headers(admin_raw)).status_code == 200


def test_token_count_is_capped(client, user_token):
    from app.services.api_token import MAX_TOKENS_PER_USER

    for i in range(MAX_TOKENS_PER_USER):
        assert _create(client, user_token, name=f"t{i}").status_code == 201
    over = _create(client, user_token, name="하나 더")
    assert over.status_code == 422
    # 폐기하면 자리가 난다.
    first = client.get(f"{API}/me/api-tokens", headers=auth_headers(user_token)).json()[-1]
    client.delete(f"{API}/me/api-tokens/{first['id']}", headers=auth_headers(user_token))
    assert _create(client, user_token, name="이제 된다").status_code == 201


def test_garbage_token_with_prefix_is_rejected_cleanly(client, bootstrapped):
    """접두사만 흉내 낸 값이 JWT 해독 오류로 보고되면 원인이 엉뚱해 보인다."""
    resp = client.get(f"{API}/auth/me", headers=auth_headers("hpcp_notarealtoken"))
    assert resp.status_code == 401
    assert "API 토큰" in resp.json()["message"]
