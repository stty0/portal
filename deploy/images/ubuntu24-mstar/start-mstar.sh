#!/bin/bash
# 단일 앱(M-Star CFD) 세션. `start-desktop.sh`가 dbus 세션 안에서 이걸 부른다.
#
# rocky9-mate의 `start-paraview.sh`와 같은 모양이다 — 창 관리자 → 작업표시줄 → 앱,
# 그리고 뜬 뒤 최대화. 다른 점은 벤더 스크립트(`mstar.sh`)를 source해서 PATH와
# LD_LIBRARY_PATH를 만든다는 것뿐이다.
#
# 앱을 닫으면 이 스크립트가 끝나고 세션(Slurm Job)도 함께 해제된다 — 의도한 동작이다.
set -u

MSTAR_HOME="${MSTAR_HOME:-/opt/mstar}"

# 지난 세션이 dconf(NFS 홈)에 남긴 창 정책을 MATE 기본값으로 되돌린다.
/opt/portal/reset-window-policy.sh

# 창 관리자가 없으면 대화상자를 옮기거나 닫을 수 없어 파일 열기 창 하나에 갇힌다.
marco &
sleep 1

# 작업표시줄. **M-Star보다 먼저 띄운다** — strut이 먼저 잡혀야 아래 최대화가 막대를 비켜 간다.
tint2 -c /opt/portal/tint2rc &
sleep 1

# --- 소프트웨어 렌더링 ------------------------------------------------
# **이 노드에는 GPU가 없다.** M-Star의 3D 뷰포트는 OpenCASCADE(`libTKOpenGl`)가 그리고
# 그것이 `libGL.so.1`을 부르는데, DRI 디바이스가 없으면 드라이버 탐색에 실패해 창이
# 검게 뜨거나 죽는다. llvmpipe(소프트웨어 래스터라이저)를 **명시적으로** 고른다.
#
# `LIBGL_ALWAYS_SOFTWARE`만으로 충분한 경우가 많지만, Mesa 24는 `GALLIUM_DRIVER`를
# 함께 봐야 확실히 llvmpipe로 간다.
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
# 소프트웨어 렌더링에서 OpenCASCADE가 코어 프로파일을 요구하면 컨텍스트 생성이 실패한다.
# Mesa가 광고하는 최대 호환 프로파일 버전을 올려 그 경로를 피한다.
export MESA_GL_VERSION_OVERRIDE="${MESA_GL_VERSION_OVERRIDE:-3.3}"

# --- 벤더 환경 --------------------------------------------------------
# `mstar.sh`는 자기 위치(`$DIR`)에서 PATH·LD_LIBRARY_PATH·MSTARPOST_*를 만든다.
# set -u 아래에서 비어 있는 LD_LIBRARY_PATH를 참조하므로 미리 정의해 둔다.
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export PATH="${PATH:-/usr/local/bin:/usr/bin:/bin}"
# shellcheck source=/dev/null
source "$MSTAR_HOME/mstar.sh"

# M-Star는 설정·라이선스를 홈(NFS)에 쓴다. 홈이 없으면 조용히 죽으므로 먼저 확인한다.
if [ ! -w "$HOME" ]; then
    echo "홈 디렉터리에 쓸 수 없습니다: $HOME — M-Star가 설정을 저장하지 못합니다" >&2
fi

# 처음부터 화면(=VNC 해상도) 전체를 쓰게 한다. 스플래시가 먼저 뜨므로 **제목이 붙은
# 일반 창**을 기다리고, 클래스로 걸러 작업표시줄(tint2)을 최대화하는 사고를 막는다.
# `-lx`의 $3이 클래스, $5부터가 제목이다.
maximize_main_window() {
    local id
    for _ in $(seq 1 90); do
        id="$(wmctrl -lx 2>/dev/null | awk 'tolower($3) ~ /mstar|m-star/ && $5 != "" { print $1; exit }')"
        if [ -n "$id" ]; then
            wmctrl -i -r "$id" -b add,maximized_vert,maximized_horz 2>/dev/null
            return 0
        fi
        sleep 1
    done
    echo "M-Star 창을 찾지 못해 최대화를 건너뜁니다" >&2
}
maximize_main_window &

# exec으로 대체한다 — 이 스크립트가 앱의 수명 그 자체가 된다.
# (정리 trap은 바깥 start-desktop.sh가 갖고 있다)
exec "$MSTAR_HOME/bin/mstar" "$@"
