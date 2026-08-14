# 이 포털에서 도는 SIF 만들기 — ParaView 기준

> §3은 **같은 이미지에 앱을 더하는** 경우(ParaView), §3.6은 **이미지를 따로 만들어야
> 하는** 경우(M-Star — 벤더 바이너리의 glibc가 베이스보다 높다)를 다룬다.
>
> M-Star 쪽은 명령·스크립트 전문과 실패한 시도까지 담은 전 과정 기록이 따로 있다 —
> [build-mstar-image.md](build-mstar-image.md).

- 작성일: 2026-08-10
- 대상: 새 앱을 컨테이너로 붙이려는 사람
- 참조 구현: [deploy/images/rocky9-mate/](../deploy/images/rocky9-mate/) — 지금 도는 이미지의
  Dockerfile·기동 스크립트와 그 README(이 문서는 **계약**을, 그쪽은 **그 이미지**를 다룬다)

## 앱 종류에 따라 계약이 다르다

| | 배치 앱 (U-JB-13) | 인터랙티브 앱 (U-IA-01·02) |
|---|---|---|
| 예 | OpenFOAM | **ParaView**, 원격 데스크톱, JupyterLab |
| 포털이 하는 일 | `apptainer exec <sif> <커맨드>` | 컨테이너를 띄우고 **접속 정보를 기다린다** |
| 이미지가 지킬 것 | **거의 없다** — 바이너리가 PATH에 있으면 끝 | 아래 4가지 |

배치 앱이면 §5만 보면 된다. ParaView는 인터랙티브 앱이라 계약이 있다.

---

## 1. 포털이 컨테이너를 어떻게 띄우는가

세션 Job의 배치 스크립트가 만드는 실행 줄이다(`services/session_script.py`):

```bash
export PORTAL_SESSION_DIR="$HOME/.portal/sessions/$SLURM_JOB_ID"
export PORTAL_GEOMETRY=1920x1080
export PORTAL_APP=paraview

apptainer exec --writable-tmpfs [--bind /var/lib/sss/pipes] <이미지> <entry> &
wait
```

읽을 점 넷:

- **`--writable-tmpfs`** — MATE·dbus가 `/etc/machine-id`·`/var/run`에 쓴다. 읽기 전용이면 뜨지 않는다.
- **`/var/lib/sss/pipes` 바인드** — AD 이름 해석용. 호스트에 SSSD가 있을 때만 붙는다.
- **`entry`는 앱 카탈로그가 정한다** — 기본 `/opt/portal/start-desktop.sh`, JupyterLab은
  `/opt/portal/start-jupyter.sh`.
- **`exec`이 아니라 백그라운드 + `wait`** — 이유는 §2.4.

---

## 2. 인터랙티브 앱 이미지가 지켜야 할 것

### 2.1 기동 스크립트를 고정 경로에 둔다

`entry`가 가리키는 파일이 실행 가능해야 한다. 관례는 `/opt/portal/` 아래다.

### 2.2 `connection.json`을 세션 디렉터리에 쓴다

**포털이 접속 대상을 아는 유일한 경로다.** 워커가 쓰고 로그인 노드가 SFTP로 읽는다 —
그래서 이 디렉터리는 **공유 홈** 아래에 있다(`$PORTAL_SESSION_DIR`).

VNC 앱이 채워야 하는 필드:

| 필드 | 쓰임 |
|---|---|
| `node` · `ip` | 접속 대상. **로그인 노드가 아니라 워커 노드**다 |
| `port` | VNC 포트 (정수) |
| `password` | 접속 비밀번호 |
| `view_password` | 보기 전용(U-IA-05) |
| `geometry` | 화면이 캔버스 크기를 잡는 데 쓴다 |

HTTP 앱(JupyterLab)이면 `scheme`·`token`·`base_url`을 대신 채운다. 이 셋은
**브라우저로 나가지 않는다** — 서버가 프록시 헤더에 넣는다.

⚠ **반드시 원자적으로 써야 한다.** 포털이 반쯤 쓰인 파일을 읽으면 접속이 깨진다:

