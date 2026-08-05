"""통계·리포트 라우터 (A-RP-01·02·03). ADMIN 전용."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import AdminUser, ClientFactoryDep, DbSession, SecretStoreDep
from app.services.cluster import ClusterService
from app.services.report import ReportService

router = APIRouter(tags=["reports"])


def _service(db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep) -> ReportService:
    return ReportService(db, ClusterService(db, secrets=secrets, client_factory=clients))


ReportServiceDep = Annotated[ReportService, Depends(_service)]


@router.get("/clusters/{cid}/reports/usage", summary="사용량 리포트 (A-RP-01)")
def usage(cid: int, actor: AdminUser, service: ReportServiceDep, days: int = 30) -> dict[str, Any]:
    return service.usage(cid, days=days)


@router.get("/clusters/{cid}/reports/utilization", summary="가동률 추이 (A-RP-02)")
def utilization(
    cid: int, actor: AdminUser, service: ReportServiceDep, days: int = 30
) -> dict[str, Any]:
    return service.utilization(cid, days=days)


@router.get("/clusters/{cid}/reports/wait-time", summary="대기시간 분석 (A-RP-03)")
def wait_time(
    cid: int, actor: AdminUser, service: ReportServiceDep, days: int = 30
) -> dict[str, Any]:
    return service.wait_time(cid, days=days)
