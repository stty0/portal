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
    # 폼 모드는 폼 값을 #SBATCH 지시자로 적고 그 아래에 본문을 둔다
    assert script.startswith("#!/bin/bash\n#SBATCH --job-name=mpi-run")
    assert "#SBATCH --partition=cpu" in script
    assert "#SBATCH --cpus-per-task=8" in script
    assert "#SBATCH --gres=gpu:2" in script
    assert "#SBATCH --mem=64G" in script
    assert "#SBATCH --time=02:00:00" in script
    assert script.rstrip().endswith("srun ./a.out")


def test_submit_without_script_fails(client, cluster, user_token):
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


# --- 스크립트 모드는 스크립트가 정본 (U-JB-02) ------------------------------
# slurmrestd는 스크립트의 `#SBATCH`를 읽지 않고 REST 속성만 본다(실측). 옮겨 주지 않으면
# 사용자가 붙여 넣은 지시자가 조용히 무시되고 폼 기본값으로 돈다.

SCRIPT = """#!/bin/bash
#SBATCH --partition=gpu
#SBATCH -N 4 -c 8
#SBATCH --mem=32G
#SBATCH --time 01:30:00
srun ./solver
"""


def _submit_script(client, cluster, token, script=SCRIPT, **extra):
    return client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={"name": "run", "mode": "script", "script": script, **extra},
        headers=auth_headers(token),
    )


def test_script_directives_become_rest_properties(client, cluster, user_token, slurm_client):
    resp = _submit_script(client, cluster, user_token)
    assert resp.status_code == 200, resp.text
    job = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]["job"]
    assert job["partition"] == "gpu"
    assert job["nodes"] == "4"
    assert job["cpus_per_task"] == 8
    assert job["memory_per_node"] == 32768   # 32G → MB
    assert job["time_limit"] == 90           # 01:30:00 → 분


def test_script_directives_beat_form_values(client, cluster, user_token, slurm_client):
    """폼 값이 함께 와도 **스크립트가 이긴다** — 그게 이 모드의 뜻이다."""
    resp = _submit_script(client, cluster, user_token, partition="cpu", nodes=1)
    assert resp.status_code == 200, resp.text
    job = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]["job"]
    assert job["partition"] == "gpu" and job["nodes"] == "4"


def test_unmapped_directives_are_reported_not_dropped(client, cluster, user_token, slurm_client):
    """조용히 버리면 사용자는 안 먹은 줄 모른다."""
    resp = _submit_script(
        client, cluster, user_token,
        script="#!/bin/bash\n#SBATCH --gres=gpu:2\n#SBATCH --output=o.log\nsrun x\n",
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["ignored_directives"]) == {"--gres", "--output"}


