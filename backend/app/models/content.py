"""포털 콘텐츠 · 감사 · 세션 · 운영 설정 (db-erd.md §'포털 콘텐츠', 정의서 §4.1③)."""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow

# MySQL은 BIGINT를 유지하되 SQLite(테스트)에서는 INTEGER여야 autoincrement가 동작한다.
BigIntPk = BigInteger().with_variant(Integer, "sqlite")


class Notice(Base):
    """U-CL-03 / A-OP-01. target_cluster_id NULL = 전체 클러스터."""

    __tablename__ = "notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    target_cluster_id: Mapped[int | None] = mapped_column(ForeignKey("cluster.id"))
    banner_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user.ad_object_guid"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class JobTemplate(Base):
    """U-JB-03 / A-OP-02."""

    __tablename__ = "job_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[str | None] = mapped_column(String(16))  # interactive / batch
    version: Mapped[str | None] = mapped_column(String(16))
    params: Mapped[dict | None] = mapped_column(JSON)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user.ad_object_guid"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Ticket(Base):
    """U-AC-04 / A-OP-05."""

    __tablename__ = "ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    requester_guid: Mapped[str] = mapped_column(ForeignKey("user.ad_object_guid"))
    assignee_guid: Mapped[str | None] = mapped_column(ForeignKey("user.ad_object_guid"))
    status: Mapped[str] = mapped_column(String(16), default="open")
    job_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    """C-05 / A-OP-03 — 모든 제어성 액션 기록."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor_guid: Mapped[str | None] = mapped_column(ForeignKey("user.ad_object_guid"))
    actor_role: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))  # JOB_SUBMIT / NODE_DOWN ...
    target_cluster_id: Mapped[int | None] = mapped_column(ForeignKey("cluster.id"))
    target: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(45))


class InteractiveSession(Base):
    """U-IA-04. node_host/node_port는 Job 콜백으로 채워지고 Traefik이 폴링해 라우트를 만든다."""

    __tablename__ = "interactive_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_guid: Mapped[str] = mapped_column(ForeignKey("user.ad_object_guid"))
    cluster_id: Mapped[int] = mapped_column(ForeignKey("cluster.id"))
    app_type: Mapped[str] = mapped_column(String(16))  # jupyter / vnc / code-server
    slurm_job_id: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="starting")
    node_host: Mapped[str | None] = mapped_column(String(128))
    node_port: Mapped[int | None] = mapped_column(Integer)
    connect_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PortalSetting(Base):
    """A-OP-04. 단일 행 — 세션 정책·알림 채널."""

    __tablename__ = "portal_setting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_interval_sec: Mapped[int] = mapped_column(Integer, default=30)  # C-04 ≤30초
    session_timeout_min: Mapped[int] = mapped_column(Integer, default=480)
    smtp_host: Mapped[str | None] = mapped_column(String(128))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_sender: Mapped[str | None] = mapped_column(String(128))
    webhook_url: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
