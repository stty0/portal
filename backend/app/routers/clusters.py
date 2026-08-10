"""클러스터 라우터 (api.md §3).

목록만 인증 사용자에게 열려 있고(클러스터 선택용), 나머지는 ADMIN 전용이다.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import (
    AdminUser,
    AppImageCacheDep,
    AppSettings,
    ClientFactoryDep,
    CurrentUser,
    DbSession,
    PermissionCacheDep,
    SecretStoreDep,
    is_admin,
)
from app.schemas.cluster import (
    SUPPORTED_API_VERSIONS,
    ClusterCreate,
    ClusterOut,
    ClusterSummary,
    ClusterUpdate,
    CredentialOut,
    CredentialPut,
    ImageDirCheck,
    NodeStateIn,
    ReservationSpec,
    RestTestResult,
)
from app.schemas.cluster import (
    AppAccessAssign,
    AppAccessOut,
    SlurmAccountCreate,
    SlurmAssociationIn,
    SlurmQosAssign,
    SlurmQosCreate,
)
from app.schemas.common import OkResponse
from app.schemas.job import JobSubmitResponse
from app.routers.jobs import JobServiceDep
from app.services.app_access import AppAccessService
from app.services.app_images import AppImageService
from app.services.cluster import ClusterService
from app.services.job import JobSpec

router = APIRouter(tags=["clusters"])


def _service(
    db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep
) -> ClusterService:
    return ClusterService(db, secrets=secrets, client_factory=clients)


ClusterServiceDep = Annotated[ClusterService, Depends(_service)]


def _app_access(db: DbSession, service: ClusterServiceDep) -> AppAccessService:
    return AppAccessService(db, service)


AppAccessServiceDep = Annotated[AppAccessService, Depends(_app_access)]


def _app_images(
    db: DbSession,
    service: ClusterServiceDep,
    secrets: SecretStoreDep,
    settings: AppSettings,
    cache: AppImageCacheDep,
) -> AppImageService:
    return AppImageService(db, service, settings=settings, secrets=secrets, cache=cache)


AppImageServiceDep = Annotated[AppImageService, Depends(_app_images)]


@router.get(
    "/cluster-api-versions",
    response_model=list[str],
    summary="지원하는 slurmrestd API 버전 (A-CL-02)",
)
def list_api_versions(actor: AdminUser) -> list[str]:
    """등록 폼의 선택지. 화면이 목록을 따로 갖지 않게 서버가 준다.

    응답 파싱이 버전에 묶여 있어 늘리려면 코드 변경이 따라온다 — 그래서 상수다.
    """
    return list(SUPPORTED_API_VERSIONS)


@router.get("/clusters", response_model=list[ClusterSummary], summary="클러스터 목록")
def list_clusters(
    user: CurrentUser,
    service: ClusterServiceDep,
    db: DbSession,
    cache: PermissionCacheDep,
    include_inactive: bool = False,
) -> list[ClusterSummary]:
    # 비활성 클러스터는 관리 화면(A-CL-01)에만 필요하다 — 사용자 선택 목록에는 노출하지 않는다.
    only_active = not (include_inactive and is_admin(db, cache, user))
    return [ClusterSummary.model_validate(c) for c in service.list(only_active=only_active)]


@router.post("/clusters", response_model=ClusterOut, status_code=201, summary="클러스터 등록")
def create_cluster(
    payload: ClusterCreate, actor: AdminUser, service: ClusterServiceDep
) -> ClusterOut:
    data = payload.model_dump()
    cluster = service.create(actor=actor, **data)
    return ClusterOut.model_validate(cluster)


@router.get("/clusters/{cid}", response_model=ClusterOut, summary="클러스터 상세")
def get_cluster(cid: int, _: AdminUser, service: ClusterServiceDep) -> ClusterOut:
    return ClusterOut.model_validate(service.get(cid))


@router.patch("/clusters/{cid}", response_model=ClusterOut, summary="클러스터 수정")
def update_cluster(
    cid: int, payload: ClusterUpdate, actor: AdminUser, service: ClusterServiceDep
) -> ClusterOut:
    cluster = service.update(cid, actor=actor, **payload.model_dump(exclude_none=True))
    return ClusterOut.model_validate(cluster)


@router.delete("/clusters/{cid}", response_model=OkResponse, summary="클러스터 삭제(비활성화)")
def delete_cluster(cid: int, actor: AdminUser, service: ClusterServiceDep) -> OkResponse:
    service.deactivate(cid, actor=actor)
    return OkResponse(message="클러스터를 비활성화했습니다.")


@router.delete(
    "/clusters/{cid}/purge", response_model=OkResponse, summary="클러스터 완전 삭제(비활성 + 무참조)"
)
def purge_cluster(cid: int, actor: AdminUser, service: ClusterServiceDep) -> OkResponse:
    service.purge(cid, actor=actor)
    return OkResponse(message="클러스터를 삭제했습니다.")


@router.put(
    "/clusters/{cid}/credentials",
    response_model=CredentialOut,
    summary="JWT/SSH 키 등록·교체",
)
def put_credential(
    cid: int, payload: CredentialPut, actor: AdminUser, service: ClusterServiceDep
) -> CredentialOut:
    credential = service.put_credential(cid, actor=actor, kind=payload.kind, value=payload.value)
    return CredentialOut.model_validate(credential)


@router.post(
    "/clusters/{cid}/test-rest", response_model=RestTestResult, summary="slurmrestd 연결 테스트"
)
def test_rest(cid: int, actor: AdminUser, service: ClusterServiceDep) -> RestTestResult:
    return RestTestResult(**service.test_rest(cid, actor=actor))


# --- 자원 조회 -------------------------------------------------------------
# slurmrestd 응답 필드는 버전마다 달라 스키마로 고정하지 않고 그대로 흘려보낸다(Job 조회와 동일).


@router.get("/clusters/{cid}/nodes", summary="노드 목록 (A-ND-02)")
def list_nodes(cid: int, actor: AdminUser, service: ClusterServiceDep) -> list[dict[str, Any]]:
    return service.nodes(cid)


@router.get("/clusters/{cid}/partitions", summary="파티션 목록 (A-ND-03, U-CL-02)")
def list_partitions(cid: int, user: CurrentUser, service: ClusterServiceDep) -> list[dict[str, Any]]:
    # 사용자 화면(U-CL-02)도 쓰는 정보라 인증 사용자에게 연다 — 조회 전용이다.
    return service.partitions(cid)


@router.get("/clusters/{cid}/accounts", summary="Slurm 계정·사용자 매핑 (A-US-02)")
def list_accounts(cid: int, actor: AdminUser, service: ClusterServiceDep) -> list[dict[str, Any]]:
    return service.accounts(cid)


@router.post("/clusters/{cid}/accounts", status_code=201, summary="Slurm 계정 생성 (A-US-02)")
def create_account(
    cid: int, payload: SlurmAccountCreate, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.create_account(
        cid,
        actor=actor,
        name=payload.name,
        description=payload.description,
        organization=payload.organization,
    )


@router.delete("/clusters/{cid}/accounts/{name}", summary="Slurm 계정 삭제 (A-US-02)")
def delete_account(
    cid: int, name: str, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.delete_account(cid, name, actor=actor)


@router.post(
    "/clusters/{cid}/accounts/{name}/users", status_code=201, summary="계정에 사용자 연결 (A-US-02)"
)
def add_account_user(
    cid: int, name: str, payload: SlurmAssociationIn, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.add_account_user(cid, actor=actor, account=name, username=payload.username)


@router.delete(
    "/clusters/{cid}/accounts/{name}/users/{username}", summary="계정에서 사용자 해제 (A-US-02)"
)
def remove_account_user(
    cid: int, name: str, username: str, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.remove_account_user(cid, actor=actor, account=name, username=username)


@router.put("/clusters/{cid}/accounts/{name}/qos", summary="계정 단위 QOS 지정 (A-US-03)")
def set_account_qos(
    cid: int, name: str, payload: SlurmQosAssign, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.set_association_qos(
        cid, actor=actor, account=name, username=None, qos=payload.qos
    )


@router.put(
    "/clusters/{cid}/accounts/{name}/users/{username}/qos",
    summary="사용자 단위 QOS 지정 (A-US-03)",
)
def set_user_qos(
    cid: int,
    name: str,
    username: str,
    payload: SlurmQosAssign,
    actor: AdminUser,
    service: ClusterServiceDep,
) -> dict[str, Any]:
    return service.set_association_qos(
        cid, actor=actor, account=name, username=username, qos=payload.qos
    )


@router.get(
    "/clusters/{cid}/app-images",
    response_model=list[str],
    summary="클러스터의 앱 이미지 파일 (A-OP-02)",
)
def list_app_images(
    cid: int, actor: AdminUser, service: AppImageServiceDep
) -> list[str]:
    """이 클러스터의 이미지 디렉터리에 있는 파일명 — 앱 등록 폼의 선택지.

    **클러스터에 물어본다.** 경로가 클러스터마다 갈리므로 포털 파드의 파일시스템으로는
    답할 수 없다. 디렉터리가 없거나 로그인 노드가 죽으면 **빈 목록**이 된다 — 그래도
    관리자는 아는 파일명을 저장할 수 있어야 하므로 오류로 만들지 않는다.
    """
    return service.available(service.clusters.get(cid), username=actor.username)


@router.get(
    "/clusters/{cid}/image-dir",
    response_model=ImageDirCheck,
    summary="이미지 디렉터리 확인 (A-CL-02)",
)
def check_image_dir(
    cid: int, actor: AdminUser, service: AppImageServiceDep
) -> ImageDirCheck:
    """등록 직후 확인용. **없어도 200이다** — 진단이지 검증이 아니다.

    포털은 디렉터리를 만들지 않는다(근거는 서비스 docstring). 대신 무엇을 해야 하는지
    말한다 — 디렉터리가 없는 것과 로그인 노드에 못 붙는 것은 할 일이 다르다.
    """
    return ImageDirCheck(
        **service.check(service.clusters.get(cid), username=actor.username)
    )


@router.post(
    "/clusters/{cid}/app-images/{kind}/{app_id}/build",
    response_model=JobSubmitResponse,
    summary="이미지 변환 Job 제출 (A-OP-02)",
)
def build_app_image(
    cid: int,
    kind: str,
    app_id: str,
    actor: AdminUser,
    images: AppImageServiceDep,
    jobs: JobServiceDep,
) -> JobSubmitResponse:
    """OCI 참조 → SIF를 **Slurm 잡으로** 만든다. 결과는 요청자 홈 아래에 떨어진다.

    파드에서 돌리지 않는 이유는 셋이다 — apptainer가 없고, 메모리 제한이 있고, 무엇보다
    **캐시가 쌓여 파드가 스스로 evict된 전례**가 있다. 클러스터에서 돌리면 스크래치도
    네트워크도 거기 것이고 진행 상황은 기존 Job 화면이 보여준다.

    목적지는 root 소유라 잡이 직접 못 쓴다 — 배치는 `install`이 따로 한다.
    """
    cluster = images.clusters.get(cid)
    name, script, work_dir = images.build_script(cluster, kind, app_id, username=actor.username)
    spec = JobSpec(name=name, script=script, mode="script", work_dir=work_dir)
    return JobSubmitResponse(**jobs.submit(cluster, spec, user=actor))


@router.post(
    "/clusters/{cid}/app-images/{kind}/{app_id}/install",
    response_model=OkResponse,
    summary="변환된 이미지를 배치 (A-OP-02)",
)
def install_app_image(
    cid: int, kind: str, app_id: str, actor: AdminUser, images: AppImageServiceDep
) -> OkResponse:
    """빌드된 SIF를 이미지 디렉터리로 옮긴다 — **포털이 유일하게 권한을 올리는 지점.**

    빌드와 나눈 이유는 포털에 백그라운드 워커가 없어서다. 잡이 끝났는지는 Job 화면이
    말해 주고, 관리자가 그때 이 버튼을 누른다. 폴링을 흉내 내느니 두 걸음이 정직하다.
    """
    path = images.install(images.clusters.get(cid), kind, app_id, username=actor.username)
    return OkResponse(message=f"이미지를 배치했습니다: {path}")


@router.get(
    "/clusters/{cid}/app-access",
    response_model=list[AppAccessOut],
    summary="앱별 허용 계정 (A-US-02)",
)
def list_app_access(
    cid: int, actor: AdminUser, service: AppAccessServiceDep
) -> list[AppAccessOut]:
    """카탈로그 전체 + 각 앱의 배정. **배정이 없는 앱도 내려보낸다** — 관리 화면이
    무엇을 배정할 수 있는지 알아야 한다. `accounts`가 비면 전원 허용이다."""
    return [AppAccessOut(**row) for row in service.assignments(cid)]


@router.put(
    "/clusters/{cid}/app-access/{kind}/{app_id}",
    response_model=AppAccessOut,
    summary="앱에 계정 배정 (A-US-02)",
)
def set_app_access(
    cid: int,
    kind: str,
    app_id: str,
    payload: AppAccessAssign,
    actor: AdminUser,
    service: AppAccessServiceDep,
) -> AppAccessOut:
    """QOS 배정과 같은 규칙 — **덮어쓰기**라 화면이 전체를 보낸다.

    빈 목록을 보내면 배정이 사라지고 그 앱은 다시 전원이 쓴다.
    """
    return AppAccessOut(**service.assign(cid, kind, app_id, accounts=payload.accounts, actor=actor))


@router.get("/clusters/{cid}/metrics", summary="클러스터 부하 요약 (A-DB-02)")
def metrics(cid: int, actor: AdminUser, service: ClusterServiceDep) -> dict[str, Any]:
    return service.metrics(cid)


@router.get("/clusters/{cid}/events", summary="최근 이벤트 (A-DB-04)")
def events(
    cid: int, actor: AdminUser, service: ClusterServiceDep, limit: int = 20
) -> list[dict[str, Any]]:
    return service.events(cid, limit=limit)


@router.get("/clusters/{cid}/qos", summary="QOS 목록 (A-US-03)")
def list_qos(cid: int, actor: AdminUser, service: ClusterServiceDep) -> list[dict[str, Any]]:
    return service.qos(cid)


@router.post("/clusters/{cid}/qos", status_code=201, summary="QOS 생성 (A-US-03)")
def create_qos(
    cid: int, payload: SlurmQosCreate, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.create_qos(
        cid,
        actor=actor,
        name=payload.name,
        description=payload.description,
        priority=payload.priority,
        max_wall_minutes=payload.max_wall_minutes,
        max_jobs_per_user=payload.max_jobs_per_user,
    )


@router.delete("/clusters/{cid}/qos/{name}", summary="QOS 삭제 (A-US-03)")
def delete_qos(
    cid: int, name: str, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.delete_qos(cid, name, actor=actor)


@router.post("/clusters/{cid}/nodes/{name}/state", summary="노드 상태 제어 (A-ND-01)")
def set_node_state(
    cid: int, name: str, payload: NodeStateIn, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.set_node_state(
        cid, name, actor=actor, state=payload.state, reason=payload.reason
    )


@router.post("/clusters/{cid}/reservations", status_code=201, summary="예약 생성 (A-ND-04)")
def create_reservation(
    cid: int, payload: ReservationSpec, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.create_reservation(
        cid, actor=actor, name=payload.name, desc=payload.to_slurm(), summary=payload.summary()
    )


@router.delete("/clusters/{cid}/reservations/{name}", summary="예약 삭제 (A-ND-04)")
def delete_reservation(
    cid: int, name: str, actor: AdminUser, service: ClusterServiceDep
) -> dict[str, Any]:
    return service.delete_reservation(cid, name, actor=actor)


@router.get("/clusters/{cid}/reservations", summary="예약 목록 (A-ND-04)")
def list_reservations(
    cid: int, actor: AdminUser, service: ClusterServiceDep
) -> list[dict[str, Any]]:
    return service.reservations(cid)
