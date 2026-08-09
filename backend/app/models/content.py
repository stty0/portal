"""포털 콘텐츠 · 감사 · 세션 · 운영 설정 (db-erd.md §'포털 콘텐츠', 정의서 §4.1③)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    """U-AC-04 / A-OP-05. **미구현 기능의 선행 스키마** — 참조하는 코드가 아직 없다.

    남겨 두는 근거는 `models/ops.py` 머리말 참조(같은 상태의 표가 다섯 더 있다).
    """

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


class AppAccess(Base):
    """앱을 쓸 수 있는 Slurm 계정 (U-IA-01 · U-JB-13, A-US-02의 배정 부분).

    **허용 목록(allowlist)이고, 행이 없으면 전원 허용이다.** 기본을 "잠김"으로 두면
    표를 만드는 순간 모든 앱이 멈춘다 — 배정하지 않은 앱은 지금까지처럼 누구나 쓴다.

    계정 자체는 클러스터별 slurmdbd 소유라 포털 표가 아니다(models/__init__ 경계).
    여기 담는 것은 **포털이 정하는 배정**이고 `account`는 그 이름의 문자열 참조다.
    slurmdbd에서 계정이 사라지면 그 행은 아무도 만족시키지 못하는 조건이 되어 앱이
    자연히 잠긴다 — 조용히 열리는 것보다 낫다.

    이 표는 앱 카탈로그(`services/session_apps.py`·`services/batch_apps.py`)를 가리키므로
    `app_id`도 문자열이다. 카탈로그에서 앱이 없어지면 남은 행은 아무 앱에도 맞지 않아
    무해하게 남는다.
    """

    __tablename__ = "app_access"
    __table_args__ = (
        UniqueConstraint("cluster_id", "kind", "app_id", "account", name="uq_app_access"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("cluster.id"))
    #: interactive / batch — 두 카탈로그의 앱 id가 겹칠 수 있어 함께 키가 된다.
    kind: Mapped[str] = mapped_column(String(16))
    app_id: Mapped[str] = mapped_column(String(32))
    account: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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


class AppCatalog(Base):
    """A-OP-02 앱 관리 — 앱의 **정보**를 관리자가 관리한다.

    실행 방식(기동 스크립트·transport·파라미터 스키마)은 코드 카탈로그
    (`services/session_apps.py`·`batch_apps.py`)가 계속 정본이다. 이미지와 실행 커맨드는
    함께 바뀌므로 코드 배포를 벗어날 수 없다 — 2026-08-07에 `job_template`을 지운 근거가
    그것이다. 여기 있는 것은 **코드 배포 없이 관리자가 고쳐야 하는 값**이다:
    벤더·버전 표기, 아이콘, 레지스트리 위치, 설명.

    `(kind, app_id)`로 코드 카탈로그와 이어진다(`app_access`와 같은 키). 코드에 없는
    app_id도 등록할 수 있다 — 도입 예정 앱을 미리 적어 두는 자리다. 반대로 등록이 없는
    코드 앱은 코드의 이름·설명이 그대로 쓰인다(표가 비어도 화면은 그대로 돈다).
    """

    __tablename__ = "app_catalog"
    __table_args__ = (UniqueConstraint("kind", "app_id", name="uq_app_catalog_kind_app"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: interactive / batch — 두 카탈로그의 앱 id가 겹칠 수 있어 함께 키가 된다.
    kind: Mapped[str] = mapped_column(String(16))
    app_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    vendor: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(32))
    #: 컨테이너 이미지 **파일명**만 담는다(`openfoam-2512.sif`). 파일은
    #: `settings.app_image_dir` 아래에 있다 — 아이콘과 같은 모양이다.
    image_file: Mapped[str | None] = mapped_column(String(128))
    #: 아이콘 **파일명**만 담는다(`jupyter.svg`). 파일은 `settings.app_icon_dir` 아래에
    #: 있고 URL은 서버가 만든다 — 배포 위치가 바뀌어도 DB를 고칠 필요가 없다.
    icon_file: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
