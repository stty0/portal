# 원격 데스크톱 세션 이미지 (U-IA-02).
#
# Apptainer SIF로 변환해 워커 노드에서 실행한다. **컨테이너는 rootless로 돌고
# 파일시스템은 read-only**이므로 쓰기가 필요한 경로는 --writable-tmpfs 또는 세션
# 디렉터리 bind로 처리한다.
#
# websockify·noVNC는 넣지 않는다 — WebSocket↔TCP 변환은 포털 백엔드가 한다
# (docs/plan.md §3.3). 컨테이너는 Xvnc와 GUI 세션만 제공한다.
#
# **이미지는 하나다.** 앱 구분은 `PORTAL_APP` 환경변수로 하고 기동 스크립트가 분기한다.
# 클러스터 설정의 이미지 참조(`desktop_image_ref`)가 필드 하나라 이쪽이 운영이 단순하다.
FROM rockylinux/rockylinux:9

# MATE는 EPEL에만 있고, **EPEL9에는 "MATE Desktop" 그룹이 없다**(Xfce만 있음).
# 그래서 세션 구성 패키지를 직접 나열한다.
RUN dnf -y install epel-release \
 && dnf -y update \
 && dnf -y install \
      mate-session-manager \
      marco \
      mate-panel \
      mate-settings-daemon \
      mate-control-center \
      mate-notification-daemon \
      mate-polkit \
      mate-menus \
      mate-themes \
      mate-icon-theme \
      mate-backgrounds \
      caja \
      mate-terminal \
      tigervnc-server \
      dbus-x11 \
      sssd-client \
      xorg-x11-xauth \
      xorg-x11-fonts-Type1 \
      xorg-x11-fonts-misc \
      mesa-dri-drivers \
      glx-utils \
      xterm \
      wmctrl \
      tint2 \
      procps-ng \
      iproute \
      hostname \
      which \
 && dnf clean all \
 && rm -rf /var/cache/dnf

# ParaView (U-IA-06). EPEL9에 5.11.1이 있어 별도 다운로드가 필요 없다.
# 의존성 python3-pygments가 **CRB(CodeReady Builder)** 저장소에 있어 먼저 켜야 한다.
# GPU가 없으면 Mesa llvmpipe 소프트웨어 렌더링으로 떨어진다 — 동작하지만 느리다.
RUN dnf -y install "dnf-command(config-manager)" \
 && dnf config-manager --set-enabled crb \
 && dnf -y install paraview \
 && dnf clean all \
 && rm -rf /var/cache/dnf

# 스크린세이버/잠금은 컨테이너 세션에서 의미가 없고, 잠기면 되살릴 방법이 없다.
RUN rm -f /etc/xdg/autostart/mate-screensaver.desktop \
          /etc/xdg/autostart/blueman.desktop \
          /etc/xdg/autostart/pulseaudio.desktop 2>/dev/null || true

COPY start-desktop.sh start-mate.sh start-paraview.sh reset-window-policy.sh /opt/portal/
# tint2 설정은 이미지에 둔다 — `-c`로 지정하지 않으면 tint2가 사용자 홈(NFS)에 기본
# 설정을 만들고, 그것이 세션·노드를 넘어 따라온다.
COPY tint2rc /opt/portal/tint2rc
RUN chmod 755 /opt/portal/start-desktop.sh /opt/portal/start-mate.sh \
              /opt/portal/start-paraview.sh /opt/portal/reset-window-policy.sh \
 && chmod 644 /opt/portal/tint2rc

# Apptainer는 이 ENTRYPOINT를 쓰지 않는다(exec로 스크립트를 직접 부른다).
# docker run으로 단독 확인할 때를 위해 남겨 둔다.
ENTRYPOINT ["/opt/portal/start-desktop.sh"]
