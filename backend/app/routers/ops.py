"""포털 운영 설정 라우터 (api.md §9, A-OP-01·02·03·04).

읽기 권한이 항목마다 다르다.
  - 공지 목록·템플릿 목록: **인증 사용자** (U-CL-03 배너가 쓴다. 템플릿을 쓰던
    Job 제출 탭은 제거됐고, 지금 목록을 읽는 곳은 관리자 등록 화면뿐이다)
  - 설정·감사 로그, 그리고 모든 쓰기: **ADMIN**
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.core.deps import IDLE_SETTING_KEY, AdminUser, AppSettings, CurrentUser, DbSession
from app.core.errors import NotFound, ValidationFailed
from app.schemas.common import OkResponse, Page
from app.schemas.ops import (
    AppCatalogCreate,
    AppCatalogOut,
    AppCatalogUpdate,
    AuditLogOut,
    NoticeCreate,
    NoticeOut,
    NoticeUpdate,
    SettingsOut,
    SettingsUpdate,
)
from app.services.app_images import IMAGE_FILE
from app.services.ops import OpsService

router = APIRouter(tags=["ops"])


def _service(db: DbSession) -> OpsService:
    return OpsService(db)


OpsServiceDep = Annotated[OpsService, Depends(_service)]


# --- A-OP-04 시스템 설정 ---------------------------------------------------
@router.get("/settings", response_model=SettingsOut, summary="포털 설정 (A-OP-04)")
def get_settings_(_: AdminUser, service: OpsServiceDep) -> SettingsOut:
    return SettingsOut.model_validate(service.settings())


@router.put("/settings", response_model=SettingsOut, summary="포털 설정 수정 (A-OP-04)")
def update_settings(
    payload: SettingsUpdate, request: Request, actor: AdminUser, service: OpsServiceDep
) -> SettingsOut:
    row = service.update_settings(actor=actor, **payload.model_dump(exclude_unset=True))
    # 유휴 타임아웃은 요청 경로에서 캐시로 읽는다 — 바꾸자마자 먹도록 캐시를 비운다.
    # 안 비워도 60초 뒤에는 반영되지만, 관리자가 "안 먹었나" 하고 다시 누르게 된다.
    request.app.state.redis.delete(IDLE_SETTING_KEY)
    return SettingsOut.model_validate(row)


# --- A-OP-01 공지 -----------------------------------------------------------
@router.get("/notices", response_model=list[NoticeOut], summary="공지 목록 (U-CL-03)")
def list_notices(
    user: CurrentUser,
    service: OpsServiceDep,
    banner: bool = False,
) -> list[NoticeOut]:
    # 공지는 포털 전체 대상이다 — 클러스터로 거르지 않는다.
    items = service.list_notices(banner_only=banner)
    return [NoticeOut.model_validate(n) for n in items]


@router.post("/notices", response_model=NoticeOut, status_code=201, summary="공지 등록 (A-OP-01)")
def create_notice(payload: NoticeCreate, actor: AdminUser, service: OpsServiceDep) -> NoticeOut:
    return NoticeOut.model_validate(service.create_notice(actor=actor, **payload.model_dump()))


@router.patch("/notices/{notice_id}", response_model=NoticeOut, summary="공지 수정 (A-OP-01)")
def update_notice(
    notice_id: int, payload: NoticeUpdate, actor: AdminUser, service: OpsServiceDep
) -> NoticeOut:
    notice = service.update_notice(
        notice_id, actor=actor, **payload.model_dump(exclude_unset=True)
    )
    return NoticeOut.model_validate(notice)


@router.delete("/notices/{notice_id}", response_model=OkResponse, summary="공지 삭제 (A-OP-01)")
def delete_notice(notice_id: int, actor: AdminUser, service: OpsServiceDep) -> OkResponse:
    service.delete_notice(notice_id, actor=actor)
    return OkResponse(message="공지를 삭제했습니다.")


# --- A-OP-02 앱 카탈로그 -----------------------------------------------------
@router.get("/apps", response_model=list[AppCatalogOut], summary="앱 목록 (A-OP-02)")
def list_apps(_: CurrentUser, service: OpsServiceDep) -> list[AppCatalogOut]:
    # 읽기는 인증 사용자에게 연다 — 사용자 화면이 아이콘·벤더·버전을 여기서 읽는다.
    # 코드 카탈로그의 앱까지 함께 나온다(등록되지 않은 앱은 id=null).
    return [AppCatalogOut(**a) for a in service.list_apps()]


@router.post("/apps", response_model=AppCatalogOut, status_code=201, summary="앱 등록 (A-OP-02)")
def create_app(
    payload: AppCatalogCreate, actor: AdminUser, service: OpsServiceDep
) -> AppCatalogOut:
    return AppCatalogOut(**service.create_app(actor=actor, **payload.model_dump()))


@router.patch("/apps/{app_pk}", response_model=AppCatalogOut, summary="앱 수정 (A-OP-02)")
def update_app(
    app_pk: int, payload: AppCatalogUpdate, actor: AdminUser, service: OpsServiceDep
) -> AppCatalogOut:
    row = service.update_app(app_pk, actor=actor, **payload.model_dump(exclude_unset=True))
    return AppCatalogOut(**row)


@router.delete("/apps/{app_pk}", response_model=OkResponse, summary="앱 삭제 (A-OP-02)")
def delete_app(app_pk: int, actor: AdminUser, service: OpsServiceDep) -> OkResponse:
    service.delete_app(app_pk, actor=actor)
    return OkResponse(message="앱 등록을 삭제했습니다.")


# --- A-OP-02 앱 아이콘 파일 --------------------------------------------------
#: 브라우저가 그릴 수 있고 서버가 확신할 수 있는 형식만 내보낸다.
ICON_TYPES = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
#: 경로 요소가 될 수 없는 이름만 통과시킨다 — `/`도 `.`으로 시작하는 것도 없다.
ICON_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _icon_dir(settings: Settings) -> Path:
    return Path(settings.app_icon_dir)


@router.get("/app-icons", response_model=list[str], summary="앱 아이콘 파일 목록 (A-OP-02)")
def list_app_icons(_: AdminUser, settings: AppSettings) -> list[str]:
    """디렉터리에 놓인 아이콘 파일명. 등록 폼이 고를 수 있는 값을 여기서 받는다."""
    directory = _icon_dir(settings)
    if not directory.is_dir():
        return []
    resolved = directory.resolve()
    return sorted(
        p.name
        for p in directory.iterdir()
        # 내보낼 수 없는 이름을 목록에 올리면 고를 수 없는 값이 폼에 뜬다 —
        # 서빙과 **같은 경계**를 본다(심볼릭 링크는 여기서도 빠진다).
        if p.is_file()
        and p.suffix.lower() in ICON_TYPES
        and ICON_NAME.match(p.name)
        and p.resolve().parent == resolved
    )


@router.get("/app-icons/{name}", summary="앱 아이콘 파일 (A-OP-02)")
def get_app_icon(name: str, _: CurrentUser, settings: AppSettings) -> FileResponse:
    if not ICON_NAME.match(name):
        raise NotFound("아이콘을 찾을 수 없습니다.", detail={"name": name})
    media_type = ICON_TYPES.get(Path(name).suffix.lower())
    if media_type is None:
        raise NotFound("아이콘을 찾을 수 없습니다.", detail={"name": name})

    directory = _icon_dir(settings).resolve()
    path = (directory / name).resolve()
    # 이름 검사를 통과해도 심볼릭 링크는 밖을 가리킬 수 있다 — **정규화 뒤에** 경계를 본다.
    if path.parent != directory or not path.is_file():
        raise NotFound("아이콘을 찾을 수 없습니다.", detail={"name": name})

    return FileResponse(
        path,
        media_type=media_type,
        headers={
            # SVG는 주소창으로 직접 열면 문서로 렌더된다 — 스크립트가 들어 있으면
            # 같은 오리진에서 실행된다. 아이콘은 그림 외에 아무것도 할 필요가 없다.
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=3600",
        },
    )


#: 아이콘 업로드 상한. 아이콘은 수십 KB면 충분하다 — 큰 파일은 실수이거나 아이콘이 아니다.
ICON_MAX_BYTES = 512 * 1024


@router.post(
    "/app-icons", response_model=list[str], status_code=201, summary="앱 아이콘 업로드 (A-OP-02)"
)
async def upload_app_icon(
    actor: AdminUser,
    settings: AppSettings,
    service: OpsServiceDep,
    file: UploadFile = File(...),
) -> list[str]:
    """아이콘 파일을 디렉터리에 넣는다. 응답은 갱신된 파일명 목록이다.

    **이름은 서버가 정한다** — 업로드한 파일명을 그대로 쓰면 경로 요소나 확장자 위장이
    섞여 들어온다. 확장자는 내용에서 판정한 형식으로 붙인다.
    """
    raw = await file.read(ICON_MAX_BYTES + 1)
    if len(raw) > ICON_MAX_BYTES:
        raise ValidationFailed(
            f"아이콘은 {ICON_MAX_BYTES // 1024}KB 이하여야 합니다.",
            detail={"limit_bytes": ICON_MAX_BYTES},
        )
    if not raw:
        raise ValidationFailed("빈 파일입니다.", detail={"filename": file.filename})

    suffix = _sniff_icon_suffix(raw)
    if suffix is None:
        raise ValidationFailed(
            "지원하지 않는 이미지 형식입니다. SVG·PNG·JPEG·WEBP만 올릴 수 있습니다.",
            detail={"filename": file.filename},
        )
    stem = Path(file.filename or "icon").stem
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", stem).strip("-.")[:40] or "icon"

    directory = Path(settings.app_icon_dir)
    if not directory.is_dir():
        raise ValidationFailed(
            "아이콘 디렉터리가 없습니다.", detail={"dir": settings.app_icon_dir}
        )
    name = f"{stem}{suffix}"
    # 덮어쓰기는 하지 않는다 — 다른 앱이 쓰던 아이콘이 말없이 바뀌면 추적이 안 된다.
    for n in range(1, 100):
        if not (directory / name).exists():
            break
        name = f"{stem}-{n}{suffix}"
    else:
        raise ValidationFailed("같은 이름의 파일이 너무 많습니다.", detail={"stem": stem})

    (directory / name).write_bytes(raw)
    service.audit.record(actor=actor, action="APP_ICON_UPLOAD", target=name)
    service.session.commit()
    return list_app_icons(actor, settings)


def _sniff_icon_suffix(raw: bytes) -> str | None:
    """확장자가 아니라 **내용**으로 형식을 정한다. 업로드된 이름은 신뢰하지 않는다."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp"
    head = raw[:512].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        # 앞부분에 SVG 루트가 보여야 한다 — XML 선언만 있고 svg가 아니면 아니다.
        return ".svg" if b"<svg" in raw[:2048].lower() else None
    return None


