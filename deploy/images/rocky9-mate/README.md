# rocky9-mate — 인터랙티브 앱 세션 이미지 (U-IA-02)

Rocky 9 + MATE + TigerVNC + ParaView. 워커 노드에서 Apptainer로 실행된다.

**이 이미지 안에서는 앱을 `PORTAL_APP`으로 고른다.** MATE와 ParaView가 함께 들어 있어
지금은 두 앱이 같은 SIF를 쓴다 — 데스크톱 위에서 도는 앱이라 기반이 겹치기 때문이다.

앱마다 이미지를 나누는 것도 가능하다. 클러스터 설정은 이미지가 **있는 곳**
(`image_repository`)만 갖고, 앱↔이미지 매핑은 포털의 앱 카탈로그
(`backend/app/services/session_apps.py`)에 있다. 나눌 때는 그 표의 `image`만 바꾼다.

| `PORTAL_APP` | 실행되는 것 |
|---|---|
| `desktop` (기본) | MATE 세션 |
| `paraview` | marco(창 관리자) + ParaView 5.11 |

- 설계 근거: [docs/plan.md](../../../docs/plan.md) §3
- **websockify·noVNC는 들어 있지 않다.** WebSocket↔TCP 변환은 포털 백엔드가 하고,
  noVNC는 프론트 번들에서 관리한다(§3.3). 컨테이너는 Xvnc와 MATE만 제공한다.

## 빌드

dev01에서 빌드한다. `/home`이 dev01·slurm01·slurm02에서 같은 NFS라 SIF를 두면
노드에서 같은 경로로 바로 보인다(개발 단계 배포 = 복사 불필요).

```bash
sudo docker build -t rocky9-mate:1.5 deploy/images/rocky9-mate/

sudo APPTAINER_TMPDIR=/home/portal/.tmp \
  apptainer build --force \
  /home/portal/images/rocky9-mate-1.5.sif \
  docker-daemon://rocky9-mate:1.5
```

**버전을 파일명에 박는다.** 실행 중인 세션이 SIF를 mmap하고 있어 같은 경로에 덮어쓰면
안 되고, 버전을 나눠야 롤백이 된다.

`APPTAINER_TMPDIR`을 `/home` 아래로 돌리는 이유: 노드·dev01 모두 `/`에 여유가 적다
(노드 12GB). 변환 중간 산출물이 여기 쌓인다.

## 실행

```bash
export PORTAL_SESSION_DIR=$HOME/.portal/sessions/$SLURM_JOB_ID
apptainer exec --writable-tmpfs --bind /var/lib/sss/pipes \
  /home/portal/images/rocky9-mate-1.5.sif \
  /opt/portal/start-desktop.sh
```

`--writable-tmpfs`가 필요하다 — MATE·dbus가 `/etc/machine-id`, `/var/run`에 쓴다.
`--bind /var/lib/sss/pipes`는 AD 이름 해석용(아래 참조). **SSSD가 없는 호스트도 있으므로
Job 스크립트는 이 경로가 있을 때만 바인드를 붙인다.**

## AD 계정 / 홈 디렉터리

Apptainer는 **호출한 사용자 그대로** 실행한다(UID 변경 없음). 그래서 AD 신원과 홈은
별도 설정 없이 그대로 들어온다 — 컨테이너 안에서 실측한 결과다.

```
id      : uid=201106(jungryul0515.park) gid=200513(domain users)
whoami  : jungryul0515.park
HOME    : /home/jungryul0515.park       목록·쓰기 모두 정상 (NFS 공유 홈)
```

이름이 풀리는 이유는 Apptainer가 **호출자의 passwd/group 항목을 컨테이너에 주입**하기
때문이다(`apptainer.conf`의 `config passwd`/`config group`). 즉 sssd 없이도 본인은 풀린다.

다만 그것만으로는 **다른 AD 사용자가 안 풀려** 공유 디렉터리에서 숫자 UID로 보인다.
`sssd-client`(= `libnss_sss.so.2`)를 이미지에 넣고 `/var/lib/sss/pipes`를 바인드하면
호스트와 동일해진다. 소켓이 `srw-rw-rw-`라 추가 권한이 필요 없다.

