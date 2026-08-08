"""Batch 앱 — 해석 solver 배치 제출 (U-JB-13).

`job_template`을 지운 이유를 반복하지 않기 위한 테스트들이다. 이미지·실행 커맨드·
파라미터가 **한 몸**이고, 준비되지 않은 앱은 **제출 전에** 막힌다.
"""

import pytest

from app.core.errors import ValidationFailed
from app.services import batch_apps as B
from tests.conftest import auth_headers

API = "/api/v1"


def _app(**kw):
    base = dict(
        id="demo",
        name="데모",
        description="테스트용",
        image="demo.sif",
        fid="U-JB-13",
        steps=(B.AppStep(run="solve -i {{input}} -n {{steps}}"),),
        params=(
            B.AppParam(key="input", label="입력", type="path"),
            B.AppParam(key="steps", label="스텝", type="number", default="10", required=False),
        ),
    )
    base.update(kw)
    return B.BatchApp(**base)


def _body(app, values, **kw):
    return B.build_body(app, "/i.sif", values, **kw)


# --- 카탈로그 --------------------------------------------------------------


def test_catalog_lists_upcoming_apps_too(client, user_token):
    """예정 앱을 숨기면 화면이 목록을 따로 갖게 되고 앞뒤가 갈린다."""
    body = client.get(f"{API}/batch-apps", headers=auth_headers(user_token)).json()
    foam = next(a for a in body if a["id"] == "openfoam")
    assert foam["ready"] is False  # 이미지가 아직 없다
    assert [p["key"] for p in foam["params"]] == ["case", "solver", "decompose", "reconstruct"]
    assert "simpleFoam" in next(p for p in foam["params"] if p["key"] == "solver")["options"]


def test_not_ready_app_is_blocked_before_submitting(client, cluster, user_token):
    """워커까지 간 뒤에 죽으면 사용자에게 원인이 안 보인다."""
    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/openfoam/jobs",
        json={"name": "run", "params": {"case": "/home/jrpark/motorbike"}},
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


# --- 값 검사 ---------------------------------------------------------------


def test_values_are_quoted_so_they_cannot_become_commands(client):
    """사용자는 **값만** 넣는다. 커맨드 틀은 카탈로그에 있다."""
    out = _body(_app(), {"input": "/h/a; rm -rf /", "steps": "1"})
    assert "; rm -rf /" in out  # 값으로는 남고
    assert "'/h/a; rm -rf /'" in out  # 따옴표 안에 갇힌다


def test_defaults_fill_in_optional_params(client):
    assert "-n 10" in _body(_app(), {"input": "/h/a"})


def test_required_param_without_default_is_rejected(client):
    with pytest.raises(ValidationFailed) as e:
        _body(_app(), {"steps": "1"})
    assert "입력" in e.value.message


def test_path_param_must_be_absolute_without_traversal(client):
    for bad in ("relative/x", "/home/../etc/shadow"):
        with pytest.raises(ValidationFailed):
            _body(_app(), {"input": bad})


def test_number_param_rejects_text(client):
    with pytest.raises(ValidationFailed):
        _body(_app(), {"input": "/h/a", "steps": "abc"})


def test_select_param_rejects_values_outside_the_list(client):
    app = _app(params=(B.AppParam(key="input", label="입력", type="select",
                                  options=("a", "b"), default="a"),),
               steps=(B.AppStep(run="run {{input}}"),))
    with pytest.raises(ValidationFailed):
        _body(app, {"input": "c"})


def test_catalog_mismatch_is_reported_not_shipped(client):
    """커맨드에 있는데 파라미터 목록에 없는 자리표시자 — **앱 정의의 버그**다."""
    broken = _app(steps=(B.AppStep(run="solve {{input}} {{nowhere}}"),))
    with pytest.raises(ValidationFailed) as e:
        _body(broken, {"input": "/h/a"})
    assert "nowhere" in e.value.message


