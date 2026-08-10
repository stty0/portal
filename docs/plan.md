# Plan: 인터랙티브 앱 — 원격 데스크톱 (SCR-06)

- 작성일: 2026-08-06
- 관련 화면/기능 ID: SCR-06, U-IA-01(앱 런처), U-IA-02(원격 데스크톱), U-IA-04(세션 관리)
- 상태: Approved (방식=OnDemand형 + 백엔드 프록시, 사용자 결정)
- 이전 에픽 plan은 git 이력 참조 (프론트엔드 Vue 이관, 2026-08-04)

## 1. 목표 / 배경

SCR-06은 현재 "아직 제공되지 않는 기능입니다"만 표시한다. 사용자가 브라우저에서
Linux 데스크톱 세션을 열어 GUI 작업을 하게 만든다.

정의서 §4.1이 이미 방식을 정해두었다 — **Job 제출은 REST(`sbatch`), 세션 연결은
SSH/프록시**. 이 계획은 그 문장을 구현으로 옮긴 것이다.

## 2. 범위

**포함**
- Rocky 9 + MATE + TigerVNC 컨테이너 이미지(Apptainer SIF)
- 세션 = Slurm 배치 Job. 자원(파티션·CPU·메모리·시간) 지정 후 제출
- 세션 목록·재접속·종료 (U-IA-04)
- 브라우저 noVNC 접속 (백엔드 WebSocket 브리지 경유)
- 앱 런처 화면 골격 (U-IA-01) — 데스크톱 카드만 활성

**제외(Non-goals)**
- Jupyter(U-IA-01 본래 대상)·VS Code(U-IA-03) — 세션/프록시 계층을 공유하므로 후속 작업에서 앱 정의만 추가
- 세션 공유 view-only 링크(U-IA-05) — TigerVNC view-only 비밀번호만 미리 발급해 둔다
- GPU / VirtualGL — 현 클러스터에 GRES 없음
- 컨테이너 레지스트리 — 개발 단계는 공유 NFS 배포. `image_repository` 설정값으로 나중에 전환

## 3. 설계 / 접근

### 3.1 전체 흐름 (Open OnDemand 방식)

```
① 제출   포털 --slurmrestd sbatch--> 클러스터            (기존 JobService 재사용)
② 기록   Job이 워커에서 Xvnc 기동 후 connection.json 기록 (공유 NFS 홈)
③ 조회   포털 --SFTP(로그인 노드, sudo -u user)--> connection.json
④ 접속   브라우저 --wss--> 백엔드 --SSH direct-tcpip(로그인 노드)--> 워커:포트
```

②의 `connection.json`이 **접속 정보의 유일한 출처**다. 포트·비밀번호를 Portal DB에
복제하지 않는다 — 비밀을 두 곳에 두지 않기 위해서다.

### 3.2 로그인 노드 / 워커 노드 분리 (필수 규칙)

포털은 **로그인 노드 자격증명만** 가진다. 컨테이너는 워커 노드에서 돈다.

```
SSH 접속 대상 = cluster.login_node        자격증명이 있는 곳. 고정.
터널 목적지   = connection.json 의 node   Job이 실제로 뜬 워커. 매번 다름.
```

SSH `direct-tcpip`의 목적지는 **로그인 노드의 sshd가 해석**하므로 워커 자격증명이
필요 없다. 실측 확인: 포털 → slurm01 경유 → 192.168.1.202:22 도달, Slurm 노드명으로도
도달(`allowtcpforwarding yes`, `permitopen any`).

현재 개발 환경은 로그인 노드 = 워커 노드라 **두 값을 혼동해도 동작한다.** 그래서
지금 틀리기 쉽고 분리 시점에 깨진다. 목적지가 `cluster.login_node`에서 오는 경로를
만들지 않으며, 이를 테스트로 고정한다(목적지 ≠ login_node인 케이스).

워커 이름은 `$SLURMD_NODENAME`(slurm.conf 등록명)을 쓰고 IP를 폴백으로 함께 기록한다.

### 3.3 websockify를 쓰지 않는다

websockify가 하는 일(WebSocket ↔ raw TCP)을 백엔드 브리지가 이미 한다. noVNC의 `RFB`는
WebSocket으로 RFB를 직접 말하므로 그대로 붙는다.

- 컨테이너에는 **Xvnc + MATE만** 넣는다. HTTP 서버·noVNC 정적 파일 불필요
- noVNC는 프론트 번들(`@novnc/novnc`)에서 관리 — 웹 터미널의 xterm.js와 같은 구조
- 서브패스 프록시 문제(`vnc.html?path=`)가 발생하지 않는다

### 3.4 인증 / 격리

- WS 인증은 웹 터미널과 동일한 방식 — **2026-08-08부터 쿠키**이며 subprotocol
  (`portal.token.<jwt>`)은 기계 클라이언트용으로 남았다
- URL에 host:port를 노출하지 않는다. 불투명한 세션 ID로 조회하며 **소유자를 확인**한다
  (OnDemand의 `/node/<host>/<port>/`는 인증 사용자면 임의 호스트로 프록시되는 통로다)
- 워커가 분리되면 Xvnc를 localhost에 묶을 수 없다(로그인 노드가 닿아야 함).
  세션마다 랜덤 VNC 비밀번호를 발급한다. 노드 독점이 필요하면 `--exclusive` 옵션 제공
  (**자원 옵션이지 접근 제어가 아니다** — 같은 노드 사용자로부터의 방어는 Xvnc의
  X 인증 쿠키가 담당한다. `-auth` 없이 띄우면 X는 로컬 연결을 인증 없이 받는다)

