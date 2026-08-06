"""감사 로그 repository (C-05 / A-OP-03)."""

from datetime import datetime

from sqlalchemy import func, select

from app.models import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def distinct_actions(self) -> list[str]:
        """기록된 액션 종류. 필터 드롭다운을 코드에 하드코딩하지 않기 위해서다."""
        return sorted(a for (a,) in self.session.execute(select(AuditLog.action).distinct()) if a)

    def search(
        self,
        *,
        actor_guid: str | None = None,
        action: str | None = None,
        cluster_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        if actor_guid:
            stmt = stmt.where(AuditLog.actor_guid == actor_guid)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if cluster_id is not None:
            stmt = stmt.where(AuditLog.target_cluster_id == cluster_id)
        if since:
            stmt = stmt.where(AuditLog.at >= since)
        if until:
            stmt = stmt.where(AuditLog.at <= until)
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(self.session.scalars(stmt.order_by(AuditLog.at.desc()).limit(limit).offset(offset)))
        return rows, total
