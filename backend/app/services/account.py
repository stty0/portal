"""내 사용량 · Fairshare 서비스 (U-AC-01·02).

**대상은 언제나 요청자 본인이다** — 클라이언트가 사용자명을 넘길 수 없다(FileService와
같은 원칙). slurmdbd가 users 필터를 무시해도 새어 나가지 않도록 한 번 더 거른다.
"""

from __future__ import annotations

import collections
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.clients.ssh.client import LoginNodeClient
from app.core.config import Settings
from app.core.secrets import SecretStore
from app.models import Cluster, User
from app.repositories.cluster import ClusterCredentialRepository
from app.services.cluster import ClusterService
from app.services.files import ssh_target_for

# Job 응답 파싱은 ReportService가 slurmdbd 형태를 이미 흡수해 두었다. 복제하면 한쪽만 고쳐진다.
from app.services.report import _cpu_hours, _is_failed, _started_on


class AccountService:
    def __init__(
        self,
        session: Session,
        clusters: ClusterService,
        *,
        settings: Settings,
        secrets: SecretStore,
    ):
        self.session = session
        self.clusters = clusters
        self.settings = settings
        self.secrets = secrets
        self.credentials = ClusterCredentialRepository(session)

    def _connect(self, cluster: Cluster) -> LoginNodeClient:
        return LoginNodeClient(
            ssh_target_for(cluster, secrets=self.secrets, credentials=self.credentials),
            known_hosts=self.settings.ssh_known_hosts,
            timeout=self.settings.ssh_timeout_seconds,
        )

    # --- U-AC-01 내 사용량 ------------------------------------------------
    def usage(self, cluster_id: int, *, user: User, days: int = 30) -> dict[str, Any]:
        cluster = self.clusters.get(cluster_id)
        client = self.clusters.slurm_client(cluster)
        end = date.today()
        start = end - timedelta(days=days)
        # start_time은 날짜만 받는다 — `T00:00:00`을 붙이면 400(실측, JobService와 동일).
        payload = client.get_accounting_jobs(start_time=str(start), users=user.username)
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        jobs = [j for j in jobs or [] if isinstance(j, dict)]
        # slurmdbd가 users 필터를 무시해도 남의 Job이 섞이지 않게 한 번 더 거른다.
        jobs = [j for j in jobs if str(j.get("user") or "") == user.username]

        daily: dict[str, dict[str, float]] = collections.defaultdict(_bucket)
        by_partition: dict[str, dict[str, float]] = collections.defaultdict(_bucket)
        by_account: dict[str, dict[str, float]] = collections.defaultdict(_bucket)
        for job in jobs:
            cpu_h = _cpu_hours(job)
            gpu_h = _gpu_hours(job)
            failed = _is_failed(job)
            day = _started_on(job)
            targets = [
                (by_partition, str(job.get("partition") or "—")),
                (by_account, str(job.get("account") or "(기본)")),
            ]
            if day:
                targets.append((daily, day))
            for group, key in targets:
                group[key]["jobs"] += 1
                group[key]["cpu_hours"] += cpu_h
                group[key]["gpu_hours"] += gpu_h
                if failed:
                    group[key]["failed"] += 1

        return {
            "start": str(start),
            "end": str(end),
            "total_jobs": len(jobs),
            "total_cpu_hours": round(sum(_cpu_hours(j) for j in jobs), 2),
            "total_gpu_hours": round(sum(_gpu_hours(j) for j in jobs), 2),
            "failed_jobs": sum(1 for j in jobs if _is_failed(j)),
            "daily": _rows(daily, key="date", sort_by_key=True),
            "by_partition": _rows(by_partition, key="label"),
            "by_account": _rows(by_account, key="label"),
        }

    # --- U-AC-02 Fairshare / QOS 한도 ------------------------------------
    def fairshare(self, cluster_id: int, *, user: User) -> dict[str, Any]:
        """내 association·QOS 한도 + 계산된 fairshare.

        slurmrestd v0.0.41의 association에는 **계산된 fairshare가 없다**(실측: `shares_raw`와
        한도만 있음). 그 값은 `sshare`(SSH)로 받는다 — 정의서 §4.1이 허용하는 CLI 래핑이며,
        실패해도 REST에서 얻은 부분은 그대로 돌려준다.
        """
        cluster = self.clusters.get(cluster_id)
        client = self.clusters.slurm_client(cluster)

        associations = _items(client.get_associations(), "associations")
        mine = [a for a in associations if str(a.get("user") or "") == user.username]

        qos_by_name = {
            str(q.get("name")): q for q in _items(client.get_qos(), "qos") if q.get("name")
        }
        used_qos = sorted({q for a in mine for q in (a.get("qos") or [])})

        shares: list[dict[str, Any]] = []
        try:
            with self._connect(cluster) as ssh:
                shares = ssh.fairshare(user.username)
        except Exception:  # noqa: BLE001 — sshare가 없어도 나머지는 보여준다
            shares = []

        return {
            "username": user.username,
            "associations": [
                {
                    "account": a.get("account"),
                    "partition": a.get("partition") or None,
                    "is_default": bool(a.get("is_default")),
                    "shares_raw": a.get("shares_raw"),
                    "qos": list(a.get("qos") or []),
                }
                for a in mine
            ],
            "qos": [_qos_limits(qos_by_name[name]) for name in used_qos if name in qos_by_name],
            #: sshare 결과. 빈 목록이면 클러스터가 이 정보를 주지 않는 것이다.
            "shares": shares,
        }


