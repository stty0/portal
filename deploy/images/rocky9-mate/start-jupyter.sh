#!/bin/bash
# 컨테이너 안에서 JupyterLab을 띄운다 (U-IA-01).
#
# **VNC를 쓰지 않는다.** 데스크톱·ParaView는 화면을 RFB로 중계하지만 JupyterLab은 HTTP
# 서비스라 X 서버가 필요 없다 — Xvnc·xauth·dbus가 전부 빠진다.
#
# 대신 포털이 **경로 접두사를 붙여 리버스 프록시**한다. 그래서 Jupyter에게 자기 주소가
# 무엇인지 알려 줘야 한다(`--ServerApp.base_url`) — 안 알려 주면 HTML 안의 링크·에셋이
# 전부 `/`로 나가 포털 SPA로 떨어진다.
#
# base_url에 **Slurm Job ID를 쓴다.** 포털 세션 ID는 Job 제출 뒤에 만들어지므로 제출
# 시점에는 알 수 없다. Job ID는 컨테이너가 스스로 안다.
set -euo pipefail

trap 'echo "start-jupyter.sh 실패 (line $LINENO)" >&2' ERR

SESSION_DIR="${PORTAL_SESSION_DIR:?PORTAL_SESSION_DIR가 필요하다}"
PORT_MIN="${PORTAL_HTTP_PORT_MIN:-8801}"
PORT_MAX="${PORTAL_HTTP_PORT_MAX:-8899}"
JOB_ID="${SLURM_JOB_ID:-$$}"

CONN_FILE="$SESSION_DIR/connection.json"
APP_LOG="$SESSION_DIR/jupyter.log"

mkdir -p "$SESSION_DIR"
chmod 700 "$SESSION_DIR"

# 포털이 프록시하는 경로. 여기와 백엔드 라우트가 **같은 규칙**을 써야 한다.
BASE_URL="/api/v1/session-apps/$JOB_ID/"

# Jupyter가 쓰는 곳을 전부 세션 디렉터리로 돌린다. 기본값은 홈(NFS)이고, 런타임 파일은
# 유닉스 소켓·락을 쓰기 때문에 NFS에서 문제가 난다.
export JUPYTER_RUNTIME_DIR="${TMPDIR:-/tmp}/portal-jupyter-$(id -u)-$JOB_ID"
export JUPYTER_DATA_DIR="$SESSION_DIR/jupyter-data"
export JUPYTER_CONFIG_DIR="$SESSION_DIR/jupyter-config"
mkdir -p "$JUPYTER_RUNTIME_DIR" "$JUPYTER_DATA_DIR" "$JUPYTER_CONFIG_DIR"
chmod 700 "$JUPYTER_RUNTIME_DIR"

# --- 접속 토큰 --------------------------------------------------------
# 토큰이 없으면 **누구나** 붙는다. 포털이 앞에서 인증하지만 워커 노드의 포트는 같은
# 노드의 다른 Job에서도 보이므로(VNC 비밀번호와 같은 이유) 여기서도 막는다.
#
# `tr < /dev/urandom | head -c N`은 쓰지 않는다 — head가 먼저 끝나며 tr이 SIGPIPE로
# 죽고 pipefail이 그걸 잡아 스크립트가 조용히 종료된다(start-desktop.sh와 같은 함정).
TOKEN="$(od -An -tx1 -N24 /dev/urandom | tr -d ' \n')"

cleanup() {
    # 접속 정보를 남겨두면 죽은 세션에 붙으려 한다.
    rm -f "$CONN_FILE"
    rm -rf "$JUPYTER_RUNTIME_DIR"
}
trap cleanup EXIT TERM INT

NODE="${SLURMD_NODENAME:-$(hostname -s)}"
NODE_IP="$(hostname -I 2>/dev/null | cut -d' ' -f1)"

# --- 기동 -------------------------------------------------------------
# 빈 포트를 미리 찾고 나중에 bind하면 그 사이에 경쟁이 난다. Jupyter가 직접 bind하게
# 하고 실패하면 다음 포트로 넘어간다 — `--port-retries=0`이라야 조용히 옆 포트로
# 옮겨가지 않는다(옮겨가면 connection.json의 포트가 거짓이 된다).
PORT=""
APP_PID=""
for ((p = PORT_MIN; p <= PORT_MAX; p++)); do
    jupyter lab \
        --no-browser \
        --ip=0.0.0.0 \
        --port="$p" \
        --port-retries=0 \
        --ServerApp.base_url="$BASE_URL" \
        --ServerApp.token="$TOKEN" \
        --ServerApp.password='' \
        --ServerApp.allow_origin='*' \
        --ServerApp.trust_xheaders=True \
        --ServerApp.disable_check_xsrf=False \
        --ServerApp.root_dir="$HOME" \
        --ServerApp.quit_button=False \
        > "$APP_LOG" 2>&1 &
    APP_PID=$!

    sleep 4
    if kill -0 "$APP_PID" 2>/dev/null; then
        PORT="$p"
        break
    fi
    wait "$APP_PID" 2>/dev/null || true
    APP_PID=""
done

if [ -z "$PORT" ]; then
    echo "빈 HTTP 포트를 찾지 못했습니다 ($PORT_MIN-$PORT_MAX)" >&2
    tail -20 "$APP_LOG" >&2 || true
    exit 1
fi

# --- 접속 정보 기록 ---------------------------------------------------
# 포털은 이 파일만 보고 붙는다(유일한 출처). VNC 세션과 **같은 키를 쓴다** —
# `node`·`port`는 그대로이고 HTTP 앱에만 `scheme`·`token`·`base_url`이 더 붙는다.
cat > "$CONN_FILE.tmp" <<EOF
{
  "app": "${PORTAL_APP:-jupyter}",
  "scheme": "http",
  "node": "$NODE",
  "ip": "$NODE_IP",
  "port": $PORT,
  "token": "$TOKEN",
  "base_url": "$BASE_URL",
  "job_id": "$JOB_ID",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
chmod 600 "$CONN_FILE.tmp"
# 포털이 반쯤 쓰인 파일을 읽지 않도록 원자적으로 교체한다.
mv "$CONN_FILE.tmp" "$CONN_FILE"

echo "JupyterLab 준비 완료: $NODE:$PORT base_url=$BASE_URL"

# **exec을 쓰지 않는다** — 셸이 대체되면 위의 cleanup trap이 사라지고, scancel 뒤에도
# connection.json이 남아 죽은 세션에 붙으려 한다(start-desktop.sh에서 실측한 함정).
wait "$APP_PID" || true
