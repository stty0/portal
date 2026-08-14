# M-Star CFD 세션 이미지 (U-IA-02).
#
# **왜 rocky9-mate에 넣지 않고 이미지를 새로 만드는가.**
# M-Star 4.1.15는 Ubuntu 24.04용 빌드이고 `GLIBC_2.38`·`GLIBCXX_3.4.32`를 요구한다.
# Rocky 9는 glibc 2.34라 **실행 자체가 불가능하다**(실측: `objdump -T bin/mstar`가
# GLIBC_2.38을 요구하고, dev01에서 ldd가 그대로 거부한다). 앱마다 이미지를 나누는 것은
# 코드 카탈로그가 처음부터 허용한 구조다(`session_apps.py`의 `image` 필드).
#
# 세션 계약은 rocky9-mate와 같다 — Xvnc + `connection.json` + `PORTAL_APP` 분기.
# websockify·noVNC는 넣지 않는다(WebSocket↔TCP 변환은 포털 백엔드가 한다).
#
# 빌드 (M-Star 설치본은 빌드 컨텍스트에 넣지 않는다 — 3.9GB를 tar로 넘기지 않으려고
# BuildKit 이름 있는 컨텍스트를 쓴다):
#   sudo docker build -t ubuntu24-mstar:1.0 \
#     --build-context mstar=/home/jrpark/workspace/mstar/mstarcfd-4.1.15-ubuntu24 \
#     deploy/images/ubuntu24-mstar
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# MATE 세션 + TigerVNC + 소프트웨어 OpenGL.
#
# ⚠ **`tigervnc-tools`를 빠뜨리면 안 된다 — `vncpasswd`가 거기 있다.** Rocky는
# `tigervnc-server` 하나에 서버와 도구를 다 넣지만 Ubuntu는 나눠 놓는다. 없으면
# 이미지는 멀쩡히 빌드되고 `Xvnc`도 있는데 기동 스크립트가 비밀번호 발급 줄에서
# `vncpasswd: command not found`로 죽는다. 실제로 SIF 스모크 테스트에서 이렇게 잡혔다
# (docker 테스트는 `-SecurityTypes None`을 써서 이 경로를 지나가지 않았다).
#
# **GPU가 없는 것을 전제로 한다.** M-Star의 뷰포트는 OpenCASCADE(`libTKOpenGl`)가 그리고
# 그것이 OS의 `libGL.so.1`을 부른다 — GPU가 없으면 Mesa llvmpipe로 떨어진다. 느리지만
# 뜨고 조작된다. 해석(`mstar-cfd-mgpu`)은 CUDA가 필요해 여기서 돌지 않는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
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
      tigervnc-standalone-server \
      tigervnc-common \
      tigervnc-tools \
      dbus-x11 \
      xauth \
      x11-xserver-utils \
      xterm \
      wmctrl \
      tint2 \
      procps \
      iproute2 \
      hostname \
      ca-certificates \
      fonts-dejavu-core \
      xfonts-base \
      libgl1-mesa-dri \
      libglx-mesa0 \
      libglu1-mesa \
      mesa-utils \
 && rm -rf /var/lib/apt/lists/*

# M-Star(wxWidgets/GTK3 빌드)가 OS에 요구하는 공유 라이브러리.
# 목록은 추측이 아니라 `objdump -p bin/mstar`의 NEEDED에서 번들(`lib/`)에 없는 것만
# 뽑아 만들었다 — 22개 중 아래가 배포판이 줘야 하는 것들이다.
# Ubuntu 24.04는 64비트 time_t 전환으로 여러 패키지가 `t64` 접미사를 쓴다.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgtk-3-0t64 \
      libgdk-pixbuf-2.0-0 \
      libcairo2 \
      libcairo-gobject2 \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
      libpangoft2-1.0-0 \
      libglib2.0-0t64 \
      libxkbcommon0 \
      libsm6 \
      libx11-6 \
      libfontconfig1 \
      libpng16-16t64 \
      libssl3t64 \
 && rm -rf /var/lib/apt/lists/*

# 스크린세이버/잠금은 컨테이너 세션에서 의미가 없고, 잠기면 되살릴 방법이 없다.
RUN rm -f /etc/xdg/autostart/mate-screensaver.desktop \
          /etc/xdg/autostart/blueman.desktop \
          /etc/xdg/autostart/pulseaudio.desktop 2>/dev/null || true

# M-Star 설치본. 벤더가 배포하는 트리를 그대로 둔다 — `mstar.sh`가 자기 위치에서
# PATH·LD_LIBRARY_PATH를 만들므로 경로만 지키면 손댈 곳이 없다.
COPY --from=mstar . /opt/mstar/

COPY start-desktop.sh start-mate.sh start-mstar.sh reset-window-policy.sh /opt/portal/
# tint2 설정은 이미지에 둔다 — `-c`로 지정하지 않으면 tint2가 사용자 홈(NFS)에 기본
# 설정을 만들고, 그것이 세션·노드를 넘어 따라온다.
COPY tint2rc /opt/portal/tint2rc
RUN chmod 755 /opt/portal/start-desktop.sh /opt/portal/start-mate.sh \
              /opt/portal/start-mstar.sh /opt/portal/reset-window-policy.sh \
 && chmod 644 /opt/portal/tint2rc \
 && chmod 755 /opt/mstar/mstar.sh

# Apptainer는 이 ENTRYPOINT를 쓰지 않는다(exec으로 스크립트를 직접 부른다).
# docker run으로 단독 확인할 때를 위해 남겨 둔다.
ENTRYPOINT ["/opt/portal/start-desktop.sh"]
