"""신원 · 인가 모델 (db-erd.md §1 '신원 & 인가', C-01/C-02).

PK 설계 근거(backend-design §3.2): sAMAccountName은 변경·재사용 가능하므로
불변 식별자 objectGUID를 PK로 쓴다. 재사용 계정은 GUID가 달라 자동으로 구분된다.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Role(Base):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # 초기 USER·ADMIN
    name: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(255))

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permission", back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 초기 admin:access 1행 → 향후 resource:action 세분화(job:cancel 등)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list[Role]] = relationship(
        secondary="role_permission", back_populates="permissions"
    )


class RolePermission(Base):
    """N:M 매핑. role/permission 추가는 스키마 변경 없이 행 삽입만으로 수용(§3.4)."""

    __tablename__ = "role_permission"

    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permission.id"), primary_key=True)


class User(Base):
    __tablename__ = "user"

    ad_object_guid: Mapped[str] = mapped_column(String(36), primary_key=True)  # 불변 신원
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sAMAccountName
    display_name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(256))
    role_id: Mapped[int | None] = mapped_column(ForeignKey("role.id"))
    default_cluster_id: Mapped[int | None] = mapped_column(ForeignKey("cluster.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_prefs: Mapped[dict | None] = mapped_column(JSON)  # U-AC-03
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)  # soft delete
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    role: Mapped[Role | None] = relationship(lazy="joined")
