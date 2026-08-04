"""Job 스코프·제출 테스트 (U-JB-*, A-JB-*).

핵심은 두 가지다.
  1. USER는 본인 Job만 보고/제어한다.
  2. Slurm 대상 사용자(`X-SLURM-USER-NAME`)는 항상 인증된 본인이다.
"""

from tests.conftest import auth_headers


def test_user_sees_only_own_jobs(client, cluster, user_token, slurm_client):
    resp = client.get(f"/api/v1/clusters/{cluster.id}/jobs", headers=auth_headers(user_token))
    assert resp.status_code == 200
    owners = {j["user_name"] for j in resp.json()["items"]}
    assert owners == {"jrpark"}


def test_admin_sees_all_jobs(client, cluster, admin_token):
    resp = client.get(f"/api/v1/clusters/{cluster.id}/jobs", headers=auth_headers(admin_token))
    assert resp.json()["total"] == 2


def test_admin_can_filter_by_user(client, cluster, admin_token):
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/jobs?username=seonsj", headers=auth_headers(admin_token)
    )
    assert {j["user_name"] for j in resp.json()["items"]} == {"seonsj"}


def test_user_username_filter_cannot_widen_scope(client, cluster, user_token):
    """USER가 username 쿼리로 남의 Job을 보려 해도 서버가 본인으로 강제한다."""
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/jobs?username=seonsj", headers=auth_headers(user_token)
    )
    assert {j["user_name"] for j in resp.json()["items"]} == {"jrpark"}


def test_user_cannot_read_other_job(client, cluster, user_token):
    resp = client.get(f"/api/v1/clusters/{cluster.id}/jobs/45813", headers=auth_headers(user_token))
    # 403이 아니라 404 — Job 존재 여부 자체를 노출하지 않는다.
    assert resp.status_code == 404


def test_user_can_read_own_job(client, cluster, user_token):
    resp = client.get(f"/api/v1/clusters/{cluster.id}/jobs/45812", headers=auth_headers(user_token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "llm-finetune"


def test_user_cannot_cancel_other_job(client, cluster, user_token, slurm_client):
    resp = client.delete(
        f"/api/v1/clusters/{cluster.id}/jobs/45813", headers=auth_headers(user_token)
    )
    assert resp.status_code == 404
    assert slurm_client.cancelled == []  # scancel이 호출되지 않아야 한다


def test_user_can_cancel_own_job(client, cluster, user_token, slurm_client):
    resp = client.delete(
        f"/api/v1/clusters/{cluster.id}/jobs/45812", headers=auth_headers(user_token)
    )
    assert resp.status_code == 200
    assert slurm_client.cancelled == ["45812"]


def test_admin_can_cancel_any_job(client, cluster, admin_token, slurm_client):
    resp = client.delete(
        f"/api/v1/clusters/{cluster.id}/jobs/45813", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert slurm_client.cancelled == ["45813"]


def test_submit_forces_authenticated_username(client, cluster, user_token, slurm_client):
    """제출 API에 사용자명 필드가 없고, 서버가 as_user를 본인으로 채운다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={
            "name": "test-job",
            "partition": "gpu",
            "gpus": 2,
            "script": "srun python train.py",
            "user_name": "seonsj",  # 있어도 무시된다(스키마에 없음)
        },
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200
    submit_calls = [c for c in slurm_client.calls if c[0] == "submit_job"]
    assert submit_calls[0][1]["as_user"] == "jrpark"


def test_submit_records_audit_log(client, db, cluster, user_token):
    from app.models import AuditLog

    client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={"name": "audited", "script": "srun true"},
        headers=auth_headers(user_token),
    )
    entries = db.query(AuditLog).filter_by(action="JOB_SUBMIT").all()
    assert len(entries) == 1
    assert entries[0].target_cluster_id == cluster.id
    assert entries[0].actor_role == "USER"


def test_script_generation_from_form(client, cluster, user_token):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs/preview-script",
        json={
            "name": "mpi-run",
            "partition": "cpu",
            "nodes": 4,
            "cpus_per_task": 8,
            "gpus": 2,
            "memory_gb": 64,
            "walltime": "02:00:00",
            "script": "srun ./a.out",
        },
        headers=auth_headers(user_token),
    )
    script = resp.json()["script"]
    assert script == "srun ./a.out"  # 스크립트를 직접 준 경우 그대로 쓴다


def test_script_generation_from_template(client, db, cluster, user_token):
    from app.models import JobTemplate

    template = JobTemplate(
        name="python", type="batch", params={"script": "python {{entry}} --epochs {{epochs}}"}
    )
    db.add(template)
    db.commit()

    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs/preview-script",
        json={
            "name": "tpl-job",
            "partition": "gpu",
            "nodes": 1,
            "gpus": 4,
            "memory_gb": 32,
            "walltime": "01:00:00",
            "template_id": template.id,
            "template_params": {"entry": "train.py", "epochs": 10},
        },
        headers=auth_headers(user_token),
    )
    script = resp.json()["script"]
    assert script.startswith("#!/bin/bash")
    assert "#SBATCH --partition=gpu" in script
    assert "#SBATCH --gres=gpu:4" in script
    assert "#SBATCH --mem=32G" in script
    assert "#SBATCH --time=01:00:00" in script
    assert "python train.py --epochs 10" in script


def test_submit_without_script_or_template_fails(client, cluster, user_token):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={"name": "empty"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


def test_history_filters_to_self_even_if_slurmdbd_ignores(client, cluster, user_token):
    """fake slurmdbd는 users 필터를 무시한다 — 서비스가 한 번 더 걸러야 한다."""
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history", headers=auth_headers(user_token)
    )
    assert {j["user_name"] for j in resp.json()["items"]} == {"jrpark"}


def test_job_control_is_admin_only(client, cluster, user_token, admin_token):
    body = {"action": "hold"}
    path = f"/api/v1/clusters/{cluster.id}/jobs/45812"
    assert client.patch(path, json=body, headers=auth_headers(user_token)).status_code == 403
    assert client.patch(path, json=body, headers=auth_headers(admin_token)).status_code == 200
