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

# JupyterLab (U-IA-01). **VNC를 쓰지 않는 첫 앱이다** — HTTP 서비스라 X 서버가 없어도 된다.
# 포털이 경로 접두사를 붙여 리버스 프록시하고, Jupyter는 `--ServerApp.base_url`로 자기
# 주소를 안다(그게 없으면 HTML의 링크가 전부 `/`로 나가 포털 SPA로 떨어진다).
#
# rocky9의 python3는 3.9라 최신 JupyterLab이 안 붙는다 — AppStream의 3.11을 쓴다.
# `--no-cache-dir`: 캐시를 남기면 이미지가 수백 MB 커진다.
RUN dnf -y install python3.11 python3.11-pip \
 && python3.11 -m pip install --no-cache-dir --upgrade pip \
 && python3.11 -m pip install --no-cache-dir jupyterlab notebook ipywidgets \
 && ln -sf /usr/bin/python3.11 /usr/local/bin/python3-portal \
 && dnf clean all \
 && rm -rf /var/cache/dnf /root/.cache

# 사용자가 **스스로** 소프트웨어를 늘릴 수 있는 최소 도구.
#
# 세션 안에서는 `dnf`가 통하지 않는다 — 컨테이너가 사용자 uid로 돌고 `/usr`는 이미지
# 안에서 root 소유다(실측: "This command has to be run with superuser privileges").
# `--fakeroot`로 root를 주려 했다가 **모든 세션이 죽었고**(AD 사용자에게 subuid가 없다),
# 설령 됐어도 쓰기 계층이 **64MB**뿐이라 `apt-get update`조차 No space left로 실패한다.
#
# 그래서 남는 길은 **홈에 설치하는 것**이고, 그 두 가지를 여기 넣는다:
#
#  1. micromamba — 빌드된 바이너리를 홈에 푼다. 컴파일러가 필요 없어 가장 실용적이다.
#  2. 컴파일러·헤더 — `pip install`이 소스 빌드로 떨어질 때 필요하다. 없으면
#     `failed-wheel-build-for-install`로 죽는다(실측).
#
# 둘 다 **홈(공유 NFS)에 설치되므로 세션이 끝나도 남는다** — 이미지 쓰기 계층과 다르다.
RUN dnf -y install gcc gcc-c++ make python3.11-devel bzip2 tar \
 && dnf clean all \
 && rm -rf /var/cache/dnf
# micromamba는 정적 단일 바이너리다. conda-forge가 주는 tar에서 실행파일만 꺼낸다.
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
      | tar -xvj -C /usr/local bin/micromamba \
 && chmod 755 /usr/local/bin/micromamba \
 && /usr/local/bin/micromamba --version

# 스크린세이버/잠금은 컨테이너 세션에서 의미가 없고, 잠기면 되살릴 방법이 없다.
RUN rm -f /etc/xdg/autostart/mate-screensaver.desktop \
          /etc/xdg/autostart/blueman.desktop \
          /etc/xdg/autostart/pulseaudio.desktop 2>/dev/null || true

COPY start-desktop.sh start-mate.sh start-paraview.sh start-jupyter.sh reset-window-policy.sh /opt/portal/
# tint2 설정은 이미지에 둔다 — `-c`로 지정하지 않으면 tint2가 사용자 홈(NFS)에 기본
# 설정을 만들고, 그것이 세션·노드를 넘어 따라온다.
COPY tint2rc /opt/portal/tint2rc
RUN chmod 755 /opt/portal/start-desktop.sh /opt/portal/start-mate.sh \
              /opt/portal/start-paraview.sh /opt/portal/start-jupyter.sh \
              /opt/portal/reset-window-policy.sh \
 && chmod 644 /opt/portal/tint2rc

# Apptainer는 이 ENTRYPOINT를 쓰지 않는다(exec로 스크립트를 직접 부른다).
# docker run으로 단독 확인할 때를 위해 남겨 둔다.
ENTRYPOINT ["/opt/portal/start-desktop.sh"]
