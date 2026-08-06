"""인터랙티브 세션 repository (U-IA-04).

세션 **대장**만 다룬다 — 접속 정보는 `connection.json`, 생사는 Slurm이 출처다
(docs/plan.md §3.1).
"""

from sqlalchemy import select

from app.models import InteractiveSession
from app.repositories.base import BaseRepository

#: 대장상의 생명주기. 실제 실행 상태는 Slurm에서 읽는다.
STATUS_ACTIVE = "active"
STATUS_ENDED = "ended"


class InteractiveSessionRepository(BaseRepository[InteractiveSession]):
    model = InteractiveSession

    def list_for_user(self, user_guid: str, *, cluster_id: int | None = None) -> list[InteractiveSession]:
        stmt = select(InteractiveSession).where(InteractiveSession.user_guid == user_guid)
        if cluster_id is not None:
            stmt = stmt.where(InteractiveSession.cluster_id == cluster_id)
        return list(self.session.scalars(stmt.order_by(InteractiveSession.id.desc())))

    def list_active(self, user_guid: str) -> list[InteractiveSession]:
        return [s for s in self.list_for_user(user_guid) if s.status == STATUS_ACTIVE]

    def owned(self, session_id: int, user_guid: str) -> InteractiveSession | None:
        """**소유자 확인을 조회에 붙여** 남의 세션을 집을 수 없게 한다.

        id로 먼저 꺼낸 뒤 소유자를 비교하면 그 검사를 빠뜨린 호출부가 생긴다.
        """
        return self.session.scalar(
            select(InteractiveSession).where(
                InteractiveSession.id == session_id,
                InteractiveSession.user_guid == user_guid,
            )
        )
