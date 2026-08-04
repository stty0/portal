"""Job 서비스 (U-JB-01·02·03·04·05·07·08·09, A-JB-01·02·03).

스코프 원칙(api.md 공통 규약):
  - Slurm 호출의 대상 사용자는 **서버가 인증된 본인으로 강제**한다 — 요청 본문으로
    사용자명을 받지 않는다(backend-design §2.3).
  - USER는 본인 소유 Job만 보고/제어한다. 목록은 서버측에서 필터하고, 단건은
    소유자 확인 후에만 돌려준다. 남의 Job은 존재 여부도 알리지 않는다(404).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.models import Cluster, JobTemplate, User
from app.services.audit import AuditService
from app.services.cluster import ClusterService


@dataclass
class JobSpec:
    """폼 기반 제출 파라미터 (U-JB-01)."""

    name: str
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    nodes: int | None = None
    cpus_per_task: int | None = None
    gpus: int | None = None
    memory_gb: int | None = None
    walltime: str | None = None
    work_dir: str | None = None
    environment: dict[str, str] | None = None
    script: str | None = None  # U-JB-02: 직접 작성한 스크립트
    template_id: int | None = None  # U-JB-03
    template_params: dict[str, Any] | None = None


class JobService:
    def __init__(self, session: Session, clusters: ClusterService):
        self.session = session
        self.clusters = clusters
        self.audit = AuditService(session)

    # --- 스코프 헬퍼 ----------------------------------------------------
    @staticmethod
    def _owner_of(job: dict[str, Any]) -> str | None:
        for key in ("user_name", "user", "username"):
            value = job.get(key)
            if isinstance(value, str):
                return value
        return None

    def _assert_visible(self, job: dict[str, Any], *, user: User, is_admin: bool) -> None:
        if is_admin:
            return
        if self._owner_of(job) != user.username:
            # 403이 아니라 404 — 존재 여부 자체를 노출하지 않는다.
            raise NotFound("Job을 찾을 수 없습니다.")

    # --- 조회 -----------------------------------------------------------
    def list_jobs(
        self,
        cluster: Cluster,
        *,
        user: User,
        is_admin: bool,
        state: str | None = None,
        partition: str | None = None,
        username: str | None = None,
    ) -> list[dict[str, Any]]:
        client = self.clusters.slurm_client(cluster)
        payload = client.get_jobs(as_user=user.username)
        jobs = _as_job_list(payload)

        if is_admin:
            # 관리자만 타인 필터를 쓸 수 있다.
            if username:
                jobs = [j for j in jobs if self._owner_of(j) == username]
        else:
            jobs = [j for j in jobs if self._owner_of(j) == user.username]

        if state:
            jobs = [j for j in jobs if _state_of(j).upper() == state.upper()]
        if partition:
            jobs = [j for j in jobs if j.get("partition") == partition]
        return jobs

    def get_job(self, cluster: Cluster, job_id: str, *, user: User, is_admin: bool) -> dict[str, Any]:
        client = self.clusters.slurm_client(cluster)
        jobs = _as_job_list(client.get_job(job_id, as_user=user.username))
        if not jobs:
            raise NotFound("Job을 찾을 수 없습니다.", detail={"job_id": job_id})
        job = jobs[0]
        self._assert_visible(job, user=user, is_admin=is_admin)
        return job

    def history(
        self, cluster: Cluster, *, user: User, is_admin: bool, **filters
    ) -> list[dict[str, Any]]:
        """완료 Job 이력 = slurmdbd(sacct 상당) (U-JB-09, A-JB-04)."""
        client = self.clusters.slurm_client(cluster)
        params = {k: v for k, v in filters.items() if v is not None}
        if not is_admin:
            params["users"] = user.username  # 서버측 강제
        jobs = _as_job_list(client.get_accounting_jobs(as_user=user.username, **params))
        if not is_admin:
            # slurmdbd가 필터를 무시해도 새어 나가지 않도록 한 번 더 거른다.
            jobs = [j for j in jobs if self._owner_of(j) == user.username]
        return jobs

    # --- 제출 -----------------------------------------------------------
    def submit(self, cluster: Cluster, spec: JobSpec, *, user: User) -> dict[str, Any]:
        script = self.build_script(spec)
        payload = {
            "script": script,
            "job": _slurm_job_properties(spec, default_name=spec.name),
        }
        client = self.clusters.slurm_client(cluster)
        # as_user는 항상 인증된 본인 — 호출자가 지정할 수 없다.
        result = client.submit_job(payload, as_user=user.username)
        job_id = _extract_job_id(result)
        self.audit.record(
            actor=user,
            action="JOB_SUBMIT",
            target=str(job_id) if job_id else spec.name,
            cluster_id=cluster.id,
            detail=f"partition={spec.partition} nodes={spec.nodes} gpus={spec.gpus}",
        )
        self.session.commit()
        return {"job_id": job_id, "raw": result}

    def build_script(self, spec: JobSpec) -> str:
        """폼/템플릿 → `#SBATCH` 배치 스크립트 생성 (U-JB-01·03).

        스크립트를 직접 준 경우(U-JB-02)는 그대로 쓴다.
        """
        if spec.script:
            return spec.script

        body = ""
        if spec.template_id is not None:
            template = self.session.get(JobTemplate, spec.template_id)
            if template is None:
                raise ValidationFailed(
                    "템플릿을 찾을 수 없습니다.", detail={"template_id": spec.template_id}
                )
            body = _render_template(template, spec.template_params or {})
        if not body:
            raise ValidationFailed("실행할 스크립트 또는 템플릿이 필요합니다.")

        directives = ["#!/bin/bash"]
        for flag, value in (
            ("--job-name", spec.name),
            ("--partition", spec.partition),
            ("--account", spec.account),
            ("--qos", spec.qos),
            ("--nodes", spec.nodes),
            ("--cpus-per-task", spec.cpus_per_task),
            ("--gres", f"gpu:{spec.gpus}" if spec.gpus else None),
            ("--mem", f"{spec.memory_gb}G" if spec.memory_gb else None),
            ("--time", spec.walltime),
            ("--chdir", spec.work_dir),
        ):
            if value not in (None, ""):
                directives.append(f"#SBATCH {flag}={value}")
        return "\n".join(directives) + "\n\n" + body.strip() + "\n"

    def resubmit(self, cluster: Cluster, job_id: str, *, user: User, is_admin: bool, **overrides):
        """완료/실패 Job을 동일 설정으로 재제출 (U-JB-08)."""
        original = self.get_job(cluster, job_id, user=user, is_admin=is_admin)
        spec = JobSpec(
            name=str(original.get("name") or f"resubmit-{job_id}"),
            partition=original.get("partition"),
            account=original.get("account"),
            qos=original.get("qos"),
            script=original.get("script") or "srun true",
        )
        for key, value in overrides.items():
            if value is not None and hasattr(spec, key):
                setattr(spec, key, value)
        return self.submit(cluster, spec, user=user)

    # --- 제어 -----------------------------------------------------------
    def cancel(self, cluster: Cluster, job_id: str, *, user: User, is_admin: bool) -> None:
        # 소유권 확인이 먼저다 — 확인 없이 scancel하면 남의 Job을 죽인다.
        self.get_job(cluster, job_id, user=user, is_admin=is_admin)
        self.clusters.slurm_client(cluster).cancel_job(job_id, as_user=user.username)
        self.audit.record(
            actor=user, action="JOB_CANCEL", target=job_id, cluster_id=cluster.id
        )
        self.session.commit()

    def control(
        self, cluster: Cluster, job_id: str, *, user: User, action: str, priority: int | None = None
    ) -> dict[str, Any]:
        """hold / release / priority (A-JB-02·03). ADMIN 전용 라우터에서만 호출된다."""
        patch: dict[str, Any]
        if action == "hold":
            patch = {"priority": 0}
        elif action == "release":
            patch = {"priority": None}
        elif action == "priority":
            if priority is None:
                raise ValidationFailed("priority 값이 필요합니다.")
            patch = {"priority": priority}
        else:
            raise ValidationFailed("지원하지 않는 제어 동작입니다.", detail={"action": action})

        result = self.clusters.slurm_client(cluster).update_job(
            job_id, patch, as_user=user.username
        )
        self.audit.record(
            actor=user,
            action=f"JOB_{action.upper()}",
            target=job_id,
            cluster_id=cluster.id,
            detail=f"priority={priority}" if priority is not None else None,
        )
        self.session.commit()
        return {"ok": True, "raw": result}


# --- slurmrestd 응답 어댑터 --------------------------------------------
# v0.0.41 응답 스키마를 실물로 확인하지 못해 구조를 단정하지 않는다(정의서 §4.1 각주).
def _as_job_list(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [j for j in payload if isinstance(j, dict)]
    if isinstance(payload, dict):
        for key in ("jobs", "job"):
            node = payload.get(key)
            if isinstance(node, list):
                return [j for j in node if isinstance(j, dict)]
            if isinstance(node, dict):
                return [node]
    return []


def _state_of(job: dict[str, Any]) -> str:
    state = job.get("job_state") or job.get("state") or ""
    if isinstance(state, list):
        return str(state[0]) if state else ""
    if isinstance(state, dict):
        return str(state.get("current") or "")
    return str(state)


def _extract_job_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("job_id", "jobId", "id"):
            if key in payload:
                return str(payload[key])
        result = payload.get("result")
        if isinstance(result, dict) and "job_id" in result:
            return str(result["job_id"])
    return None


def _slurm_job_properties(spec: JobSpec, *, default_name: str) -> dict[str, Any]:
    props: dict[str, Any] = {"name": default_name, "environment": spec.environment or {}}
    for key, value in (
        ("partition", spec.partition),
        ("account", spec.account),
        ("qos", spec.qos),
        ("nodes", spec.nodes),
        ("cpus_per_task", spec.cpus_per_task),
        ("memory_per_node", f"{spec.memory_gb}G" if spec.memory_gb else None),
        ("time_limit", spec.walltime),
        ("current_working_directory", spec.work_dir),
    ):
        if value not in (None, ""):
            props[key] = value
    return props


def _render_template(template: JobTemplate, params: dict[str, Any]) -> str:
    """템플릿 본문의 `{{key}}`를 파라미터로 치환한다 (U-JB-03)."""
    body = ""
    if isinstance(template.params, dict):
        body = str(template.params.get("script") or "")
    for key, value in params.items():
        body = body.replace("{{%s}}" % key, str(value))
    return body
