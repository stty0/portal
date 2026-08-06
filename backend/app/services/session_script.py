"""인터랙티브 세션 Job 스크립트 생성 (U-IA-02).

컨테이너를 **워커 노드에서** 띄우는 배치 스크립트를 만든다. 컨테이너 안에서 도는
기동 스크립트는 `deploy/images/rocky9-mate/start-desktop.sh`이고, 여기서 만드는 것은
그것을 감싸 실행하는 호스트 쪽 스크립트다.

주의: slurmrestd 제출에서 `#SBATCH`는 **적용되지 않는다**(JobService와 같은 실측).
자원 적용은 REST 페이로드가 담당하고, 지시자는 스크립트를 그대로 `sbatch`로 재실행하거나
내용을 확인할 수 있게 남기는 기록이다.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from app.core.errors import ValidationFailed

# 세션 산출물은 사용자 홈 아래에 둔다. 워커가 쓰고 로그인 노드가 읽어야 하므로
# **공유 파일시스템이어야 한다**(docs/plan.md §4 전제조건).
SESSION_SUBDIR = ".portal/sessions"
LOG_SUBDIR = ".portal/logs"

# 컨테이너 안의 기동 스크립트 (deploy/images/rocky9-mate/)
CONTAINER_ENTRY = "/opt/portal/start-desktop.sh"

# 호스트의 SSSD 소켓. 바인드하면 컨테이너에서 다른 AD 사용자 이름이 풀린다.
# 소켓이 srw-rw-rw- 라 추가 권한이 필요 없다.
SSSD_PIPES = "/var/lib/sss/pipes"

_GEOMETRY_RE = re.compile(r"^\d{3,5}x\d{3,5}$")
_APP_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class SessionSpec:
    """인터랙티브 세션 제출 파라미터 (U-IA-01 폼)."""

    image_ref: str
    app: str = "desktop"
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    cpus: int | None = None
    memory_gb: int | None = None
    walltime: str | None = None
    geometry: str = "1920x1080"
    exclusive: bool = False


def session_dir(home: str, job_id: str | int) -> str:
    """세션 디렉터리 절대 경로. 스크립트와 조회 쪽이 **같은 규칙**을 써야 한다."""
    return f"{home.rstrip('/')}/{SESSION_SUBDIR}/{job_id}"


def log_dir(home: str) -> str:
    return f"{home.rstrip('/')}/{LOG_SUBDIR}"


def log_path(home: str) -> str:
    """Slurm이 여는 로그 경로. `%j`는 Slurm이 Job ID로 치환한다.

    Slurm은 로그 파일을 만들 뿐 **상위 디렉터리는 만들지 않는다** — 제출 전에
    `log_dir()`를 만들어 두어야 한다.
    """
    return f"{log_dir(home)}/%j.log"


def build_session_script(spec: SessionSpec) -> str:
    """세션 Job의 배치 스크립트.

    스크립트에 값을 끼워 넣으므로 **전부 검증하고 인용한다** — 이미지 참조는 관리자
    설정값이고 해상도는 사용자 입력이다.
    """
    if not spec.image_ref:
        raise ValidationFailed(
            "클러스터에 데스크톱 이미지가 설정되어 있지 않습니다.",
            detail={"field": "desktop_image_ref"},
        )
    if not _GEOMETRY_RE.match(spec.geometry):
        raise ValidationFailed(
            "해상도 형식이 올바르지 않습니다(예: 1920x1080).",
            detail={"geometry": spec.geometry},
        )
    if not _APP_RE.match(spec.app):
        raise ValidationFailed("앱 이름이 올바르지 않습니다.", detail={"app": spec.app})

    directives = ["#!/bin/bash"]
    for flag, value in (
        ("--job-name", f"portal-{spec.app}"),
        ("--partition", spec.partition),
        ("--account", spec.account),
        ("--qos", spec.qos),
        ("--cpus-per-task", spec.cpus),
        ("--mem", f"{spec.memory_gb}G" if spec.memory_gb else None),
        ("--time", spec.walltime),
    ):
        if value not in (None, ""):
            directives.append(f"#SBATCH {flag}={value}")
    if spec.exclusive:
        directives.append("#SBATCH --exclusive")

    image = shlex.quote(spec.image_ref)
    geometry = shlex.quote(spec.geometry)
    app = shlex.quote(spec.app)
    entry = shlex.quote(CONTAINER_ENTRY)
    pipes = shlex.quote(SSSD_PIPES)

    body = f"""
set -euo pipefail

# slurmrestd 제출은 environment를 **통째로 교체**한다 — 수동 sbatch와 달리 HOME이
# 비어 있을 수 있고, set -u 아래에서는 그 즉시 Job이 죽는다(실측: FAILED 1:0).
# 제출 쪽에서도 HOME을 넣지만 여기서 한 번 더 방어한다.
: "${{HOME:=$(getent passwd "$(id -un)" | cut -d: -f6)}}"
export HOME

# 세션 디렉터리는 홈 아래(공유 NFS)에 둔다 — 워커가 쓰고 로그인 노드가 읽는다.
SESSION_DIR="$HOME/{SESSION_SUBDIR}/$SLURM_JOB_ID"
mkdir -p "$SESSION_DIR"
chmod 700 "$SESSION_DIR"

# Job이 끝나면 접속 정보를 지운다 — 남겨두면 죽은 세션에 붙으려 한다.
# 컨테이너 안에도 같은 정리가 있지만 **거기에만 두면 안 된다**: apptainer가 별도
# 프로세스 그룹을 만들어 scancel의 SIGTERM이 컨테이너 안까지 닿지 않는다(실측).
# 이 스크립트는 Slurm이 직접 신호를 주는 대상이라 확실하게 실행된다.
cleanup() {{ rm -f "$SESSION_DIR/connection.json"; }}
trap cleanup EXIT TERM INT

# 노드 루트 파일시스템은 여유가 적다. apptainer 임시/캐시를 홈으로 돌린다.
export APPTAINER_TMPDIR="$HOME/.apptainer/tmp"
export APPTAINER_CACHEDIR="$HOME/.apptainer/cache"
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"

export PORTAL_SESSION_DIR="$SESSION_DIR"
export PORTAL_GEOMETRY={geometry}
export PORTAL_APP={app}

# AD 이름 해석용. SSSD가 없는 호스트도 있으므로 있을 때만 붙인다.
BINDS=()
if [ -d {pipes} ]; then
    BINDS+=(--bind {pipes})
fi

echo "세션 시작: node=${{SLURMD_NODENAME:-?}} job=$SLURM_JOB_ID dir=$SESSION_DIR"

# --writable-tmpfs: MATE·dbus가 /etc/machine-id, /var/run에 쓴다.
# exec을 쓰지 않는다 — 셸이 대체되면 위의 cleanup trap이 사라진다.
apptainer exec --writable-tmpfs "${{BINDS[@]}}" {image} {entry} &
APPTAINER_PID=$!
wait "$APPTAINER_PID" || true
"""
    return "\n".join(directives) + "\n" + body.lstrip("\n")