def test_image_reference_needs_a_repository(client):
    with pytest.raises(ValidationFailed) as e:
        B.image_ref(None, _app())
    assert "이미지 저장소" in e.value.message
    assert B.image_ref("/home/images/", _app()) == "/home/images/demo.sif"


# --- 다단계 실행 -----------------------------------------------------------


def test_steps_can_be_switched_off_by_a_checkbox(client):
    """OpenFOAM은 이미 분해한 케이스를 다시 분해하면 안 된다."""
    app = _app(
        params=(B.AppParam(key="pre", label="전처리", type="bool", default="1", required=False),),
        steps=(B.AppStep(run="prepare", when="pre"), B.AppStep(run="solve")),
    )
    assert "prepare" in _body(app, {"pre": "1"})
    assert "prepare" not in _body(app, {"pre": "0"})
    assert "solve" in _body(app, {"pre": "0"})  # 조건 없는 단계는 남는다


def test_parallel_steps_go_through_srun_not_mpirun(client):
    """컨테이너 안에서 mpirun을 부르면 호스트 Slurm이 랭크를 모른다."""
    app = _app(steps=(B.AppStep(run="solve", parallel=True), B.AppStep(run="post")))
    lines = _body(app, {"input": "/h/a"}).splitlines()
    assert lines[1].startswith("srun apptainer exec ")
    assert lines[2].startswith("apptainer exec ")  # 병렬 아닌 단계는 srun 없이


def test_host_steps_run_outside_the_container(client):
    """`touch`처럼 호스트에서 해도 되는 일은 컨테이너를 띄우지 않는다."""
    app = _app(steps=(B.AppStep(run="touch {{input}}/case.foam", in_container=False),))
    # shlex.quote는 특수문자가 없으면 따옴표를 붙이지 않는다.
    assert _body(app, {"input": "/h/c"}) == "set -euo pipefail\ntouch /h/c/case.foam"


def test_ntasks_comes_from_resources_not_params(client):
    """MPI 랭크 수는 자원 칸의 값이 정본이다 — 앱은 참조만 한다."""
    app = _app(steps=(B.AppStep(run="check {{ntasks}}", in_container=False),))
    assert "check 64" in _body(app, {"input": "/h/a"}, ntasks=64)


def test_openfoam_guards_the_rank_mismatch(client):
    """decomposeParDict는 케이스 파일 안에 있어 화면에서 안 보인다 — 세어 보고 막는다."""
    body = B.build_body(
        B.get("openfoam"),
        "/i.sif",
        {"case": "/h/c", "solver": "simpleFoam", "decompose": "1", "reconstruct": "1"},
        ntasks=32,
    )
    assert "processor*" in body and "-ne 32" in body
    assert "numberOfSubdomains" in body  # 실패 사유를 스크립트가 직접 알려준다
    # ParaView가 열 수 있게 하는 표식 — 이게 없으면 "결과가 안 열린다"가 된다.
    assert body.rstrip().endswith("/case.foam")


def test_script_stops_at_the_first_failing_step(client):
    """앞 단계가 실패했는데 다음이 도는 것이 가장 나쁘다."""
    assert _body(_app(), {"input": "/h/a"}).startswith("set -euo pipefail\n")


# --- 제출 경로 -------------------------------------------------------------


def test_submitted_script_comes_from_the_catalog_not_the_request(
    client, db, cluster, user_token, slurm_client, monkeypatch
):
    """요청의 `script`를 무시하지 않으면 카탈로그를 두는 의미가 없다."""
    monkeypatch.setattr(B, "APPS", (_app(),))
    cluster.image_repository = "/home/images"
    db.commit()

    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/demo/jobs",
        json={
            "name": "run",
            "partition": "cpu",
            "ntasks": 16,
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
    assert "/home/images/demo.sif" in spec["script"]
    # 자원 입력은 Job 제출과 같은 경로를 탄다.
    assert spec["job"]["tasks"] == 16
    assert spec["job"]["array"] == "1-4"
    assert "#SBATCH --ntasks=16" in spec["script"]
