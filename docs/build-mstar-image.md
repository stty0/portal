# M-Star CFD SIF 만들기 — 실제로 밟은 순서 전체

- 작성일: 2026-08-13
- 대상: 벤더가 배포한 M-Star CFD 4.1.15 설치본을 포털에서 도는 인터랙티브 앱으로 붙이기
- 결과물: `/home/.portal/images/ubuntu24-mstar-1.0.sif` (2.1GB) · 앱 id `mstar`
- 관련 문서: [build-app-image.md](build-app-image.md)(일반 계약) ·
  [deploy/images/ubuntu24-mstar/README.md](../deploy/images/ubuntu24-mstar/README.md)(이 이미지 요약)

> 이 문서는 **한 번의 실제 작업 기록**이다. 잘못 든 길과 거기서 나온 판단까지 남긴다 —
> 다음에 다른 상용 코드를 붙일 때 같은 곳에서 막히기 때문이다.

---

## 0. 전제

- 설치본: `/home/jrpark/workspace/mstar/mstarcfd-4.1.15-ubuntu24` (벤더 tar를 푼 트리, 3.9GB)
- **GPU 노드가 없다.** 요구사항은 "VNC로 GUI가 뜨는 것"까지이고 해석은 대상이 아니다.
- 빌드 기계 = dev01 (`/` 31GB, `/home`은 100TB NFS)

---

## 1. 설치본을 먼저 읽는다 — 여기서 이미지 베이스가 결정된다

무엇을 실행할지, 무엇을 요구하는지부터 본다. **이 단계를 건너뛰면 뒤가 전부 헛수고가 된다.**

```bash
cd /home/jrpark/workspace/mstar/mstarcfd-4.1.15-ubuntu24
ls
# bin/ data/ docs/ lib/ post/ scripts/ mstar.sh mstar-mesa.sh

file bin/mstar bin/MStarPost
# bin/mstar:     ELF 64-bit LSB pie executable, x86-64, dynamically linked, not stripped
# bin/MStarPost: POSIX shell script      ← post는 ParaView 래퍼다
```

`mstar.sh`가 벤더가 정한 실행 환경이다. 이걸 그대로 쓰면 경로를 손댈 일이 없다:

```bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export GDK_BACKEND=x11
export PATH=$DIR/bin:$PATH
export MSTARPOST_LD=$DIR/post/lib
export MSTARPOST_PATH=$DIR/post/bin
export LD_LIBRARY_PATH=$DIR/lib:$LD_LIBRARY_PATH
```

### 1.1 결정적인 확인 — glibc

```bash
objdump -T bin/mstar | grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -5
# GLIBC_2.29 / 2.32 / 2.33 / 2.34 / GLIBC_2.38   ← 최고 요구치
objdump -T bin/mstar | grep -o 'GLIBCXX_[0-9.]*' | sort -Vu | tail -3
# GLIBCXX_3.4.26 / 3.4.29 / GLIBCXX_3.4.32

ldd --version | head -1
# ldd (GNU libc) 2.34      ← Rocky 9
```

**여기서 갈렸다.** 기존 세션 이미지 `rocky9-mate`는 glibc 2.34다. 확인 사살:

