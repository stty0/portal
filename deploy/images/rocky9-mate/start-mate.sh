#!/bin/bash
# 전체 데스크톱(MATE) 세션. `start-desktop.sh`가 dbus 세션 안에서 이걸 부른다.
#
# 창 정책을 **명시적으로 MATE 기본값으로 되돌린다.** gsettings는 사용자 dconf(NFS 홈)에
# 영구 저장되므로, 예전 이미지에서 끈 최소화·닫기가 남아 있으면 데스크톱에서도 버튼이
# 사라진다. 여기는 mate-panel이 있어 최소화가 안전하다.
set -u

/opt/portal/reset-window-policy.sh

exec mate-session "$@"