def test_form_mode_does_not_parse_the_script(client, cluster, user_token, slurm_client):
    """폼 모드의 `#SBATCH`는 포털이 만든 것이라 다시 파싱할 이유가 없다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={"name": "run", "partition": "cpu", "script": "srun x"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ignored_directives"] == []


# --- GPU 파티션 판별 (U-JB-01) ----------------------------------------------
# 파티션 응답이 아니라 **노드에서 거슬러 올라간다** — 노드의 gres·partitions는 화면이
# 이미 쓰고 있어 형태가 확인된 값이다.


def test_gpu_partitions_come_from_node_gres(client, cluster, user_token, slurm_client):
    slurm_client.nodes_payload = {
        "nodes": [
            {"name": "cn01", "gres": "gpu:a100:4", "partitions": ["gpu", "all"]},
            {"name": "cn02", "gres": "", "partitions": ["cpu", "all"]},
        ]
    }
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/job-options", headers=auth_headers(user_token)
    ).json()
    assert body["gpu_partitions"] == ["gpu", "all"]


def test_unknown_gpu_support_is_null_not_empty(
    client, cluster, user_token, slurm_client, monkeypatch
):
    """조회 실패를 '빈 목록'으로 뭉뚱그리면 **GPU 없음으로 둔갑**해 멀쩡한 제출을 막는다.

    고를 수 있어야 할 것을 못 고르게 만드는 쪽이 더 나쁘므로 '모른다'로 남긴다.
    """
    def boom(*, as_user=None):
        raise RuntimeError("slurmctld 응답 없음")

    # 클래스가 아니라 **인스턴스**에 건다 — 클래스 속성을 지우면 원본 메서드까지 사라져
    # 뒤따르는 테스트가 깨진다(실제로 겪음).
    monkeypatch.setattr(slurm_client, "get_nodes", boom)
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/job-options", headers=auth_headers(user_token)
    ).json()
    assert body["gpu_partitions"] is None
    assert body["partitions"]  # 나머지 선택지는 그대로 온다


# --- slurmrestd v0.0.41 페이로드 형식 (실측 기반) ---------------------------


def test_walltime_is_converted_to_minutes():
    """v0.0.41의 time_limit은 분 단위 정수다 — 문자열이면 9202로 거부된다."""
    from app.services.job import walltime_minutes

    assert walltime_minutes("00:05:00") == 5
    assert walltime_minutes("02:00:00") == 120
    assert walltime_minutes("1-00:00:00") == 1440
    assert walltime_minutes("30") == 30
    # 초는 올림 — 30초를 0분으로 만들면 작업이 즉시 끝난다
    assert walltime_minutes("00:00:30") == 1


def test_job_properties_match_v0_0_41_types():
    from app.services.job import JobSpec, _slurm_job_properties

    spec = JobSpec(
        name="t", partition="cpu", nodes=1, cpus_per_task=2,
        memory_gb=1, walltime="00:05:00", environment={"FOO": "bar"},
    )
    props = _slurm_job_properties(spec, default_name="t")
    assert props["time_limit"] == 5
    assert props["memory_per_node"] == 1024
    assert props["nodes"] == "1"
    # environment는 배열이며 **비어 있으면 안 된다**(2019 I/O error)
    assert "FOO=bar" in props["environment"]
    assert any(e.startswith("PATH=") for e in props["environment"])


def test_environment_is_never_empty():
    from app.services.job import JobSpec, _slurm_job_properties

    props = _slurm_job_properties(JobSpec(name="t"), default_name="t")
    assert props["environment"], "빈 environment는 Slurm이 제출을 거부한다"


def test_user_script_gets_shebang_when_missing():
    """shebang이 없으면 sbatch가 배치 스크립트로 인정하지 않아 즉시 FAILED가 된다."""
    from app.services.job import JobService, JobSpec

    svc = JobService.__new__(JobService)
    built = svc.build_script(JobSpec(name="t", script="sleep 30", mode="script"))
    assert built.startswith("#!/bin/bash\n")
    # 이미 있으면 건드리지 않는다
    given = "#!/bin/zsh\nsleep 30\n"
    assert svc.build_script(JobSpec(name="t", script=given, mode="script")) == given


def test_work_dir_must_be_absolute_without_traversal(client, cluster, user_token):
    """화면이 홈 하위로 제한하지만 API 직접 호출도 막는다."""
    for bad in ("relative/path", "/home/jrpark/../opadmin", ".."):
        resp = client.post(
            f"/api/v1/clusters/{cluster.id}/jobs",
            json={"name": "t", "script": "sleep 1", "work_dir": bad},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 422, f"{bad} 가 통과했다"

    ok = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs",
        json={"name": "t", "script": "sleep 1", "work_dir": "/home/jrpark/work"},
        headers=auth_headers(user_token),
    )
    assert ok.status_code == 200


def test_job_options_survive_partial_slurmdbd_failure(client, cluster, user_token, slurm_client):
    """slurmdbd만 끊겨도 파티션은 골라야 한다 — 전부 실패로 처리하면 제출이 막힌다."""
    def boom(*a, **kw):
        raise RuntimeError("Connection refused")

    slurm_client.get_qos = boom
    slurm_client.get_associations = boom

    body = client.get(
        f"/api/v1/clusters/{cluster.id}/job-options", headers=auth_headers(user_token)
    ).json()
    assert body["partitions"] == ["debug"]
    assert body["accounts"] == [] and body["qos"] == []


def test_job_options_salvage_list_from_partial_500(client, cluster, user_token, slurm_client):
    """slurmrestd는 부분 실패도 500으로 준다 — 본문에 목록이 있으면 건져 쓴다(실측)."""
    from app.core.errors import ExternalServiceError

    def partial_failure(*a, **kw):
        raise ExternalServiceError(
            "외부 서비스 호출이 실패했습니다.",
            detail={"status": 500, "body": {"partitions": [{"name": "cpu"}], "errors": [{"error": "Connection refused"}]}},
        )

    slurm_client.get_partitions = partial_failure
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/job-options", headers=auth_headers(user_token)
    ).json()
    assert body["partitions"] == ["cpu"]


def test_history_falls_back_to_slurmctld_when_slurmdbd_is_down(
    client, cluster, user_token, slurm_client
):
    """slurmdbd가 끊겨도 최근 완료 Job은 보여준다 — 출처를 함께 알린다."""
    def boom(*a, **kw):
        raise RuntimeError("Connection refused")

    slurm_client.get_accounting_jobs = boom
    slurm_client.jobs = [
        {"job_id": 1, "name": "done", "user_name": "jrpark", "job_state": ["COMPLETED"]},
        {"job_id": 2, "name": "now", "user_name": "jrpark", "job_state": ["RUNNING"]},
    ]
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history", headers=auth_headers(user_token)
    ).json()
    assert body["source"] == "slurmctld"
    # 실행 중인 Job은 이력이 아니다
    assert [j["name"] for j in body["items"]] == ["done"]


def test_history_uses_slurmdbd_when_available(client, cluster, user_token, slurm_client):
    slurm_client.jobs = [{"job_id": 7, "name": "acct", "user_name": "jrpark",
                          "job_state": ["COMPLETED"]}]
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history", headers=auth_headers(user_token)
    ).json()
    assert body["source"] == "slurmdbd"


def test_validation_errors_use_the_standard_envelope(client, cluster, user_token):
    """검증 오류도 code·message를 갖는다 — 화면이 '[UNKNOWN]'만 띄우면 원인을 알 수 없다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs/preview-script",
        json={"name": "", "script": "sleep 1"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert "name" in body["message"]
    assert body["detail"][0]["field"].endswith("name")


def test_script_mode_keeps_user_body_untouched(client, cluster, user_token):
    """스크립트 모드는 사용자가 쓴 그대로 쓴다 — 임의로 지시자를 넣지 않는다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/jobs/preview-script",
        json={"name": "raw", "mode": "script", "partition": "cpu", "nodes": 4,
              "script": "#!/bin/bash\n#SBATCH --nodes=1\nsrun ./a.out"},
        headers=auth_headers(user_token),
    )
    script = resp.json()["script"]
    assert script == "#!/bin/bash\n#SBATCH --nodes=1\nsrun ./a.out"
    assert "--nodes=4" not in script


def test_admin_can_filter_history_by_user(client, cluster, admin_token, slurm_client):
    client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history?username=someone",
        headers=auth_headers(admin_token),
    )
    call = next(c for c in reversed(slurm_client.calls) if c[0] == "get_accounting_jobs")
    assert call[1]["users"] == "someone"


def test_user_cannot_widen_history_scope(client, cluster, user_token, slurm_client):
    """USER가 username을 넘겨도 무시되고 본인으로 강제된다."""
    client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history?username=opadmin",
        headers=auth_headers(user_token),
    )
    call = next(c for c in reversed(slurm_client.calls) if c[0] == "get_accounting_jobs")
    assert call[1]["users"] == "jrpark"


def test_history_state_filter_is_applied_locally(client, cluster, user_token, slurm_client):
    """slurmdbd의 state 필터는 이 빌드에서 0건만 돌려준다 — 서버로 넘기지 않고 직접 거른다."""
    slurm_client.jobs = [
        {"job_id": 1, "name": "ok", "user": "jrpark", "state": {"current": ["COMPLETED"]}},
        {"job_id": 2, "name": "bad", "user": "jrpark", "state": {"current": ["FAILED"]}},
    ]
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history?state=FAILED",
        headers=auth_headers(user_token),
    ).json()
    assert [j["name"] for j in body["items"]] == ["bad"]
    call = next(c for c in reversed(slurm_client.calls) if c[0] == "get_accounting_jobs")
    assert "state" not in call[1], "state를 slurmdbd로 넘기면 0건이 된다"


def test_account_choices_are_limited_to_own_associations(client, cluster, user_token):
    """소속되지 않은 계정을 고르면 Slurm이 제출을 거부한다 — 애초에 보여주지 않는다."""
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/job-options", headers=auth_headers(user_token)
    ).json()
    assert body["accounts"] == ["hpc"]  # 'other'(남의 연결)는 빠진다


def test_no_account_association_yields_empty_choices(client, cluster, user_token, slurm_client):
    """연결이 없으면 전체 계정으로 대체하지 않고 비운다."""
    slurm_client.get_associations = lambda *, as_user=None: {"associations": []}
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/job-options", headers=auth_headers(user_token)
    ).json()
    assert body["accounts"] == []


def test_history_always_sends_a_start_time(client, cluster, user_token, slurm_client):
    """slurmdbd는 start_time이 없으면 오늘 것만 준다 — 날짜가 바뀌면 이력이 사라진다(실측)."""
    from datetime import date, timedelta

    client.get(f"/api/v1/clusters/{cluster.id}/jobs/history", headers=auth_headers(user_token))
    call = next(c for c in reversed(slurm_client.calls) if c[0] == "get_accounting_jobs")
    assert call[1]["start_time"] == str(date.today() - timedelta(days=30))
    # 날짜만 보낸다 — `T00:00:00`을 붙이면 slurmrestd가 400을 낸다
    assert "T" not in call[1]["start_time"]


def test_history_period_is_overridable(client, cluster, user_token, slurm_client):
    from datetime import date, timedelta

    client.get(
        f"/api/v1/clusters/{cluster.id}/jobs/history?days=7", headers=auth_headers(user_token)
    )
    call = next(c for c in reversed(slurm_client.calls) if c[0] == "get_accounting_jobs")
    assert call[1]["start_time"] == str(date.today() - timedelta(days=7))