```bash
ldd bin/mstar 2>&1 | head -3
# bin/mstar: /lib64/libm.so.6: version `GLIBC_2.38' not found (required by bin/mstar)
# bin/mstar: /lib64/libc.so.6: version `GLIBC_2.38' not found (required by bin/mstar)
# bin/mstar: /lib64/libstdc++.so.6: version `GLIBCXX_3.4.32' not found (required by bin/mstar)
```

→ **Rocky 9에서는 실행 자체가 불가능하다. Ubuntu 24.04(glibc 2.39) 이미지를 새로 만든다.**

지금까지 인터랙티브 앱은 전부 `rocky9-mate` 하나에 `PORTAL_APP` 분기로 들어갔으므로,
이것이 **이미지가 갈라진 첫 사례**다.

### 1.2 OS가 줘야 하는 라이브러리 — 추측하지 않고 뽑는다

벤더 번들(`lib/`)에 있는 것은 설치하면 안 된다(중복·충돌). `NEEDED` 중 번들에 **없는**
것만 골라낸다:

```bash
python3 - <<'PY'
import subprocess, os, re
need=set()
out=subprocess.run(['objdump','-p','bin/mstar'],capture_output=True,text=True).stdout
for m in re.finditer(r'NEEDED\s+(\S+)', out): need.add(m.group(1))
have=set(os.listdir('lib'))
print("번들에 있는 것:", len(need & have))
print("OS가 줘야 하는 것:")
for n in sorted(need-have): print("  ", n)
PY
```

결과 — 58개는 번들, 22개가 OS 몫이었다:

```
ld-linux-x86-64.so.2  libSM.so.6  libX11.so.6  libc.so.6
libcairo-gobject.so.2 libcairo.so.2  libcrypto.so.3  libfontconfig.so.1
libgcc_s.so.1  libgdk-3.so.0  libgdk_pixbuf-2.0.so.0  libgio-2.0.so.0
libglib-2.0.so.0  libgobject-2.0.so.0  libgtk-3.so.0  libm.so.6
libpango-1.0.so.0  libpangocairo-1.0.so.0  libpangoft2-1.0.so.0
libpng16.so.16  libstdc++.so.6  libxkbcommon0
```

→ **GTK3 기반**(wxWidgets의 GTK 백엔드)이다. Qt가 아니다.

3D는 번들 OpenCASCADE가 그린다 — 그것이 OS의 `libGL`을 부른다:

```bash
objdump -p lib/libTKOpenGl.so.7.7 | grep NEEDED | grep -iE 'gl|x11'
# NEEDED  libGL.so.1
# NEEDED  libX11.so.6
```

### 1.3 라이선스 방식

```bash
strings bin/mstar | grep -iE "license" | sort -u | head
# LicenseSetupDialog / ActivationWizard / InstallLicenseFilePage ...
# "Activate a local license with a key in the form XXXX-XXXX-XXXX-XXXX"
```

자체 활성화 방식(FlexLM 아님)이고 **라이선스 파일이 없다.** 요구사항이 "GUI 기동까지"라
그대로 진행하되, 사용자에게 보이도록 앱 카드에 적기로 했다(§7).

---

## 2. 이미지 정의

`deploy/images/ubuntu24-mstar/`를 새로 만들고, 세션 계약(Xvnc·`connection.json`·
`PORTAL_APP`)을 지키는 스크립트는 `rocky9-mate`에서 **복사**했다.

```bash
mkdir -p deploy/images/ubuntu24-mstar
cp deploy/images/rocky9-mate/{start-mate.sh,reset-window-policy.sh,tint2rc} \
   deploy/images/ubuntu24-mstar/
cp deploy/images/rocky9-mate/start-desktop.sh deploy/images/ubuntu24-mstar/
```

복사본이 생겼다는 것은 **갈라질 위험이 생겼다**는 뜻이다. §6의 테스트로 묶었다.

### 2.1 `Dockerfile`

```dockerfile
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
```

### 2.2 `start-mstar.sh` — 이번에 새로 쓴 유일한 스크립트

`rocky9-mate/start-paraview.sh`와 뼈대가 같다. 다른 점은 **벤더 스크립트를 source**하고
**소프트웨어 렌더링을 명시**한다는 것.

```bash
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
```

> **`export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"` 는 장식이 아니다.**
> `mstar.sh`가 `$LD_LIBRARY_PATH`를 정의 없이 참조해서 `set -u` 아래에서는
> `LD_LIBRARY_PATH: unbound variable`로 죽는다. 스모크 테스트 1차에서 실제로 이걸로
> 멈췄다(§4.1).

### 2.3 `start-desktop.sh` — 분기만 고쳤다

복사본이라 **앱 분기 앞부분은 손대지 않았다.** 바꾼 곳은 머리말 경고와 `case` 뿐이다.

```bash
# --- 앱 실행 ----------------------------------------------------------
# **exec을 쓰면 안 된다** — 셸이 대체되면서 위의 cleanup trap이 사라지고,
# scancel 후에도 connection.json이 남아 죽은 세션에 접속을 시도하게 된다(실측).
# 백그라운드 + wait이라야 SIGTERM을 즉시 받아 정리한다.
# 기본값을 `desktop`으로 두는 것은 rocky9-mate와 같다 — 이 이미지도 MATE를 갖고 있어
# `PORTAL_APP` 없이 들어와도 쓸 수 있는 화면이 뜬다. 포털은 언제나 값을 채워 보낸다.
case "${PORTAL_APP:-desktop}" in
    mstar)
        # 창 관리자 기동과 최대화는 start-mstar.sh가 한다.
        # gsettings가 dbus 세션 안에서 돌아야 해서 한 덩어리로 묶었다.
        dbus-launch --exit-with-session /opt/portal/start-mstar.sh &
        APP_PID=$!
        ;;
    desktop)
        dbus-launch --exit-with-session /opt/portal/start-mate.sh &
        APP_PID=$!
        ;;
    *)
        echo "알 수 없는 앱: $PORTAL_APP" >&2
        exit 1
        ;;
esac

wait "$APP_PID" || true
```

