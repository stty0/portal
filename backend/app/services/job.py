"""Job 서비스 (U-JB-01·02·03·04·05·07·08·09, A-JB-01·02·03).

스코프 원칙(api.md 공통 규약):
  - Slurm 호출의 대상 사용자는 **서버가 인증된 본인으로 강제**한다 — 요청 본문으로
    사용자명을 받지 않는다(backend-design §2.3).
  - USER는 본인 소유 Job만 보고/제어한다. 목록은 서버측에서 필터하고, 단건은
    소유자 확인 후에만 돌려준다. 남의 Job은 존재 여부도 알리지 않는다(404).
"""

import re
import shlex
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.models import Cluster, User
from app.services.audit import AuditService
from app.services.cluster import ClusterService


# 아직 끝나지 않은 상태 — 이력 대체 조회에서 제외한다.
RUNNING_STATES = {"RUNNING", "PENDING", "SUSPENDED", "CONFIGURING", "COMPLETING", "RESIZING"}


@dataclass
class JobSpec:
    """폼 기반 제출 파라미터 (U-JB-01)."""

    name: str
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    nodes: int | None = None
    #: MPI 랭크 수(`--ntasks`). 노드·CPU와 별개다 — MPI는 랭크 수가 정본이고,
    #: OpenFOAM처럼 도메인 분해 수와 맞아야 하는 solver가 있다.
    ntasks: int | None = None
    cpus_per_task: int | None = None
    gpus: int | None = None
    memory_gb: int | None = None
    walltime: str | None = None
    work_dir: str | None = None
    environment: dict[str, str] | None = None
    script: str | None = None  # U-JB-02: 직접 작성한 스크립트
    #: 배열 잡 인덱스(`1-240`, `1-240%4`, `17,58` 등). 렌더링처럼 같은 일을 인덱스만
    #: 바꿔 N번 돌릴 때 쓴다 — 없으면 프레임 1장만 나온다.
    array: str | None = None
    #: 앞 Job이 끝나야 시작(`afterok:123`). 단계를 잇는 유일한 수단이다.
    dependency: str | None = None
    # form: 폼 값으로 #SBATCH 지시자를 생성 / script: 사용자가 준 본문을 그대로 사용
    mode: str = "form"


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
        self, cluster: Cluster, *, user: User, is_admin: bool, days: int = 30, **filters
    ) -> tuple[list[dict[str, Any]], str]:
        """완료 Job 이력 = slurmdbd(sacct 상당) (U-JB-09, A-JB-04).

        slurmdbd가 끊긴 환경에서는 **slurmctld가 아직 들고 있는 완료 Job**으로 대체한다.
        보존 기간이 짧아(`MinJobAge`, 기본 300초) 완전한 이력은 아니지만,
        화면 전체를 오류로 막는 것보다 최근 결과라도 보이는 편이 낫다.
        어느 쪽에서 왔는지를 함께 돌려주어 화면이 그 차이를 밝힐 수 있게 한다.
        """
        client = self.clusters.slurm_client(cluster)
        params = {k: v for k, v in filters.items() if v is not None}
        # slurmdbd는 start_time이 없으면 **오늘 것만** 준다(sacct와 동일 — 실측).
        # 날짜가 바뀌면 어제 Job이 통째로 사라지므로 기본 조회 구간을 항상 넣는다.
        # `T00:00:00`을 붙이면 400 "Unable to parse query"가 나므로 날짜만 보낸다.
        params.setdefault("start_time", str(date.today() - timedelta(days=days)))
        # slurmdbd의 state 필터는 이 빌드에서 항상 0건을 돌려준다(실측) — 서버로 넘기지 않고
        # 받아온 뒤 직접 거른다. users 필터를 한 번 더 거르는 것과 같은 이유다.
        state_filter = params.pop("state", None)
        if not is_admin:
            params["users"] = user.username  # 서버측 강제
        requested_user = params.get("users") if is_admin else None
        try:
            jobs = _as_job_list(client.get_accounting_jobs(as_user=user.username, **params))
            source = "slurmdbd"
        except Exception:
            jobs = [
                j
                for j in _as_job_list(client.get_jobs(as_user=user.username))
                if _state_of(j).upper() not in RUNNING_STATES
            ]
            # 대체 경로는 slurmdbd의 users 필터를 못 쓰므로 여기서 직접 건다.
            if requested_user:
                jobs = [j for j in jobs if self._owner_of(j) == requested_user]
            source = "slurmctld"
        if not is_admin:
            # slurmdbd가 필터를 무시해도 새어 나가지 않도록 한 번 더 거른다.
            jobs = [j for j in jobs if self._owner_of(j) == user.username]
        if state_filter:
            jobs = [j for j in jobs if _state_of(j).upper() == state_filter.upper()]
        return jobs, source

    # --- 제출 폼 선택지 (U-JB-01) ----------------------------------------
    def options(self, cluster: Cluster, *, user: User) -> dict[str, Any]:
        """파티션·계정·QOS 목록.

        **한 항목이 실패해도 나머지는 돌려준다.** 파티션은 slurmctld, 계정·QOS는
        slurmdbd에서 오는데 slurmdbd만 끊긴 환경이 흔하다(실측). 전부 실패로 처리하면
        파티션까지 못 고르게 되어 제출 자체가 막힌다.
        """
        client = self.clusters.slurm_client(cluster)

        def safe(fetch, key: str) -> list[str]:
            """실패해도 응답 본문에 목록이 실려 있으면 건져 쓴다.

            slurmrestd는 **부분 실패도 500으로 돌려준다** — 파티션 조회에서
            slurmdbd TRES 조회만 실패해도 전체가 500이 되는데, 본문에는 파티션 목록이
            정상적으로 들어 있다(실측). 여기서까지 버리면 고를 수 있는 값이 하나도 없어
            제출이 막힌다. 오류 자체는 노드/파티션 관리 화면에서 그대로 드러난다.
            """
            try:
                return fetch()
            except Exception as exc:
                detail = getattr(exc, "detail", None)
                body = detail.get("body") if isinstance(detail, dict) else None
                return _names(body.get(key)) if isinstance(body, dict) else []

        def partitions() -> list[str]:
            payload = client.get_partitions(as_user=user.username)
            return _names(payload.get("partitions") if isinstance(payload, dict) else None)

        def accounts() -> list[str]:
            """**이 사용자에게 연결된 계정만** 돌려준다.

            전체 계정 목록으로 대체하면 안 된다 — 소속되지 않은 계정을 골라 제출하면
            Slurm이 거부한다. 고를 수 없는 값을 보여주는 화면이 더 나쁘다.

            출처는 `/associations`다. `/user/{name}`은 응답에 associations를 채워주지
            않아(항상 빈 배열 — 실측) 소속을 알 수 없다.
            """
            payload = client.get_associations(as_user=user.username)
            associations = payload.get("associations") if isinstance(payload, dict) else None
            found: list[str] = []
            for assoc in associations or []:
                if not isinstance(assoc, dict) or assoc.get("user") != user.username:
                    continue
                account = assoc.get("account")
                if account and account not in found:
                    found.append(str(account))
            return found

        def qos() -> list[str]:
            payload = client.get_qos(as_user=user.username)
            return _names(payload.get("qos") if isinstance(payload, dict) else None)

        return {
            "partitions": safe(partitions, "partitions"),
            "accounts": safe(accounts, "accounts"),
            "qos": safe(qos, "qos"),
            "gpu_partitions": _gpu_partitions(client, as_user=user.username),
        }

    # --- 제출 -----------------------------------------------------------
    def submit(self, cluster: Cluster, spec: JobSpec, *, user: User) -> dict[str, Any]:
        script = self.build_script(spec)
        props = _slurm_job_properties(spec, default_name=spec.name)
        ignored: list[str] = []
        if spec.mode == "script":
            # U-JB-02는 **스크립트가 정본**이다. 지시자를 REST 속성으로 옮기지 않으면
            # 사용자가 붙여 넣은 `#SBATCH`가 조용히 무시되고 기본값으로 돈다(실측).
            parsed, ignored = parse_sbatch(script)
            props.update(parsed)
        payload = {"script": script, "job": props}
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
        # 옮기지 못한 지시자는 **화면에 알린다** — 안 알리면 안 먹은 줄 모른다.
        return {"job_id": job_id, "raw": result, "ignored_directives": ignored}

    def build_script(self, spec: JobSpec) -> str:
        """폼 → `#SBATCH` 배치 스크립트 생성 (U-JB-01).

        모드별로 다르게 만든다.
          - `script`(U-JB-02): 사용자가 준 본문을 **그대로** 쓴다. shebang만 보강한다.
          - `form`(U-JB-01): 폼 값을 `#SBATCH` 지시자로 적고 그 아래에 실행 본문을 둔다.

        주의: slurmrestd 제출에서 `#SBATCH`는 **적용되지 않는다**(실측 — REST의 job
        속성이 이긴다). 지시자는 스크립트를 그대로 `sbatch`로 재실행하거나 내용을
        확인할 수 있게 남기는 기록이며, 실제 자원 적용은 REST 페이로드가 담당한다.
        두 곳 모두 같은 폼 값에서 나오므로 어긋나지 않는다.
        """
        if spec.mode == "script":
            if not spec.script:
                raise ValidationFailed("실행할 스크립트가 필요합니다.")
            # shebang이 없으면 sbatch가 배치 스크립트로 인정하지 않아 제출 직후 FAILED가 된다(실측).
            if spec.script.lstrip().startswith("#!"):
                return spec.script
            return "#!/bin/bash\n" + spec.script.lstrip("\n")

        body = spec.script or ""
        if not body:
            raise ValidationFailed("실행할 스크립트가 필요합니다.")

        directives = ["#!/bin/bash"]
        for flag, value in (
            ("--job-name", spec.name),
            ("--partition", spec.partition),
            ("--account", spec.account),
            ("--qos", spec.qos),
            ("--nodes", spec.nodes),
            ("--ntasks", spec.ntasks),
            ("--cpus-per-task", spec.cpus_per_task),
            ("--gres", f"gpu:{spec.gpus}" if spec.gpus else None),
            ("--mem", f"{spec.memory_gb}G" if spec.memory_gb else None),
            ("--time", spec.walltime),
            ("--chdir", spec.work_dir),
            ("--array", spec.array),
            ("--dependency", spec.dependency),
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
        # slurmdbd는 {"current": ["COMPLETED"], "reason": ...} 형태로 준다 — 리스트를 한 번 더 푼다.
        current = state.get("current")
        if isinstance(current, list):
            return str(current[0]) if current else ""
        return str(current or "")
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


def walltime_minutes(walltime: str) -> int:
    """`D-HH:MM:SS`·`HH:MM:SS`·`MM` → 분.

    slurmrestd v0.0.41의 `time_limit`은 **분 단위 정수**다. 문자열을 그대로 보내면
    `Expected integer but got "00:05:00"`(9202)로 제출이 거부된다(실측).
    초는 올림한다 — 30초짜리를 0분으로 만들면 즉시 종료된다.
    """
    text = walltime.strip()
    days = 0
    if "-" in text:
        head, _, text = text.partition("-")
        days = int(head)
    parts = [int(p) for p in text.split(":")] if text else [0]
    if len(parts) == 1:
        h, m, s = 0, parts[0], 0
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    elif len(parts) == 3:
        h, m, s = parts
    else:
        raise ValidationFailed("Walltime 형식이 올바르지 않습니다.", detail={"walltime": walltime})
    return days * 1440 + h * 60 + m + (1 if s else 0)


def _environment(spec: JobSpec) -> list[str]:
    """`KEY=VALUE` 배열. slurmrestd v0.0.41은 객체를 받지 않는다.

    **비우면 안 된다** — 빈 배열로 보내면 Slurm이
    `I/O error writing script/environment to file`(2019)로 제출을 실패시킨다(실측).
    """
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    env.update(spec.environment or {})
    return [f"{k}={v}" for k, v in env.items()]


def _gpu_partitions(client, *, as_user: str) -> list[str] | None:
    """GPU를 가진 노드가 하나라도 있는 파티션 이름.

    파티션 응답에서 GRES를 읽지 않고 **노드에서 거슬러 올라간다** — 노드의 `gres`·
    `partitions`는 화면이 이미 쓰고 있어 형태가 확인된 값이다.

    **알 수 없으면 `None`을 돌려준다.** 빈 목록으로 뭉뚱그리면 조회 실패가 "GPU 없음"으로
    둔갑해 멀쩡한 제출을 막는다 — 고를 수 있어야 할 것을 못 고르게 만드는 쪽이 더 나쁘다.
    """
    try:
        payload = client.get_nodes(as_user=as_user)
    except Exception:  # noqa: BLE001 — 못 읽으면 '모른다'로 남긴다
        return None
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    if not isinstance(nodes, list):
        return None
    found: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or "gpu" not in str(node.get("gres") or "").lower():
            continue
        for name in node.get("partitions") or []:
            if name and str(name) not in found:
                found.append(str(name))
    return found


def _names(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(i["name"]) for i in items if isinstance(i, dict) and i.get("name")]


#: `#SBATCH` 지시자 → REST job 속성. **여기 없는 지시자는 적용되지 않는다.**
#: slurmrestd는 스크립트의 지시자를 읽지 않고 REST 속성만 본다(실측) — 그래서 포털이
#: 직접 옮겨 준다. 옮기지 못한 것은 조용히 버리지 않고 목록으로 돌려준다.
_SBATCH_LINE = re.compile(r"^\s*#SBATCH\s+(.+?)\s*$", re.MULTILINE)
_SBATCH_SHORT = {
    "p": "partition", "A": "account", "q": "qos", "N": "nodes",
    "c": "cpus-per-task", "t": "time", "J": "job-name", "D": "chdir",
    "a": "array", "d": "dependency", "G": "gpus", "n": "ntasks",
}
#: `--gres=gpu:a100:2`처럼 타입이 끼어도 개수만 뽑는다. gpu 이외의 gres는 다루지 않는다.
_GRES_GPU = re.compile(r"^gpu(?::[A-Za-z0-9_.-]+)?:(\d+)$")
_MEM_UNIT = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}