**전제조건 — 노드를 분리하기 전에 반드시 재검토한다.**

세 갈래 방어선이 서로 다른 문을 맡는다. 헷갈리면 안 된다.

| 문 | 방어 |
|---|---|
| 브라우저 → 백엔드 | WSS(TLS) |
| 백엔드 → 로그인 노드 | SSH |
| 로그인 노드 → 워커:5901 | **없음(평문)** |
| 워커 로컬 X 소켓 | MIT-MAGIC-COOKIE (`Xvnc -auth`) |
| 워커 5901 접속 인증 | 세션별 랜덤 VNC 비밀번호 |

마지막 평문 구간을 지금 방치하는 이유는 **로그인 노드와 워커가 같은 기계라 loopback이기
때문**이다. 분리하는 순간 화면·키 입력이 실제 네트워크에 평문으로 흐른다. 비밀번호는
접속을 막을 뿐 **관찰을 막지 못한다**(RFB 인증은 1회, 이후 프레임버퍼·KeyEvent는 평문).

→ 위험 수용 근거·재검토 조건·착수 시 해법과 걸림돌은 **[session-transport-security.md](session-transport-security.md)**
에 따로 정리했다. **노드 분리를 계획할 때 그 문서를 먼저 연다.**

### 3.5 구조 규칙

- 레이어링: `router → service → repository/client`. 라우터는 WS 프레임만 다루고
  인증·터널·세션 상태는 `SessionService`가 갖는다 (`terminal.py`와 동일, 레이어링 테스트 통과)
- 화면 요소에 `<Fid id="U-IA-0X" />` 매핑 유지
- 클러스터 설정값은 이미지가 **있는 곳**(`image_repository`)뿐이고, 어떤 이미지를 쓸지는
  앱 카탈로그(`app/services/session_apps.py`)가 정한다 — 앱이 늘어도 클러스터 설정은 그대로다.
  공유 SIF 디렉터리·`oras://`·`docker://`를 모두 같은 자리에서 받으므로 레지스트리 전환이
  DB 값 변경으로 끝난다

## 4. 제약 / 리스크

**환경 실측치**

| 항목 | 값 |
|---|---|
| 노드 | 클러스터당 1대, 2 vCPU / 3915MB / GPU 없음 |
| `/` 여유 | 노드 12GB, dev01 20GB |
| `/home` | `198.19.64.8:/scp_users_tl8g1s` 100TB NFS — dev01·slurm01·slurm02 **동일** |
| apptainer | 노드 1.5.3, rootless. `exec`·`--writable-tmpfs`·`--fakeroot` 모두 동작 |

**리스크**

- **노드 사양**: MATE 세션만으로 1GB 안팎. 2코어를 점유하면 그 노드에서 다른 Job이 못 돈다.
  노드가 1대뿐이라 사실상 클러스터 전체를 점유한다. 기능 검증용으로는 충분, 실사용은 증설 전제
- **userns**: 커널은 `apparmor_restrict_unprivileged_userns=1`로 막혀 있으나
  `/etc/apparmor.d/apptainer` 프로파일이 바이너리에 예외를 준다. **판정은 `apptainer exec`로만 한다**
  (`unshare` 테스트는 차단으로 나오며 이는 정상). 호스트 설정을 바꾸지 않는다
- **디스크**: 노드 `/`가 12GB뿐이라 SIF·캐시·`APPTAINER_TMPDIR`을 `/home`으로 돌린다
- **공유 FS 전제**: `connection.json`을 워커가 쓰고 로그인 노드가 읽는다. 홈이 노드 로컬이면
  이 설계는 성립하지 않는다 — 전제 조건으로 문서화
- **대역폭**: 화면 트래픽이 백엔드 파드와 로그인 노드를 모두 통과한다. 세션이 늘면
  전용 릴레이 분리가 필요(그때 `relay_host` 필드 추가). 현 규모에서는 문제 없음
- 고위험 영역: **사용자 impersonation·터널 목적지 결정**. 남의 세션에 붙는 경로가 생기면 안 된다

## 5. 수용 기준 (Acceptance)

- [ ] dev01에서 SIF 빌드 → `/home` 공유 경로에 배치, 두 노드에서 동일 경로로 보인다
- [ ] 노드에서 `apptainer exec`로 Xvnc가 뜨고 포트가 LISTEN 된다
- [ ] 포털에서 데스크톱 세션 제출 → `squeue`에 뜨고 `connection.json`이 생성된다
- [ ] 브라우저에서 MATE 데스크톱 화면이 보이고 마우스·키보드가 동작한다
- [ ] 세션 목록에 상태가 표시되고, 재접속·종료(`scancel`)가 동작한다
- [ ] 남의 세션 ID로 접속 시 거부된다 (소유자 검증 테스트)
- [ ] 터널 목적지가 `login_node`가 아니라 `connection.json`의 node에서 온다 (테스트로 고정)
- [ ] 백엔드 테스트 전체 통과 (레이어링 테스트 포함), 프론트 `vue-tsc` + 빌드 통과

## 6. 승인
- 검토자: 사용자 (2026-08-06 승인)
- 승인일: 2026-08-06