앞부분 전문은 [deploy/images/ubuntu24-mstar/start-desktop.sh](../deploy/images/ubuntu24-mstar/start-desktop.sh)
(= `rocky9-mate` 판과 동일). 하는 일은 VNC 비밀번호 2종 발급 → xauth 쿠키 생성 →
빈 포트에 Xvnc bind(경쟁 회피) → `connection.json` 원자적 쓰기다.

### 2.4 그대로 복사한 두 스크립트

```bash
# start-mate.sh — PORTAL_APP=desktop일 때만 쓴다
#!/bin/bash
set -u
/opt/portal/reset-window-policy.sh
exec mate-session "$@"
```

```bash
# reset-window-policy.sh — 지난 세션이 NFS 홈 dconf에 남긴 창 정책을 되돌린다
#!/bin/bash
set -u
gsettings set org.mate.Marco.general button-layout "menu:minimize,maximize,close" 2>/dev/null || true
gsettings set org.mate.Marco.window-keybindings minimize "<Alt>F9" 2>/dev/null || true
gsettings set org.mate.Marco.window-keybindings close "<Alt>F4" 2>/dev/null || true
gsettings set org.mate.Marco.general action-right-click-titlebar "menu" 2>/dev/null || true
```

`tint2rc`(작업표시줄 설정)도 그대로 복사했다.

---

## 3. 빌드 — 3.9GB를 컨텍스트에 넣지 않는다

그냥 빌드하면 설치본 3.9GB를 매번 tar로 말아 데몬에 넘긴다. BuildKit **이름 있는
컨텍스트**를 쓰면 컨텍스트는 스크립트 몇 개로 유지되고 `COPY --from=mstar`가 직접 읽는다.

```bash
cd /home/jrpark/workspace/portal
chmod 755 deploy/images/ubuntu24-mstar/*.sh

sudo docker build -t ubuntu24-mstar:1.0 \
  --build-context mstar=/home/jrpark/workspace/mstar/mstarcfd-4.1.15-ubuntu24 \
  deploy/images/ubuntu24-mstar
```

결과: **4.97GB** 이미지. `COPY --from=mstar` 레이어에 22초.

### 3.1 라이브러리가 다 풀렸는지 먼저 본다

GUI를 띄우기 전에 이것부터. 여기서 걸리면 패키지 목록을 고친다.

```bash
sudo docker run --rm --entrypoint bash ubuntu24-mstar:1.0 -c '
source /opt/mstar/mstar.sh
ldd /opt/mstar/bin/mstar 2>&1 | grep -iE "not found|version .GLIBC" | sort -u | head -20
echo "(위가 비어 있으면 전부 해결됨)"
ldd --version | head -1
ls /usr/lib/x86_64-linux-gnu/libGL.so.1; echo Xvnc: $(command -v Xvnc)'
```

```
(위가 비어 있으면 전부 해결됨)
ldd (Ubuntu GLIBC 2.39-0ubuntu8.8) 2.39
/usr/lib/x86_64-linux-gnu/libGL.so.1
Xvnc: /usr/bin/Xvnc
```

---

## 4. 스모크 테스트 — 컨테이너 안에서 GUI를 실제로 띄운다

### 4.1 `smoke.sh` — 창이 뜰 때까지 기다린다

임시 스크립트다(레포에 넣지 않았다). `/tmp` 스크래치에 두고 bind mount로 넣어 돌렸다.

