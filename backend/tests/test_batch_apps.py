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


def test_catalog_exposes_the_parameter_schema(client, user_token):
    """화면은 이 스키마로 폼을 그린다 — 필드를 화면이 갖고 있으면 앱마다 화면을 고쳐야 한다."""
    body = client.get(f"{API}/batch-apps", headers=auth_headers(user_token)).json()
    foam = next(a for a in body if a["id"] == "openfoam")
    keys = [p["key"] for p in foam["params"]]
    assert keys[:2] == ["case", "solver"]
    # 실측으로 정한 항목들 — 시간 제어와 격자·병렬 토글
    assert {"end_time", "write_interval", "block_mesh", "decompose", "reconstruct"} <= set(keys)
    assert "simpleFoam" in next(p for p in foam["params"] if p["key"] == "solver")["options"]


def test_not_ready_app_is_blocked_before_submitting(
    client, cluster, user_token, monkeypatch
):
    """워커까지 간 뒤에 죽으면 사용자에게 원인이 안 보인다.

    실제 앱의 `ready` 상태에 묶지 않는다 — 이미지가 준비되면 그때 테스트가 깨진다.
    """
    monkeypatch.setattr(B, "APPS", (_app(id="pending", image="", ready=False),))
    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/pending/jobs",
        json={"name": "run", "params": {"input": "/home/jrpark/a"}},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422
    assert "제공되지 않습니다" in resp.json()["message"]


def test_ready_app_resolves_its_image_from_the_repository(client):
    """준비된 앱은 클러스터 저장소 아래에서 이미지를 찾는다."""
    foam = B.get("openfoam")
    assert foam.ready and foam.image
    assert B.image_ref("/home/portal/images", foam) == "/home/portal/images/openfoam-2512.sif"


def test_isaac_sim_is_listed_as_a_gpu_app_that_is_not_ready_yet(client, user_token):
    """이미지도 GPU 노드도 없다 — 목록에는 보이되 고를 수 없어야 한다."""
    body = client.get(f"{API}/batch-apps", headers=auth_headers(user_token)).json()
    isaac = next(a for a in body if a["id"] == "isaac-sim")
    assert isaac["needs_gpu"] is True
    assert isaac["ready"] is False
    assert [p["key"] for p in isaac["params"]] == ["script", "config"]


def test_isaac_sim_command_carries_gpu_flag_and_eula(client):
    """`--nv`(GPU)와 `ACCEPT_EULA`가 빠지면 Kit이 시작조차 하지 않는다."""
    isaac = B.get("isaac-sim")
    out = _body(isaac, {"script": "/home/u/sdg.py"})
    assert "apptainer exec --nv " in out
    assert "--env ACCEPT_EULA=Y" in out
    assert "--env PRIVACY_CONSENT=Y" in out
    assert "/isaac-sim/python.sh -u /home/u/sdg.py" in out
    # 설정 파일을 안 줬으면 `--config`가 빈 채로 실리면 안 된다.
    assert "--config" not in out


def test_isaac_sim_passes_the_config_file_when_given(client):
    out = _body(B.get("isaac-sim"), {"script": "/home/u/sdg.py", "config": "/home/u/c.yaml"})
    assert "-u /home/u/sdg.py --config /home/u/c.yaml" in out


def test_only_gpu_apps_get_the_nv_flag(client):
    """CPU 앱에 `--nv`가 붙으면 GPU 없는 노드에서 apptainer가 실패한다."""
    assert "--nv" not in _body(_app(), {"input": "/h/a"})
    assert "--env" not in _body(_app(), {"input": "/h/a"})


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


def test_openfoam_sets_the_subdomain_count_instead_of_failing_on_it(client):
    """**실측**: 튜토리얼 케이스에 `decomposeParDict`가 없는 경우가 흔하다(pitzDaily).

    예전에는 개수가 다르면 멈추게 했는데, 그러면 평범한 케이스에서 바로 실패한다.
    없으면 만들고 랭크 수에 맞춘다. `scotch`는 계수 없이 임의 개수를 분해한다.
    """
    body = B.build_body(
        B.get("openfoam"), "/i.sif",
        {"case": "/h/c", "solver": "simpleFoam", "decompose": "1", "reconstruct": "1"},
        ntasks=32,
    )
    assert "decomposeParDict" in body and "numberOfSubdomains -set 32" in body
    assert "method -set scotch" in body
    assert 'if [ ! -f "$D" ]' in body  # 없을 때만 만든다 — 있으면 케이스 것을 존중
    # ParaView가 열 수 있게 하는 표식이 마지막이다.
    assert body.rstrip().endswith("/case.foam")


