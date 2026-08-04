"""인증 라우터 (api.md §1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import (
    AppSettings,
    CurrentSession,
    CurrentUser,
    DbSession,
    SecretStoreDep,
    client_ip,
    get_permission_cache,
    get_session_store,
    permissions_for,
)
from app.core.redis_client import PermissionCache, SessionStore
from app.schemas.auth import (
    AdCandidate,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SetupProbeRequest,
    SetupProbeResponse,
    SetupRequest,
    SetupStatus,
)
from app.schemas.common import OkResponse
from app.services.auth import AuthService

router = APIRouter(tags=["auth"])


def _service(
    db: DbSession,
    settings: AppSettings,
    secrets: SecretStoreDep,
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> AuthService:
    return AuthService(db, settings, secrets=secrets, sessions=sessions)


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
def login(payload: LoginRequest, request: Request, service: AuthServiceDep) -> LoginResponse:
    result = service.login(payload.username, payload.password, ip=client_ip(request))
    return LoginResponse(access_token=result.token)


@router.post("/auth/logout", response_model=OkResponse, summary="로그아웃")
def logout(user: CurrentUser, session: CurrentSession, service: AuthServiceDep) -> OkResponse:
    service.logout(user, session.sid)
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