| | 바인드 없음 | `--bind /var/lib/sss/pipes` |
|---|---|---|
| 본인 uid/이름/홈 | OK | OK |
| 타 AD 사용자 조회 | 실패 | OK |
| 그룹 멤버 목록 | 실패 | OK (`domain users` 멤버 전체) |

Rocky 9의 `/etc/nsswitch.conf`는 이미 `passwd: sss files systemd`라 수정할 필요가 없다.
모듈이 없을 때는 조용히 `files`로 넘어간다.

검증: 호스트와 컨테이너의 `getent passwd` 결과가 **완전히 일치**한다. 양쪽 모두에서
안 나오는 계정(`sysadmin`)은 SSSD 검색 범위(`OU=people`) 밖이라 컨테이너와 무관하다.

### 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `PORTAL_SESSION_DIR` | (필수) | 세션 디렉터리. `connection.json`이 여기 생긴다 |
| `PORTAL_GEOMETRY` | `1920x1080` | 화면 해상도 |
| `PORTAL_PORT_MIN`/`MAX` | `5901`/`5999` | RFB 포트 탐색 범위 |
| `PORTAL_APP` | `desktop` | 실행할 앱 — `desktop` / `paraview` |

## connection.json

포털이 접속 정보를 얻는 **유일한 출처**다. 포트·비밀번호를 Portal DB에 복제하지 않는다.

```json
{
  "app": "desktop", "node": "slurm01", "ip": "192.168.1.201",
  "port": 5901, "display": ":1",
  "password": "········", "view_password": "········",
  "geometry": "1280x800", "job_id": "123",
  "started_at": "2026-08-06T00:29:18Z"
}
```

`node`는 `$SLURMD_NODENAME`(slurm.conf 등록명)을 쓴다 — 로그인 노드에서 반드시
해석되기 때문이다. `ip`는 폴백. 반쯤 쓰인 파일을 포털이 읽지 않도록 임시 파일에
쓰고 `mv`로 교체한다. 세션이 끝나면 지운다(죽은 세션에 붙는 것을 막는다).

## 주의사항

- **포트는 Xvnc가 직접 bind한다.** 빈 포트를 미리 탐색하고 나중에 bind하면 그 사이에
  경쟁이 난다. 실패하면 다음 포트로 넘어간다 — bind는 원자적이다.
- **`tr < /dev/urandom | head -c N` 금지.** head가 먼저 끝나면 tr이 SIGPIPE로 죽고
  `pipefail`이 그걸 잡아 스크립트가 조용히 종료된다(실제로 겪음).
- **`pkill -f mate-session` 금지.** 같은 문자열을 포함한 자기 셸까지 죽는다.
  `pkill -f '[m]ate-session'`을 쓴다.
- **마지막에 `exec`을 쓰지 않는다.** 셸이 대체되면 정리 trap이 사라져 세션 종료 후에도
  `connection.json`이 남고, 포털이 죽은 세션에 붙으려 한다.
- **컨테이너 안의 정리 trap만 믿으면 안 된다.** apptainer가 별도 프로세스 그룹을 만들어
  `scancel`의 SIGTERM이 컨테이너 안까지 닿지 않는다(실측 — 직접 SIGTERM을 주면 동작).
  접속 정보 삭제는 Slurm이 직접 신호를 주는 **호스트 쪽 Job 스크립트**가 책임진다.
- Xvnc는 `-localhost no`로 연다. 워커가 분리되면 로그인 노드에서 닿아야 하기 때문이다
  (§3.4). 방어는 세션별 랜덤 비밀번호다. **노드를 분리하기 전에 재검토해야 한다** —
  로그인 노드→워커 구간이 평문이라 그때부터 화면·키 입력이 네트워크에 노출된다
  (docs/plan.md §3.4 "전제조건").
- **`-auth`를 빼면 안 된다.** 아래 "X 접근 제어" 참조 — 빼는 순간 같은 노드의 다른
  사용자가 인증 없이 화면을 보고 키를 넣을 수 있다.

## X 접근 제어 (MIT-MAGIC-COOKIE)

**RFB 비밀번호는 X 프로토콜을 막지 못한다.** 그건 VNC 접속 인증이고, X 서버에는 유닉스
소켓(`/tmp/.X11-unix/X<n>`, `srwxrwxrwx`)이라는 별도 입구가 있다. `-auth` 없이 띄우면
X 서버는 그 입구로 오는 로컬 연결을 **인증 없이 받는다.** 1.4까지가 그랬고, 실측 결과다.

