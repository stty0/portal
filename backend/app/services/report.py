"""통계·리포트 서비스 (A-RP-01·02·03).

세 화면 모두 **slurmdbd의 완료 Job 레코드 하나**에서 파생된다.
  - A-RP-01 사용량   : 사용자/계정/파티션별 CPU-시간·Job 수
  - A-RP-02 가동률   : 기간 내 CPU-시간 합 ÷ 클러스터 총 CPU-시간
  - A-RP-03 대기시간 : 제출→시작 지연 분포

CPU-시간은 `tres.allocated`의 cpu 수 × `time.elapsed`로 계산한다. slurmdbd가 주는
`billing` 값은 사이트 정책(TRESBillingWeights)에 따라 달라져 자원량 지표로 쓸 수 없다.
"""

from __future__ import annotations

import collections
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Cluster
from app.services.cluster import ClusterService


class ReportService:
    def __init__(self, session: Session, clusters: ClusterService):
        self.session = session
        self.clusters = clusters

    # --- 원천 데이터 -----------------------------------------------------
    def _jobs(self, cluster: Cluster, *, days: int) -> tuple[list[dict[str, Any]], date, date]:
        end = date.today()
        start = end - timedelta(days=days)
        client = self.clusters.slurm_client(cluster)
        # start_time은 날짜만 받는다 — `T00:00:00`을 붙이면 400 "Unable to parse query"(실측).
        payload = client.get_accounting_jobs(start_time=str(start))
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        return [j for j in jobs or [] if isinstance(j, dict)], start, end

    # --- A-RP-01 사용량 --------------------------------------------------
    def usage(self, cluster_id: int, *, days: int = 30) -> dict[str, Any]:
        cluster = self.clusters.get(cluster_id)
        jobs, start, end = self._jobs(cluster, days=days)

        by_user: dict[str, dict[str, float]] = collections.defaultdict(_bucket)
        by_account: dict[str, dict[str, float]] = collections.defaultdict(_bucket)
        by_partition: dict[str, dict[str, float]] = collections.defaultdict(_bucket)
        for job in jobs:
            hours = _cpu_hours(job)
            node_hours = _node_hours(job)
            finished = _finished_at(job)
            for group, key in (
                (by_user, str(job.get("user") or "—")),
                (by_account, str(job.get("account") or "(기본)")),
                (by_partition, str(job.get("partition") or "—")),
            ):
                group[key]["jobs"] += 1
                group[key]["cpu_hours"] += hours
                group[key]["node_hours"] += node_hours
                if finished:
                    group[key]["last_end"] = max(group[key]["last_end"], finished)
                if _is_failed(job):
                    group[key]["failed"] += 1

        return {
            "start": str(start),
            "end": str(end),
            "total_jobs": len(jobs),
            "total_cpu_hours": round(sum(_cpu_hours(j) for j in jobs), 2),
            "by_user": _rows(by_user),
            "by_account": _rows(by_account),
            "by_partition": _rows(by_partition),
        }

    # --- A-RP-02 가동률 --------------------------------------------------
    def utilization(self, cluster_id: int, *, days: int = 30) -> dict[str, Any]:
        """일자별 CPU-시간과 가동률.

        분모는 `노드별 CPU 합 × 24시간`이다. 노드가 기간 중에 늘거나 줄면 과거 구간의
        분모가 현재 구성으로 계산되므로, 장기 구간에서는 근사치임을 화면에 밝힌다.
        """
        cluster = self.clusters.get(cluster_id)
        jobs, start, end = self._jobs(cluster, days=days)
        total_cpus = sum(
            int(n.get("cpus") or 0) for n in self.clusters.nodes(cluster_id)
        )

        by_day: dict[str, float] = collections.defaultdict(float)
        for job in jobs:
            day = _started_on(job)
            if day:
                by_day[day] += _cpu_hours(job)

        capacity = total_cpus * 24
        daily = []
        cursor = start
        while cursor <= end:
            key = str(cursor)
            used = round(by_day.get(key, 0.0), 2)
            daily.append(
                {
                    "date": key,
                    "cpu_hours": used,
                    "pct": round(used / capacity * 100, 1) if capacity else None,
                }
            )
            cursor += timedelta(days=1)

        return {
            "start": str(start),
            "end": str(end),
            "total_cpus": total_cpus,
            "daily_capacity_cpu_hours": capacity,
            "daily": daily,
        }

    # --- A-RP-03 대기시간 ------------------------------------------------
    def wait_time(self, cluster_id: int, *, days: int = 30) -> dict[str, Any]:
        cluster = self.clusters.get(cluster_id)
        jobs, start, end = self._jobs(cluster, days=days)

        waits: list[float] = []
        by_partition: dict[str, list[float]] = collections.defaultdict(list)
        for job in jobs:
            seconds = _wait_seconds(job)
            if seconds is None:
                continue
            waits.append(seconds)
            by_partition[str(job.get("partition") or "—")].append(seconds)

        buckets = [("1분 미만", 60), ("5분 미만", 300), ("30분 미만", 1800), ("1시간 미만", 3600)]
        histogram = []
        previous = 0
        for label, limit in buckets:
            histogram.append(
                {"label": label, "count": sum(1 for w in waits if previous <= w < limit)}
            )
            previous = limit
        histogram.append({"label": "1시간 이상", "count": sum(1 for w in waits if w >= 3600)})

        return {
            "start": str(start),
            "end": str(end),
            "samples": len(waits),
            "avg_seconds": round(sum(waits) / len(waits), 1) if waits else None,
            "median_seconds": _median(waits),
            "max_seconds": round(max(waits), 1) if waits else None,
            "histogram": histogram,
            "by_partition": [
                {
                    "partition": name,
                    "samples": len(values),
                    "avg_seconds": round(sum(values) / len(values), 1),
                    "max_seconds": round(max(values), 1),
                }
                for name, values in sorted(by_partition.items())
            ],
        }


