#!/bin/bash
# 창 정책을 MATE 기본값으로 되돌린다. 앱 스크립트가 dbus 세션 안에서 부른다.
#
# **설정을 빼는 것만으로는 원복이 안 된다.** gsettings는 사용자 dconf(NFS 홈)에 영구
# 저장되므로, 최소화·닫기를 막았던 이미지(1.2/1.3)를 써 본 사용자의 홈에는 그 값이
# 그대로 남아 있다. 명시적으로 기본값을 다시 써야 한다.
#
# 두 앱(start-mate.sh / start-paraview.sh)이 같은 값을 쓰므로 한 파일로 모았다 —
# 갈라지면 한쪽만 고쳐지는 버그가 난다.
set -u

gsettings set org.mate.Marco.general button-layout "menu:minimize,maximize,close" 2>/dev/null || true
gsettings set org.mate.Marco.window-keybindings minimize "<Alt>F9" 2>/dev/null || true
gsettings set org.mate.Marco.window-keybindings close "<Alt>F4" 2>/dev/null || true
gsettings set org.mate.Marco.general action-right-click-titlebar "menu" 2>/dev/null || true