```
1.4 (-auth 없음)                     1.5 (-auth 있음)
intruder 계정 xdpyinfo    → 성공      → unable to open display ":1"
화면 캡처                 → 성공(191KB) → unable to open X server
키 입력 주입              → 성공      → Failed creating new xdo instance
쿠키 파일 읽기            → (해당 없음) → Permission denied
```

그래서 `start-desktop.sh`가 Xvnc를 띄우기 전에 128비트 쿠키를 만들어 `-auth`로 넘긴다.

- 쿠키는 **노드 로컬**(`$XDG_RUNTIME_DIR/Xauthority`, 파일 600 / 디렉터리 700)에 둔다.
  NFS 홈에 두면 세션끼리 섞이고 xauth 락 파일이 문제가 된다.
- **포트 탐색 루프 안에서** 시도할 디스플레이마다 등록한다 — 포트가 막히면 다음 후보로
  넘어가는 구조라 쿠키가 Xvnc보다 먼저 있어야 한다. 건너뛴 디스플레이의 잔여 항목은 무해하다.
- `XAUTHORITY`를 export하므로 marco·tint2·ParaView·mate-session이 그대로 물려받는다.
  **이걸 못 물려받으면 GUI가 아예 안 뜬다** — 이 부분을 건드릴 때의 주된 회귀 위험이다.
- 세션이 끝나면 쿠키를 지운다(자격증명이다).

`--exclusive`는 **자원 옵션이지 접근 제어가 아니다.** 1.4까지는 그것이 사실상 유일한
방어선이었지만(같은 노드에 다른 사용자가 없으면 노출도 없으므로), 그건 인과가 뒤바뀐
상태였다. 이제 방어는 쿠키가 하고 `--exclusive`는 성능 옵션으로 돌아갔다.

## 무해한 경고

컨테이너에 systemd·system bus가 없어서 나온다. 동작에는 영향이 없다.

```
Could not connect to Systemd: /run/dbus/system_bus_socket
gnome-keyring-daemon: no process capabilities
libEGL warning: failed to open /dev/dri/card0   ← GPU 없음, llvmpipe 소프트웨어 렌더링
```

## ParaView (U-IA-02)

EPEL9에 **5.11.1**이 있어 별도 다운로드가 필요 없다. 다만 의존성 `python3-pygments`가
**CRB(CodeReady Builder)** 저장소에 있어 `dnf config-manager --set-enabled crb`가 먼저다.

**GPU가 없으면 Mesa llvmpipe 소프트웨어 렌더링으로 떨어진다.** 실측:

```
OpenGL renderer : llvmpipe (LLVM 21.1.8, 256 bits)
OpenGL version  : 4.5 (Compatibility Profile) Mesa 25.2.7
direct rendering: Yes
```

ParaView가 요구하는 OpenGL 3.2+를 충족하므로 **동작은 한다.** 다만 현재 노드가
2 vCPU라 큰 데이터셋은 실용적이지 않다. GPU 노드가 생기면 VirtualGL을 얹는 것이 정석이다.

ParaView 단독 실행 시 **창 관리자(marco)를 함께 띄운다.** 없으면 파일 열기 대화상자를
옮기거나 닫을 수 없어 세션이 그 창에 갇힌다.

### 단일 앱 모드에도 작업표시줄을 둔다 (tint2)

작업표시줄이 없으면 **창을 최소화했을 때 되살릴 방법이 없다**(실사용에서 확인).
Alt+Tab은 브라우저·호스트 OS가 가로채는 경우가 많아 의존할 수 없다.

한때(1.2/1.3) 제목표시줄 버튼을 전부 없애 최소화를 막았지만, **`File → Exit`는 어차피
막을 수 없었다.** 막는 대신 되살릴 수단을 준다 — `start-paraview.sh`가 marco 다음에
`tint2 -c /opt/portal/tint2rc`를 띄우고, **창 버튼(최소화·최대화·닫기)은 전부 정상
동작한다.**

`tint2rc`를 이미지에 넣고 `-c`로 지정하는 이유: 지정하지 않으면 tint2가 사용자 홈에
기본 설정을 만들고, 홈이 NFS라 그 설정이 세션·노드를 넘어 따라온다.

