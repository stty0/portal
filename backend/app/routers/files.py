"""파일 브라우저·조작·스토리지 라우터 (U-FM-01·02·04, A-DB-05).

경로만 받고 **사용자는 받지 않는다** — 대상 사용자는 세션에서 정한다.
"""

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.core.deps import AppSettings, ClientFactoryDep, CurrentUser, DbSession, SecretStoreDep
from app.schemas.files import MoveIn, PathIn, PathOut
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


# --- 파일 조작 (U-FM-02·04) ---------------------------------------------


@router.post(
    "/clusters/{cid}/files/directory", response_model=PathOut, summary="디렉터리 생성 (U-FM-04)"
)
def make_dir(cid: int, payload: PathIn, user: CurrentUser, service: FileServiceDep) -> PathOut:
    return PathOut(**service.make_dir(cid, user=user, path=payload.path))


@router.post("/clusters/{cid}/files/file", response_model=PathOut, summary="파일 생성 (U-FM-04)")
def create_file(cid: int, payload: PathIn, user: CurrentUser, service: FileServiceDep) -> PathOut:
    return PathOut(**service.create_file(cid, user=user, path=payload.path))


@router.post(
    "/clusters/{cid}/files/move", response_model=PathOut, summary="이동·이름 변경 (U-FM-04)"
)
def move(cid: int, payload: MoveIn, user: CurrentUser, service: FileServiceDep) -> PathOut:
    return PathOut(**service.move(cid, user=user, path=payload.path, to=payload.to))


@router.delete("/clusters/{cid}/files", response_model=PathOut, summary="삭제 (U-FM-04)")
def remove(
    cid: int,
    path: str,
    user: CurrentUser,
    service: FileServiceDep,
    recursive: bool = False,
) -> PathOut:
    return PathOut(**service.remove(cid, user=user, path=path, recursive=recursive))


@router.post("/clusters/{cid}/files/upload", summary="업로드 (U-FM-02)")
def upload(
    cid: int,
    user: CurrentUser,
    service: FileServiceDep,
    path: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """multipart로 받아 **SFTP로 그대로 흘려보낸다** — 서버에 통째로 담지 않는다.

    이 라우터는 동기 함수라 FastAPI가 스레드풀에서 실행한다. `file.file`은 동기
    파일 객체이므로 paramiko와 그대로 맞물린다.
    """
    return service.upload(
        cid,
        user=user,
        directory=path,
        filename=file.filename or "",
        source=file.file,
    )


@router.get("/clusters/{cid}/files/download", summary="다운로드 (U-FM-02)")
def download(cid: int, path: str, user: CurrentUser, service: FileServiceDep) -> StreamingResponse:
    resolved, size, stream = service.download(cid, user=user, path=path)
    name = resolved.rsplit("/", 1)[-1]
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            # 한글 파일명 때문에 RFC 5987 형식이 필요하다. filename*만 쓰면 구형
            # 클라이언트가 못 읽으므로 둘 다 넣는다.
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
            "Content-Length": str(size),
        },
    )
