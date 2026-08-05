"""파일 브라우저·스토리지 라우터 (U-FM-01, A-DB-05).

경로만 받고 **사용자는 받지 않는다** — 대상 사용자는 세션에서 정한다.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import AppSettings, ClientFactoryDep, CurrentUser, DbSession, SecretStoreDep
from app.services.cluster import ClusterService
from app.services.files import FileService

router = APIRouter(tags=["files"])


def _service(
    db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep, settings: AppSettings
) -> FileService:
    return FileService(
        db,
        ClusterService(db, secrets=secrets, client_factory=clients),
        settings=settings,
        secrets=secrets,
    )


FileServiceDep = Annotated[FileService, Depends(_service)]


@router.get("/clusters/{cid}/files", summary="파일 목록 (U-FM-01)")
def browse(
    cid: int, user: CurrentUser, service: FileServiceDep, path: str | None = None
) -> dict[str, Any]:
    return service.browse(cid, user=user, path=path)


@router.get("/clusters/{cid}/storage", summary="스토리지 현황 (A-DB-05)")
def storage(cid: int, user: CurrentUser, service: FileServiceDep) -> dict[str, Any]:
    return service.storage(cid, user=user)
