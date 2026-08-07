"""포털 콘텐츠 · 감사 · 세션 · 운영 설정 (db-erd.md §'포털 콘텐츠', 정의서 §4.1③)."""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow

# MySQL은 BIGINT를 유지하되 SQLite(테스트)에서는 INTEGER여야 autoincrement가 동작한다.
BigIntPk = BigInteger().with_variant(Integer, "sqlite")


class Notice(Base):
    """U-CL-03 / A-OP-01. **공지는 포털 전체 대상이다** — 클러스터 스코프를 두지 않는다."""

    __tablename__ = "notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    banner_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("user.ad_object_guid"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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
    """U-IA-04 세션 대장(臺帳).

    **접속 정보(호스트·포트·비밀번호)는 여기 저장하지 않는다.** 세션 Job이 워커에서
    기록하는 `connection.json`이 유일한 출처이고(docs/plan.md §3.1), 세션이 살아 있는지는
    Slurm Job 상태가 권위 있는 출처다 — 노드가 죽으면 파일이 남기 때문이다(T-02 실측).
    이 표는 "누가 어떤 클러스터에 무엇을 띄웠나"만 기록한다.

    `node_host`/`node_port`/`connect_url`은 초기 설계(Traefik이 폴링해 라우트 생성)의
    잔재로 **사용하지 않는다**. 채우면 접속 정보의 출처가 둘이 되어 어긋난다.
    """

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
