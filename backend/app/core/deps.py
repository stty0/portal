"""FastAPI 의존성 — 인증/인가·리소스 주입 (backend-design §3.5).

인가는 Middleware가 아니라 `Depends`로 한다: API별 권한을 라우터 옆에 두어야
URL-permission 매핑이 따로 놀지 않는다(§3.5).

라우터는 항상 `require_permission("...")` **문법**을 쓴다. 현재 permission은
`admin:access` 하나뿐이지만, 향후 `job:cancel` 등으로 세분화해도 내부 조회만
바뀌고 라우터는 수정되지 않는다(§3.4).
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.clients.factory import ClusterClientFactory
from app.core.config import Settings, get_settings
from app.core.errors import Forbidden, Unauthenticated
from app.core.redis_client import PermissionCache, SessionData, SessionStore
from app.core.secrets import SecretStore
from app.core.security import decode_session_token
from app.db.session import session_scope
from app.models import User
from app.repositories.identity import RoleRepository, UserRepository


def get_db() -> Iterator[Session]:
    yield from session_scope()


DbSession = Annotated[Session, Depends(get_db)]


def get_app_settings() -> Settings:
    return get_settings()


AppSettings = Annotated[Settings, Depends(get_app_settings)]


# --- app.state에 lifespan이 심어 둔 싱글턴들 ---------------------------
def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_permission_cache(request: Request) -> PermissionCache:
    return request.app.state.permission_cache


def get_secret_store(request: Request) -> SecretStore:
    return request.app.state.secret_store


def get_client_factory(request: Request) -> ClusterClientFactory:
    return request.app.state.client_factory


SecretStoreDep = Annotated[SecretStore, Depends(get_secret_store)]
ClientFactoryDep = Annotated[ClusterClientFactory, Depends(get_client_factory)]


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthenticated("인증 토큰이 필요합니다.")
    return token


def get_current_session(
    request: Request,
    settings: AppSettings,
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> SessionData:
    """JWT 서명 검증 → `sid`로 Redis 세션 조회.

    JWT 서명만 믿지 않고 세션 레코드도 확인한다 — 그래야 로그아웃·강제 종료가
    토큰 만료를 기다리지 않고 즉시 반영된다(§4.1).
    """
    payload = decode_session_token(settings, _bearer_token(request))
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
