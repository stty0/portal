"""사용자·AD 연결 라우터 (api.md §2). 전부 ADMIN 전용."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import (
    AdminUser,
    AppSettings,
    DbSession,
    SecretStoreDep,
    get_permission_cache,
    get_session_store,
)
from app.core.redis_client import PermissionCache, SessionStore
from app.schemas.common import Page
from app.schemas.user import (
    AdConnectionOut,
    AdConnectionUpdate,
    AdSyncResult,
    UserOut,
    UserUpdate,
)
from app.services.ad import AdService
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter(tags=["users"])


def _auth_service(
    db: DbSession,
    settings: AppSettings,
    secrets: SecretStoreDep,
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> AuthService:
    return AuthService(db, settings, secrets=secrets, sessions=sessions)


AuthServiceDep = Annotated[AuthService, Depends(_auth_service)]


def _user_service(
    db: DbSession,
    cache: Annotated[PermissionCache, Depends(get_permission_cache)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> UserService:
    return UserService(db, permission_cache=cache, sessions=sessions)


def _ad_service(db: DbSession, auth: AuthServiceDep) -> AdService:
    return AdService(db, auth)


UserServiceDep = Annotated[UserService, Depends(_user_service)]
AdServiceDep = Annotated[AdService, Depends(_ad_service)]


@router.get("/users", response_model=Page[UserOut], summary="포털 사용자 목록")
def list_users(
    _: AdminUser,
    service: UserServiceDep,
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> Page[UserOut]:
    rows, total = service.search(
        q=q, role_code=role, is_active=is_active, limit=size, offset=(page - 1) * size
    )
    return Page[UserOut](
        items=[UserOut.model_validate(r) for r in rows], total=total, page=page, size=size
    )


@router.get("/users/{guid}", response_model=UserOut, summary="사용자 상세")
def get_user(guid: str, _: AdminUser, service: UserServiceDep) -> UserOut:
    return UserOut.model_validate(service.get(guid))


@router.patch("/users/{guid}", response_model=UserOut, summary="역할 부여·비활성화")
def update_user(
    guid: str, payload: UserUpdate, actor: AdminUser, service: UserServiceDep
) -> UserOut:
    user = service.update(guid, actor=actor, role_code=payload.role, is_active=payload.is_active)
    return UserOut.model_validate(user)


@router.get("/ad/connection", response_model=AdConnectionOut, summary="AD 연결 설정 조회")
def get_ad_connection(_: AdminUser, service: AdServiceDep) -> AdConnectionOut:
    conn = service.get_connection()
    out = AdConnectionOut.model_validate(conn)
    out.bind_secret_configured = bool(conn.bind_secret_ref)
    out.bootstrap_completed = bool(conn.seed_admin_guid)
    return out


@router.put("/ad/connection", response_model=AdConnectionOut, summary="AD 연결 설정 등록/수정")
def put_ad_connection(
    payload: AdConnectionUpdate, actor: AdminUser, service: AdServiceDep
) -> AdConnectionOut:
    fields = payload.model_dump(exclude={"bind_password"}, exclude_none=True)
    conn = service.upsert_connection(actor=actor, bind_password=payload.bind_password, **fields)
    out = AdConnectionOut.model_validate(conn)
    out.bind_secret_configured = bool(conn.bind_secret_ref)
    out.bootstrap_completed = bool(conn.seed_admin_guid)
    return out


@router.post("/ad/connection/test", summary="AD 연결 테스트")
def test_ad_connection(_: AdminUser, service: AdServiceDep) -> dict:
    return {"ok": service.test_connection()}


@router.post("/ad/sync", response_model=AdSyncResult, summary="AD 동기화 수동 실행")
def sync_ad(actor: AdminUser, service: AdServiceDep) -> AdSyncResult:
    result = service.sync(actor=actor)
    return AdSyncResult(
        ok=result.ok,
        created=result.created,
        updated=result.updated,
        deactivated=result.deactivated,
        message=result.summary(),
    )
