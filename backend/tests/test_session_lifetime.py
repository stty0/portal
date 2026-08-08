"""세션 수명 — 유휴 슬라이딩 + 절대 상한 (C-01, A-OP-04).

유휴 판정을 **refresh 토큰에 걸면 안 된다.** 액세스 토큰이 살아 있는 동안
`/auth/refresh`는 한 번도 불리지 않으므로, 활발히 쓰는 중에도 refresh는 늙는다.
실제 활동이 지나가는 길목은 **인증된 모든 요청**이다.
"""

import time

from app.core.deps import IDLE_SETTING_KEY
from tests.conftest import auth_headers, login

API = "/api/v1"


def _session_key(redis):
    return next(k for k in redis.store if k.startswith("session:"))


def test_every_request_rewinds_the_idle_clock(client, redis, user_token):
    """세션 레코드의 만료 시각이 요청마다 뒤로 밀린다."""
    key = _session_key(redis)
    before = redis.store[key][1]

    time.sleep(0.05)
    assert client.get(f"{API}/auth/me", headers=auth_headers(user_token)).status_code == 200

    assert redis.store[key][1] > before


def test_idle_window_comes_from_the_admin_setting(client, redis, db, admin_token):
    """수명은 코드에 박지 않는다 — 관리자가 화면에서 정한다(A-OP-04)."""
    from app.models import PortalSetting

    db.add(PortalSetting(session_timeout_min=15))
    db.commit()
    redis.delete(IDLE_SETTING_KEY)

    key = _session_key(redis)
    client.get(f"{API}/auth/me", headers=auth_headers(admin_token))

    remaining = redis.store[key][1] - time.time()
    assert 14 * 60 < remaining <= 15 * 60


def test_changing_the_setting_takes_effect_immediately(client, redis, admin_token):
    """60초 캐시가 있어도 관리자가 바꾸자마자 먹어야 한다 — 아니면 다시 누르게 된다."""
    client.get(f"{API}/auth/me", headers=auth_headers(admin_token))
    assert redis.get(IDLE_SETTING_KEY) is not None

    client.put(
        f"{API}/settings", json={"session_timeout_min": 20}, headers=auth_headers(admin_token)
    )
    assert redis.get(IDLE_SETTING_KEY) is None  # 캐시가 비워졌다

    key = _session_key(redis)
    client.get(f"{API}/auth/me", headers=auth_headers(admin_token))
    remaining = redis.store[key][1] - time.time()
    assert 19 * 60 < remaining <= 20 * 60


def test_absolute_cap_is_not_rewound_by_activity(client, redis, settings, user_token):
    """유휴 연장으로 세션이 젊어지면 재로그인 지점이 영영 오지 않는다."""
    key = _session_key(redis)
    import json

    payload = json.loads(redis.store[key][0])
    payload["created"] = time.time() - settings.session_absolute_ttl_seconds - 1
    redis.store[key] = (json.dumps(payload), redis.store[key][1])

    resp = client.get(f"{API}/auth/me", headers=auth_headers(user_token))
    assert resp.status_code == 401
    assert "유효기간" in resp.json()["message"]
    # 상한을 넘긴 세션은 남겨 두지 않는다.
    assert key not in redis.store


def test_expired_idle_session_cannot_be_refreshed(client, redis, bootstrapped):
    """유휴로 죽은 세션은 refresh 토큰이 살아 있어도 되살아나지 않는다."""
    body = client.post(
        f"{API}/auth/login", json={"username": "jrpark", "password": "pw-user"}
    ).json()
    redis.delete(_session_key(redis))  # 유휴 만료를 흉내낸다

    resp = client.post(f"{API}/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert resp.status_code == 401


def test_reading_the_setting_does_not_create_a_row(client, db, redis, user_token):
    """읽기 경로에서 쓰기가 일어나면 안 된다 — 요청마다 INSERT가 생긴다."""
    from app.models import PortalSetting

    redis.delete(IDLE_SETTING_KEY)
    assert db.query(PortalSetting).count() == 0
    client.get(f"{API}/auth/me", headers=auth_headers(user_token))
    assert db.query(PortalSetting).count() == 0