def _bucket() -> dict[str, float]:
    return {"jobs": 0, "cpu_hours": 0.0, "failed": 0, "node_hours": 0.0, "last_end": 0}


def _rows(group: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "key": key,
                "jobs": int(v["jobs"]),
                "failed": int(v["failed"]),
                "cpu_hours": round(v["cpu_hours"], 2),
                # 노드-시간은 CPU-시간과 다른 이야기다 — 노드를 통째로 잡고 코어를 조금만
                # 쓴 Job은 CPU-시간이 작아도 노드-시간이 크다.
                "node_hours": round(v["node_hours"], 2),
                "last_active": _as_date(int(v["last_end"])),
            }
            for key, v in group.items()
        ),
        key=lambda row: row["cpu_hours"],
        reverse=True,
    )


def _allocated(job: dict[str, Any], kind: str) -> int:
    tres = job.get("tres")
    allocated = tres.get("allocated") if isinstance(tres, dict) else None
    for entry in allocated or []:
        if isinstance(entry, dict) and entry.get("type") == kind:
            return int(entry.get("count") or 0)
    return 0


def _elapsed(job: dict[str, Any]) -> int:
    time = job.get("time")
    return int(time.get("elapsed") or 0) if isinstance(time, dict) else 0


def _cpu_hours(job: dict[str, Any]) -> float:
    return _allocated(job, "cpu") * _elapsed(job) / 3600


def _node_hours(job: dict[str, Any]) -> float:
    return _allocated(job, "node") * _elapsed(job) / 3600


def _finished_at(job: dict[str, Any]) -> int:
    """마지막 활동 판정용 종료 시각(epoch). 없으면 0."""
    time = job.get("time")
    return (_epoch(time.get("end")) if isinstance(time, dict) else None) or 0


def _as_date(epoch: int) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone().date().isoformat()


#: Slurm이 "값 없음"을 나타내는 센티넬(`NO_VAL`=0xFFFFFFFE, `INFINITE`=0xFFFFFFFF).
#: **0이 아니다.** 시작하지 못한 Job의 `time.start`로 이 값이 오는데 `not start` 검사에
#: 걸리지 않아, 그런 Job이 "79년 대기"로 집계됐다(실측: 최대 대기 696938시간 =
#: 0xFFFFFFFF − 제출시각). 64비트 센티넬(`NO_VAL64` 등)은 더 크므로 같은 비교에 걸린다.
_TIME_SENTINEL = 0xFFFFFFFE


def _epoch(value: Any) -> int | None:
    """slurmdbd 시각 → epoch 초. 미설정·센티넬은 None.

    시각을 읽는 곳이 **모두 이걸 거쳐야 한다** — 한 곳만 빠뜨리면 센티넬이 2106년
    날짜나 수십 년짜리 구간으로 조용히 흘러든다.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    seconds = int(value)
    if seconds <= 0 or seconds >= _TIME_SENTINEL:
        return None
    return seconds


def _wait_seconds(job: dict[str, Any]) -> float | None:
    """제출 → 시작 지연. 시작하지 못한 Job(취소 등)은 표본에서 뺀다."""
    time = job.get("time")
    if not isinstance(time, dict):
        return None
    submission = _epoch(time.get("submission"))
    start = _epoch(time.get("start"))
    if submission is None or start is None or start < submission:
        return None
    return float(start - submission)


def _started_on(job: dict[str, Any]) -> str | None:
    time = job.get("time")
    start = _epoch(time.get("start")) if isinstance(time, dict) else None
    return _as_date(start or 0)


def _is_failed(job: dict[str, Any]) -> bool:
    state = job.get("state")
    current = state.get("current") if isinstance(state, dict) else state
    if isinstance(current, list):
        current = current[0] if current else ""
    return str(current or "").upper().startswith(("FAIL", "NODE_FAIL", "TIMEOUT", "OUT_OF"))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)
