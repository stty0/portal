"""클러스터 라우터 (api.md §3).

목록만 인증 사용자에게 열려 있고(클러스터 선택용), 나머지는 ADMIN 전용이다.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import (
    AdminUser,
    ClientFactoryDep,
    CurrentUser,
    DbSession,
    PermissionCacheDep,
    SecretStoreDep,
    is_admin,
)
from app.schemas.cluster import (
    ClusterCreate,
    ClusterOut,
    ClusterSummary,
    ClusterUpdate,
    CredentialOut,
    CredentialPut,
    RestTestResult,
)
from app.schemas.cluster import (
    SlurmAccountCreate,
    SlurmAssociationIn,
    SlurmQosAssign,
    SlurmQosCreate,
)
from app.schemas.common import OkResponse
from app.services.cluster import ClusterService

router = APIRouter(tags=["clusters"])


def _service(
    db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep
) -> ClusterService:
    return ClusterService(db, secrets=secrets, client_factory=clients)


ClusterServiceDep = Annotated[ClusterService, Depends(_service)]


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


@router.get("/clusters/{cid}/reservations", summary="예약 목록 (A-ND-04)")
def list_reservations(
    cid: int, actor: AdminUser, service: ClusterServiceDep
) -> list[dict[str, Any]]:
    return service.reservations(cid)
