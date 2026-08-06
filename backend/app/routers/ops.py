"""포털 운영 설정 라우터 (api.md §9, A-OP-01·02·03·04).

읽기 권한이 항목마다 다르다.
  - 공지 목록·템플릿 목록: **인증 사용자** (U-CL-03 배너, U-JB-03 제출 폼이 쓴다)
  - 설정·감사 로그, 그리고 모든 쓰기: **ADMIN**
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.schemas.common import OkResponse, Page
from app.schemas.ops import (
    AuditLogOut,
    NoticeCreate,
    NoticeOut,
    NoticeUpdate,
    SettingsOut,
    SettingsUpdate,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
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
    payload: SettingsUpdate, actor: AdminUser, service: OpsServiceDep
) -> SettingsOut:
    row = service.update_settings(actor=actor, **payload.model_dump(exclude_unset=True))
    return SettingsOut.model_validate(row)


# --- A-OP-01 공지 -----------------------------------------------------------
@router.get("/notices", response_model=list[NoticeOut], summary="공지 목록 (U-CL-03)")
def list_notices(
    user: CurrentUser,
    service: OpsServiceDep,
    cluster_id: int | None = None,
    banner: bool = False,
) -> list[NoticeOut]:
    items = service.list_notices(cluster_id=cluster_id, banner_only=banner)
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


# --- A-OP-02 템플릿 ---------------------------------------------------------
@router.get("/templates", response_model=list[TemplateOut], summary="템플릿 목록 (U-JB-03)")
def list_templates(user: CurrentUser, service: OpsServiceDep) -> list[TemplateOut]:
    return [TemplateOut.model_validate(t) for t in service.list_templates(user=user)]


@router.post(
    "/templates", response_model=TemplateOut, status_code=201, summary="템플릿 등록 (A-OP-02)"
)
def create_template(
    payload: TemplateCreate, actor: AdminUser, service: OpsServiceDep
) -> TemplateOut:
    return TemplateOut.model_validate(service.create_template(actor=actor, **payload.model_dump()))


@router.patch("/templates/{template_id}", response_model=TemplateOut, summary="템플릿 수정 (A-OP-02)")
def update_template(
    template_id: int, payload: TemplateUpdate, actor: AdminUser, service: OpsServiceDep
) -> TemplateOut:
    template = service.update_template(
        template_id, actor=actor, **payload.model_dump(exclude_unset=True)
    )
    return TemplateOut.model_validate(template)


@router.delete("/templates/{template_id}", response_model=OkResponse, summary="템플릿 삭제 (A-OP-02)")
def delete_template(template_id: int, actor: AdminUser, service: OpsServiceDep) -> OkResponse:
    service.delete_template(template_id, actor=actor)
    return OkResponse(message="템플릿을 삭제했습니다.")


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