def _memory_mb(text: str) -> int:
    """`32G`·`4096M`·`1024`(단위 없으면 MB) → MB 정수."""
    raw = text.strip().upper()
    unit = _MEM_UNIT.get(raw[-1:], None)
    number = float(raw[:-1] if unit else raw)
    return int(number * (unit or 1))


def parse_sbatch(script: str) -> tuple[dict[str, Any], list[str]]:
    """스크립트의 `#SBATCH` → (REST 속성, 옮기지 못한 지시자).

    U-JB-02는 **스크립트가 정본**이다. 폼 값으로 자원을 정하면 사용자가 붙여 넣은
    지시자가 조용히 무시되어, 잘 돌던 스크립트가 엉뚱한 자원으로 돈다.
    """
    props: dict[str, Any] = {}
    ignored: list[str] = []

    for line in _SBATCH_LINE.findall(script):
        try:
            tokens = shlex.split(line.split(" #", 1)[0])
        except ValueError:
            ignored.append(line)
            continue
        i = 0
        while i < len(tokens):
            token = tokens[i]
            i += 1
            if token.startswith("--"):
                name, sep, value = token[2:].partition("=")
                if not sep and i < len(tokens) and not tokens[i].startswith("-"):
                    value = tokens[i]
                    i += 1
            elif token.startswith("-") and len(token) > 1:
                name = _SBATCH_SHORT.get(token[1], token[1])
                value = token[2:]
                if not value and i < len(tokens) and not tokens[i].startswith("-"):
                    value = tokens[i]
                    i += 1
            else:
                continue
            if not _apply_directive(name, value, props):
                ignored.append(f"--{name}" if len(name) > 1 else f"-{name}")
    return props, ignored


