"""Batch 앱 — 해석 solver 배치 제출 (U-JB-13).

`job_template`을 지운 이유를 반복하지 않기 위한 테스트들이다. 이미지·커맨드·파라미터가
**한 몸**이고, 준비되지 않은 앱은 **제출 전에** 막힌다.
"""

import pytest

from app.core.errors import ValidationFailed
from app.services import batch_apps
from tests.conftest import auth_headers

API = "/api/v1"


def _app(**kw):
    base = dict(
        id="demo",
        name="데모",
        description="테스트용",
        image="demo.sif",
        fid="U-JB-13",
        command="solve -i {{input}} -n {{steps}}",
        params=(
            batch_apps.AppParam(key="input", label="입력", type="path"),
            batch_apps.AppParam(key="steps", label="스텝", type="number", default="10",
                                required=False),
        ),
    )
    base.update(kw)
    return batch_apps.BatchApp(**base)


# --- 카탈로그 --------------------------------------------------------------


def test_catalog_lists_upcoming_apps_too(client, user_token):
    """예정 앱을 숨기면 화면이 목록을 따로 갖게 되고 앞뒤가 갈린다."""
    body = client.get(f"{API}/batch-apps", headers=auth_headers(user_token)).json()
    assert body, "카탈로그가 비어 있으면 화면이 만들 게 없다"
    gromacs = next(a for a in body if a["id"] == "gromacs")
    assert gromacs["ready"] is False  # 이미지가 아직 없다
    assert [p["key"] for p in gromacs["params"]] == ["tpr", "prefix", "nsteps"]


def test_not_ready_app_is_blocked_before_submitting(client, cluster, user_token):
    """워커까지 간 뒤에 죽으면 사용자에게 원인이 안 보인다."""
    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/gromacs/jobs",
        json={"name": "md", "params": {"tpr": "/home/jrpark/a.tpr"}},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422
    assert "제공되지 않습니다" in resp.json()["message"]


def test_unknown_app_is_rejected(client, cluster, user_token):
    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/nope/jobs",
        json={"name": "x"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


# --- 커맨드 생성 -----------------------------------------------------------


def test_values_are_quoted_so_they_cannot_become_commands(client):
    """사용자는 **값만** 넣는다. 커맨드 틀은 카탈로그에 있다."""
    out = batch_apps.render_command(_app(), {"input": "/h/a.tpr; rm -rf /", "steps": "1"})
    assert "; rm -rf /" in out  # 값으로 남는다
    assert out.startswith("solve -i '/h/a.tpr; rm -rf /'")  # 따옴표 안에


def test_defaults_fill_in_optional_params(client):
    assert batch_apps.render_command(_app(), {"input": "/h/a"}).endswith("-n 10")


def test_required_param_without_default_is_rejected(client):
    with pytest.raises(ValidationFailed) as e:
        batch_apps.render_command(_app(), {"steps": "1"})
    assert "입력" in e.value.message


def test_path_param_must_be_absolute_without_traversal(client):
    for bad in ("relative/x", "/home/../etc/shadow"):
        with pytest.raises(ValidationFailed):
            batch_apps.render_command(_app(), {"input": bad})


def test_number_param_rejects_text(client):
    with pytest.raises(ValidationFailed):
        batch_apps.render_command(_app(), {"input": "/h/a", "steps": "abc"})


def test_catalog_mismatch_is_reported_not_shipped(client):
    """커맨드에 있는데 파라미터 목록에 없는 자리표시자 — **앱 정의의 버그**다.

    그대로 나가면 워커에서 `{{missing}}`이 인자로 들어가 조용히 이상하게 돈다.
    """
    broken = _app(command="solve {{input}} {{nowhere}}")
    with pytest.raises(ValidationFailed) as e:
        batch_apps.render_command(broken, {"input": "/h/a"})
    assert "nowhere" in e.value.message


def test_gpu_apps_get_the_nv_flag(client):
    assert batch_apps.build_body(_app(needs_gpu=True), "/i.sif", {"input": "/h/a"}).startswith(
        "apptainer exec --nv "
    )
    assert "--nv" not in batch_apps.build_body(_app(), "/i.sif", {"input": "/h/a"})


def test_image_reference_needs_a_repository(client):
    with pytest.raises(ValidationFailed) as e:
        batch_apps.image_ref(None, _app())
    assert "이미지 저장소" in e.value.message
    assert batch_apps.image_ref("/home/images/", _app()) == "/home/images/demo.sif"


# --- 제출 경로 -------------------------------------------------------------


def test_submitted_script_comes_from_the_catalog_not_the_request(
    client, db, cluster, user_token, slurm_client, monkeypatch
):
    """요청의 `script`를 무시하지 않으면 카탈로그를 두는 의미가 없다."""
    monkeypatch.setattr(batch_apps, "APPS", (_app(),))
    cluster.image_repository = "/home/images"
    db.commit()

    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/demo/jobs",
        json={
            "name": "run",
            "partition": "cpu",
            "gpus": 2,
            "array": "1-4",
            "params": {"input": "/home/jrpark/a.tpr", "steps": "7"},
            "script": "rm -rf /",  # ← 무시되어야 한다
            "mode": "script",  # ← 무시되어야 한다
        },
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200, resp.text

    spec = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]
    assert "rm -rf /" not in spec["script"]
    assert "apptainer exec /home/images/demo.sif solve -i /home/jrpark/a.tpr -n 7" in spec["script"]
    # 자원 입력은 Job 제출과 같은 경로를 탄다.
    assert spec["job"]["tres_per_node"] == "gres:gpu:2"
    assert spec["job"]["array"] == "1-4"
    # 폼 모드이므로 #SBATCH 지시자도 함께 적힌다(그대로 sbatch 재실행 가능).
    assert "#SBATCH --partition=cpu" in spec["script"]
