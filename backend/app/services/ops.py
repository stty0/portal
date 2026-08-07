"""포털 운영 설정 서비스 (A-OP-01·02·03·04).

공지·템플릿·감사 로그·시스템 설정은 전부 **Portal DB 소유**다(정의서 §4.1 ③).
클러스터에 나가는 호출이 없어 slurmrestd·SSH가 죽어도 이 화면은 동작한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.models import Notice, PortalSetting, User
from app.repositories.audit import AuditLogRepository
from app.repositories.content import (
    NoticeRepository,
    PortalSettingRepository,
)
from app.repositories.identity import UserRepository
from app.services.audit import AuditService

#: 설정 변경 시 감사 로그에 남길 필드. 값이 아니라 **바뀐 필드 이름만** 남긴다 —
#: SMTP 호스트·웹훅 URL이 로그로 새지 않게.
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


def _check_period(start: datetime | None, end: datetime | None) -> None:
    if start and end and end < start:
        raise ValidationFailed(
            "종료 시각이 시작 시각보다 빠릅니다.",
            detail={"start_at": str(start), "end_at": str(end)},
        )
