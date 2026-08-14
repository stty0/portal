#!/bin/bash
# 컨테이너 안에서 도는 GUI 세션 기동 스크립트 (U-IA-02).
#
# 순서: VNC 비밀번호 발급 → Xvnc 기동(빈 포트 확보) → connection.json 기록 → 앱 실행.
# 앱이 끝나면(로그아웃/종료) Xvnc를 정리하고 종료한다 = Slurm Job 종료.
#
# ⚠ **rocky9-mate/start-desktop.sh와 같은 파일이다** — 아래 `PORTAL_APP` 분기만 다르다.
# 그 위쪽(VNC 비밀번호·xauth 쿠키·포트 경쟁·connection.json)은 보안과 직결되고 실측으로
# 다듬은 부분이라 갈라지면 안 된다. 갈라짐은 테스트가 막는다
# (`backend/tests/test_session_images.py`).
set -euo pipefail

# 배치 Job이라 실패해도 아무도 안 보고 있다. 어디서 죽었는지는 남긴다.
trap 'echo "start-desktop.sh 실패 (line $LINENO)" >&2' ERR

SESSION_DIR="${PORTAL_SESSION_DIR:?PORTAL_SESSION_DIR가 필요하다}"
GEOMETRY="${PORTAL_GEOMETRY:-1920x1080}"
PORT_MIN="${PORTAL_PORT_MIN:-5901}"
PORT_MAX="${PORTAL_PORT_MAX:-5999}"

CONN_FILE="$SESSION_DIR/connection.json"
PASSWD_FILE="$SESSION_DIR/vncpasswd"
XVNC_LOG="$SESSION_DIR/xvnc.log"
XVNC_PID=""

mkdir -p "$SESSION_DIR"
chmod 700 "$SESSION_DIR"

# dbus 소켓은 유닉스 도메인 소켓이라 NFS 홈에 두면 안 된다. 노드 로컬을 쓴다.
export XDG_RUNTIME_DIR="${TMPDIR:-/tmp}/portal-rt-$(id -u)-${SLURM_JOB_ID:-$$}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# X 접근 제어 쿠키도 여기 둔다. NFS 홈에 두면 세션끼리 섞이고 xauth 락 파일이 문제가 된다.
# 디렉터리가 700이라 같은 노드의 다른 사용자는 쿠키를 읽지 못한다.
# **cleanup보다 먼저 정해야 한다** — set -u 아래에서 trap이 이 변수를 읽는다.
export XAUTHORITY="$XDG_RUNTIME_DIR/Xauthority"

# machine-id가 비면 dbus가 죽는다. --writable-tmpfs 위에 만든다.
if [ ! -s /etc/machine-id ]; then
    dbus-uuidgen > /etc/machine-id 2>/dev/null || true
fi

