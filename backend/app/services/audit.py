"""감사 로그 서비스 (C-05).

모든 제어성 액션(제출/취소/노드 제어/설정 변경)은 여기를 거친다.
"""

from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.repositories.audit import AuditLogRepository


class AuditService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = AuditLogRepository(session)

    def record(
        self,
        *,
        actor: User | None,
        action: str,
        target: str | None = None,
        cluster_id: int | None = None,
        detail: str | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_guid=actor.ad_object_guid if actor else None,
            actor_role=actor.role.code if actor and actor.role else None,
            action=action,
            target=target,
            target_cluster_id=cluster_id,
            detail=detail[:512] if detail else None,
            ip=ip,
        )
        return self.repo.add(entry)
