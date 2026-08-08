"""쿠키 전송 · 액세스/refresh 분리 (C-01).

**전환이 아니라 분리다.** 브라우저는 HttpOnly 쿠키를, 기계 클라이언트는 Bearer를 쓴다.
하나로 통일하면 한쪽이 반드시 불편해진다.
"""

from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from tests.conftest import auth_headers, login


def _login(client):
    return client.post(
        "/api/v1/auth/login", json={"username": "jrpark", "password": "pw-user"}
    )


def test_login_sets_httponly_cookies(client, bootstrapped):
    resp = _login(client)
    assert resp.status_code == 200

    jar = {c.name: c for c in resp.cookies.jar}
    assert ACCESS_COOKIE in jar and REFRESH_COOKIE in jar

    raw = resp.headers.get_list("set-cookie")
    access = next(h for h in raw if h.startswith(ACCESS_COOKIE))
    refresh = next(h for h in raw if h.startswith(REFRESH_COOKIE))
    csrf = next(h for h in raw if h.startswith(CSRF_COOKIE))

    # 액세스·refresh는 JS가 읽으면 안 된다 — 그게 이 방식의 요점이다.
    assert "HttpOnly" in access and "HttpOnly" in refresh
    assert "SameSite=strict" in access.lower() or "samesite=strict" in access.lower()
    # refresh는 갱신 경로에만 실려 다닌다.
    assert "Path=/api/v1/auth/refresh" in refresh
    # CSRF 쿠키만 읽을 수 있어야 SPA가 헤더로 되돌려 보낼 수 있다.
    assert "HttpOnly" not in csrf


def test_cookie_auth_works_without_bearer(client, bootstrapped):
    _login(client)
    # TestClient가 쿠키를 들고 간다. Authorization 헤더는 없다.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_state_change_by_cookie_requires_csrf_header(client, bootstrapped):
    _login(client)
    # 쿠키만으로 오는 POST는 다른 사이트가 만들었을 수 있다.
    assert client.post("/api/v1/auth/logout").status_code == 401

    csrf = client.cookies.get(CSRF_COOKIE)
    ok = client.post("/api/v1/auth/logout", headers={CSRF_HEADER: csrf})
    assert ok.status_code == 200


def test_bearer_is_exempt_from_csrf(client, bootstrapped):
    """헤더는 브라우저가 자동으로 붙이지 않는다 — CSRF가 성립하지 않는다."""
    # login() 헬퍼는 쿠키를 남기지 않는다 — 순수 Bearer 요청이 된다.
    token = login(client, "jrpark", "pw-user")
    assert client.post("/api/v1/auth/logout", headers=auth_headers(token)).status_code == 200


def test_refresh_rotates_and_old_token_dies(client, bootstrapped):
    body = _login(client).json()
    first = body["refresh_token"]

    again = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert again.status_code == 200
    second = again.json()["refresh_token"]
    assert second and second != first

    # 쓴 토큰은 즉시 죽는다 — 사본이 돌아다녀도 못 쓴다.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first}).status_code == 401


def test_reused_refresh_token_kills_the_whole_session(client, bootstrapped):
    """재사용은 **사본이 돌아다닌다는 신호**다 — 회전만으로는 방어가 되지 않는다.

    회전만 하면 먼저 쓴 쪽(공격자)이 받아 간 새 토큰이 그대로 살아 있다. 정상 사용자는
    "만료됐네" 하고 다시 로그인할 뿐이고, 공격자 세션은 절대 상한까지 유지된다.
    그래서 재사용을 보면 그 세션 자체를 끊는다.
    """
    body = _login(client).json()
    first = body["refresh_token"]
    access = body["access_token"]

    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first}).json()
    assert client.get("/api/v1/auth/me", headers=auth_headers(second["access_token"])).status_code == 200

    # 이미 쓴 토큰이 다시 들어온다.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401
    assert "세션을 종료했습니다" in replay.json()["message"]

    # 회전으로 받아 간 토큰도, 원래 액세스 토큰도 함께 죽는다.
    assert client.get("/api/v1/auth/me", headers=auth_headers(second["access_token"])).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth_headers(access)).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    ).status_code == 401


def test_access_token_is_short_lived(client, bootstrapped, settings):
    """30분. 길게 잡으면 유출 시 창이 넓어지고, 짧게 잡으면 refresh가 감당한다."""
    from jose import jwt

    token = _login(client).json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert claims["exp"] - claims["iat"] == settings.access_token_ttl_seconds == 30 * 60
    assert settings.refresh_token_ttl_seconds == 14 * 24 * 3600


def test_logout_clears_cookies_and_kills_refresh(client, bootstrapped):
    refresh = _login(client).json()["refresh_token"]
    csrf = client.cookies.get(CSRF_COOKIE)
    assert client.post("/api/v1/auth/logout", headers={CSRF_HEADER: csrf}).status_code == 200

    # 세션이 끊겼으므로 refresh도 함께 죽는다.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_refresh_denied_after_account_is_disabled(client, db, bootstrapped):
    """계정을 막았는데 갱신이 되면 막은 의미가 없다."""
    from app.models import User

    refresh = _login(client).json()["refresh_token"]
    user = db.query(User).filter(User.username == "jrpark").one()
    user.is_active = False
    db.commit()

    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_login_helper_leaves_no_session_cookie(client, bootstrapped):
    """`login()`이 쿠키를 남기면 **"자격증명 없음" 테스트가 조용히 인증된다.**

    이 성질이 깨지면 401을 기대하는 권한 테스트들이 의미를 잃는다 — 실패가 아니라
    통과로 새는 쪽이라 눈치채기 어렵다. 그래서 여기서 못 박아 둔다.
    """
    login(client, "jrpark", "pw-user")
    assert client.cookies.get(ACCESS_COOKIE) is None
    assert client.cookies.get(CSRF_COOKIE) is None
    # 그래서 헤더 없는 요청은 정말로 익명이다.
    assert client.get("/api/v1/auth/me").status_code == 401
