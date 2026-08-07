"""클러스터 · 자격증명 · AD 연결 (db-erd.md §'클러스터 & 시크릿', C-03/A-CL/A-US-01).

경계: account·QOS·association·slurm user 는 **클러스터별 독립 slurmdbd** 소유이며
Portal DB 테이블이 아니다. 여기엔 '어떤 클러스터에 어떻게 접속하는가'만 둔다.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Cluster(Base):
    __tablename__ = "cluster"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # slurm.conf ClusterName. **등록 시점에는 비어 있다** — REST 연결 테스트가
    # slurmrestd에서 읽어 채우고, 그 뒤로는 포털에서 수정할 수 없다.
    name: Mapped[str | None] = mapped_column(String(64), unique=True)
    # 사람이 붙이는 이름. 이름이 확인되기 전까지 화면에서 클러스터를 가리키는 값이다.
    alias: Mapped[str | None] = mapped_column(String(255))
    slurmrestd_url: Mapped[str | None] = mapped_column(String(255))
    api_version: Mapped[str | None] = mapped_column(String(16))  # v0.0.43
    # jwt 고정. munge는 포털이 클러스터의 munge.key를 갖게 되어 범위 밖이다.
    # 컬럼은 남긴다 — 나중에 다른 방식이 생기면 여기가 자리다.
    auth_method: Mapped[str | None] = mapped_column(String(16))
    login_node: Mapped[str | None] = mapped_column(String(128))  # SSH (웹터미널·SFTP 공용)
    ssh_port: Mapped[int | None] = mapped_column(Integer, default=22)
    ssh_account: Mapped[str | None] = mapped_column(String(64))  # 서비스 계정 (제한 sudo)
    # 홈의 **상위** 경로(예: /home). 사용자 홈은 이 아래 사용자명이다 — 사용자명은
    # 서버가 인증 정보에서 채우므로 설정에 자리표시자를 두지 않는다.
    # 비우면 NSS(`getent passwd`)로 사용자별 자동 인식한다.
    home_base: Mapped[str | None] = mapped_column(String(255))
    # U-IA-01·02 세션 컨테이너가 **들어 있는 곳**. 이미지 파일명은 앱 카탈로그가
    # 갖는다(services/session_apps.py). 공유 SIF 디렉터리(/home/portal/images)와
    # OCI 레지스트리(docker://, oras://)를 모두 받는다 — apptainer가 둘 다 실행한다.
    image_repository: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # A-CL-01 "마지막 헬스체크" — 상태 컬럼이 스스로 말하게 한다. NULL = 아직 확인 안 함.
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_health_ok: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    # 자격증명은 클러스터 소유물이다 — 등록 여부·만료를 폼에서 보여주고, 삭제 시 함께 사라진다.
    credentials: Mapped[list["ClusterCredential"]] = relationship(
        lazy="selectin",
        order_by="ClusterCredential.id",
        cascade="all, delete-orphan",
    )


class ClusterCredential(Base):
    """JWT/SSH 키의 **참조와 만료**만 보관. 실값은 Secret 저장소(backend-design §2.2)."""

    __tablename__ = "cluster_credential"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("cluster.id"))
    kind: Mapped[str] = mapped_column(String(16))  # SLURM_JWT / SSH_KEY
    secret_ref: Mapped[str] = mapped_column(String(255))  # 값 평문 저장 금지
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)  # JWT exp (만료 알림용)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdConnection(Base):
    """단일 AD 연결 설정 + 최초 seed ADMIN (A-US-01, C-02)."""

    __tablename__ = "ad_connection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ldaps_url: Mapped[str | None] = mapped_column(String(255))
    base_dn: Mapped[str | None] = mapped_column(String(255))
    bind_account: Mapped[str | None] = mapped_column(String(128))
    bind_secret_ref: Mapped[str | None] = mapped_column(String(255))  # Secret 저장소 참조
    allowed_group: Mapped[str | None] = mapped_column(String(255))  # memberOf 필터
    id_attribute: Mapped[str] = mapped_column(String(32), default="sAMAccountName")
    sync_interval: Mapped[str | None] = mapped_column(String(16))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_sync_result: Mapped[str | None] = mapped_column(String(255))
    # 이 값의 존재 여부가 곧 부트스트랩 완료 여부다(AuthService.is_bootstrapped).
    seed_admin_guid: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