```bash
#!/bin/bash
set -u
export HOME=/tmp/mstarhome; mkdir -p "$HOME"
export XDG_RUNTIME_DIR=/tmp/rt; mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
dbus-uuidgen > /etc/machine-id 2>/dev/null || true
Xvnc :1 -rfbport 5901 -SecurityTypes None -geometry 1600x900 -depth 24 > /tmp/xvnc.log 2>&1 &
sleep 3
export DISPLAY=:1
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_GL_VERSION_OVERRIDE=3.3
echo "=== glxinfo (소프트웨어 렌더러 확인) ==="
glxinfo -B 2>&1 | grep -iE "OpenGL renderer|OpenGL version" | head -3
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source /opt/mstar/mstar.sh
marco >/tmp/marco.log 2>&1 &
sleep 1
echo "=== mstar 기동 ==="
/opt/mstar/bin/mstar > /tmp/mstar.log 2>&1 &
MPID=$!
for i in $(seq 1 40); do
  sleep 2
  if ! kill -0 $MPID 2>/dev/null; then
    echo "!! mstar 종료됨 (${i}번째 확인, $((i*2))초)"; echo "--- 로그 ---"; tail -30 /tmp/mstar.log; exit 1
  fi
  W="$(wmctrl -lx 2>/dev/null)"
  if [ -n "$W" ]; then echo "창 발견 ($((i*2))초):"; echo "$W"; fi
  if echo "$W" | grep -qiE "mstar|m-star"; then
     echo "=== 성공: M-Star 창이 떴다 ==="; echo "$W"
     tail -20 /tmp/mstar.log; exit 0
  fi
done
echo "!! 80초 안에 M-Star 창을 찾지 못했다"
echo "--- 로그 ---"; tail -40 /tmp/mstar.log; echo "--- 창 ---"; wmctrl -lx 2>&1
exit 2
```

```bash
sudo docker run --rm -v /tmp/.../smoke.sh:/smoke.sh:ro \
  --entrypoint bash ubuntu24-mstar:1.0 /smoke.sh
```

**1차 실행 — 실패했다:**

```
OpenGL renderer string: llvmpipe (LLVM 20.1.2, 256 bits)
OpenGL version string: 3.3 (Compatibility Profile) Mesa 25.2.8
/opt/mstar/mstar.sh: line 6: LD_LIBRARY_PATH: unbound variable
```

벤더 스크립트가 `set -u`와 안 맞는다. **`start-mstar.sh`에 넣어 둔 `${LD_LIBRARY_PATH:-}`
가드가 옳았다는 확인**이기도 하다. 스모크 스크립트에 같은 줄을 넣고 재실행:

```
=== mstar 기동 ===
창 발견 (6초):
0x00a00017  0 mstar.GUI    e91a67ba06c2 M-Star Pre
=== 성공: M-Star 창이 떴다 ===
```

로그에 남은 경고(둘 다 치명적이지 않다):

```
Gtk-CRITICAL **: gtk_image_menu_item_set_image: assertion 'GTK_IS_IMAGE_MENU_ITEM (...)' failed
TKOpenGl | Message: OpenGl_Window::CreateWindow: window Visual is incomplete:
                    no depth buffer, no stencil buffer
Error: no image library available   ← 배경 큐브맵(장식)
```

### 4.2 `glx2.sh` — depth 버퍼 경고를 파고든 기록

"depth buffer 없음"이 **환경 문제인지 앱 선택 문제인지** 갈라야 했다.

```bash
#!/bin/bash
export XDG_RUNTIME_DIR=/tmp/rt; mkdir -p "$XDG_RUNTIME_DIR"
Xvnc :1 -rfbport 5901 -SecurityTypes None -geometry 1600x900 -depth 24 > /tmp/xvnc.log 2>&1 &
sleep 3
export DISPLAY=:1 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
echo "=== visual 표 헤더 + depth(dp) / stencil(st) 열 ==="
glxinfo 2>/dev/null | sed -n '/^ *id *dep/,+6p'
echo "=== depth24 stencil8 을 가진 visual 개수 ==="
glxinfo 2>/dev/null | awk '/^0x/ {if ($13+0>0 && $14+0>0) n++} END{print n+0}'
echo "=== depth 버퍼 있는 visual 예시 3개 ==="
glxinfo 2>/dev/null | awk '/^0x/ {if ($13+0>0) print}' | head -3
```

```
  id dep cl sp  sz l  ci b ro  r  g  b  a F gb bf th cl  ...
0x1cc 24 tc  0  32  0 r  . .   8  8  8  8 .  .  0 24  8  ...   ← th=24(depth) cl=8(stencil)
```

→ **환경에는 depth·stencil 가진 visual이 있다.** 앱(GTK 창의 visual)이 다른 것을 골랐다.
GPU 없는 환경의 소프트웨어 GL 조합 문제이고, **와이어프레임 렌더링은 정상**이라
여기서 멈추고 제약으로 기록했다(§7). 셰이딩된 곡면에서 z-순서가 이상하면 여기가 원인이다.

