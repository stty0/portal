"""통계·리포트 테스트 (A-RP-01·02·03).

CPU-시간·대기시간 계산이 핵심이다 — 숫자가 틀리면 화면이 조용히 거짓말을 한다.
"""

import pytest

from tests.conftest import auth_headers

BASE = 1785900000


def _job(user, partition, cpus, elapsed, wait=0, state="COMPLETED", account=""):
    return {
        "user": user,
        "account": account,
        "partition": partition,
        "state": {"current": [state]},
        "time": {"submission": BASE, "start": BASE + wait, "end": BASE + wait + elapsed,
                 "elapsed": elapsed},
        "tres": {"allocated": [{"type": "cpu", "count": cpus},
                               {"type": "node", "count": 1}]},
    }


@pytest.fixture
def jobs(slurm_client):
    slurm_client.jobs = [
        _job("jrpark", "cpu", cpus=2, elapsed=3600, wait=0),        # 2 CPU-시간
        _job("jrpark", "cpu", cpus=4, elapsed=1800, wait=120),      # 2 CPU-시간
        _job("opadmin", "gpu", cpus=1, elapsed=7200, wait=4000, state="FAILED"),  # 2 CPU-시간
    ]
    return slurm_client


def test_usage_aggregates_cpu_hours(client, cluster, admin_token, jobs):
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/reports/usage", headers=auth_headers(admin_token)
    ).json()
    assert body["total_jobs"] == 3
    assert body["total_cpu_hours"] == 6.0
    by_user = {r["key"]: r for r in body["by_user"]}
    assert by_user["jrpark"]["cpu_hours"] == 4.0
    assert by_user["jrpark"]["jobs"] == 2
    # 실패 Job도 자원은 썼다 — 사용량에 포함하되 실패 건수를 따로 센다
    assert by_user["opadmin"]["failed"] == 1
    assert by_user["opadmin"]["cpu_hours"] == 2.0


def test_usage_groups_missing_account_as_default(client, cluster, admin_token, jobs):
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/reports/usage", headers=auth_headers(admin_token)
    ).json()
    assert {r["key"] for r in body["by_account"]} == {"(기본)"}


def test_wait_time_stats_and_histogram(client, cluster, admin_token, jobs):
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/reports/wait-time", headers=auth_headers(admin_token)
    ).json()
    assert body["samples"] == 3
    assert body["max_seconds"] == 4000.0
    assert body["median_seconds"] == 120.0
    counts = {h["label"]: h["count"] for h in body["histogram"]}
    assert counts["1분 미만"] == 1        # 0초
    assert counts["5분 미만"] == 1        # 120초
    assert counts["1시간 이상"] == 1      # 4000초


def test_wait_time_skips_jobs_that_never_started(client, cluster, admin_token, slurm_client):
    slurm_client.jobs = [
        {"user": "jrpark", "partition": "cpu", "state": {"current": ["CANCELLED"]},
         "time": {"submission": BASE, "start": 0, "elapsed": 0}, "tres": {"allocated": []}},
    ]
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/reports/wait-time", headers=auth_headers(admin_token)
    ).json()
    assert body["samples"] == 0 and body["avg_seconds"] is None


def test_utilization_uses_node_cpu_capacity(client, cluster, admin_token, jobs):
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/reports/utilization?days=2",
        headers=auth_headers(admin_token),
    ).json()
    # fake 노드는 cpus=8 하나 → 하루 용량 192 CPU-시간
    assert body["total_cpus"] == 8
    assert body["daily_capacity_cpu_hours"] == 192
    assert len(body["daily"]) == 3  # start~end 포함


def test_reports_are_admin_only(client, cluster, user_token):
    for path in ("usage", "utilization", "wait-time"):
        assert client.get(
            f"/api/v1/clusters/{cluster.id}/reports/{path}", headers=auth_headers(user_token)
        ).status_code == 403
