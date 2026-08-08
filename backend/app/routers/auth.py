"""인증 라우터 (api.md §1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.deps import (
    AppSettings,
    CurrentSession,
    CurrentUser,
    DbSession,
    SecretStoreDep,
    client_ip,
    get_permission_cache,
    get_refresh_token_store,
    get_session_store,
    permissions_for,
)
from app.core.redis_client import PermissionCache, SessionStore
from app.schemas.auth import (
    AdCandidate,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshRequest,
    SetupProbeRequest,
    SetupProbeResponse,
    SetupRequest,
    SetupStatus,
)
from app.schemas.common import OkResponse
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.errors import Unauthenticated
from app.core.redis_client import RefreshTokenStore
from app.services.auth import AuthService

router = APIRouter(tags=["auth"])


def _service(
    db: DbSession,
    settings: AppSettings,
    secrets: SecretStoreDep,
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    refresh_tokens: Annotated[RefreshTokenStore, Depends(get_refresh_token_store)],
) -> AuthService:
    return AuthService(
        db, settings, secrets=secrets, sessions=sessions, refresh_tokens=refresh_tokens
    )


AuthServiceDep = Annotated[AuthService, Depends(_service)]


@router.get("/auth/setup-status", response_model=SetupStatus, summary="부트스트랩 필요 여부")
def setup_status(service: AuthServiceDep) -> SetupStatus:
    """공개 엔드포인트 — Vue 라우터가 최초 설정/로그인 화면을 분기하는 데 쓴다."""
    return SetupStatus(bootstrap_required=not service.is_bootstrapped())


@router.post(
    "/auth/setup/probe",
    response_model=SetupProbeResponse,
    summary="최초 실행 1단계 — AD 연결 검증 + 관리자 후보 조회",
)
def setup_probe(payload: SetupProbeRequest, service: AuthServiceDep) -> SetupProbeResponse:
    """AD에 bind해서 seed ADMIN으로 지정 가능한 계정 목록을 돌려준다.

    저장은 하지 않는다 — 연결이 실제로 되는지, 어떤 계정이 보이는지 먼저 확인시키는 단계다.
    """
    users = service.probe_ad(
        setup_token=payload.setup_token,
        ldaps_url=payload.ldaps_url,
        base_dn=payload.base_dn,
        bind_account=payload.bind_account,
        bind_password=payload.bind_password,
        allowed_group=payload.allowed_group,
        id_attribute=payload.id_attribute,
    )
    return SetupProbeResponse(
        ok=True,
        users=[
            AdCandidate(
                object_guid=u.object_guid, username=u.username,
                display_name=u.display_name, email=u.email,
            )
            for u in users
        ],
    )


@router.post("/auth/setup", response_model=OkResponse, summary="최초 실행 부트스트랩")
def setup(payload: SetupRequest, service: AuthServiceDep) -> OkResponse:
    """AD 연결 검증 + seed ADMIN 1명 지정. 1회용 — 완료 후 서버가 하드 거부한다."""
    user = service.setup(
        setup_token=payload.setup_token,
        ldaps_url=payload.ldaps_url,
        base_dn=payload.base_dn,
        bind_account=payload.bind_account,
        bind_password=payload.bind_password,
        allowed_group=payload.allowed_group,
        id_attribute=payload.id_attribute,
        seed_admin_username=payload.seed_admin_username,
    )
    return OkResponse(message=f"seed ADMIN으로 {user.username} 지정 완료")


@router.post("/auth/login", response_model=LoginResponse, summary="AD 로그인")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: AppSettings,
    service: AuthServiceDep,
) -> LoginResponse:
    """AD 인증 → 액세스(30분) + refresh(2주).

    **브라우저와 기계 클라이언트에 같은 값을 다른 방식으로 준다.** 쿠키는 SPA가 쓰고,
    응답 본문의 토큰은 CLI·워크플로 엔진이 쓴다. SPA는 본문을 무시하면 된다.
    """
    result = service.login(payload.username, payload.password, ip=client_ip(request))
    set_auth_cookies(response, settings, access=result.token, refresh=result.refresh_token)
    return LoginResponse(access_token=result.token, refresh_token=result.refresh_token)


@router.post("/auth/refresh", response_model=LoginResponse, summary="액세스 토큰 갱신")
def refresh(
    request: Request,
    response: Response,
    settings: AppSettings,
    service: AuthServiceDep,
    payload: RefreshRequest | None = None,
) -> LoginResponse:
    """refresh 토큰 → 새 액세스 토큰. **refresh도 회전한다.**

    브라우저는 쿠키로, 기계 클라이언트는 본문으로 보낸다. 이 엔드포인트는 액세스 토큰이
    이미 만료된 상태에서 불리므로 `CurrentUser`에 의존할 수 없다.
    """
    token = (payload.refresh_token if payload else None) or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise Unauthenticated("refresh 토큰이 없습니다.")
    result = service.refresh(token)
    set_auth_cookies(response, settings, access=result.token, refresh=result.refresh_token)
    return LoginResponse(access_token=result.token, refresh_token=result.refresh_token)


@router.post("/auth/logout", response_model=OkResponse, summary="로그아웃")
def logout(
    user: CurrentUser,
    session: CurrentSession,
    response: Response,
    settings: AppSettings,
    service: AuthServiceDep,
) -> OkResponse:
    service.logout(user, session.sid)
    clear_auth_cookies(response, settings)
    return OkResponse(message="로그아웃되었습니다.")


@router.get("/auth/me", response_model=MeResponse, summary="내 정보")
def me(
    user: CurrentUser,
    db: DbSession,
    cache: Annotated[PermissionCache, Depends(get_permission_cache)],
) -> MeResponse:
    role_code = user.role.code if user.role else None
    return MeResponse(
        username=user.username,
        display_name=user.display_name,
        role=role_code,
        permissions=sorted(permissions_for(db, cache, role_code)),
        default_cluster_id=user.default_cluster_id,
    )
