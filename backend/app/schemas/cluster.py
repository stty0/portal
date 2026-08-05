"""클러스터 스키마 (api.md §3).

Secret(JWT·SSH 개인키)은 응답 모델에 필드 자체가 없다 — 마스킹이 아니라 부재다.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    expires_at: datetime | None
    created_at: datetime


class ClusterSummary(BaseModel):
    """사용자용 — 클러스터 선택에 필요한 최소 정보."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
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
    group_path_tpl: str | None
    scratch_path_tpl: str | None
    created_at: datetime | None = None
    last_health_at: datetime | None = None
    last_health_ok: bool | None = None
    #: 등록된 자격증명의 **참조 정보만** — 값은 여기에도 없다(A-CL-02).
    credentials: list[CredentialOut] = []


class ClusterCreate(BaseModel):
    # 이름은 REST 연결 테스트로 자동 조회되지만, 등록 시점엔 임시값이 필요하다.
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    slurmrestd_url: str | None = None
    api_version: str | None = None
    auth_method: str | None = "jwt"
    login_node: str | None = None
    ssh_port: int | None = 22
    ssh_account: str | None = None
    group_path_tpl: str | None = None
    scratch_path_tpl: str | None = None
    is_default: bool = False


class ClusterUpdate(BaseModel):
    description: str | None = None
    slurmrestd_url: str | None = None
    api_version: str | None = None
    auth_method: str | None = None
    login_node: str | None = None
    ssh_port: int | None = None
    ssh_account: str | None = None
    group_path_tpl: str | None = None
    scratch_path_tpl: str | None = None
    is_default: bool | None = None


class CredentialPut(BaseModel):
    kind: str = Field(..., pattern="^(SLURM_JWT|SSH_KEY)$")
    value: str = Field(..., min_length=1)  # Secret 저장소로만 흘러가고 응답에 없다


class RestTestResult(BaseModel):
    ok: bool
    cluster_name: str | None = None
    api_version: str | None = None


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
