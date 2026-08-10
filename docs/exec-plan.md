# Exec Plan: 인터랙티브 앱 — 원격 데스크톱 (SCR-06)

- 근거 plan: [docs/plan.md](plan.md)
- 담당: 구현·검증 Claude
- 이전 에픽 exec-plan은 git 이력 참조

> **상태: T-01~T-08 전부 완료.** 실 클러스터 검증까지 마쳤고 결과는
> [progress.md](progress.md)에 있다. 아래 수용 기준은 충족 확인된 것이다.

## Task 목록

### T-01 Rocky 9 + MATE + TigerVNC 이미지
- 대상 파일: `deploy/images/rocky9-mate/Dockerfile`, `deploy/images/rocky9-mate/start-desktop.sh`, `deploy/images/rocky9-mate/README.md`
- 내용: EPEL9 + MATE + TigerVNC(`tigervnc-server`) 설치. `start-desktop.sh`가 Xvnc를
  기동하고 MATE 세션을 붙인다. dev01에 apptainer 설치 후 `docker-daemon://`로 SIF 빌드,
  `/home/portal/images/rocky9-mate-1.0.sif` 배치. **버전을 파일명에 박는다**(실행 중 세션이 mmap)
- 의존성: 없음
- 수용 기준:
  - [x] dev01에서 SIF 빌드 성공, 두 노드에서 같은 경로로 보인다
  - [x] 노드에서 `apptainer exec`로 Xvnc 기동, 포트 LISTEN 확인
  - [x] `/etc/machine-id` 등 쓰기 필요 경로가 `--writable-tmpfs`로 해결된다
- 검증: 노드에서 수동 실행 → `ss -ltn`으로 포트 확인
- 위험도: 중간 (노드 디스크 12GB, TMPDIR 유도 필요)

### T-02 세션 Job 스크립트 + connection.json 규약
- 대상 파일: `backend/app/services/session_script.py`, `backend/tests/test_session_script.py`
- 내용: sbatch 스크립트 생성. 빈 display를 **vncserver가 직접 고르게** 하고 그 결과를 읽어
  기록한다(사전 probe 후 bind는 경쟁 발생). 랜덤 VNC 비밀번호 + view-only 비밀번호 발급.
  `connection.json`에 `node`($SLURMD_NODENAME)·`ip`·`port`·`password`·`view_password`·`app`·`started_at`
- 의존성: T-01
- 수용 기준:
  - [x] 폼 값이 `#SBATCH` 지시자로 들어간다 (Job 제출과 동일 규칙)
  - [x] 세션 디렉터리 권한 700
  - [x] 수동 sbatch로 connection.json 생성 + 포트 LISTEN 확인
- 검증: 단위 테스트 + 실 클러스터 수동 제출
- 위험도: 중간

### T-03 DB 모델 · 마이그레이션
- 대상 파일: `backend/app/models/session.py`, `backend/app/models/cluster.py`, `backend/alembic/versions/*`, `backend/app/repositories/session.py`
- 내용: `interactive_session`(cluster_id, user_id, app, job_id, state, created_at, ended_at).
  `cluster.desktop_image_ref` 컬럼 추가. **포트·비밀번호는 저장하지 않는다** — connection.json이 유일한 출처
- 의존성: 없음
- 수용 기준:
  - [x] 마이그레이션 up/down 동작
  - [x] 컨테이너(Python 3.13)에서 import 검증 — `from __future__ import annotations` 확인
- 검증: `alembic upgrade head` + `docker run ... python -c "import app.main"`
- 위험도: 낮음

### T-04 SessionService
- 대상 파일: `backend/app/services/session.py`, `backend/tests/test_session_service.py`
- 내용: 제출(sbatch)·목록·상태·종료(scancel). `connection.json`을 SFTP(`sudo -u user`)로 읽는다.
  **대상 사용자는 언제나 요청자 본인**(FileService와 같은 원칙). 소유자 검증
- 의존성: T-02, T-03
- 수용 기준:
  - [x] 남의 세션 조회/종료 시 거부
  - [x] Job 상태 → 세션 상태 매핑(PENDING/RUNNING/종료)
  - [x] connection.json 미생성 시 "준비 중"으로 구분
- 검증: 단위 테스트
- 위험도: **고위험** (impersonation·소유자 검증)

### T-05 SSH direct-tcpip 터널 스트림
- 대상 파일: `backend/app/clients/ssh/tunnel.py`, `backend/tests/test_ssh_tunnel.py`
- 내용: 로그인 노드에 접속해 `open_channel("direct-tcpip", (worker, port), ...)`.
  전송 계층을 인터페이스 하나로 뽑아 2단 SSH 교체 여지를 남긴다.
  **목적지는 인자로만 받고 login_node에서 유도하지 않는다**
- 의존성: 없음
- 수용 기준:
  - [x] 목적지 ≠ login_node 케이스가 테스트로 고정된다
  - [x] 비차단 read/write (PtySession과 동일 패턴)
- 검증: 단위 테스트 + 실 노드 릴레이 (검증 완료: slurm01 경유 → .202:22 도달)
- 위험도: **고위험** (터널 목적지 결정)

### T-06 세션 REST + WS 브리지 라우터
- 대상 파일: `backend/app/routers/sessions.py`, `backend/app/schemas/session.py`, `backend/app/main.py`, `backend/tests/test_sessions.py`
- 내용: `POST/GET/DELETE /clusters/{cid}/sessions`, `WS /sessions/{sid}/connect`.
  라우터는 프레임만 다루고 인증·터널은 서비스가 갖는다(레이어링 테스트)
- 의존성: T-04, T-05
- 수용 기준:
  - [x] WS 인증 동작 (당시 subprotocol → 2026-08-08 쿠키로 전환)
  - [x] 레이어링 테스트 통과
- 검증: 단위 테스트
- 위험도: 중간

### T-07 프론트 — 앱 런처 · 세션 목록 · noVNC 뷰
- 대상 파일: `frontend/src/views/user/AppsView.vue`, `frontend/src/views/user/DesktopView.vue`, `frontend/src/api/sessions.ts`, `frontend/src/router/index.ts`, `frontend/package.json`
- 내용: `@novnc/novnc` 의존성 추가. `RFB`를 WS에 붙인다. 런처(U-IA-01)·세션 목록(U-IA-04)·
  데스크톱 화면. `staticOnly: true` 제거. `<Fid>` 매핑 유지
- 의존성: T-06
- 수용 기준:
  - [x] `vue-tsc` + 빌드 통과
  - [x] 자원 폼 → 제출 → 세션 목록 → 접속 흐름이 화면에서 완결
- 검증: 빌드 + 배포 후 실사용
- 위험도: 중간

### T-08 실 클러스터 통합 검증
- 대상 파일: `docs/progress.md`
- 내용: 실제 데스크톱 세션 제출·접속·종료. plan §5 수용 기준 전수 확인
- 의존성: T-07
- 수용 기준:
  - [x] plan §5 항목 전부 통과
  - [x] 백엔드 테스트 전체 통과
- 검증: 실 클러스터 E2E
- 위험도: 중간

## 실행 순서

```
T-01 ─┬─ T-02 ─┐
      │        ├─ T-04 ─┐
T-03 ─┴────────┘        ├─ T-06 ─ T-07 ─ T-08
T-05 ───────────────────┘
```

T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08 순으로 진행한다.