### 4.3 `shot.sh` — 눈으로 확인한다

"창이 떴다"는 것과 "화면이 제대로 그려졌다"는 다른 말이다. 호스트에 이미지 도구가 없어서
**M-Star가 번들한 ffmpeg**(`post/bin/ffmpeg`)의 `x11grab`으로 캡처했다.

```bash
#!/bin/bash
export HOME=/tmp/mstarhome; mkdir -p "$HOME"
export XDG_RUNTIME_DIR=/tmp/rt; mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
dbus-uuidgen > /etc/machine-id 2>/dev/null || true
Xvnc :1 -rfbport 5901 -SecurityTypes None -geometry 1600x900 -depth 24 > /tmp/xvnc.log 2>&1 &
sleep 3
export DISPLAY=:1 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_GL_VERSION_OVERRIDE=3.3
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source /opt/mstar/mstar.sh
marco >/tmp/marco.log 2>&1 & sleep 1
/opt/mstar/bin/mstar > /tmp/mstar.log 2>&1 &
sleep 25
wmctrl -lx > /out/windows.txt 2>&1
id="$(wmctrl -lx | awk 'tolower($3) ~ /mstar/ {print $1; exit}')"
[ -n "$id" ] && wmctrl -i -r "$id" -b add,maximized_vert,maximized_horz
sleep 6
LD_LIBRARY_PATH=/opt/mstar/post/lib /opt/mstar/post/bin/ffmpeg -loglevel error \
  -f x11grab -video_size 1600x900 -i :1 -frames:v 1 -y /out/shot.png
echo "exit=$?"; ls -l /out/
```

```bash
mkdir -p out && chmod 777 out
sudo docker run --rm -v $PWD/shot.sh:/shot.sh:ro -v $PWD/out:/out \
  --entrypoint bash ubuntu24-mstar:1.0 /shot.sh
```

캡처 결과: 모델 트리(Simulation Parameters / Main Lattice / Output Plane X·Y·Z) ·
툴바 · **3D 뷰포트에 격자 경계상자와 좌표축이 정상 렌더링** · 하단 콘솔.
상태 표시줄에 `Version 4.1.15`와 **`No license`**.

---

## 5. SIF 변환과 배치

```bash
export APPTAINER_TMPDIR=/home/jrpark/.apptainer-tmp
export APPTAINER_CACHEDIR=/home/jrpark/.apptainer-cache
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"

time sudo -E apptainer build "$APPTAINER_TMPDIR/ubuntu24-mstar-1.0.sif" \
     docker-daemon://ubuntu24-mstar:1.0
# real 8m11s → 2.1GB
```

> **`APPTAINER_TMPDIR`·`APPTAINER_CACHEDIR`을 둘 다 `/home`(NFS)으로 돌린다.**
> 한쪽만 돌렸다가 `/root/.apptainer`에 blob이 쌓여 dev01이 DiskPressure에 걸리고
> 포털 파드가 evict된 사고가 있었다. `sudo -E`로 환경을 넘기는 것도 그 때문이다.

### 5.1 SIF를 **워커와 똑같은 명령으로** 돌려본다 — 여기서 버그가 잡혔다

포털이 만드는 실행 줄은 `apptainer exec --writable-tmpfs <sif> <entry>`다. 그대로 재현한다:

```bash
export PORTAL_SESSION_DIR=/tmp/.../sess PORTAL_GEOMETRY=1600x900 PORTAL_APP=mstar
mkdir -p "$PORTAL_SESSION_DIR"
apptainer exec --writable-tmpfs \
  /home/jrpark/.apptainer-tmp/ubuntu24-mstar-1.0.sif /opt/portal/start-desktop.sh
```

**1차 — 실패:**

```
/opt/portal/start-desktop.sh: line 71: vncpasswd: command not found
start-desktop.sh 실패 (line 71)
```

원인: **Ubuntu는 `vncpasswd`를 `tigervnc-tools`에 따로 뗀다.** Rocky는 서버 패키지에
함께 넣는다. docker 스모크 테스트는 `-SecurityTypes None`으로 Xvnc를 직접 띄워서
이 줄을 **지나가지 않았다**. 이미지는 멀쩡히 빌드됐고 `Xvnc`도 있어서 빌드로도 안 잡힌다.

