"""Job 스키마 (api.md §5).

제출 요청에 **사용자명 필드가 없다** — Slurm 대상 사용자는 서버가 인증된 본인으로
강제한다(backend-design §2.3). 이 부재가 곧 impersonation 방어다.
"""

from typing import Any

from pydantic import BaseModel, Field


class JobSubmitRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    nodes: int | None = Field(None, ge=1)
    cpus_per_task: int | None = Field(None, ge=1)
    gpus: int | None = Field(None, ge=0)
    memory_gb: int | None = Field(None, ge=1)
    walltime: str | None = None
    work_dir: str | None = None
    environment: dict[str, str] | None = None
    script: str | None = None  # U-JB-02
    template_id: int | None = None  # U-JB-03
    template_params: dict[str, Any] | None = None


class JobSubmitResponse(BaseModel):
    job_id: str | None
    raw: Any = None


class JobControlRequest(BaseModel):
    action: str = Field(..., pattern="^(hold|release|priority)$")
    priority: int | None = None


class JobResubmitRequest(BaseModel):
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    walltime: str | None = None


class JobListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


class ScriptPreview(BaseModel):
    script: str
