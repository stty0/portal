"""세션 Job 스크립트 생성 (T-02, U-IA-02)."""

import pytest

from app.core.errors import ValidationFailed
from app.services.session_script import (
    SessionSpec,
    build_session_script,
    log_path,
    session_dir,
)

IMAGE = "/home/portal/images/rocky9-mate-1.0.sif"


def spec(**kw) -> SessionSpec:
    return SessionSpec(image_ref=IMAGE, **kw)


def test_script_runs_the_container_entrypoint():
    script = build_session_script(spec())
    assert script.startswith("#!/bin/bash")
    assert "apptainer exec --writable-tmpfs" in script
    assert IMAGE in script
    assert "/opt/portal/start-desktop.sh" in script


def test_form_values_become_sbatch_directives():
    script = build_session_script(
        spec(partition="cpu", account="root", qos="normal", cpus=2, memory_gb=3, walltime="02:00:00")
    )
    for line in (
        "#SBATCH --job-name=portal-desktop",
        "#SBATCH --partition=cpu",
        "#SBATCH --account=root",
        "#SBATCH --qos=normal",
        "#SBATCH --cpus-per-task=2",
        "#SBATCH --mem=3G",
        "#SBATCH --time=02:00:00",
    ):
        assert line in script


def test_exclusive_is_opt_in():
    assert "#SBATCH --exclusive" not in build_session_script(spec())
    assert "#SBATCH --exclusive" in build_session_script(spec(exclusive=True))


def test_session_dir_is_under_the_home_on_shared_storage():
    # 워커가 쓰고 로그인 노드가 읽으므로 홈(공유 NFS) 아래여야 한다.
    script = build_session_script(spec())
    assert '"$HOME/.portal/sessions/$SLURM_JOB_ID"' in script
    assert 'chmod 700 "$SESSION_DIR"' in script


def test_job_script_removes_connection_info_on_exit():
    # apptainer가 별도 프로세스 그룹을 만들어 scancel 신호가 컨테이너 안까지 닿지
    # 않는다(실측). 정리는 Slurm이 직접 신호를 주는 이 스크립트가 책임진다.
    script = build_session_script(spec())
    assert 'rm -f "$SESSION_DIR/connection.json"' in script
    assert "trap cleanup EXIT TERM INT" in script
    # exec으로 셸을 대체하면 trap이 사라진다.
    assert "exec apptainer" not in script
    assert 'wait "$APPTAINER_PID"' in script


def test_sssd_bind_is_conditional():
    # SSSD가 없는 호스트에서도 세션이 떠야 한다.
    script = build_session_script(spec())
    assert "if [ -d /var/lib/sss/pipes ]" in script
    assert "--bind /var/lib/sss/pipes" in script


def test_apptainer_tmpdir_moves_off_the_root_filesystem():
    # 노드 루트는 여유가 적다(실측 12GB). 이미지 전개가 여기서 터지면 세션이 죽는다.
    script = build_session_script(spec())
    assert 'export APPTAINER_TMPDIR="$HOME/.apptainer/tmp"' in script


def test_geometry_is_validated():
    with pytest.raises(ValidationFailed):
        build_session_script(spec(geometry="1920x1080; rm -rf /"))
    with pytest.raises(ValidationFailed):
        build_session_script(spec(geometry="huge"))


def test_app_name_is_validated():
    with pytest.raises(ValidationFailed):
        build_session_script(spec(app="desktop; whoami"))


def test_image_ref_is_required():
    with pytest.raises(ValidationFailed):
        build_session_script(SessionSpec(image_ref=""))


def test_image_ref_accepts_registry_urls():
    # 개발은 SIF 경로, 나중에 레지스트리로 전환한다(설정값 하나만 바뀐다).
    for ref in (
        "/home/portal/images/rocky9-mate-1.0.sif",
        "oras://reg.example.com/hpc/rocky9-mate:1.0",
        "docker://reg.example.com/hpc/rocky9-mate:1.0",
    ):
        assert ref in build_session_script(SessionSpec(image_ref=ref))


def test_paths_share_one_layout():
    # 스크립트가 쓰는 경로와 포털이 읽는 경로가 어긋나면 세션이 영원히 "준비 중"이 된다.
    assert session_dir("/home/u", 42) == "/home/u/.portal/sessions/42"
    assert session_dir("/home/u/", "42") == "/home/u/.portal/sessions/42"
    assert log_path("/home/u") == "/home/u/.portal/logs/%j.log"
    assert SessionSpec(image_ref=IMAGE).geometry == "1920x1080"


def test_script_recovers_home_when_the_environment_is_replaced():
    """slurmrestd 제출은 environment를 통째로 교체한다 — HOME이 비면 set -u에서 즉사한다.

    수동 sbatch는 사용자 환경을 물려받아 이 차이가 드러나지 않는다(실측: FAILED 1:0).
    """
    script = build_session_script(spec())
    assert ': "${HOME:=$(getent passwd "$(id -un)" | cut -d: -f6)}"' in script
    assert "export HOME" in script
    # Slurm이 넣어주는 변수도 없을 수 있다고 보고 방어한다.
    assert "${SLURMD_NODENAME:-?}" in script


def test_app_selection_reaches_the_container():
    """같은 이미지에서 `PORTAL_APP`으로 앱이 갈린다 — 이 값이 안 넘어가면 늘 데스크톱이 뜬다."""
    assert "export PORTAL_APP=desktop" in build_session_script(spec())
    assert "export PORTAL_APP=paraview" in build_session_script(spec(app="paraview"))
    # Job 이름도 앱을 따라가야 squeue에서 구분된다.
    assert "#SBATCH --job-name=portal-paraview" in build_session_script(spec(app="paraview"))
