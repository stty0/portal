"""내 사용량 · Fairshare 라우터 (api.md §6, U-AC-01·02).

전부 **본인 것만** 다룬다 — 사용자명을 받는 파라미터가 없다.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import ClientFactoryDep, CurrentUser, DbSession, SecretStoreDep
from app.services.account import AccountService
from app.services.cluster import ClusterService

router = APIRouter(tags=["account"])


def _service(db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep) -> AccountService:
    clusters = ClusterService(db, secrets=secrets, client_factory=clients)
    return AccountService(db, clusters, settings=get_settings(), secrets=secrets)


AccountServiceDep = Annotated[AccountService, Depends(_service)]


@router.get("/clusters/{cid}/me/usage", summary="내 사용량 통계 (U-AC-01)")
def my_usage(
    cid: int, user: CurrentUser, service: AccountServiceDep, days: int = 30
) -> dict[str, Any]:
    return service.usage(cid, user=user, days=days)


@router.get("/clusters/{cid}/me/fairshare", summary="내 Fairshare · QOS 한도 (U-AC-02)")
def my_fairshare(cid: int, user: CurrentUser, service: AccountServiceDep) -> dict[str, Any]:
    return service.fairshare(cid, user=user)