def _apply_directive(name: str, value: str, props: dict[str, Any]) -> bool:
    """알려진 지시자면 REST 속성에 담고 True. 모르면 False."""
    try:
        if name == "partition":
            props["partition"] = value
        elif name == "account":
            props["account"] = value
        elif name == "qos":
            props["qos"] = value
        elif name == "nodes":
            props["nodes"] = value  # "2-4" 범위 표기를 허용하므로 문자열이다
        elif name == "cpus-per-task":
            props["cpus_per_task"] = int(value)
        elif name == "ntasks":
            props["tasks"] = int(value)
        elif name == "mem":
            props["memory_per_node"] = _memory_mb(value)
        elif name == "time":
            props["time_limit"] = walltime_minutes(value)
        elif name == "job-name":
            props["name"] = value
        elif name == "chdir":
            props["current_working_directory"] = value
        elif name == "array":
            props["array"] = value  # "1-240", "1-240%4", "17,58" — Slurm이 해석한다
        elif name == "dependency":
            props["dependency"] = value  # "afterok:123" — 형식 검사는 Slurm에 맡긴다
        elif name in ("gres", "gpus-per-node"):
            # --gres는 gpu 외의 자원(license, mps…)도 받지만 포털이 옮기는 것은 gpu뿐이다.
            count = _GRES_GPU.match(value.strip()) if name == "gres" else None
            props["tres_per_node"] = gres_gpu(count.group(1) if count else int(value))
        elif name == "gpus":
            props["tres_per_job"] = gres_gpu(int(value))
        elif name == "gpus-per-task":
            props["tres_per_task"] = gres_gpu(int(value))
        else:
            return False
    except (ValueError, ValidationFailed):
        # 값이 이상하면 **적용했다고 하지 않는다** — 화면에 목록으로 뜬다.
        return False
    return True


