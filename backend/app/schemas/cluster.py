"""클러스터 스키마 (api.md §3).

Secret(JWT·SSH 개인키)은 응답 모델에 필드 자체가 없다 — 마스킹이 아니라 부재다.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    expires_at: datetime | None
    created_at: datetime


class RestTestResult(BaseModel):
    ok: bool
    cluster_name: str | None = None
    api_version: str | None = None
