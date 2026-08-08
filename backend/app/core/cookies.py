"""브라우저 자격증명 쿠키 (C-01).

**전환이 아니라 분리다.** 브라우저는 쿠키를, 기계 클라이언트(CLI·워크플로 엔진)는
`Authorization: Bearer`를 쓴다. 하나로 통일하면 한쪽이 반드시 불편해진다 —
쿠키 항아리를 다루는 `curl`이거나, XSS에 토큰이 노출되는 SPA다.

쿠키를 쓰면 브라우저가 요청에 **자동으로** 붙이므로 CSRF가 생긴다. 그래서 두 겹으로 막는다.
  1. `SameSite=Strict` — 다른 사이트에서 온 요청에는 아예 안 붙는다.
  2. **double-submit CSRF 토큰** — JS가 읽을 수 있는 쿠키를 헤더로 되돌려 보내게 한다.
     다른 오리진은 쿠키를 읽지 못하므로 이 헤더를 만들 수 없다.

Bearer 요청은 CSRF 검사에서 제외한다. 헤더는 브라우저가 자동으로 붙이지 않으므로
애초에 CSRF가 성립하지 않는다.
"""

import secrets

from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "portal_access"
REFRESH_COOKIE = "portal_refresh"
CSRF_COOKIE = "portal_csrf"
CSRF_HEADER = "X-CSRF-Token"

#: refresh 쿠키는 **갱신 경로에만** 보낸다. 다른 요청에 실려 다닐 이유가 없다.
REFRESH_PATH = "/api/v1/auth/refresh"


def set_auth_cookies(
    response: Response, settings: Settings, *, access: str, refresh: str | None
) -> None:
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "strict",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=settings.access_token_ttl_seconds, path="/", **common
    )
    if refresh is not None:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=settings.refresh_token_ttl_seconds,
            path=REFRESH_PATH,
            **common,
        )
    # CSRF 토큰만 httponly가 아니다 — SPA가 읽어서 헤더로 되돌려 보내야 한다.
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=settings.refresh_token_ttl_seconds,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, path in (
        (ACCESS_COOKIE, "/"),
        (REFRESH_COOKIE, REFRESH_PATH),
        (CSRF_COOKIE, "/"),
    ):
        response.delete_cookie(name, path=path, domain=settings.cookie_domain)
