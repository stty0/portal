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


class ApiToken(Base):
    """사용자별 API 토큰 — 기계 클라이언트용 장수명 자격증명 (C-01).

    액세스 토큰(30분)으로는 자동화를 감당할 수 없고, AD 비밀번호를 스크립트에 박으면
    **반복 실패로 계정이 잠긴다.** 그래서 사람 로그인과 분리된 자격증명을 따로 둔다.

    **원문을 저장하지 않는다** — DB가 새어도 토큰을 되살릴 수 없게 sha256만 둔다.
    발급 직후 한 번만 화면에 보여 준다. 무엇을 폐기할지 고를 수 있도록 앞 8자리
    (`prefix`)와 이름만 남긴다.

    권한은 **소유자의 역할을 그대로 따른다.** 토큰별 스코프는 아직 없다 —
    필요해지면 그때 permission 목록을 붙인다(라우터는 이미 permission 문법을 쓴다).
    """

    __tablename__ = "api_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_guid: Mapped[str] = mapped_column(ForeignKey("user.ad_object_guid"), index=True)
    #: 사람이 알아볼 이름("렌더 파이프라인", "노트북 CLI").
    name: Mapped[str] = mapped_column(String(64))
    #: sha256(hex). 조회는 이 값으로만 한다.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: 목록에서 어느 토큰인지 알아보게 하는 앞자리. 비밀이 아니다.
    prefix: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    #: 비우면 만료 없음. 기본은 만료를 두도록 화면이 유도한다.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    #: 매 요청 쓰면 DB 쓰기가 요청마다 생긴다 — 일정 간격으로만 갱신한다.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
