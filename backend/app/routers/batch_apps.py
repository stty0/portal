"""Batch 앱 라우터 (U-JB-13) — 해석 solver를 배치 Job으로 제출한다.

인터랙티브 앱과 같은 자리에서 출발하되 **끝이 다르다**. 세션이 아니라 Job이 남고,
결과는 홈 디렉터리에 떨어진다.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import AppSettings, ClientFactoryDep, CurrentUser, DbSession, SecretStoreDep
from app.schemas.batch_app import AppParamOut, BatchAppOut, BatchAppSubmitRequest
from app.schemas.job import JobSubmitResponse
from app.services import app_images, batch_apps
from app.services.app_access import KIND_BATCH, Allowance, AppAccessService
from app.services.cluster import ClusterService
from app.services.job import JobService, JobSpec
from app.routers.jobs import JobServiceDep

router = APIRouter(tags=["batch-apps"])


def _access(
    db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep
) -> AppAccessService:
    return AppAccessService(db, ClusterService(db, secrets=secrets, client_factory=clients))


AppAccessServiceDep = Annotated[AppAccessService, Depends(_access)]


def _out(app: batch_apps.BatchApp, verdict: Allowance) -> BatchAppOut:
    return BatchAppOut(
        id=app.id,
        name=app.name,
        description=app.description,
        fid=app.fid,
        needs_gpu=app.needs_gpu,
        ready=app.ready,
        allowed=verdict.allowed,
        accounts=verdict.accounts,
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


@router.get(
    "/clusters/{cid}/batch-apps",
    response_model=list[BatchAppOut],
    summary="Batch 앱 목록 (U-JB-13)",
)
def list_apps(
    cid: int, user: CurrentUser, access: AppAccessServiceDep
) -> list[BatchAppOut]:
    """**예정 앱까지 내려보낸다.** 화면이 목록을 따로 갖고 있으면 앞뒤가 갈린다.

    인터랙티브 앱과 같은 이유로 **클러스터에 매인다** — 앱을 쓸 수 있는 계정은
    클러스터별 slurmdbd 소유라 같은 앱이 클러스터마다 다르게 잠긴다.
    """
    cluster = access.clusters.get(cid)
    verdict = access.allowances(cluster, KIND_BATCH, user=user)
    return [_out(a, verdict[a.id]) for a in batch_apps.APPS]


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
    access: AppAccessServiceDep,
    settings: AppSettings,
) -> JobSubmitResponse:
    """앱 + 파라미터 → 배치 스크립트 → sbatch.

    **스크립트는 서버가 만든다.** 요청의 `script`는 무시한다 — 앱이 정한 커맨드가
    정본이고, 사용자가 바꿀 수 있으면 카탈로그를 두는 의미가 없다.
    """
    app = batch_apps.get(app_id)
    cluster = service.clusters.get(cid)
    image = app_images.resolve(service.session, settings, app_images.KIND_BATCH, app_id)
    # 배정된 앱이면 소속을 확인하고, 안 골랐으면 쓸 계정을 채운다(세션과 같은 규칙).
    account = access.resolve_account(
        cluster, KIND_BATCH, app_id, user=user, account=payload.account
    )

    values = {k: "" if v is None else str(v) for k, v in (payload.params or {}).items()}
    spec_fields: dict[str, Any] = payload.model_dump(
        exclude={"params", "script", "mode", "account"}
    )
    spec = JobSpec(
        **spec_fields,
        account=account,
        script=batch_apps.build_body(app, image, values, ntasks=payload.ntasks),
        mode="form",
    )
    return JobSubmitResponse(**service.submit(cluster, spec, user=user))