```bash
# 확인
sudo docker run --rm --entrypoint bash ubuntu24-mstar:1.0 -c \
  'dpkg -L tigervnc-common tigervnc-standalone-server | grep bin/'
# /usr/bin/tigervncconfig /usr/bin/Xtigervnc /usr/bin/tigervncserver ... ← vncpasswd 없음
apt-cache search tigervnc   # → tigervnc-tools 가 따로 있다
```

Dockerfile에 `tigervnc-tools`를 넣고 재빌드 → SIF 재변환(8분) → 재실행:

```json
{
  "app": "mstar",
  "node": "dev01",
  "ip": "192.168.1.100",
  "port": 5901,
  "display": ":1",
  "password": "e0WeNe7D",
  "view_password": "UPKuEBSq",
  "geometry": "1600x900",
  "job_id": "",
  "started_at": "2026-08-13T00:15:31Z"
}
```

SIF 세션 안에서도 창과 작업표시줄을 확인했다:

```bash
XAUTH=$(ls -d /tmp/portal-rt-$(id -u)-*/Xauthority | head -1)
DISPLAY=:1 XAUTHORITY=$XAUTH apptainer exec <sif> wmctrl -lx
# 0x00a00009 -1 tint2.Tint2   N/A   tint2
# 0x00c00017  0 mstar.GUI     dev01 M-Star Pre
```

### 5.2 클러스터 이미지 디렉터리로 옮긴다

```bash
sudo mv /home/jrpark/.apptainer-tmp/ubuntu24-mstar-1.0.sif /home/.portal/images/
sudo chown root:root /home/.portal/images/ubuntu24-mstar-1.0.sif
sudo chmod 755      /home/.portal/images/ubuntu24-mstar-1.0.sif
```

> **`chown root:root`을 빼면 안 된다.** `mv`는 소유권을 그대로 옮기므로 빌드한 사용자
> 소유로 남고, 그러면 **그 사용자가 남들이 실행할 코드를 덮어쓸 수 있다.**
> 옆의 `rocky9-mate-1.6.sif`도 같은 규칙으로 root 소유다.

### 5.3 빌드 캐시 정리 — 잊으면 노드가 죽는다

```bash
sudo docker builder prune -af
# 이번 작업에서 누적 13.98GB를 회수했다
```

---

## 6. 포털에 등록

### 6.1 코드 카탈로그

`backend/app/services/session_apps.py`의 `APPS`에 한 항목:

```python
InteractiveApp(
    id="mstar",
    name="M-Star CFD",
    description="M-Star Pre 4.1.15 — 모델 작성·시각화 (해석은 GPU 노드 필요)",
    image="ubuntu24-mstar-1.0.sif",
    fid="U-IA-02",
    entry="/opt/portal/start-desktop.sh",
    note=(
        "**GPU가 없어 해석(Solve)은 돌지 않습니다.** 화면은 소프트웨어 렌더링"
        "(Mesa llvmpipe)이라 회전·확대가 느립니다. 라이선스가 등록되지 않은 "
        "상태에서는 상태 표시줄에 'No license'가 뜨며 모델 작성·저장만 됩니다."
    ),
),
```

`image`가 앱마다 다를 수 있게 처음부터 설계돼 있어서 **이 한 줄로 다른 SIF를 쓴다.**

### 6.2 복사본이 갈라지지 않게 잠근다

`backend/tests/test_session_images.py`(신규). 핵심은 두 개다:

- **공유 파일 3개**(`start-mate.sh`·`reset-window-policy.sh`·`tint2rc`)는 바이트까지 동일
- **`start-desktop.sh`는 앱 분기를 뺀 본문**이 동일 — 비교 구간은
  `set -euo pipefail`부터 `# --- 앱 실행 -`까지다. 머리말은 뺀다(이미지마다 자기 사정을 적는다)

```python
BODY_START = "set -euo pipefail"
DISPATCH_MARKER = "# --- 앱 실행 -"

def _bootstrap_body(path):
    text = path.read_text(encoding="utf-8")
    _, started, rest = text.partition(BODY_START)
    assert started
    body, sep, _ = rest.partition(DISPATCH_MARKER)
    assert sep
    return body
```

나머지는 `entry` 스크립트 존재 확인, M-Star가 Ubuntu 이미지를 쓰는지, `note`에 GPU·
라이선스가 적혔는지, Dockerfile에 `tigervnc-tools`가 있는지.