def gres_gpu(count: int | str) -> str:
    """GPU 개수 → `tres_per_node` 문자열.

    **실측(2026-08-08, v0.0.43)**: 형식에 따라 도달하는 파서가 다르다.
      - `"gpu:1"`      → 2115 *Invalid Trackable RESource (TRES) specification*
      - `"gres:gpu:1"` → 2072 *Invalid generic resource (gres) specification*

    2072는 gres 파서까지 도달했다는 뜻이다(이 클러스터에 GPU가 없어 이름 조회에서 실패).
    즉 `--gres=gpu:N`이 노리는 경로는 **`gres:` 접두사 형식**이다. `sbatch --gres=gpu:N`도
    `TresPerNode=gres:gpu:N`으로 남긴다.

    GPU 노드가 들어오면 **성공 제출로 최종 확인해야 한다** — 지금은 "형식이 맞다"까지만
    확인됐고 "실제로 할당된다"는 확인하지 못했다.
    """
    return f"gres:gpu:{count}"


def _slurm_job_properties(spec: JobSpec, *, default_name: str) -> dict[str, Any]:
    props: dict[str, Any] = {"name": default_name, "environment": _environment(spec)}
    for key, value in (
        ("partition", spec.partition),
        ("account", spec.account),
        ("qos", spec.qos),
        # nodes는 문자열이다("1", "2-4" 같은 범위 표기를 허용하므로)
        ("nodes", str(spec.nodes) if spec.nodes else None),
        ("tasks", spec.ntasks),
        ("cpus_per_task", spec.cpus_per_task),
        # 메모리는 MB 정수
        ("memory_per_node", spec.memory_gb * 1024 if spec.memory_gb else None),
        ("time_limit", walltime_minutes(spec.walltime) if spec.walltime else None),
        ("current_working_directory", spec.work_dir),
        # 0은 "GPU 0개 요청"이 되어 거부될 수 있으므로 아예 넣지 않는다.
        ("tres_per_node", gres_gpu(spec.gpus) if spec.gpus else None),
        ("array", spec.array),
        ("dependency", spec.dependency),
    ):
        if value not in (None, ""):
            props[key] = value
    return props


