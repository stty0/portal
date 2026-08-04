"""Job 라우터 (api.md §5).

권한 표기가 `인증`인 엔드포인트도 **서버측에서 본인 범위로 강제**된다 —
관리자 여부에 따라 service가 스코프를 넓힌다.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import (
    AdminUser,
    ClientFactoryDep,
    CurrentUser,
    DbSession,
    SecretStoreDep,
    get_permission_cache,
    is_admin,
)
from app.core.redis_client import PermissionCache
from app.schemas.common import OkResponse
from app.schemas.job import (
    JobControlRequest,
    JobListResponse,
    JobResubmitRequest,
    JobSubmitRequest,
    JobSubmitResponse,
    ScriptPreview,
)
from app.services.cluster import ClusterService
from app.services.job import JobService, JobSpec

router = APIRouter(tags=["jobs"])


def _service(db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep) -> JobService:
    return JobService(db, ClusterService(db, secrets=secrets, client_factory=clients))


JobServiceDep = Annotated[JobService, Depends(_service)]
PermCache = Annotated[PermissionCache, Depends(get_permission_cache)]


def _spec_from(payload: JobSubmitRequest) -> JobSpec:
    return JobSpec(**payload.model_dump())


@router.get("/clusters/{cid}/jobs", response_model=JobListResponse, summary="Job 목록")
def list_jobs(
    cid: int,
    user: CurrentUser,
    db: DbSession,
    cache: PermCache,
    service: JobServiceDep,
    state: str | None = None,
    partition: str | None = None,
    username: str | None = None,
) -> JobListResponse:
    cluster = service.clusters.get(cid)
    jobs = service.list_jobs(
        cluster,
        user=user,
        is_admin=is_admin(db, cache, user),
        state=state,
        partition=partition,
        username=username,
    )
    return JobListResponse(items=jobs, total=len(jobs))


@router.get("/clusters/{cid}/jobs/history", response_model=JobListResponse, summary="Job 이력")
def job_history(
    cid: int,
    user: CurrentUser,
    db: DbSession,
    cache: PermCache,
    service: JobServiceDep,
    start_time: str | None = None,
    end_time: str | None = None,
) -> JobListResponse:
    cluster = service.clusters.get(cid)
    jobs = service.history(
        cluster,
        user=user,
        is_admin=is_admin(db, cache, user),
        start_time=start_time,
        end_time=end_time,
    )
    return JobListResponse(items=jobs, total=len(jobs))


@router.post("/clusters/{cid}/jobs", response_model=JobSubmitResponse, summary="Job 제출")
def submit_job(
    cid: int, payload: JobSubmitRequest, user: CurrentUser, service: JobServiceDep
) -> JobSubmitResponse:
    cluster = service.clusters.get(cid)
    result = service.submit(cluster, _spec_from(payload), user=user)
    return JobSubmitResponse(**result)


@router.post(
    "/clusters/{cid}/jobs/preview-script",
    response_model=ScriptPreview,
    summary="제출 전 배치 스크립트 미리보기",
)
def preview_script(
    cid: int, payload: JobSubmitRequest, _: CurrentUser, service: JobServiceDep
) -> ScriptPreview:
    return ScriptPreview(script=service.build_script(_spec_from(payload)))


@router.get("/clusters/{cid}/jobs/{job_id}", response_model=dict, summary="Job 상세")
def get_job(
    cid: int,
    job_id: str,
    user: CurrentUser,
    db: DbSession,
    cache: PermCache,
    service: JobServiceDep,
) -> dict[str, Any]:
    cluster = service.clusters.get(cid)
    return service.get_job(cluster, job_id, user=user, is_admin=is_admin(db, cache, user))


@router.delete("/clusters/{cid}/jobs/{job_id}", response_model=OkResponse, summary="Job 취소")
def cancel_job(
    cid: int,
    job_id: str,
    user: CurrentUser,
    db: DbSession,
    cache: PermCache,
    service: JobServiceDep,
) -> OkResponse:
    cluster = service.clusters.get(cid)
    service.cancel(cluster, job_id, user=user, is_admin=is_admin(db, cache, user))
    return OkResponse(message="Job을 취소했습니다.")


@router.post(
    "/clusters/{cid}/jobs/{job_id}/resubmit",
    response_model=JobSubmitResponse,
    summary="Job 재제출",
)
def resubmit_job(
    cid: int,
    job_id: str,
    payload: JobResubmitRequest,
    user: CurrentUser,
    db: DbSession,
    cache: PermCache,
    service: JobServiceDep,
) -> JobSubmitResponse:
    cluster = service.clusters.get(cid)
    result = service.resubmit(
        cluster,
        job_id,
        user=user,
        is_admin=is_admin(db, cache, user),
        **payload.model_dump(exclude_none=True),
    )
    return JobSubmitResponse(**result)


@router.patch(
    "/clusters/{cid}/jobs/{job_id}", response_model=dict, summary="hold/release/우선순위 (ADMIN)"
)
def control_job(
    cid: int,
    job_id: str,
    payload: JobControlRequest,
    actor: AdminUser,
    service: JobServiceDep,
) -> dict[str, Any]:
    cluster = service.clusters.get(cid)
    return service.control(
        cluster, job_id, user=actor, action=payload.action, priority=payload.priority
    )
