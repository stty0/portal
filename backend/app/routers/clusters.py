"""클러스터 라우터 (api.md §3).

목록만 인증 사용자에게 열려 있고(클러스터 선택용), 나머지는 ADMIN 전용이다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import AdminUser, ClientFactoryDep, CurrentUser, DbSession, SecretStoreDep
from app.schemas.cluster import (
    ClusterCreate,
    ClusterOut,
    ClusterSummary,
    ClusterUpdate,
    CredentialOut,
    CredentialPut,
    RestTestResult,
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
def list_clusters(_: CurrentUser, service: ClusterServiceDep) -> list[ClusterSummary]:
    return [ClusterSummary.model_validate(c) for c in service.list()]


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
