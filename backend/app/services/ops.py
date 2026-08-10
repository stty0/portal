"""포털 운영 설정 서비스 (A-OP-01·02·03·04).

공지·템플릿·감사 로그·시스템 설정은 전부 **Portal DB 소유**다(정의서 §4.1 ③).
클러스터에 나가는 호출이 없어 slurmrestd·SSH가 죽어도 이 화면은 동작한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import AppCatalog, Notice, PortalSetting, User
from app.repositories.audit import AuditLogRepository
from app.repositories.content import (
    AppCatalogRepository,
    NoticeRepository,
    PortalSettingRepository,
)
from app.repositories.identity import UserRepository
from app.services import batch_apps, session_apps
from app.services.app_images import IMAGE_REF
from app.services.audit import AuditService

#: 설정 변경 시 감사 로그에 남길 필드. 값이 아니라 **바뀐 필드 이름만** 남긴다 —
#: SMTP 호스트·웹훅 URL이 로그로 새지 않게.
#: 아이콘 주소의 접두사. 라우터 경로(`/app-icons/{name}`)와 짝이다.
ICON_URL_PREFIX = "/api/v1/app-icons"

SETTING_FIELDS = (
    "poll_interval_sec",
    "session_timeout_min",
    "smtp_host",
    "smtp_port",
    "smtp_sender",
    "webhook_url",
)


class OpsService:
    def __init__(self, session: Session):
        self.session = session
        self.notices = NoticeRepository(session)
        self.apps = AppCatalogRepository(session)
        self.settings_repo = PortalSettingRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    # --- A-OP-04 시스템 설정 ---------------------------------------------
    def settings(self) -> PortalSetting:
        row = self.settings_repo.get_or_create()
        self.session.commit()
        return row

    def update_settings(self, *, actor: User, **values: Any) -> PortalSetting:
        row = self.settings_repo.get_or_create()
        changed: list[str] = []
        for field in SETTING_FIELDS:
            if field not in values:
                continue
            new = values[field]
            if getattr(row, field) != new:
                setattr(row, field, new)
                changed.append(field)
        # C-04: 폴링 주기는 30초 이하여야 한다(정의서 비기능 요구).
        if row.poll_interval_sec is not None and not 5 <= row.poll_interval_sec <= 30:
            raise ValidationFailed(
                "폴링 주기는 5~30초여야 합니다(C-04).",
                detail={"poll_interval_sec": row.poll_interval_sec},
            )
        if row.session_timeout_min is not None and row.session_timeout_min < 5:
            raise ValidationFailed(
                "세션 타임아웃은 5분 이상이어야 합니다.",
                detail={"session_timeout_min": row.session_timeout_min},
            )
        if changed:
            self.audit.record(
                actor=actor, action="SETTING_UPDATE", target=",".join(changed)
            )
        self.session.commit()
        return row

    # --- A-OP-01 공지 -----------------------------------------------------
    def list_notices(
        self, *, banner_only: bool = False
    ) -> list[Notice]:
        now = datetime.now(timezone.utc).replace(tzinfo=None) if banner_only else None
        return self.notices.search(banner_only=banner_only, now=now)

    def create_notice(self, *, actor: User, **values: Any) -> Notice:
        _check_period(values.get("start_at"), values.get("end_at"))
        notice = Notice(created_by=actor.ad_object_guid, **values)
        self.session.add(notice)
        self.audit.record(actor=actor, action="NOTICE_CREATE", target=notice.title)
        self.session.commit()
        return notice

    def update_notice(self, notice_id: int, *, actor: User, **values: Any) -> Notice:
        notice = self.notices.get(notice_id)
        if notice is None:
            raise NotFound("공지를 찾을 수 없습니다.", detail={"id": notice_id})
        for key, value in values.items():
            setattr(notice, key, value)
        _check_period(notice.start_at, notice.end_at)
        self.audit.record(actor=actor, action="NOTICE_UPDATE", target=notice.title)
        self.session.commit()
        return notice

    def delete_notice(self, notice_id: int, *, actor: User) -> None:
        notice = self.notices.get(notice_id)
        if notice is None:
            raise NotFound("공지를 찾을 수 없습니다.", detail={"id": notice_id})
        title = notice.title
        self.session.delete(notice)
        self.audit.record(actor=actor, action="NOTICE_DELETE", target=title)
        self.session.commit()

    # --- A-OP-02 앱 카탈로그 ------------------------------------------------
    def list_apps(self) -> list[dict[str, Any]]:
        """코드 카탈로그의 앱 + 등록된 메타데이터를 **합쳐서** 준다.

        등록된 것만 주면 아직 등록하지 않은 앱은 관리 화면에서 존재하지 않는 것이 된다 —
        관리자가 봐야 하는 것은 "무엇을 등록할 수 있는가"다. 코드에 없는 등록(도입 예정
        앱)도 빠뜨리지 않는다.
        """
        registered = {(r.kind, r.app_id): r for r in self.apps.list_all()}
        rows: list[dict[str, Any]] = []
        in_code: set[tuple[str, str]] = set()
        for kind, catalog in (("interactive", session_apps.APPS), ("batch", batch_apps.APPS)):
            for app in catalog:
                key = (kind, app.id)
                in_code.add(key)
                rows.append(_app_row(kind, app.id, registered.get(key), code=app))
        for (kind, app_id), row in registered.items():
            if (kind, app_id) not in in_code:
                rows.append(_app_row(kind, app_id, row, code=None))  # 코드에 없는 등록
        rows.sort(key=lambda r: (r["kind"], r["app_id"]))
        return rows

    def create_app(self, *, actor: User, kind: str, app_id: str, **values: Any) -> dict[str, Any]:
        _check_image_ref(values.get("image_ref"))
        if self.apps.get_by_app(kind, app_id):
            raise Conflict(
                "같은 종류·id의 앱이 이미 등록되어 있습니다.",
                detail={"kind": kind, "app_id": app_id},
            )
        app = AppCatalog(kind=kind, app_id=app_id, **values)
        self.session.add(app)
        self.audit.record(
            actor=actor, action="APP_CREATE", target=app.name, detail=f"{kind}/{app_id}"
        )
        self.session.commit()
        return _app_row(kind, app_id, app, code=_code_app(kind, app_id))

    def update_app(self, app_pk: int, *, actor: User, **values: Any) -> dict[str, Any]:
        app = self.apps.get(app_pk)
        if app is None:
            raise NotFound("앱을 찾을 수 없습니다.", detail={"id": app_pk})
        _check_image_ref(values.get("image_ref"))
        # kind·app_id는 코드 카탈로그로 가는 연결 키다 — 바꾸면 다른 앱이 된다. 지우고 다시 등록한다.
        for key, value in values.items():
            setattr(app, key, value)
        self.audit.record(
            actor=actor, action="APP_UPDATE", target=app.name, detail=f"{app.kind}/{app.app_id}"
        )
        self.session.commit()
        return _app_row(app.kind, app.app_id, app, code=_code_app(app.kind, app.app_id))

    def delete_app(self, app_pk: int, *, actor: User) -> None:
        app = self.apps.get(app_pk)
        if app is None:
            raise NotFound("앱을 찾을 수 없습니다.", detail={"id": app_pk})
        name, ref = app.name, f"{app.kind}/{app.app_id}"
        self.session.delete(app)
        # 코드 카탈로그의 앱이면 등록만 사라지고 앱 자체는 계속 뜬다 — 화면이 그렇게 말한다.
        self.audit.record(actor=actor, action="APP_DELETE", target=name, detail=ref)
        self.session.commit()

    # --- A-OP-03 감사 로그 -------------------------------------------------
    def audit_logs(
        self,
        *,
        actor_username: str | None = None,
        action: str | None = None,
        cluster_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        actor_guid = None
        if actor_username:
            user = self.users.get_by_username(actor_username)
            if user is None:
                # 없는 사용자로 거르면 결과가 0건이어야 한다 — 필터를 무시하면 안 된다.
                return [], 0
            actor_guid = user.ad_object_guid

        rows, total = self.audit_repo.search(
            actor_guid=actor_guid,
            action=action,
            cluster_id=cluster_id,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
        # GUID는 화면에서 쓸모가 없다 — 한 번에 이름으로 바꿔 준다(N+1 회피).
        guids = {r.actor_guid for r in rows if r.actor_guid}
        names = {
            u.ad_object_guid: (u.display_name or u.username)
            for u in self.users.by_guids(guids)
        } if guids else {}
        return (
            [
                {
                    "id": r.id,
                    "at": r.at,
                    "actor": names.get(r.actor_guid or "", r.actor_guid),
                    "actor_role": r.actor_role,
                    "action": r.action,
                    "cluster_id": r.target_cluster_id,
                    "target": r.target,
                    "detail": r.detail,
                    "ip": r.ip,
                }
                for r in rows
            ],
            total,
        )

    def audit_actions(self) -> list[str]:
        """필터 드롭다운용 — 실제로 기록된 액션만 보여준다."""
        return self.audit_repo.distinct_actions()




def _code_app(kind: str, app_id: str) -> Any:
    """코드 카탈로그에서 같은 id의 앱을 찾는다. 없으면 None(도입 예정 앱)."""
    catalog = session_apps.APPS if kind == "interactive" else batch_apps.APPS
    return next((a for a in catalog if a.id == app_id), None)


def _icon_url(name: str) -> str:
    """DB의 파일명 → 화면이 쓸 주소. 경로 조립을 한 곳에만 둔다."""
    return f"{ICON_URL_PREFIX}/{name}"


def _check_image_ref(value: Any) -> None:
    """OCI 참조의 모양. **스킴이 없으면 거절한다** — apptainer가 출처 종류를 그것으로
    판정하고, 요구하지 않으면 로컬 경로를 붙여 넣어도 통과한다. 이 값은 변환 잡에서
    `apptainer build`로 넘어간다(T-08)."""
    if value and not IMAGE_REF.match(str(value)):
        raise ValidationFailed(
            "이미지 출처는 `docker://…`처럼 스킴으로 시작해야 합니다.",
            detail={"image_ref": value},
        )


def _app_row(kind: str, app_id: str, row: AppCatalog | None, *, code: Any) -> dict[str, Any]:
    """등록분과 코드 카탈로그를 겹친다 — 등록이 없으면 코드의 이름·설명이 그대로 쓰인다."""
    return {
        "id": row.id if row else None,  # None = 아직 등록 안 함(POST 대상)
        "kind": kind,
        "app_id": app_id,
        "name": (row.name if row else None) or (code.name if code else app_id),
        "vendor": row.vendor if row else None,
        "version": row.version if row else None,
        "image_file": (row.image_file if row else None) or (code.image if code else None),
        "image_ref": (row.image_ref if row else None) or (
            getattr(code, "image_ref", "") if code else None
        ) or None,
        "icon_file": row.icon_file if row else None,
        "icon_url": _icon_url(row.icon_file) if row and row.icon_file else None,
        "description": (row.description if row else None) or (code.description if code else None),
        "in_code": code is not None,
        "updated_at": row.updated_at if row else None,
    }


def _check_period(start: datetime | None, end: datetime | None) -> None:
    if start and end and end < start:
        raise ValidationFailed(
            "종료 시각이 시작 시각보다 빠릅니다.",
            detail={"start_at": str(start), "end_at": str(end)},
        )
