"""Job 스키마 (api.md §5).

제출 요청에 **사용자명 필드가 없다** — Slurm 대상 사용자는 서버가 인증된 본인으로
강제한다(backend-design §2.3). 이 부재가 곧 impersonation 방어다.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("work_dir")
    @classmethod
    def _absolute_without_traversal(cls, value: str | None) -> str | None:
        """절대 경로만, `..` 금지.

        화면이 홈 하위로 제한하지만 API를 직접 부르는 경로도 있으므로 서버에서도 막는다.
        (실제 파일 권한은 Slurm이 사용자 권한으로 실행하며 OS가 판정한다 —
        여기서는 오타·경로 조작으로 엉뚱한 곳에 쓰는 것을 걸러낸다.)
        """
        if value is None or value == "":
            return None
        if not value.startswith("/"):
            raise ValueError("작업 디렉토리는 절대 경로여야 합니다.")
        if ".." in value.split("/"):
            raise ValueError("작업 디렉토리에 상위 경로(..)를 쓸 수 없습니다.")
        return value
    environment: dict[str, str] | None = None
    script: str | None = None  # U-JB-02
    # 폼 값을 #SBATCH 지시자로 만들지, 준 스크립트를 그대로 쓸지
    mode: str = Field(default="form", pattern="^(form|script|template)$")
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
    # 이력 조회 출처. slurmdbd가 끊기면 slurmctld의 잔여 완료 Job으로 대체된다.
    source: str | None = None


class ScriptPreview(BaseModel):
    script: str