def test_openfoam_runs_serially_when_decomposition_is_off(client):
    """`-parallel`을 랭크 1개로 주면 실패한다 — 갈래를 나눈다."""
    values = {"case": "/h/c", "solver": "icoFoam", "decompose": "0"}
    body = B.build_body(B.get("openfoam"), "/i.sif", values, ntasks=1)
    assert "-parallel" not in body
    assert "srun " not in body
    assert "decomposePar" not in body
    assert "icoFoam -case /h/c" in body


def test_time_controls_are_injected_into_the_case(client):
    """**실측**: `writeInterval > endTime`이면 결과가 하나도 안 나오고 재조합이 실패한다.

    그래서 케이스 파일을 `foamDictionary`로 직접 고친다. 빈 값은 단계 자체가 빠져
    케이스 설정을 그대로 둔다.
    """
    app = B.get("openfoam")
    full = B.build_body(app, "/i.sif",
                        {"case": "/h/c", "solver": "simpleFoam", "decompose": "0",
                         "end_time": "500", "delta_t": "0.01", "write_interval": "50"},
                        ntasks=1)
    assert "controlDict -entry endTime -set 500" in full
    assert "controlDict -entry deltaT -set 0.01" in full
    assert "controlDict -entry writeInterval -set 50" in full

    bare = B.build_body(app, "/i.sif",
                        {"case": "/h/c", "solver": "simpleFoam", "decompose": "0"}, ntasks=1)
    assert "controlDict" not in bare  # 비우면 케이스 설정을 건드리지 않는다


def test_restart_only_when_asked(client):
    app = B.get("openfoam")
    on = B.build_body(app, "/i.sif",
                      {"case": "/h/c", "solver": "simpleFoam", "decompose": "0", "restart": "1"},
                      ntasks=1)
    assert "startFrom -set latestTime" in on
    off = B.build_body(app, "/i.sif",
                       {"case": "/h/c", "solver": "simpleFoam", "decompose": "0"}, ntasks=1)
    assert "startFrom" not in off


def test_mesh_steps_are_optional(client):
    app = B.get("openfoam")
    with_mesh = B.build_body(app, "/i.sif",
                             {"case": "/h/c", "solver": "simpleFoam", "decompose": "0",
                              "block_mesh": "1", "check_mesh": "1"}, ntasks=1)
    assert "blockMesh" in with_mesh and "checkMesh" in with_mesh
    without = B.build_body(app, "/i.sif",
                           {"case": "/h/c", "solver": "simpleFoam", "decompose": "0",
                            "block_mesh": "0", "check_mesh": "0"}, ntasks=1)
    assert "blockMesh" not in without and "checkMesh" not in without


def test_generated_script_has_no_stray_newlines(client):
    """단계 하나가 여러 줄로 깨지면 `set -e`가 뒷줄을 별도 명령으로 실행한다.

    실제로 `printf "\\n"` 판본이 이스케이프를 한 겹 잃어 스크립트를 깨뜨렸다.
    """
    body = B.build_body(
        B.get("openfoam"), "/i.sif",
        {"case": "/h/c", "solver": "simpleFoam", "block_mesh": "1", "check_mesh": "1",
         "end_time": "50", "write_interval": "25", "decompose": "1", "reconstruct": "1"},
        ntasks=2,
    )
    lines = body.splitlines()
    assert len(lines) == 10, lines
    # 컨테이너 단계는 한 줄에 하나씩 완결되어야 한다.
    assert sum(1 for l in lines if l.startswith("apptainer exec ")) == 6
    assert sum(1 for l in lines if l.startswith("srun apptainer exec ")) == 1


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
