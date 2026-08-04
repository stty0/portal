"""Billing · License · 리포트 (db-erd.md §Billing/§License/§리포트).

A-BL은 SCP 클라우드 청구 비용, A-RP-05(chargeback_rate)는 Slurm 사용량×요율의
내부 과금이다 — 출처가 다르다(정의서 §3.9 각주).
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow

# MySQL은 BIGINT 유지, SQLite(테스트)에서만 INTEGER로 대체 — autoincrement 때문.
BigIntPk = BigInteger().with_variant(Integer, "sqlite")


class BillingConfig(Base):
    """A-BL-01. 단일 행. Secret Key는 참조만 저장."""

    __tablename__ = "billing_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_endpoint: Mapped[str | None] = mapped_column(String(255))
    scp_account_id: Mapped[str | None] = mapped_column(String(32))
    access_key: Mapped[str | None] = mapped_column(String(128))  # Scp-Accesskey
    secret_ref: Mapped[str | None] = mapped_column(String(255))  # Scp-Signature 서명용
    collect_interval: Mapped[str | None] = mapped_column(String(16))
    monthly_alert_krw: Mapped[int | None] = mapped_column(BigInteger)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)


class BillingRule(Base):
    """A-BL-02. SCP 응답에 Tag가 없어 조건식으로 자원을 식별한다."""

    __tablename__ = "billing_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16))
    condition: Mapped[str] = mapped_column(String(255))
    mapping_label: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class BillingSnapshot(Base):
    """A-BL-03·04 — 수집 비용."""

    __tablename__ = "billing_snapshot"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    dimension: Mapped[str | None] = mapped_column(String(64))
    cost_krw: Mapped[int | None] = mapped_column(BigInteger)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LicenseServer(Base):
    """A-LM-01. LicenseClient가 백엔드 내장 lmutil로 직접 TCP 접속(SSH 아님)."""

    __tablename__ = "license_server"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    host: Mapped[str | None] = mapped_column(String(128))  # port@host 의 host
    port: Mapped[int | None] = mapped_column(Integer)
    vendor_daemon: Mapped[str | None] = mapped_column(String(64))
    collect_interval: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_check_result: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LicenseFeatureSnapshot(Base):
    """A-LM-02·05 — lmstat 수집 결과."""

    __tablename__ = "license_feature_snapshot"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("license_server.id"))
    feature: Mapped[str] = mapped_column(String(128))
    total: Mapped[int | None] = mapped_column(Integer)
    in_use: Mapped[int | None] = mapped_column(Integer)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReportSchedule(Base):
    """A-RP-04. 단일 행 — 정기 리포트 발송 설정."""

    __tablename__ = "report_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipients: Mapped[str | None] = mapped_column(String(512))
    cycle: Mapped[str | None] = mapped_column(String(16))  # weekly / monthly / quarterly
    format: Mapped[str | None] = mapped_column(String(8))  # pdf / excel / csv
    scope: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ChargebackRate(Base):
    """A-RP-05 — 자원별 요율(예: CPU 12원/core·h)."""

    __tablename__ = "chargeback_rate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(String(16), unique=True)  # cpu / gpu
    rate_krw: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(16))  # core·h / gpu·h
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