```bash
cat > "$CONN_FILE.tmp" <<EOF
{ "node": "$NODE", "ip": "$NODE_IP", "port": $PORT, ... }
EOF
chmod 600 "$CONN_FILE.tmp"
mv "$CONN_FILE.tmp" "$CONN_FILE"     # ← rename은 원자적이다
```

### 2.3 `PORTAL_APP`으로 갈래를 판단한다

**이미지 하나에 앱 여럿을 담을 수 있다.** 지금 `desktop`·`paraview`가 같은 SIF를 쓴다 —
데스크톱 전체를 주느냐, ParaView 하나만 주느냐의 차이뿐이라 이미지를 나눌 이유가 없었다.

```bash
case "${PORTAL_APP:-desktop}" in
    desktop)  dbus-launch --exit-with-session /opt/portal/start-mate.sh & ;;
    paraview) dbus-launch --exit-with-session /opt/portal/start-paraview.sh & ;;
    *)        echo "알 수 없는 앱: $PORTAL_APP" >&2; exit 1 ;;
esac
wait "$APP_PID" || true
```

### 2.4 ⚠ 바깥 스크립트에서 `exec`을 쓰면 안 된다

`exec`은 셸을 **대체**하므로 그 셸이 걸어 둔 `trap`이 사라진다. 그러면 `scancel` 뒤에도
`connection.json`이 남아 **죽은 세션에 접속을 시도한다**(실측).

```bash
trap 'rm -f "$CONN_FILE"' EXIT TERM INT
앱 &            # 백그라운드로 띄우고
wait "$APP_PID" # 기다린다 → SIGTERM을 즉시 받아 정리한다
```

**가장 안쪽 스크립트에서는 `exec`이 맞다** — 거기서는 그 프로세스가 곧 앱의 수명이고,
정리 trap은 바깥이 갖고 있다(`start-paraview.sh` 마지막 줄이 `exec paraview`인 이유).

> 포털은 이 정리를 **바깥 배치 스크립트에도 한 번 더** 건다. apptainer가 별도 프로세스
> 그룹을 만들어 `scancel`의 SIGTERM이 컨테이너 안까지 안 닿기 때문이다(실측).

---

## 3. ParaView 예제 — 실제 구성

### 3.1 Dockerfile (핵심만)

```dockerfile
FROM rockylinux/rockylinux:9

# 데스크톱 기반 — VNC 앱은 X 서버와 창 관리자가 필요하다
RUN dnf -y install epel-release \
 && dnf -y install tigervnc-server mate-desktop marco dbus-x11 wmctrl tint2

# ParaView는 EPEL9에 5.11.1이 있어 따로 받을 필요가 없다
RUN dnf -y install "dnf-command(config-manager)" \
 && dnf -y install paraview

# 기동 스크립트를 고정 경로에
COPY start-desktop.sh start-mate.sh start-paraview.sh reset-window-policy.sh /opt/portal/
COPY tint2rc /opt/portal/tint2rc
RUN chmod +x /opt/portal/*.sh
```

### 3.2 스크립트가 3층인 이유

```
start-desktop.sh    Xvnc 기동 → 비밀번호 생성 → connection.json → PORTAL_APP 분기
  └ start-paraview.sh   창 관리자(marco) → 작업표시줄(tint2) → 최대화 → exec paraview
```

**바깥은 세션을, 안쪽은 앱을 책임진다.** 새 VNC 앱을 붙일 때는 안쪽 스크립트만 쓰고
`case` 한 줄을 더하면 된다 — VNC·접속 정보는 이미 되어 있다.

`start-paraview.sh`가 창 관리자를 띄우는 이유는 없으면 **파일 열기 대화상자 하나에
갇히기 때문**이다(옮길 수도 닫을 수도 없다). 작업표시줄은 최소화한 창을 되살릴 수단이다.

### 3.3 빌드 → SIF

```bash
# 1) 컨테이너 이미지
sudo docker build -t rocky9-mate:1.6 deploy/images/rocky9-mate/

# 2) SIF로 변환. 캐시·tmp를 /home 아래로 돌린다(§4.2)
export APPTAINER_TMPDIR=/home/.portal/.tmp
export APPTAINER_CACHEDIR=/home/.portal/.cache
sudo -E apptainer build --force \
  /home/.portal/images/rocky9-mate-1.6.sif \
  docker-daemon://rocky9-mate:1.6

# 3) 빌드 캐시 정리 — 안 하면 노드가 DiskPressure에 걸린다
sudo docker builder prune -af
```