# --- A-OP-02 앱 이미지 파일 --------------------------------------------------
@router.get("/app-images", response_model=list[str], summary="앱 이미지 파일 목록 (A-OP-02)")
def list_app_images(_: AdminUser, settings: AppSettings) -> list[str]:
    """`app_image_dir`에 놓인 컨테이너 이미지 파일명 — 등록 폼의 선택지.

    **경로는 워커 노드 기준**이다. 포털 파드에서 이 디렉터리가 안 보이면 빈 목록이 되고,
    그래도 관리자는 파일명을 아는 값으로 저장할 수 있어야 하므로 오류로 만들지 않는다.
    """
    directory = Path(settings.app_image_dir)
    if not directory.is_dir():
        return []
    resolved = directory.resolve()
    return sorted(
        p.name
        for p in directory.iterdir()
        if p.is_file() and IMAGE_FILE.match(p.name) and p.resolve().parent == resolved
    )


# --- A-OP-03 감사 로그 -------------------------------------------------------
@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="감사 로그 (A-OP-03, C-05)")
def audit_logs(
    _: AdminUser,
    service: OpsServiceDep,
    actor_username: str | None = None,
    action: str | None = None,
    cluster_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = 1,
    size: int = 50,
) -> Page[AuditLogOut]:
    size = max(1, min(size, 200))
    page = max(1, page)
    items, total = service.audit_logs(
        actor_username=actor_username,
        action=action,
        cluster_id=cluster_id,
        since=since,
        until=until,
        limit=size,
        offset=(page - 1) * size,
    )
    return Page[AuditLogOut](
        items=[AuditLogOut(**i) for i in items], total=total, page=page, size=size
    )


@router.get("/audit-logs/actions", response_model=list[str], summary="감사 로그 액션 종류")
def audit_actions(_: AdminUser, service: OpsServiceDep) -> list[str]:
    return service.audit_actions()
