"""클러스터·자격증명·AD 연결 repository."""

from sqlalchemy import func, select

from app.models import AdConnection, AuditLog, Cluster, ClusterCredential, InteractiveSession, User
from app.repositories.base import BaseRepository

#: 완전 삭제를 막는 참조들. cluster_credential은 클러스터 소유물이라 제외한다.
#: 공지는 **포털 전체 대상**이라 클러스터를 참조하지 않는다 — 여기서 빠진 이유다.
CLUSTER_REFERENCES: tuple[tuple[str, type, object], ...] = (
    ("감사 로그", AuditLog, AuditLog.target_cluster_id),
    ("인터랙티브 세션", InteractiveSession, InteractiveSession.cluster_id),
    ("기본 클러스터로 지정한 사용자", User, User.default_cluster_id),
)


class ClusterRepository(BaseRepository[Cluster]):
    model = Cluster

    def get_by_name(self, name: str) -> Cluster | None:
        return self.session.scalar(select(Cluster).where(Cluster.name == name))

    def list_active(self) -> list[Cluster]:
        return list(
            self.session.scalars(select(Cluster).where(Cluster.is_active.is_(True)).order_by(Cluster.name))
        )

    def count_references(self, cluster_id: int) -> dict[str, int]:
        """이 클러스터를 가리키는 다른 테이블의 행 수. 0건인 항목은 담지 않는다."""
        counts = {}
        for label, model, column in CLUSTER_REFERENCES:
            n = self.session.scalar(select(func.count()).select_from(model).where(column == cluster_id))
            if n:
                counts[label] = n
        return counts

    def clear_default(self, except_id: int | None = None) -> None:
        """기본 클러스터는 하나만 유지한다."""
        stmt = select(Cluster).where(Cluster.is_default.is_(True))
        if except_id is not None:
            stmt = stmt.where(Cluster.id != except_id)
        for cluster in self.session.scalars(stmt):
            cluster.is_default = False


class ClusterCredentialRepository(BaseRepository[ClusterCredential]):
    model = ClusterCredential

    def get_active(self, cluster_id: int, kind: str) -> ClusterCredential | None:
        """가장 최근 등록분을 쓴다 — 무중단 교체 시 신규 토큰이 우선(backend-design §2.2)."""
        return self.session.scalar(
            select(ClusterCredential)
            .where(ClusterCredential.cluster_id == cluster_id, ClusterCredential.kind == kind)
            .order_by(ClusterCredential.id.desc())
        )

    def list_for_cluster(self, cluster_id: int) -> list[ClusterCredential]:
        return list(
            self.session.scalars(
                select(ClusterCredential).where(ClusterCredential.cluster_id == cluster_id)
            )
        )


class AdConnectionRepository(BaseRepository[AdConnection]):
    """단일 행 테이블 (db-erd.md §3 설계 노트)."""

    model = AdConnection

    def get_single(self) -> AdConnection | None:
        return self.session.scalar(select(AdConnection).order_by(AdConnection.id).limit(1))