**레지스트리를 거칠 수도 있다.** 그때는 Docker 데몬도 `docker pull`도 필요 없다 —
계산 노드에 docker가 없어도 apptainer만으로 변환된다(실측):

```bash
apptainer build rocky9-mate-1.6.sif docker://<계정>/rocky9-mate:1.6
```

### 3.4 클러스터에 배치

SIF를 **각 클러스터의** `{홈 상위 경로}/.portal/images/`에 둔다. 포털은 이 디렉터리를
읽기만 하고 쓰지 않는다.

```bash
sudo install -m 644 rocky9-mate-1.6.sif /home/.portal/images/
```

⚠ **파일명에 버전을 박는다.** 실행 중인 세션이 SIF를 mmap하고 있어 같은 경로에 덮어쓰면
안 되고, 버전이 나뉘어야 롤백이 된다.

### 3.5 포털에 알리기

**포탈 설정 › 운영 › 앱 관리**에서 해당 앱의 **컨테이너 이미지 파일**을 새 파일명으로
바꾼다. 코드 배포가 필요 없다 — 목록 캐시가 만료되는 **최대 60초 뒤** 열린다.

새 앱을 추가하는 경우에는 코드 카탈로그(`services/session_apps.py`)에 항목이 필요하다.
**실행 방식(entry·transport·파라미터)은 코드가 정본**이기 때문이다:

```python
InteractiveApp(
    id="paraview",
    name="ParaView",
    description="과학 시각화 5.11 (소프트웨어 렌더링)",
    image="rocky9-mate-1.5.sif",   # 기본값. 앱 관리에서 덮을 수 있다
    fid="U-IA-02",
    # entry·transport는 기본값(start-desktop.sh · vnc)을 쓴다
)
```

---

## 3.6 두 번째 이미지가 필요할 때 — M-Star CFD (2026-08-13)

지금까지는 이미지가 하나였다(`rocky9-mate`, `PORTAL_APP`으로 분기). **M-Star에서 처음
갈라졌다.** 벤더 바이너리가 베이스 이미지보다 새 glibc를 요구하면 선택의 여지가 없다.

```bash
# 실측 — 이걸 먼저 본다. 여기서 갈리면 뒤 작업이 전부 헛수고다
$ objdump -T bin/mstar | grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -1
GLIBC_2.38
$ ldd --version | head -1      # Rocky 9
ldd (GNU libc) 2.34
```

Rocky 9에서는 `ldd`가 실행을 거부한다. 그래서 `deploy/images/ubuntu24-mstar`
(Ubuntu 24.04, glibc 2.39)를 따로 만들었다. 세션 계약은 그대로라 카탈로그에 한 줄이면 붙는다.

### 설치본을 빌드 컨텍스트에 넣지 않는다

M-Star 설치본은 3.9GB다. 그대로 두면 매 빌드마다 그만큼을 tar로 말아 데몬에 넘긴다.
BuildKit의 **이름 있는 컨텍스트**를 쓰면 컨텍스트는 스크립트 몇 개로 유지된다.

```bash
sudo docker build -t ubuntu24-mstar:1.0 \
  --build-context mstar=/home/jrpark/workspace/mstar/mstarcfd-4.1.15-ubuntu24 \
  deploy/images/ubuntu24-mstar
```
```dockerfile
COPY --from=mstar . /opt/mstar/
```

### 배포판이 바뀌면 패키지 이름부터 다시 확인한다

**`vncpasswd`가 Ubuntu에서는 `tigervnc-tools`에 있다.** Rocky는 서버 패키지에 함께 넣는다.
빠뜨려도 **이미지는 멀쩡히 빌드되고 `Xvnc`도 있어서** docker 확인을 통과하고,
SIF로 돌릴 때 비밀번호 발급 줄에서 `vncpasswd: command not found`로 죽는다.

→ **스모크 테스트를 실제 기동 경로로 해야 잡힌다.** `-SecurityTypes None`으로 Xvnc만
띄워 보면 그 줄을 지나가지 않는다(이 함정에 그대로 걸렸다).

### GPU 없이 3D를 띄우는 환경변수