# --- 헬퍼 -----------------------------------------------------------------


def _bucket() -> dict[str, float]:
    return {"jobs": 0.0, "cpu_hours": 0.0, "gpu_hours": 0.0, "failed": 0.0}


def _rows(group: dict[str, dict[str, float]], *, key: str, sort_by_key: bool = False) -> list[dict[str, Any]]:
    rows = [
        {
            key: name,
            "jobs": int(v["jobs"]),
            "cpu_hours": round(v["cpu_hours"], 2),
            "gpu_hours": round(v["gpu_hours"], 2),
            "failed": int(v["failed"]),
        }
        for name, v in group.items()
    ]
    rows.sort(key=lambda r: r[key] if sort_by_key else -r["cpu_hours"])
    return rows


def _items(payload: Any, key: str) -> list[dict[str, Any]]:
    node = payload.get(key) if isinstance(payload, dict) else None
    return [i for i in node or [] if isinstance(i, dict)]


def _gpu_hours(job: dict[str, Any]) -> float:
    """GPU-시간. GRES가 없는 클러스터에서는 0이 나오며 그게 사실이다."""
    tres = job.get("tres")
    allocated = tres.get("allocated") if isinstance(tres, dict) else None
    gpus = 0
    for entry in allocated or []:
        if isinstance(entry, dict) and entry.get("type") == "gres" and entry.get("name") == "gpu":
            gpus = int(entry.get("count") or 0)
            break
    time = job.get("time")
    elapsed = int(time.get("elapsed") or 0) if isinstance(time, dict) else 0
    return gpus * elapsed / 3600


def _number(node: Any) -> int | None:
    """slurmdbd의 `{set, infinite, number}` 삼중항 → 값.

    `set=false`거나 `infinite=true`면 **한도 없음**이다. 0으로 접으면 "0 제한"으로 오해된다.
    """
    if not isinstance(node, dict):
        return None
    if not node.get("set") or node.get("infinite"):
        return None
    return int(node.get("number") or 0)


def _qos_limits(qos: dict[str, Any]) -> dict[str, Any]:
    limits = qos.get("limits") if isinstance(qos.get("limits"), dict) else {}
    maximum = limits.get("max") if isinstance(limits.get("max"), dict) else {}
    wall = maximum.get("wall_clock") if isinstance(maximum.get("wall_clock"), dict) else {}
    jobs = maximum.get("jobs") if isinstance(maximum.get("jobs"), dict) else {}
    active = jobs.get("active_jobs") if isinstance(jobs.get("active_jobs"), dict) else {}
    return {
        "name": qos.get("name"),
        "description": qos.get("description"),
        "priority": _number(qos.get("priority")),
        "usage_factor": _number(qos.get("usage_factor")),
        "max_wall_minutes": _number(_dig(wall, "per", "job")),
        "max_jobs_per_user": _number(_dig(active, "per", "user")),
        "max_submit_per_user": _number(_dig(jobs, "per", "user")),
    }


def _dig(node: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node