cleanup() {
    # 접속 정보를 남겨두면 죽은 세션에 붙으려 한다.
    rm -f "$CONN_FILE"
    # 쿠키는 자격증명이다 — 세션이 끝나면 남기지 않는다(-l/-c는 xauth 락 파일).
    rm -f "$XAUTHORITY" "$XAUTHORITY-l" "$XAUTHORITY-c"
    if [ -n "$XVNC_PID" ]; then
        kill "$XVNC_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT TERM INT

# --- VNC 비밀번호 -----------------------------------------------------
# 고전 VNC 비밀번호는 8자에서 잘린다. rfbauth 파일은 8바이트(전체) +
# 8바이트(view-only) 구조라 vncpasswd 출력을 두 번 이어 붙이면 둘 다 담긴다.
#
# `tr < /dev/urandom | head -c 8`은 쓰지 않는다 — head가 먼저 끝나며 tr이 SIGPIPE로
# 죽고, pipefail이 그걸 잡아 스크립트가 조용히 종료된다. 먼저 유한 바이트를 읽는다.
rand8() {
    local raw
    raw="$(head -c 512 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9')"
    printf '%s' "${raw:0:8}"
}
VNC_PASSWORD="$(rand8)"
VNC_VIEW_PASSWORD="$(rand8)"

umask 077
{
    printf '%s' "$VNC_PASSWORD"      | vncpasswd -f
    printf '%s' "$VNC_VIEW_PASSWORD" | vncpasswd -f
} > "$PASSWD_FILE"

# --- X 접근 제어 ------------------------------------------------------
# **-auth 없이 띄우면 X 서버가 로컬 연결을 인증 없이 받는다.** 같은 노드에 Job이 있는
# 다른 사용자가 유닉스 소켓(/tmp/.X11-unix/X<n>, srwxrwxrwx)으로 붙어 화면을 캡처하고
# 키 입력까지 주입할 수 있다(실측 — 캡처·주입 모두 성공했다).
#
# RFB 비밀번호는 이 경로를 막지 못한다. 그건 VNC 프로토콜 인증이고, 여기는 X 프로토콜이다.
: > "$XAUTHORITY"
chmod 600 "$XAUTHORITY"
# 128비트. `/dev/urandom | tr | head` 형태는 쓰지 않는다 — head가 먼저 끝나며 SIGPIPE로
# 조용히 죽는다(실제로 겪음). od가 -N으로 유한 바이트만 읽는다.
XCOOKIE="$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')"

# --- Xvnc 기동 --------------------------------------------------------
# 빈 포트를 미리 탐색하고 나중에 bind하면 그 사이에 경쟁이 난다.
# Xvnc가 직접 bind하게 하고 실패하면 다음 포트로 넘어간다 — bind는 원자적이다.
PORT=""
DISPLAY_NUM=""
for ((p = PORT_MIN; p <= PORT_MAX; p++)); do
    d=$((p - 5900))
    # 쿠키는 Xvnc가 뜨기 **전에** 있어야 한다. 포트가 막혀 건너뛴 디스플레이의 잔여
    # 항목은 무해하다 — 파일이 600이고 세션 전용이며 노드 로컬이다.
    xauth -q -f "$XAUTHORITY" add ":$d" MIT-MAGIC-COOKIE-1 "$XCOOKIE" 2>/dev/null || true
    Xvnc ":$d" \
        -rfbport "$p" \
        -rfbauth "$PASSWD_FILE" \
        -auth "$XAUTHORITY" \
        -geometry "$GEOMETRY" \
        -depth 24 \
        -SecurityTypes VncAuth \
        -localhost no \
        -AlwaysShared \
        -desktop "HPC Portal Desktop" \
        > "$XVNC_LOG" 2>&1 &
    XVNC_PID=$!

    sleep 2
    if kill -0 "$XVNC_PID" 2>/dev/null; then
        PORT="$p"
        DISPLAY_NUM="$d"
        break
    fi
    # 포트가 이미 쓰이면 Xvnc는 즉시 죽는다. 다음 후보로.
    wait "$XVNC_PID" 2>/dev/null || true
    XVNC_PID=""
done

if [ -z "$PORT" ]; then
    echo "빈 VNC 포트를 찾지 못했습니다 ($PORT_MIN-$PORT_MAX)" >&2
    tail -20 "$XVNC_LOG" >&2 || true
    exit 1
fi

export DISPLAY=":$DISPLAY_NUM"

# --- 접속 정보 기록 ---------------------------------------------------
# 포털은 이 파일만 보고 접속한다(유일한 출처). 워커 이름은 slurm.conf 등록명을
# 우선 쓴다 — 로그인 노드에서 반드시 해석되기 때문. IP는 폴백.
NODE="${SLURMD_NODENAME:-$(hostname -s)}"
NODE_IP="$(hostname -I 2>/dev/null | cut -d' ' -f1)"

cat > "$CONN_FILE.tmp" <<EOF
{
  "app": "${PORTAL_APP:-desktop}",
  "node": "$NODE",
  "ip": "$NODE_IP",
  "port": $PORT,
  "display": "$DISPLAY",
  "password": "$VNC_PASSWORD",
  "view_password": "$VNC_VIEW_PASSWORD",
  "geometry": "$GEOMETRY",
  "job_id": "${SLURM_JOB_ID:-}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
chmod 600 "$CONN_FILE.tmp"
# 포털이 반쯤 쓰인 파일을 읽지 않도록 원자적으로 교체한다.
mv "$CONN_FILE.tmp" "$CONN_FILE"

echo "VNC 준비 완료: $NODE:$PORT ($DISPLAY)"

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
