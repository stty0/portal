"""내 사용량 · Fairshare (U-AC-01·02).

핵심은 **대상이 언제나 본인**이라는 것 — 사용자명을 받는 파라미터가 없다.
"""

import pytest

from app.models import User
from app.services.account import AccountService

def job(user, *, cpus=2, elapsed=3600, gpus=0, state="COMPLETED", started=1754400000, partition="cpu"):
    allocated = [{"type": "cpu", "name": "", "count": cpus}]
    if gpus:
        allocated.append({"type": "gres", "name": "gpu", "count": gpus})
    return {
        "user": user,
        "account": "dt-hpc",
        "partition": partition,
        "state": {"current": [state]},
        "tres": {"allocated": allocated},
        "time": {"elapsed": elapsed, "start": started, "submission": started - 60},
    }


@pytest.fixture
def me(db, user_token) -> User:
    return db.query(User).filter(User.username == "jrpark").one()


@pytest.fixture
def service(db, settings, secret_store, slurm_client):
    from tests.fakes import FakeClientFactory
    from app.services.cluster import ClusterService

    clusters = ClusterService(db, secrets=secret_store, client_factory=FakeClientFactory(slurm_client))
    return AccountService(db, clusters, settings=settings, secrets=secret_store)


# --- U-AC-01 사용량 --------------------------------------------------------


def test_usage_counts_only_my_jobs(service, cluster, me, slurm_client, monkeypatch):
    monkeypatch.setattr(
        slurm_client, "get_accounting_jobs",
        lambda **kw: {"jobs": [job("jrpark"), job("someone"), job("jrpark", cpus=4)]},
    )
    result = service.usage(cluster.id, user=me)
    # slurmdbd가 users 필터를 무시해도 남의 Job이 섞이면 안 된다.
    assert result["total_jobs"] == 2
    assert result["total_cpu_hours"] == 6.0  # (2 + 4) CPU × 1시간


def test_usage_requests_only_my_jobs_from_slurmdbd(service, cluster, me, slurm_client):
    service.usage(cluster.id, user=me, days=7)
    call = [c for c in slurm_client.calls if c[0] == "get_accounting_jobs"][0][1]
    assert call["users"] == "jrpark"
    # 날짜만 보낸다 — `T00:00:00`을 붙이면 400이 난다(실측).
    assert "T" not in call["start_time"]


def test_usage_separates_gpu_hours(service, cluster, me, slurm_client, monkeypatch):
    monkeypatch.setattr(
        slurm_client, "get_accounting_jobs",
        lambda **kw: {"jobs": [job("jrpark", cpus=8, gpus=2, elapsed=1800)]},
    )
    result = service.usage(cluster.id, user=me)
    assert result["total_cpu_hours"] == 4.0
    assert result["total_gpu_hours"] == 1.0


def test_usage_reports_zero_gpu_hours_without_gres(service, cluster, me, slurm_client, monkeypatch):
    # GPU가 없는 클러스터에서는 0이 나오며 그게 사실이다.
    monkeypatch.setattr(slurm_client, "get_accounting_jobs", lambda **kw: {"jobs": [job("jrpark")]})
    assert service.usage(cluster.id, user=me)["total_gpu_hours"] == 0.0


def test_usage_groups_by_day_and_partition(service, cluster, me, slurm_client, monkeypatch):
    monkeypatch.setattr(
        slurm_client, "get_accounting_jobs",
        lambda **kw: {"jobs": [job("jrpark", partition="cpu"), job("jrpark", partition="gpu")]},
    )
    result = service.usage(cluster.id, user=me)
    assert {r["label"] for r in result["by_partition"]} == {"cpu", "gpu"}
    assert len(result["daily"]) == 1


# --- U-AC-02 Fairshare ----------------------------------------------------


def test_fairshare_returns_only_my_associations(service, cluster, me, slurm_client, monkeypatch):
    monkeypatch.setattr(
        slurm_client, "get_associations",
        lambda **kw: {"associations": [
            {"account": "dt-hpc", "user": "jrpark", "shares_raw": 1, "qos": ["normal"], "is_default": True},
            {"account": "dt-hpc", "user": "someone", "shares_raw": 1, "qos": ["normal"]},
            {"account": "dt-hpc", "user": "", "shares_raw": 1, "qos": ["normal"]},
        ]},
    )
    result = service.fairshare(cluster.id, user=me)
    assert [a["account"] for a in result["associations"]] == ["dt-hpc"]
    assert result["username"] == "jrpark"


def test_fairshare_unwraps_qos_limit_triples(service, cluster, me, slurm_client, monkeypatch):
    """slurmdbd 한도는 `{set, infinite, number}`다 — 미설정을 0으로 접으면 오해된다."""
    monkeypatch.setattr(
        slurm_client, "get_associations",
        lambda **kw: {"associations": [{"account": "a", "user": "jrpark", "qos": ["normal"]}]},
    )
    monkeypatch.setattr(
        slurm_client, "get_qos",
        lambda **kw: {"qos": [{
            "name": "normal",
            "description": "기본",
            "priority": {"set": True, "infinite": False, "number": 10},
            "limits": {"max": {
                "wall_clock": {"per": {"job": {"set": True, "infinite": False, "number": 120}}},
                "jobs": {
                    "active_jobs": {"per": {"user": {"set": False, "infinite": True, "number": 0}}},
                    "per": {"user": {"set": False, "infinite": True, "number": 0}},
                },
            }},
        }]},
    )
    qos = service.fairshare(cluster.id, user=me)["qos"][0]
    assert qos["priority"] == 10
    assert qos["max_wall_minutes"] == 120
    # 미설정/무제한은 None이다. 0이면 "0개 제한"으로 읽힌다.
    assert qos["max_jobs_per_user"] is None


def test_fairshare_survives_missing_sshare(service, cluster, me, slurm_client, monkeypatch):
    """slurmrestd에 계산된 fairshare가 없어 sshare(SSH)로 받는다 — 실패해도 나머지는 준다."""
    monkeypatch.setattr(
        slurm_client, "get_associations",
        lambda **kw: {"associations": [{"account": "a", "user": "jrpark", "qos": []}]},
    )

    def boom(cluster):
        raise RuntimeError("ssh 불가")

    service._connect = boom  # type: ignore[method-assign]
    result = service.fairshare(cluster.id, user=me)
    assert result["shares"] == []
    assert result["associations"]
