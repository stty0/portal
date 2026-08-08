"""FastAPI 의존성 — 인증/인가·리소스 주입 (backend-design §3.5).

인가는 Middleware가 아니라 `Depends`로 한다: API별 권한을 라우터 옆에 두어야
URL-permission 매핑이 따로 놀지 않는다(§3.5).

라우터는 항상 `require_permission("...")` **문법**을 쓴다. 현재 permission은
`admin:access` 하나뿐이지만, 향후 `job:cancel` 등으로 세분화해도 내부 조회만
바뀌고 라우터는 수정되지 않는다(§3.4).
"""

from collections.abc import Iterator
from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.clients.factory import ClusterClientFactory
from app.core.config import Settings, get_settings
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.core.errors import Forbidden, Unauthenticated
from app.core.redis_client import (
    PermissionCache,
    RefreshTokenStore,
    SessionData,
    SessionStore,
)
from app.core.secrets import SecretStore
from app.core.security import decode_session_token
from app.db.session import session_scope
from app.models import User
from app.repositories.identity import RoleRepository, UserRepository
from app.services.api_token import TOKEN_PREFIX as API_TOKEN_PREFIX
from app.services.api_token import ApiTokenService


def get_db() -> Iterator[Session]:
    yield from session_scope()


DbSession = Annotated[Session, Depends(get_db)]


def get_app_settings() -> Settings:
    return get_settings()


AppSettings = Annotated[Settings, Depends(get_app_settings)]


# --- app.state에 lifespan이 심어 둔 싱글턴들 ---------------------------
def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_refresh_token_store(request: Request) -> RefreshTokenStore:
    return request.app.state.refresh_token_store


def get_permission_cache(request: Request) -> PermissionCache:
    return request.app.state.permission_cache


def get_secret_store(request: Request) -> SecretStore:
    return request.app.state.secret_store


def get_client_factory(request: Request) -> ClusterClientFactory:
    return request.app.state.client_factory


SecretStoreDep = Annotated[SecretStore, Depends(get_secret_store)]
ClientFactoryDep = Annotated[ClusterClientFactory, Depends(get_client_factory)]
PermissionCacheDep = Annotated[PermissionCache, Depends(get_permission_cache)]


#: 본문을 바꾸지 않는 메서드는 CSRF 검사에서 제외한다.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _access_token(request: Request) -> str:
    """액세스 토큰을 **헤더 우선, 없으면 쿠키**에서 읽는다.

    브라우저는 쿠키(HttpOnly)를, 기계 클라이언트는 `Authorization: Bearer`를 쓴다.
    헤더를 먼저 보는 이유는, 쿠키가 남아 있는 브라우저에서 다른 토큰으로 시험할 때
    명시적으로 준 쪽이 이겨야 하기 때문이다.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token

    cookie = request.cookies.get(ACCESS_COOKIE)
    if not cookie:
        raise Unauthenticated("인증 토큰이 필요합니다.")
    _require_csrf(request)
    return cookie


def _require_csrf(request: Request) -> None:
    """쿠키 인증에만 적용하는 double-submit 검사.

    쿠키는 브라우저가 자동으로 붙이므로, 그것만으로는 "이 페이지가 보낸 요청"임을
    증명하지 못한다. 다른 오리진은 쿠키를 **읽지** 못하니 값을 헤더로 되돌려 보낼 수
    없다 — 그 차이가 증명이 된다.
    """
    if request.method in _SAFE_METHODS:
        return
    sent = request.headers.get(CSRF_HEADER)
    expected = request.cookies.get(CSRF_COOKIE)
    if not sent or not expected or not compare_digest(sent, expected):
        raise Unauthenticated("CSRF 토큰이 없거나 일치하지 않습니다.")


def get_current_session(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> SessionData:
    """자격증명 → 신원(SessionData).

    받아들이는 자격증명이 **두 종류**다.
      - 세션 토큰(JWT): 서명 검증 → `sid`로 Redis 세션 조회. 서명만 믿지 않고 레코드도
        확인해야 로그아웃·강제 종료가 토큰 만료를 기다리지 않고 즉시 먹는다(§4.1).
      - API 토큰(`hpcp_…`): DB 조회. Redis 세션이 없으므로 **합성 SessionData**를 만든다.
        `sid`에 `apiToken:<id>`를 넣어 로그가 사람 세션과 구분되게 한다.

    접두사로 갈라서 **JWT 해독을 시도조차 하지 않는다** — 실패 예외로 분기하면 원인이
    엉뚱하게 보고된다.
    """
    raw = _access_token(request)
    if raw.startswith(API_TOKEN_PREFIX):
        record = ApiTokenService(db).resolve(raw)
        if record is None:
            raise Unauthenticated("API 토큰이 유효하지 않거나 폐기·만료되었습니다.")
        user = UserRepository(db).get_by_guid(record.user_guid)
        if user is None:
            raise Unauthenticated("토큰 소유자를 찾을 수 없습니다.")
        return SessionData(
            sid=f"apiToken:{record.id}", user_guid=record.user_guid, username=user.username
        )

    payload = decode_session_token(settings, raw)
    sid = payload.get("sid")
    if not sid:
        raise Unauthenticated("세션 토큰에 세션 정보가 없습니다.")
    session = sessions.get(sid)
    if session is None:
        raise Unauthenticated("세션이 만료되었거나 로그아웃되었습니다.")
    return session


CurrentSession = Annotated[SessionData, Depends(get_current_session)]


def get_current_user(db: DbSession, session: CurrentSession) -> User:
    """세션 레코드의 `user_guid`로만 사용자를 로드한다.

    JWT의 `sub`(username)로 조회하지 않는 것이 핵심이다 — username은 변경·재사용되지만
    objectGUID는 불변이라(§3.2), 이름 재사용으로 남의 세션에 올라타는 경로가 없다.
    """
    user = UserRepository(db).get_by_guid(session.user_guid)
    if user is None or user.deleted_at is not None:
        raise Unauthenticated("사용자를 찾을 수 없습니다.")
    if not user.is_active:
        raise Forbidden("비활성화된 계정입니다.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def permissions_for(db: Session, cache: PermissionCache, role_code: str | None) -> set[str]:
    if not role_code:
        return set()
    cached = cache.get(role_code)
    if cached is not None:
        return cached
    perms = RoleRepository(db).permissions_of(role_code)
    cache.put(role_code, perms)
    return perms


def require_permission(permission: str):
    """권한 체크 의존성 팩토리. 라우터: `Depends(require_permission("admin:access"))`."""

    def dependency(
        user: CurrentUser,
        db: DbSession,
        cache: Annotated[PermissionCache, Depends(get_permission_cache)],
    ) -> User:
        role_code = user.role.code if user.role else None
        if permission not in permissions_for(db, cache, role_code):
            raise Forbidden(
                "이 작업을 수행할 권한이 없습니다.", detail={"required": permission}
            )
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_permission("admin:access"))]


def is_admin(db: Session, cache: PermissionCache, user: User) -> bool:
    role_code = user.role.code if user.role else None
    return "admin:access" in permissions_for(db, cache, role_code)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