> 이 테스트는 **작성 도중 실제로 걸렸다.** 처음엔 머리말까지 비교했는데 내가
> ubuntu 판 머리말에 "복사본이니 갈라지지 마라" 경고를 넣은 것을 잡아냈다.
> 그래서 비교 구간을 본문으로 좁혔다.

### 6.3 백엔드 반영

```bash
cd backend && .venv/bin/python -m pytest -q          # 445 passed
cd .. && sudo docker build -q -t hpc-portal-backend:0.1.0 -f backend/Dockerfile backend/
sudo docker save hpc-portal-backend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
sudo docker builder prune -af
kubectl -n hpc-portal rollout restart deploy/portal-backend
kubectl -n hpc-portal rollout status  deploy/portal-backend
```

확인 — 포털이 **SSH로 클러스터에 물어서** 이미지를 찾는지:

```
--- cluster 13 dir=/home/.portal/images
    {'ok': True, 'images': 9, 'message': '이미지 디렉터리 확인 — ... (파일 9개)'}
   installed: {'desktop': True, 'paraview': True, 'mstar': True, 'jupyter': True, 'code-server': False}
--- cluster 14  … mstar: True
```

---

## 7. 실측값과 남은 제약

| 항목 | 값 |
|---|---|
| 설치본 | 3.9GB (bin 958M · lib 1.4G · post 818M · docs 583M · data 161M) |
| docker 이미지 | 4.97GB |
| **SIF** | **2.1GB** · 변환 8분 11초 |
| 유휴 세션 RSS | **674MB** (mstar 439 · Xvnc 109 · marco 91 · tint2 19) |
| 노드 메모리 | 3915MB — 여유 있음 |
| 렌더러 | `llvmpipe (LLVM 20.1.2, 256 bits)` · OpenGL 3.3 Compatibility · Mesa 25.2.8 |
| 창 클래스 | `mstar.GUI` / 제목 `M-Star Pre` (최대화 스크립트가 이걸로 찾는다) |

메모리 측정:

```bash
ps -eo rss,comm --no-headers | awk '/Xvnc|mstar|marco|tint2/ {printf "%-12s %6.0f MB\n", $2, $1/1024}'
```

### 남은 제약 — 전부 앱 카드(`note`)에 적혀 사용자에게 보인다

1. **라이선스 없음.** 상태 표시줄 `No license`, 콘솔 `License: Bad, ... "License stat: -1"`.
   모델 작성·저장·시각화는 되고 Solve는 막힌다.
2. **GPU 없음 → 해석 불가.** `mstar-cfd-mgpu`가 CUDA를 요구한다.
3. **소프트웨어 렌더링이라 느리다.**
4. `OpenGl_Window::CreateWindow: window Visual is incomplete` — 와이어프레임은 정상이었다.
   셰이딩된 곡면에서 z-순서가 어긋나면 §4.2를 다시 판다.

### 검증하지 않은 것

**포털 화면에서 실제 세션을 띄우지는 않았다**(Slurm Job이 생긴다). 컨테이너는 워커와
동일한 apptainer 명령으로 검증했고, 남은 미검증 구간은 ParaView와 공유하는 잡 제출·
프록시 경로뿐이다.

---

## 8. 다음에 다른 상용 코드를 붙일 때의 체크리스트

1. `objdump -T <바이너리> | grep GLIBC_ | sort -Vu | tail -1` — **베이스 이미지가 여기서 정해진다**
2. `objdump -p`의 `NEEDED` − 벤더 번들 `lib/` = **설치할 패키지 목록**(추측 금지)
3. 벤더 기동 스크립트를 읽고 그대로 `source` — 경로를 직접 만들지 않는다
4. 벤더 스크립트가 `set -u`를 견디는지 확인(대개 못 견딘다 → 변수 가드)
5. GPU 없으면 `LIBGL_ALWAYS_SOFTWARE=1` + `GALLIUM_DRIVER=llvmpipe`
6. 설치본이 크면 `--build-context`로 컨텍스트 밖에 둔다
7. **배포판이 바뀌면 패키지 이름을 다시 확인**한다(`vncpasswd` → `tigervnc-tools`)
8. 스모크 테스트는 **실제 기동 스크립트**로 한다 — 우회하면 그 경로의 버그를 못 잡는다
9. 창이 뜬 것으로 끝내지 말고 **화면을 캡처해 눈으로 본다**
10. SIF는 `chown root:root`, 빌드 뒤 `docker builder prune -af`
