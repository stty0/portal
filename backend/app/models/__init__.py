"""Portal DB ORM 모델 — db-erd.md의 포털 소유 20개 엔티티와 1:1.

경계(db-erd.md §경계): account·QOS·association·slurm user 는 클러스터별
slurmdbd 소유라 여기에 없다. session/캐시/락은 Redis라 DB 밖이다.
"""

from app.db.base import Base
from app.models.cluster import AdConnection, Cluster, ClusterCredential
from app.models.content import (
    AppAccess,
    AppCatalog,
    AuditLog,
    InteractiveSession,
    Notice,
    PortalSetting,
    Ticket,
)
from app.models.identity import ApiToken, Permission, Role, RolePermission, User
from app.models.ops import (
    BillingConfig,
    BillingRule,
    BillingSnapshot,
    ChargebackRate,
    LicenseFeatureSnapshot,
    LicenseServer,
    ReportSchedule,
)

__all__ = [
    "ApiToken",
    "Base",
    # 신원 · 인가
    "User",
    "Role",
    "Permission",
    "RolePermission",
    # 클러스터 · 연동
    "Cluster",
    "ClusterCredential",
    "AdConnection",
    # 포털 콘텐츠 · 감사
    "Notice",
    "Ticket",
    "AuditLog",
    "InteractiveSession",
    "PortalSetting",
    "AppAccess",
    "AppCatalog",
    # Billing · License · 리포트
    "BillingConfig",
    "BillingRule",
    "BillingSnapshot",
    "LicenseServer",
    "LicenseFeatureSnapshot",
    "ReportSchedule",
    "ChargebackRate",
]
