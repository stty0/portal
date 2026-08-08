"""Batch 앱 라우터 (U-JB-13) — 해석 solver를 배치 Job으로 제출한다.

인터랙티브 앱과 같은 자리에서 출발하되 **끝이 다르다**. 세션이 아니라 Job이 남고,
결과는 홈 디렉터리에 떨어진다.
"""

from typing import Any

from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.schemas.batch_app import AppParamOut, BatchAppOut, BatchAppSubmitRequest
from app.schemas.job import JobSubmitResponse
from app.services import batch_apps
from app.services.job import JobService, JobSpec
from app.routers.jobs import JobServiceDep

router = APIRouter(tags=["batch-apps"])


def _out(app: batch_apps.BatchApp) -> BatchAppOut:
    return BatchAppOut(
        id=app.id,
        name=app.name,
        description=app.description,
        fid=app.fid,
        needs_gpu=app.needs_gpu,
        ready=app.ready,
        params=[
            AppParamOut(
                key=p.key,
                label=p.label,
                type=p.type,
                required=p.required,
                default=p.default,
                hint=p.hint,
                options=list(p.options),
            )
            for p in app.params
        ],
    )


@router.get("/batch-apps", response_model=list[BatchAppOut], summary="Batch 앱 목록 (U-JB-13)")
def list_apps(_: CurrentUser) -> list[BatchAppOut]:
    """**예정 앱까지 내려보낸다.** 화면이 목록을 따로 갖고 있으면 앞뒤가 갈린다."""
    return [_out(a) for a in batch_apps.APPS]


@router.post(
    "/clusters/{cid}/batch-apps/{app_id}/jobs",
    response_model=JobSubmitResponse,
    summary="Batch 앱 제출 (U-JB-13)",
)
def submit(
    cid: int,
    app_id: str,
    payload: BatchAppSubmitRequest,
    user: CurrentUser,
    service: JobServiceDep,
) -> JobSubmitResponse:
    """앱 + 파라미터 → 배치 스크립트 → sbatch.

    **스크립트는 서버가 만든다.** 요청의 `script`는 무시한다 — 앱이 정한 커맨드가
    정본이고, 사용자가 바꿀 수 있으면 카탈로그를 두는 의미가 없다.
    """
    app = batch_apps.get(app_id)
    cluster = service.clusters.get(cid)
    image = batch_apps.image_ref(cluster.image_repository, app)

    values = {k: "" if v is None else str(v) for k, v in (payload.params or {}).items()}
    spec_fields: dict[str, Any] = payload.model_dump(exclude={"params", "script", "mode"})
    spec = JobSpec(
        **spec_fields,
        script=batch_apps.build_body(app, image, values, ntasks=payload.ntasks),
        mode="form",
    )
    return JobSubmitResponse(**service.submit(cluster, spec, user=user))