```bash
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export MESA_GL_VERSION_OVERRIDE=3.3
```

실측으로 `llvmpipe (LLVM 20.1.2) / OpenGL 3.3 Compatibility`가 잡히고 뷰포트가 정상
렌더링된다. OpenCASCADE가 `window Visual is incomplete: no depth buffer` 경고를 남기지만
와이어프레임 표시에는 영향이 없었다.

### 복사한 스크립트는 테스트로 묶는다

`start-desktop.sh`의 VNC 부트스트랩(비밀번호·xauth 쿠키·포트 경쟁·`connection.json`)은
보안과 직결되고 실측으로 다듬은 부분이다. 두 이미지에 복사본이 생겼으므로
[test_session_images.py](../backend/tests/test_session_images.py)가 **앱 분기를 뺀 본문이
글자까지 같은지** 검사한다. 머리말은 뺀다 — 이미지마다 자기 사정을 적는 자리다.

---

## 4. 함정 — 겪은 것

### 4.1 `.sif`·`.sqsh`만 목록에 뜬다

이미지 디렉터리에 `README.txt`를 같이 둬도 선택지에는 안 나온다. 반대로 **확장자가 다르면
아무리 올바른 이미지라도 안 보인다.**

### 4.2 apptainer 캐시가 노드를 채운다

`/`에 여유가 적다. `APPTAINER_TMPDIR`·`APPTAINER_CACHEDIR`을 **둘 다** `/home` 아래로
돌린다. 한쪽만 돌렸다가 `/root/.apptainer`에 blob이 11GB 쌓여 **dev01이 DiskPressure에
걸리고 포털 파드가 evict된 사고**가 있었다.

변환 중 순간 사용량이 최종 SIF보다 훨씬 크다 — 실측으로 2.62GB 이미지가 스크래치
**2.4GB**를 쓰고 9분 3초 만에 1.3GB SIF가 됐다.

### 4.3 NFS에 xattr가 없다

빌드 로그의 `destination filesystem does not support xattrs` 경고는 NFS라서 나는 것이고
실행에는 문제가 없었다. 권한 관련 이상이 나오면 여기를 의심한다.

### 4.4 지난 세션의 설정이 따라온다

홈이 NFS라 앱 설정(`dconf`, ParaView 창 크기)이 세션을 넘어 남는다. ParaView가 지난
세션의 작은 창 크기를 복원해 화면 구석에만 뜨던 문제가 있었고, 그래서
`start-paraview.sh`가 창이 뜬 뒤 최대화한다.

---

## 5. 배치 앱은 계약이 거의 없다

`connection.json`도 기동 스크립트도 필요 없다. 포털이 만드는 것은 이런 줄이다:

```bash
apptainer exec [--nv] [--env K=V] <이미지> <커맨드>
```

**바이너리가 PATH에 있으면 끝난다.** OpenFOAM 이미지는 공식 이미지를 그대로 변환해서
쓴다(`docker://opencfd/openfoam-default:2512`).

실행 커맨드와 파라미터 스키마는 코드 카탈로그(`services/batch_apps.py`)가 정본이고,
**이미지와 한 몸**이다 — 그래서 DB로 빼지 않았다.

---

## 6. 검증

이미지를 넣은 뒤 순서대로 확인한다.

```bash
# 1) 노드에서 컨테이너가 뜨는가
apptainer exec --writable-tmpfs /home/.portal/images/rocky9-mate-1.6.sif \
  bash -lc 'which paraview vncserver marco tint2'

# 2) 포털 목록에 뜨는가 (관리자)
#    앱 관리 › 수정 › 컨테이너 이미지 파일 드롭다운에 새 파일명이 있는지

# 3) 사용자 화면에서 잠금이 풀렸는가
#    인터랙티브 앱 카드가 [이 클러스터에 없음]이 아니어야 한다
```

세션을 실제로 띄운 뒤에는:

```bash
cat ~/.portal/sessions/<job_id>/connection.json   # 필드가 다 있는지
scancel <job_id> && ls ~/.portal/sessions/<job_id>/   # connection.json이 사라졌는지
```

**마지막 확인이 중요하다** — 남아 있으면 §2.4의 `exec`/`trap` 문제다.
