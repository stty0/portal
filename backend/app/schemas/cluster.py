"""클러스터 스키마 (api.md §3).

Secret(JWT·SSH 개인키)은 응답 모델에 필드 자체가 없다 — 마스킹이 아니라 부재다.
"""

import re
from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    expires_at: datetime | None
    created_at: datetime


#: 지원하는 slurmrestd API 버전. 응답 파싱이 버전에 묶여 있어(예: `time_limit`은 분 단위
#: 정수) 버전을 늘리려면 코드 변경이 따라온다 — 그래서 설정이 아니라 상수다.
#:
#: **v0.0.43을 쓰는 이유는 예약 생성이다.** `POST /reservation`은 0.0.43에만 있다
#: (0.0.40~0.0.42는 조회·삭제만 — 실측). 그래서 0.0.43을 서비스하지 않는 구버전 Slurm
#: 클러스터는 이 포털로 등록할 수 없다.
SUPPORTED_API_VERSIONS: tuple[str, ...] = ("v0.0.43",)
_API_VERSION_PATTERN = "^(" + "|".join(re.escape(v) for v in SUPPORTED_API_VERSIONS) + ")$"


class ClusterSummary(BaseModel):
    """사용자용 — 클러스터 선택에 필요한 최소 정보."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: slurm.conf ClusterName. REST 연결 테스트 전에는 **아직 없다**.
    name: str | None
    #: 사람이 붙인 이름. 화면은 이 값을 먼저 보여준다.
    alias: str | None
    is_default: bool
    is_active: bool


class ClusterOut(ClusterSummary):
    """관리자용 — 설정 포함(단, Secret 원문은 없음)."""

    slurmrestd_url: str | None
    api_version: str | None
    auth_method: str | None
    login_node: str | None
    ssh_port: int | None
    ssh_account: str | None
    home_base: str | None = None
    created_at: datetime | None = None
    last_health_at: datetime | None = None
    last_health_ok: bool | None = None
    #: 등록된 자격증명의 **참조 정보만** — 값은 여기에도 없다(A-CL-02).
    credentials: list[CredentialOut] = []


class ClusterCreate(BaseModel):
    #: **이름은 받지 않는다.** slurm.conf `ClusterName`이 정본이고 REST 연결 테스트가
    #: 채운다. 그때까지 클러스터를 가리킬 이름이 필요하므로 별칭을 받는다.
    alias: str = Field(..., min_length=1, max_length=255)
    slurmrestd_url: str | None = None
    api_version: str | None = Field(default=None, pattern=_API_VERSION_PATTERN)
    #: JWT만 지원한다. munge는 포털 파드가 클러스터의 `munge.key`를 가져야 해서
    #: 최소권한 방향과 정반대이므로 범위 밖이다(정의서 §4.1).
    auth_method: str | None = Field(default="jwt", pattern="^jwt$")
    login_node: str | None = None
    ssh_port: int | None = 22
    ssh_account: str | None = None
    home_base: str | None = None
    is_default: bool = False


class ClusterUpdate(BaseModel):
    #: 이름은 없다 — slurmrestd가 정한 값을 포털에서 고치지 않는다.
    alias: str | None = None
    slurmrestd_url: str | None = None
    api_version: str | None = Field(default=None, pattern=_API_VERSION_PATTERN)
    auth_method: str | None = Field(default=None, pattern="^jwt$")
    login_node: str | None = None
    ssh_port: int | None = None
    ssh_account: str | None = None
    home_base: str | None = None
    is_default: bool | None = None


#: 예약 플래그. Slurm은 훨씬 많이 받지만 운영 화면에서 쓰는 것만 연다.
#: `MAINT`=점검(다른 Job 배정 중단), `IGNORE_JOBS`=실행 중인 Job을 무시하고 예약 성립.
RESERVATION_FLAGS = ("MAINT", "IGNORE_JOBS", "DAILY", "WEEKLY")


def _no_val(number: int) -> dict[str, Any]:
    """slurmrestd의 `*_no_val_struct` 래퍼.

    **맨 숫자를 보내면 거부된다**(실측: 요청 스키마가 `{set, infinite, number}`다).
    """
    return {"set": True, "infinite": False, "number": number}


class ReservationSpec(BaseModel):
    """A-ND-04 예약 생성. `POST /slurm/v0.0.43/reservation` 요청 본문으로 옮긴다."""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    #: 시작 시각(epoch 초). 화면은 로컬 시각을 받아 변환해 보낸다.
    start_time: int = Field(..., gt=0)
    #: 분 단위. 종료 시각 대신 기간으로 받는다 — "2시간 점검"이 사람이 쓰는 단위다.
    duration_minutes: int = Field(..., ge=1, le=60 * 24 * 365)
    node_list: str | None = Field(default=None, max_length=255)
    node_count: int | None = Field(default=None, ge=1)
    partition: str | None = Field(default=None, max_length=64)
    #: 예약을 쓸 수 있는 대상. 둘 다 비면 관리자만 쓸 수 있는 예약이 된다.
    users: str | None = Field(default=None, max_length=255)
    accounts: str | None = Field(default=None, max_length=255)
    flags: list[str] = Field(default_factory=list)
    comment: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _needs_an_owner(self) -> "ReservationSpec":
        """**Slurm이 요구한다** — 없으면 2053 `Either Users/Groups and/or Accounts must be
        specified`로 거부된다(실측). 서버까지 갔다가 502를 받는 것보다 여기서 막는다.
        """
        if not (self.users or "").strip() and not (self.accounts or "").strip():
            raise ValueError("예약을 쓸 대상(사용자 또는 계정)을 지정해야 합니다.")
        return self

    @model_validator(mode="after")
    def _needs_nodes(self) -> "ReservationSpec":
        """노드 지정을 **요구한다.**

        둘 다 없으면 Slurm이 어디를 잡을지 정하지 못하거나 클러스터 전체를 잡아 버린다.
        """
        if not self.node_list and not self.node_count:
            raise ValueError("노드 목록이나 노드 수 중 하나는 지정해야 합니다.")
        return self

    @field_validator("flags")
    @classmethod
    def _known_flags(cls, value: list[str]) -> list[str]:
        unknown = [f for f in value if f.upper() not in RESERVATION_FLAGS]
        if unknown:
            raise ValueError(f"지원하지 않는 플래그: {', '.join(unknown)}")
        return [f.upper() for f in value]

    def to_slurm(self) -> dict[str, Any]:
        desc: dict[str, Any] = {
            "name": self.name,
            "start_time": _no_val(self.start_time),
            "duration": _no_val(self.duration_minutes),
        }
        if self.node_list:
            # 스펙은 **배열**을 요구한다(문자열도 받아 주지만 경고를 낸다 — 실측).
            desc["node_list"] = [n.strip() for n in self.node_list.split(",") if n.strip()]
        if self.node_count:
            desc["node_count"] = _no_val(self.node_count)
        for key in ("partition", "users", "accounts", "comment"):
            value = getattr(self, key)
            if value:
                desc[key] = value
        if self.flags:
            desc["flags"] = self.flags
        return desc

    def summary(self) -> str:
        """감사 로그 detail. 나중에 "그때 뭘 잡았지?"를 답할 수 있어야 한다."""
        parts = [self.node_list or f"{self.node_count}개 노드", f"{self.duration_minutes}분"]
        if self.flags:
            parts.append(",".join(self.flags))
        return " · ".join(parts)


class NodeStateIn(BaseModel):
    """A-ND-01 노드 상태 제어. 사유 요구 여부는 서비스가 상태별로 판정한다."""

    state: str = Field(..., pattern="^(?i:drain|resume|down|undrain)$")
    reason: str | None = Field(default=None, max_length=255)


class CredentialPut(BaseModel):
    kind: str = Field(..., pattern="^(SLURM_JWT|SSH_KEY)$")
    value: str = Field(..., min_length=1)  # Secret 저장소로만 흘러가고 응답에 없다


class RestTestResult(BaseModel):
    ok: bool
    cluster_name: str | None = None
    api_version: str | None = None


class ImageDirCheck(BaseModel):
    """등록 화면의 이미지 디렉터리 진단 (A-CL-02). **없어도 등록은 성공한다** —
    순서를 강요하면 클러스터를 먼저 등록할 수 없다."""

    path: str
    ok: bool
    images: int
    message: str


class SlurmAccountCreate(BaseModel):
    """Slurm 계정 생성 (A-US-02). 이름은 sacctmgr 규칙에 맞춰 제한한다."""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    description: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)


class SlurmAssociationIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")


class SlurmQosCreate(BaseModel):
    """QOS 생성 (A-US-03). 제한값은 비워두면 무제한이다."""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    description: str | None = Field(default=None, max_length=255)
    priority: int | None = Field(default=None, ge=0)
    max_wall_minutes: int | None = Field(default=None, ge=1)
    max_jobs_per_user: int | None = Field(default=None, ge=1)


class SlurmQosAssign(BaseModel):
    """association에 허용할 QOS 집합. **덮어쓰기**이므로 전체를 보낸다."""

    qos: list[str] = Field(default_factory=list, max_length=32)


class AppAccessOut(BaseModel):
    """앱 하나의 배정 현황 (A-US-02). `accounts`가 비면 전원 허용이다."""

    kind: str
    app_id: str
    name: str
    accounts: list[str]


class AppAccessAssign(BaseModel):
    """앱에 허용할 계정 집합. QOS 배정과 같은 규칙 — **덮어쓰기**라 전체를 보낸다."""

    accounts: list[str] = Field(default_factory=list, max_length=64)
