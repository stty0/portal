#!/bin/bash
# 단일 앱(ParaView) 세션. `start-desktop.sh`가 dbus 세션 안에서 이걸 부른다.
#
# 창 버튼(최소화·최대화·닫기)은 **전부 정상 동작한다.** 한때 최소화·닫기를 막았지만
# `File → Exit`는 어차피 막을 수 없었고, 막는 것보다 **되살릴 수단을 주는 것**이 맞다.
# 최소화 복구는 아래 작업표시줄(tint2)이 맡는다.
#
# 앱을 닫으면 이 스크립트가 끝나고 세션(Slurm Job)도 함께 해제된다 — 의도한 동작이다.
set -u

# 지난 세션이 dconf(NFS 홈)에 남긴 창 정책을 MATE 기본값으로 되돌린다.
/opt/portal/reset-window-policy.sh

# 창 관리자가 없으면 대화상자를 옮기거나 닫을 수 없어 파일 열기 창 하나에 갇힌다.
marco &
sleep 1

# 작업표시줄. **ParaView보다 먼저 띄운다** — strut이 먼저 잡혀야 아래 최대화가
# 막대를 비켜 간다.
tint2 -c /opt/portal/tint2rc &
sleep 1

# 처음부터 화면(=VNC 해상도) 전체를 쓰게 한다.
# ParaView는 지난 세션의 창 크기를 자기 설정에 저장해 두었다가 그대로 복원한다.
# 그 크기가 지금 해상도보다 작으면 창이 화면 한 구석에만 뜬다 — 뜬 뒤에 최대화한다.
#
# 스플래시 화면이 먼저 뜨므로 **제목이 붙은 일반 창**을 기다리고, 클래스로 걸러
# 작업표시줄(tint2) 자체를 최대화하는 사고를 막는다. `-lx`의 $3이 클래스, $5부터가 제목이다.
maximize_main_window() {
    local id
    for _ in $(seq 1 60); do
        id="$(wmctrl -lx 2>/dev/null | awk 'tolower($3) ~ /paraview/ && $5 != "" { print $1; exit }')"
        if [ -n "$id" ]; then
            wmctrl -i -r "$id" -b add,maximized_vert,maximized_horz 2>/dev/null
            return 0
        fi
        sleep 1
    done
    echo "ParaView 창을 찾지 못해 최대화를 건너뜁니다" >&2
}
maximize_main_window &

# exec으로 대체한다 — 이 스크립트가 앱의 수명 그 자체가 된다.
# (정리 trap은 바깥 start-desktop.sh가 갖고 있다)
exec paraview "$@"