설정에서 중요한 것은 **`strut_policy = follow_size`** 하나다. strut을 잡아야 marco의
최대화가 막대를 비켜 간다 — 없으면 최대화한 앱이 막대를 덮어 복구 수단 자체가 사라진다.
실측(1280x800, 막대 24px):

```
WA: 0,0 1280x776                                 ← 작업 영역이 막대만큼 줄었다
0x00c00006  0 0 56 1280 748  paraview.ParaView   ← 최대화가 막대를 침범하지 않는다
```

**창 정책은 앱 스크립트가 명시적으로 되돌린다**(`reset-window-policy.sh`). gsettings는
사용자 dconf(NFS 홈)에 영구 저장되므로, 1.2/1.3을 써 본 사용자 홈에는 `button-layout=':'`,
`minimize/close='disabled'`가 남아 있다 — **설정을 빼는 것만으로는 원복이 안 된다.**

```
button-layout               "menu:minimize,maximize,close"
window-keybindings/minimize "<Alt>F9"
window-keybindings/close    "<Alt>F4"
action-right-click-titlebar "menu"
```

`gsettings`는 dbus 세션 안에서 돌아야 해서 `start-desktop.sh`(dbus 바깥)가 아니라
두 앱 스크립트가 각각 부른다. 여담 — 그때 키바인딩의 "끔" 값이 `[]`가 아니라
`"disabled"`라는 것도 알아냈다(`[]`는 marco가 `not a valid value`로 무시한다).

### 시작하자마자 화면 전체를 쓴다

ParaView는 지난 세션의 창 크기를 자기 설정에 저장해 두었다가 복원한다. 홈이 NFS로
공유되므로 그 값이 세션·노드를 넘어 따라오고, 지금 VNC 해상도보다 작으면 창이 화면
한 구석에만 뜬다. `start-paraview.sh`가 **창이 뜬 뒤 `wmctrl`로 최대화**한다
(`wmctrl` 패키지는 EPEL9).

스플래시 화면이 먼저 뜨므로 **제목이 붙은 창**을 최대 60초 기다린다. 이때 클래스가
`paraview`인 것만 고른다 — 안 그러면 tint2 막대를 최대화하는 사고가 난다(막대도
`wmctrl` 목록에 나온다). 실측:

```
0x00a00009 -1 tint2.Tint2        tint2                 ← 걸러야 하는 창
0x00c00006  0 paraview.ParaView  ParaView 5.11.1       ← 이것을 최대화한다
0x00c00022  0 paraview.ParaView  Welcome to ParaView
```

이미지가 커진다: 1.25GB → **2.62GB** (SIF 387MB → 1.3GB).

## 검증 이력 (2026-08-06)

```
apptainer exec / --writable-tmpfs / --fakeroot   전부 동작 (노드 apptainer 1.5.3)
Xvnc TigerVNC 1.15.0 기동 → 0.0.0.0:5901 LISTEN
connection.json 생성 확인
포털 → SSH(로그인 노드) → direct-tcpip("slurm01", 5901) → "RFB 003.008"

PORTAL_APP=paraview → paraview + marco 프로세스 확인, GLX llvmpipe OpenGL 4.5

1.4 창 정책·작업표시줄 (dev01 docker + 화면 캡처로 실측)
  paraview : 'menu:minimize,maximize,close' / '<Alt>F9' / '<Alt>F4' / 'menu' — 전부 원복
             tint2 기동, 작업 영역 1280x776(=800-24) → 최대화가 막대를 안 덮는다
             xdotool로 최소화 → 막대에 "ParaView 5.11.1" 버튼 남음 → 활성화하니
             최대화 상태 그대로 복귀
  desktop  : 같은 네 값 기본값, tint2 안 뜸(mate-panel 상·하단만)

1.5 X 접근 제어 (dev01 docker, 1.4에서 성공했던 공격을 그대로 재현)
  다른 사용자: xdpyinfo·화면 캡처·키 입력 주입·쿠키 파일 읽기 전부 거부됨
  세션 본인  : Xvnc·paraview·marco·tint2 정상 기동, 쿠키를 주면 wmctrl 정상
  desktop    : mate-session·mate-panel 정상 기동
  쿠키 600 / XDG_RUNTIME_DIR 700
```
