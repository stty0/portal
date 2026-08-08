# API 목록 — Slurm HPC Portal Backend

FastAPI 라우터로 제공할 REST API 목록(= Swagger/OpenAPI에 노출될 면).
기능 SoT는 [정의서.md](../정의서.md)(U-/A- ID·우선순위), 계층 설계는 [backend-design.md](backend-design.md)·[Architecture.md](Architecture.md).

> **상태(2026-08-07 기준): 구현된 코드와 대조해 갱신함.** 라우터가 실제로 노출하는
> **83개** 엔드포인트가 정본이며, 이 문서는 그것을 반영한다
> (`grep -rhoE '@router\.(get|post|put|patch|delete)\(' app/routers/*.py | wc -l`).
>
> - 취소선 + **미구현** 표기는 **설계에는 있으나 아직 구현되지 않은** 항목이다.
>   지우지 않고 남기는 이유는 로드맵으로서 값이 있기 때문이다.
> - 미구현이 몰려 있는 영역: License(A-LM 전부), 티켓(A-OP-05·U-AC-04),
>   파일 편집(U-FM-03), 파티션 쓰기·점검 모드(A-ND-03·05, 범위 밖), 리포트 내보내기·차지백.
> - 우선순위 열은 정의서 기준(필수=MVP)이며 **구현 여부와 무관하다**.
>
> 정합성은 `portal-verifier` 에이전트가 라우터 데코레이터를 `ast`로 파싱해 이 표와
> 대조하는 방식으로 재확인할 수 있다.

## 공통 규약

| 항목 | 규약 |
|---|---|
| Base URL | `/api/v1` (아래 경로는 모두 이 프리픽스 생략) |
| 인증 | **브라우저는 HttpOnly 쿠키, 기계 클라이언트는 `Authorization: Bearer`.** 자동화는 **API 토큰**(`hpcp_…`, 장수명·폐기 가능)을 같은 Bearer 자리에 넣는다 — 둘 다 같은 액세스 토큰(JWT, **30분**)이고 Redis 세션(`sid`)을 검증한다. 쿠키 인증의 상태 변경 요청은 `X-CSRF-Token` 헤더 필수(`portal_csrf` 쿠키 값) — Bearer는 면제 |
| 세션 갱신 | `POST /auth/refresh` — refresh 토큰(HttpOnly·경로 한정)으로 액세스 토큰 재발급. **refresh도 회전**하며, 쓴 토큰 재사용은 탈취로 보고 거부 |
| 세션 수명 | **유휴 타임아웃**(관리자 설정 `session_timeout_min`, 기본 480분)은 **인증된 요청마다 되감긴다**. 그와 별개로 **절대 상한 14일** — 활동해도 이 시점엔 재로그인. 유휴로 죽은 세션은 refresh 토큰이 살아 있어도 되살아나지 않는다 |
| 권한 표기 | `인증` = 로그인 사용자 전체, `admin:access` = ADMIN 전용(초기 유일 permission). 라우터는 `require_permission("...")` 문법으로 작성 — 향후 `job:cancel` 등 세분화 시 무수정(backend §3.4) |
| 클러스터 스코프 | Slurm 종속 자원은 `/clusters/{cid}/...` (`cid`=Portal DB cluster.id). 클러스터별 독립 slurmdbd |
| Impersonation | Slurm 호출의 대상 사용자명은 **서버가 인증된 본인으로 강제** — 요청 본문으로 받지 않음(backend §2.3) |
| USER 범위 강제 | Job·사용량 등 USER 호출은 본인 소유 데이터로 서버측 필터(관리자는 전체) |
| 오류 형식 | `{ "code": string, "message": string, "detail": any }` + HTTP 상태코드. Slurm 401 → 클러스터 토큰 재등록 안내(backend §2.2) |
| 목록 공통 | `?page=&size=` 페이지네이션, 도메인별 필터 쿼리. 실시간 화면 폴링 주기 ≤30초(C-04) |
| 스트리밍 | (SSE)·(WS) 표기는 Server-Sent Events/WebSocket — Swagger에는 경로만 노출. **WS 인증은 쿠키**(같은 오리진 handshake에 실린다). 기계 클라이언트는 `Authorization` 헤더나 subprotocol `portal.token.<jwt>` |
| 감사 로그 | 모든 제어성 액션(POST/PATCH/DELETE)은 audit_log 기록(C-05) |
| 헬스체크 | `GET /healthz` — `/api/v1` 프리픽스 **밖**이며 인증이 없다. k8s liveness/readiness probe 전용 |

---

## 1. Auth — 인증/세션 (C-01·C-02) `AuthRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/auth/setup-status` | 부트스트랩 필요 여부(`{bootstrap_required: bool}`) — Vue 라우터가 최초 설정 화면/로그인 화면 분기에 사용 | C-02 | 없음(공개) | 필수 |
| POST | `/auth/setup` | 최초 실행 부트스트랩: AD 연결 검증 + seed ADMIN 1명 지정 (1회용 setup 토큰 보호). `bootstrap_required=false`가 된 뒤엔 서버가 하드 거부(재실행 불가) | C-02 | setup 토큰 | 필수 |
| POST | `/auth/login` | AD bind 인증 → JIT 프로비저닝 → 액세스(30분)+refresh(2주) 발급 + Redis 세션 등록. **쿠키와 응답 본문 둘 다** 준다 — SPA는 쿠키를, CLI는 본문을 쓴다 | C-01, A-US-01 | 없음 | 필수 |
| POST | `/auth/refresh` | 액세스 토큰 갱신. refresh는 쿠키 또는 본문으로 받는다. **회전** — 옛 토큰은 즉시 죽는다 | C-01 | refresh 토큰 | 필수 |
| GET | `/me/api-tokens` | 내 API 토큰 목록. **원문은 담기지 않는다** | C-01 | 인증 | 필수 |
| POST | `/me/api-tokens` | API 토큰 발급 — **원문은 이 응답에만** 한 번 나온다(서버에는 sha256만) | C-01 | 인증 | 필수 |
| DELETE | `/me/api-tokens/{id}` | 토큰 폐기. 만료를 기다리지 않고 **즉시** 먹는다 | C-01 | 인증 | 필수 |
| POST | `/auth/logout` | 세션 무효화(Redis revoke) + 쿠키 삭제. refresh도 함께 죽는다 | C-01 | 인증 | 필수 |
| GET | `/auth/me` | 내 정보(username, display_name, role, permissions, 기본 클러스터) | C-02 | 인증 | 필수 |
| POST | `/auth/setup/probe` | 부트스트랩 화면에서 AD 연결만 미리 검증(사용자 조회 전) | C-02 | setup 토큰 | 필수 |

## 2. Users / AD — 사용자·역할·AD 연결 (A-US-01, U-AC-03) `UserRouter` `AdRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/users` | 포털 사용자 목록(검색·role·활성 필터) | A-US-01 | admin:access | 필수 |
| GET | `/users/{guid}` | 사용자 상세(objectGUID 키) | A-US-01 | admin:access | 필수 |
| PATCH | `/users/{guid}` | 역할(role_id) 부여·비활성화(is_active) — AD 신원 필드는 수정 불가 | A-US-01, C-02 | admin:access | 필수 |
| GET | `/ad/connection` | AD 연결 설정 조회(bind 암호 등 Secret 마스킹) | A-US-01 | admin:access | 필수 |
| PUT | `/ad/connection` | AD 연결 설정 등록/수정(Secret은 참조 저장, 재표시 안 함) | A-US-01 | admin:access | 필수 |
| POST | `/ad/connection/test` | AD 연결 테스트(bind·조회) | A-US-01 | admin:access | 필수 |
| POST | `/ad/sync` | AD 동기화 수동 실행(soft delete·GUID 재사용 판별, 분산락) | A-US-01 | admin:access | 필수 |
| ~~GET~~ | ~~`/me/profile`~~ | 내 프로필(AD 신원 read-only + 알림 수신 설정) — **미구현**| U-AC-03 | 인증 | 권장 |
| ~~PUT~~ | ~~`/me/profile`~~ | 알림 수신 설정 변경(Job 이메일·포털 푸시·SMS) — **미구현**| U-AC-03 | 인증 | 권장 |
| ~~GET~~ | ~~`/me/ssh-keys`~~ | 내 SSH 공개키 목록 — **미구현**| U-AC-03 | 인증 | 권장 |
| ~~POST~~ | ~~`/me/ssh-keys`~~ | SSH 공개키 등록 — **미구현**| U-AC-03 | 인증 | 권장 |
| ~~DELETE~~ | ~~`/me/ssh-keys/{id}`~~ | SSH 공개키 삭제 — **미구현**| U-AC-03 | 인증 | 권장 |

## 3. Clusters — 클러스터 등록/연동 (A-CL, C-03) `ClusterRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters` | 클러스터 목록(사용자: 선택용 요약 / 관리자: 설정 포함). `?include_inactive=true`는 관리자에게만 비활성 행을 포함 | C-03 | 인증 | 필수 |
| GET | `/cluster-api-versions` | 등록 폼의 API 버전 선택지. **목록의 단일 출처** — 응답 파싱이 버전에 묶여 있어 늘리려면 코드 변경이 따라온다 | A-CL-02 | admin:access | 필수 |
| POST | `/clusters` | 클러스터 등록(`api_version`은 지원 목록, `auth_method`는 `jwt`만 허용 — munge는 범위 밖). **이름은 받지 않는다** — `alias`(별칭)만 필수이고, `name`은 REST 연결 테스트가 slurm.conf `ClusterName`으로 채운다 | A-CL | admin:access | 필수 |
| GET | `/clusters/{cid}` | 클러스터 상세(Secret 마스킹). `last_health_at`·`last_health_ok`와 자격증명 참조 목록(`credentials`: kind·expires_at, **값 없음**) 포함 | A-CL | admin:access | 필수 |
| PATCH | `/clusters/{cid}` | 수정(별칭·엔드포인트·SSH·홈/이미지 경로·기본 여부). **이름은 수정할 수 없다.** `api_version`·`auth_method`는 등록과 같은 제약을 받는다 | A-CL | admin:access | 필수 |
| DELETE | `/clusters/{cid}` | 삭제(비활성화) | A-CL | admin:access | 필수 |
| DELETE | `/clusters/{cid}/purge` | 완전 삭제. 비활성 + 무참조(감사 로그·세션·공지·기본 클러스터)일 때만 허용, 아니면 409. 자격증명·Secret 실값 동반 파기 | A-CL | admin:access | 권장 |
| PUT | `/clusters/{cid}/credentials` | JWT/SSH 키 등록·교체(kind=SLURM_JWT/SSH_KEY, 무중단 교체) | C-03 | admin:access | 필수 |
| POST | `/clusters/{cid}/test-rest` | slurmrestd 연결 테스트(ping). 성공·실패 모두 `last_health_*`에 기록. **이름은 여기서 정해진다** — 이미 같은 `ClusterName`이 등록돼 있으면 409 | A-CL | admin:access | 필수 |
| ~~POST~~ | ~~`/clusters/{cid}/test-ssh`~~ | 로그인 노드 SSH 연결 테스트 — **미구현**| A-CL | admin:access | 필수 |

## 4. Cluster 현황/대시보드 (U-CL, A-DB) `DashboardRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| ~~GET~~ | ~~`/clusters/{cid}/overview`~~ | 상태·노드 수·idle·GPU 가용 요약 — **미구현**| U-CL-01, A-DB-01 | 인증 | 필수 |
| GET | `/clusters/{cid}/partitions` | 파티션별 idle/alloc·CPU/GPU/메모리 가용 | U-CL-02 | 인증 | 필수 |
| ~~GET~~ | ~~`/clusters/{cid}/queue-stats`~~ | 파티션별 Running/Pending 수·평균 대기시간 — **미구현**| A-DB-03 | admin:access | 필수 |
| GET | `/clusters/{cid}/events` | 노드 down/drain·스케줄러 이상 이벤트 | A-DB-04 | admin:access | 필수 |
| GET | `/clusters/{cid}/metrics` | CPU/GPU/메모리/네트워크 시계열(Prometheus 프록시) | A-DB-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/storage` | **본인 기준** 홈 사용량(df) + quota. tmpfs·/ 같은 무관한 마운트는 제외한다 — top 사용자 집계는 미구현 | A-DB-05, U-FM-01 | 인증 | 권장 |

## 5. Jobs (U-JB, A-JB) `JobRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/jobs` | Job 목록 — USER는 본인만, ADMIN은 전체(+사용자 필터). 상태·파티션·기간·검색 | U-JB-04, A-JB-01 | 인증 | 필수 |
| POST | `/clusters/{cid}/jobs` | Job 제출(폼 파라미터 or 스크립트 → 서버가 스크립트 생성·sbatch). `mode`는 **`form`·`script` 둘뿐이다**(템플릿 제출은 2026-08-07 제거). **`mode=script`는 스크립트가 정본** — `#SBATCH`를 파싱해 REST 속성으로 옮기고, 옮기지 못한 지시자는 `ignored_directives`로 돌려준다. GPU는 `tres_per_node="gres:gpu:N"`(실측), 배열은 `array`, 의존성은 `dependency` | U-JB-01·02 | 인증 | 필수 |
| ~~POST~~ | ~~`/clusters/{cid}/jobs/validate`~~ | 제출 전 검증(연결성·`#SBATCH` 파싱·파티션 권한·walltime 한도) — 기존 서비스 조합, 신규 Slurm 호출 없음. **대기시간 예측·클러스터 추천 미포함**(§미결) — **미구현**| U-JB-01·02 | 인증 | 필수 |
| GET | `/clusters/{cid}/jobs/{job_id}` | 상세(할당 노드·자원·스크립트·작업 디렉토리·대기 사유·예상 시작) | U-JB-05·10·12 | 인증 | 필수 |
| DELETE | `/clusters/{cid}/jobs/{job_id}` | 취소(복수는 반복 호출 or `?ids=`) — USER는 본인 Job만 | U-JB-07, A-JB-02 | 인증 | 필수 |
| POST | `/clusters/{cid}/jobs/{job_id}/resubmit` | 동일 설정 재제출(설정 오버라이드 허용) | U-JB-08 | 인증 | 필수 |
| PATCH | `/clusters/{cid}/jobs/{job_id}` | hold / release / priority 변경 | A-JB-02·03 | admin:access | 필수·권장 |
| ~~GET~~ | ~~`/clusters/{cid}/jobs/{job_id}/logs`~~ | stdout/stderr 실시간 tail (SSE) — **미구현**| U-JB-06 | 인증 | 필수 |
| GET | `/clusters/{cid}/jobs/history` | 완료 Job 이력(sacct — 기간·자원 사용량·종료 코드) | U-JB-09, A-JB-04 | 인증 | 필수 |
| GET | `/clusters/{cid}/job-options` | 제출 폼 선택지(파티션·계정·QOS·`gpu_partitions`) — 폼이 자유 입력 대신 실제 값을 고르게 한다. `gpu_partitions`는 **`null`이면 '모름'**(노드 조회 실패), 빈 배열이면 'GPU 없음' | U-JB-01 | 인증 | 필수 |
| POST | `/clusters/{cid}/jobs/preview-script` | 폼 값으로 생성될 스크립트 미리보기(제출 없음) | U-JB-02 | 인증 | 필수 |

## 6. Nodes / Partitions / Reservations (A-ND) `NodeRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/nodes` | 노드 목록·상태 맵 | A-ND-02, A-DB-01 | admin:access | 필수 |
| ~~GET~~ | ~~`/clusters/{cid}/nodes/{name}`~~ | 노드 상세(스펙·실행 Job·상태 이력) — **미구현**| A-ND-02 | admin:access | 필수 |
| POST | `/clusters/{cid}/nodes/{name}/state` | drain / resume / down / undrain + 사유(reason). **사용자로 위장하지 않는다** — 운영자 권한이 필요해 토큰 소유자로 수행하고 감사 로그가 행위자를 남긴다. `drain`·`down`은 사유 필수 | A-ND-01 | admin:access | 필수 |
| ~~PATCH~~ | ~~`/clusters/{cid}/partitions/{name}`~~ | 파티션 수정 — **범위 밖**. slurmrestd는 **모든 버전에서 파티션 조회만** 연다(실측). `scontrol` + slurm.conf 영속화가 필요해 최소권한 방향과 어긋난다(정의서 §4.1) | A-ND-03 | admin:access | 필수 |
| GET | `/clusters/{cid}/reservations` | 예약 목록 | A-ND-04 | admin:access | 권장 |
| POST | `/clusters/{cid}/reservations` | 예약 생성(점검·전용). **v0.0.43 전용 엔드포인트** — 0.0.40~0.0.42는 조회·삭제만 연다(실측). 숫자는 `{set,infinite,number}` 래퍼로 보낸다. `node_list`/`node_count` 중 하나 필수 | A-ND-04 | admin:access | 권장 |
| DELETE | `/clusters/{cid}/reservations/{name}` | 예약 삭제 | A-ND-04 | admin:access | 권장 |
| ~~POST~~ | ~~`/clusters/{cid}/maintenance`~~ | 점검 모드 — **범위 밖**. 예약(A-ND-04)으로 노드를 잡고 공지(A-OP-01)를 따로 쓰면 같은 일이 된다. 둘을 묶는 편의 하나를 위해 화면·API를 더 두지 않는다 | A-ND-05 | admin:access | 선택 |

## 7. Accounts / QOS / Slurm 사용자 (A-US-02~05) `AccountRouter` `QosRouter`

slurmdbd 대상(= sacctmgr). Portal DB에 미러링하지 않음.

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/accounts` | 계정 목록(+소속 사용자·QOS·share) | A-US-02 | admin:access | 필수 |
| POST | `/clusters/{cid}/accounts` | 계정 생성(허용/기본 QOS·fairshare share 포함) | A-US-02·04 | admin:access | 필수 |
| ~~PATCH~~ | ~~`/clusters/{cid}/accounts/{name}`~~ | 계정 수정(QOS·share) — **미구현**| A-US-02·04 | admin:access | 필수 |
| DELETE | `/clusters/{cid}/accounts/{name}` | 계정 삭제 | A-US-02 | admin:access | 필수 |
| PUT | `/clusters/{cid}/accounts/{name}/qos` | 계정의 허용/기본 QOS 설정 | A-US-02·03 | admin:access | 필수 |
| POST | `/clusters/{cid}/accounts/{name}/users` | 계정에 사용자 추가(association 생성) | A-US-02 | admin:access | 필수 |
| DELETE | `/clusters/{cid}/accounts/{name}/users/{username}` | 계정에서 사용자 제거 | A-US-02 | admin:access | 필수 |
| PUT | `/clusters/{cid}/accounts/{name}/users/{username}/qos` | 사용자별 QOS 지정(association 단위) | A-US-03 | admin:access | 필수 |
| ~~PUT~~ | ~~`/clusters/{cid}/accounts/{name}/users`~~ | 계정↔사용자 N:M 매핑(association 추가/제거) — **미구현**| A-US-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/qos` | QOS 목록 | A-US-03 | admin:access | 필수 |
| POST | `/clusters/{cid}/qos` | QOS 생성(한도·우선순위) | A-US-03 | admin:access | 필수 |
| ~~PATCH~~ | ~~`/clusters/{cid}/qos/{name}`~~ | QOS 수정 — **미구현**| A-US-03 | admin:access | 필수 |
| DELETE | `/clusters/{cid}/qos/{name}` | QOS 삭제 | A-US-03 | admin:access | 필수 |
| ~~PUT~~ | ~~`/clusters/{cid}/slurm-users/{username}/qos`~~ | 사용자 허용/기본 QOS 배정(`sacctmgr modify user set qos+=`) — **미구현**| A-US-03 | admin:access | 필수 |
| ~~GET~~ | ~~`/clusters/{cid}/slurm-users/{username}`~~ | Slurm 사용자 조회(associations·기본 계정/QOS) — **미구현**| A-US-02·03 | admin:access | 필수 |
| ~~PATCH~~ | ~~`/clusters/{cid}/slurm-users/{username}`~~ | 사용자 기준 계정 join/해제(N:M) + 기본 계정(DefaultAccount) 변경 — userEditModal 대응 — **미구현**| A-US-02 | admin:access | 필수 |
| ~~GET~~ | ~~`/clusters/{cid}/partitions/{name}/access`~~ | 파티션 허용 계정/그룹 조회(AllowAccounts) — **미구현**| A-US-05 | admin:access | 권장 |
| ~~PUT~~ | ~~`/clusters/{cid}/partitions/{name}/access`~~ | 파티션 허용 계정 설정 — slurm.conf 반영 + reconfigure(CLI 래핑, §4.1) — **미구현**| A-US-05 | admin:access | 권장 |

## 8. Usage / Reports (U-AC-01·02, A-RP) `UsageRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/me/usage` | 내 기간별 CPU/GPU 시간·Job 수(차트용) | U-AC-01 | 인증 | 필수 |
| GET | `/clusters/{cid}/me/fairshare` | 내 계정 fairshare·QOS 한도/잔여 | U-AC-02 | 인증 | 권장 |
| GET | `/clusters/{cid}/reports/usage` | 기간·사용자·계정·파티션별 사용량. 행마다 `cpu_hours`·`node_hours`·`jobs`·`failed`·`last_active` | A-RP-01 | admin:access | 필수 |
| GET | `/clusters/{cid}/reports/utilization` | 가동률·파티션별 사용률 추이 | A-RP-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/reports/wait-time` | 파티션/QOS별 평균 대기시간 추이 | A-RP-03 | admin:access | 권장 |
| ~~GET~~ | ~~`/clusters/{cid}/reports/export`~~ | CSV/Excel/PDF 내보내기(`?format=`) — **미구현**| A-RP-04 | admin:access | 권장 |
| ~~GET~~ | ~~`/reports/schedule`~~ | 정기 리포트 설정 조회(수신자·주기·형식·범위·활성화) — **미구현**| A-RP-04 | admin:access | 권장 |
| ~~PUT~~ | ~~`/reports/schedule`~~ | 정기 리포트 설정 저장(단일 설정, 배치 발송) — **미구현**| A-RP-04 | admin:access | 권장 |
| ~~GET~~ | ~~`/reports/chargeback/rates`~~ | 과금 요율 조회(CPU 원/core·h, GPU 원/gpu·h) — **미구현**| A-RP-05 | admin:access | 선택 |
| ~~PUT~~ | ~~`/reports/chargeback/rates`~~ | 과금 요율 설정 — **미구현**| A-RP-05 | admin:access | 선택 |
| ~~GET~~ | ~~`/clusters/{cid}/reports/chargeback`~~ | 사용량 × 요율 과금 산출(기간·계정별) — **미구현**| A-RP-05 | admin:access | 선택 |

## 9. Files (U-FM) `FileRouter` — SSH/SFTP 경유

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/files` | 디렉토리 목록(`?path=`). 응답에 `home`·`roots`가 함께 온다 — 별도 locations API가 필요 없다. 홈은 클러스터의 `home_base` + **인증된 본인**의 사용자명이며, 미설정이면 `getent passwd` | U-FM-01 | 인증 | 필수 |
| POST | `/clusters/{cid}/files/upload` | 업로드(multipart `path`=대상 디렉터리 + `file`). SFTP로 **스트리밍**하며 상한은 `file_upload_max_mb`(기본 2048) | U-FM-02 | 인증 | 필수 |
| GET | `/clusters/{cid}/files/download` | 다운로드(`?path=`, SFTP 스트리밍). 디렉터리는 거부 | U-FM-02 | 인증 | 필수 |
| POST | `/clusters/{cid}/files/directory` | 디렉터리 생성(`{path}`) | U-FM-04 | 인증 | 필수 |
| POST | `/clusters/{cid}/files/file` | 빈 파일 생성(`{path}`, 배타 모드 — 덮어쓰지 않음) | U-FM-04 | 인증 | 필수 |
| POST | `/clusters/{cid}/files/move` | 이동·이름 변경(`{path, to}`). 같은 연산이며 목적지가 있으면 실패 | U-FM-04 | 인증 | 필수 |
| DELETE | `/clusters/{cid}/files` | 삭제(`?path=&recursive=`). 비어 있지 않은 디렉터리는 `recursive=true`를 **명시**해야 지워진다 | U-FM-04 | 인증 | 필수 |
| ~~GET/PUT~~ | ~~`/clusters/{cid}/files/content`~~ | **미구현** — U-FM-03 웹 편집기 | U-FM-03 | 인증 | 필수 |

> **경로 관문(구현 규칙)**: 모든 조작은 서버 `realpath`로 정규화한 **뒤에** 허용 루트
> (홈)를 확인한다. 조회 범위와 변경 범위가 같아야 목록에
> 없는 곳을 지울 수 없다. 없는 경로(생성·이동 목적지)는 **부모까지만** 서버에 물어보고
> 마지막 조각의 `..`는 이름 단계에서 막는다. 홈 같은 최상위 자체는 삭제·이동 불가.
> U-FM-04의 **복사·권한 변경·압축/해제는 미구현**이다.

## 10. Terminal / Interactive (U-SH, U-IA) `TerminalRouter` `SessionRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| WS | `/clusters/{cid}/terminal` | 로그인 노드 셸 (WS·PTY, `sudo -n -u <user> -i`) | U-SH-01 | 인증 | 권장 |
| GET | `/interactive-apps` | 앱 카탈로그(id·이름·설명·`fid`·`ready`). **목록의 단일 출처** — 화면이 같은 배열을 따로 갖지 않는다. 어떤 이미지를 쓰는지는 담지 않는다(운영 정보) | U-IA-01 | 인증 | 필수 |
| GET | `/clusters/{cid}/sessions` | 내 인터랙티브 세션 목록(클러스터 스코프) | U-IA-04 | 인증 | 필수 |
| POST | `/clusters/{cid}/sessions` | 세션 실행(`app`=desktop/paraview + 자원 스펙 → slurmrestd 제출). 이미지는 **클러스터의 `image_repository` + 앱 카탈로그의 이미지명**으로 서버가 정한다 — 클라이언트가 지정할 수 없다. 제출 직후는 `PENDING` — 준비되면 `is_running` | U-IA-01·02 | 인증 | 필수 |
| GET | `/sessions/{sid}` | 세션 상태(Slurm Job 상태가 권위 있는 출처) | U-IA-04 | 인증 | 필수 |
| GET | `/sessions/{sid}/connection` | RFB 핸드셰이크용 **비밀번호·해상도만**. **host/port는 응답에 필드 자체가 없다** — 열린 프록시가 되지 않게 | U-IA-02 | 인증(소유자) | 필수 |
| WS | `/sessions/{sid}/connect` | 브라우저 noVNC ↔ 워커 Xvnc RFB 바이트 중계. 토큰은 subprotocol `portal.token.<jwt>`로 전달 | U-IA-02 | 인증(소유자) | 필수 |
| DELETE | `/sessions/{sid}` | 세션 종료(scancel + 대장 상태 변경) | U-IA-04 | 인증(소유자) | 필수 |
| ~~WS~~ | ~~`/clusters/{cid}/terminal/node/{name}`~~ | **미구현** | U-SH-02 | 인증 | 선택 |
| ~~POST~~ | ~~`/sessions/{id}/share`~~ | **미구현** — view-only 공유 | U-IA-05 | 인증 | 선택 |

> 앱 종류는 컨테이너 기동 스크립트의 `PORTAL_APP` 분기로 갈린다(세션·프록시 계층은 공유).
> 현재 `desktop`(MATE)·`paraview`. JupyterLab·VS Code Server(U-IA-01·03)는 미구현.

### 10.1 내부 전용 — **채택하지 않음**

초기 설계는 Job이 host:port를 콜백 보고하고 Traefik이 `dynamic-config`를 폴링해 라우트를
구성하는 방식이었다. **Traefik에는 경로에서 노드·포트를 뽑는 수단이 없어**(OnDemand의
`ProxyPassMatch` 상당물 부재) 백엔드 WebSocket 브리지로 바꿨다(docs/plan.md §3.3).
`/internal/sessions/{id}/ready`·`/internal/sessions/{id}/authorize`·
`/internal/gateway/dynamic-config`는 **구현되지 않았다.**

접속 정보의 유일한 출처는 세션 Job이 워커에 남기는 `connection.json`(공유 홈)이며,
백엔드가 로그인 노드 경유 SFTP로 읽는다.

## 11. Notices / Tickets (U-CL-03, U-AC-04, A-OP-01·05) `ContentRouter`

> Job 템플릿 API 4개(`/templates`)는 **2026-08-07 제거**했다 — 제출 탭(U-JB-03)을 걷어내자
> 등록해도 쓰는 곳이 없어졌다. `job_template` 표도 함께 지웠다(마이그레이션 `0012`).

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/notices` | 공지 목록(배너 활성 포함, `?banner=true`). **포털 전체 대상** — 클러스터로 거르지 않는다 | U-CL-03 | 인증 | 필수 |
| POST | `/notices` | 공지 등록(배너·기간). 대상 클러스터는 **받지 않는다** | A-OP-01 | admin:access | 필수 |
| PATCH | `/notices/{id}` | 공지 수정 | A-OP-01 | admin:access | 필수 |
| DELETE | `/notices/{id}` | 공지 삭제 | A-OP-01 | admin:access | 필수 |
| ~~GET~~ | ~~`/tickets`~~ | 티켓 목록 — USER 본인, ADMIN 전체 — **미구현**| U-AC-04, A-OP-05 | 인증 | 선택 |
| ~~POST~~ | ~~`/tickets`~~ | 티켓 제출(Job ID 자동 첨부) — **미구현**| U-AC-04 | 인증 | 선택 |
| ~~PATCH~~ | ~~`/tickets/{id}`~~ | 응답/상태 변경(담당자 배정) — **미구현**| A-OP-05 | admin:access | 선택 |

## 12. Billing (A-BL) `BillingRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/billing/config` | SCP Billing API 연동 설정 조회(Secret Key 재표시 안 함) | A-BL-01 | admin:access | 필수 |
| PUT | `/billing/config` | 연동 설정 등록/수정 | A-BL-01 | admin:access | 필수 |
| ~~POST~~ | ~~`/billing/config/verify`~~ | 연결 확인 — **미구현**| A-BL-01 | admin:access | 필수 |
| GET | `/billing/rules` | 자원 식별 규칙 목록(Tag/Type) | A-BL-02 | admin:access | 필수 |
| POST | `/billing/rules` | 규칙 추가 | A-BL-02 | admin:access | 필수 |
| ~~PATCH~~ | ~~`/billing/rules/{id}`~~ | 규칙 수정(활성·순서) — **미구현**| A-BL-02 | admin:access | 필수 |
| DELETE | `/billing/rules/{id}` | 규칙 삭제 | A-BL-02 | admin:access | 필수 |
| ~~GET~~ | ~~`/billing/summary`~~ | 기간 요약(`?period=YYYY-MM`) — **미구현**| A-BL-03 | admin:access | 필수 |
| GET | `/billing/trend` | 추이·Tag별 집계(snapshot 기반) | A-BL-03·04 | admin:access | 필수 |

## 13. License (A-LM) `LicenseRouter`

> A-LM-01·02·05는 `LicenseClient`가 백엔드에서 FlexLM 벤더 서버로 **직접 TCP 접속**(SSH 아님, 클러스터 무관). A-LM-03만 예외로 **대상 클러스터**의 `SlurmrestdClient`(REST/CLI 폴백)를 사용 — `cluster_id`를 지정해야 함.

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| ~~GET~~ | ~~`/license/servers`~~ | 라이선스 서버 목록 — **미구현**| A-LM-01 | admin:access | 필수 |
| ~~POST~~ | ~~`/license/servers`~~ | 서버 등록(host/port·벤더 데몬) — **미구현**| A-LM-01 | admin:access | 필수 |
| ~~PATCH~~ | ~~`/license/servers/{id}`~~ | 서버 수정 — **미구현**| A-LM-01 | admin:access | 필수 |
| ~~DELETE~~ | ~~`/license/servers/{id}`~~ | 서버 삭제 — **미구현**| A-LM-01 | admin:access | 필수 |
| ~~POST~~ | ~~`/license/servers/{id}/test`~~ | 연결 테스트(lmstat 직접 접속) — **미구현**| A-LM-01 | admin:access | 필수 |
| ~~GET~~ | ~~`/license/features`~~ | Feature별 총/사용/가용(수집 스냅샷) — **미구현**| A-LM-02 | admin:access | 필수 |
| ~~GET~~ | ~~`/license/features/{name}/usage`~~ | 체크아웃 현황(사용자·Job 매핑) — **미구현**| A-LM-05 | admin:access | 권장 |
| ~~POST~~ | ~~`/license/servers/{id}/sync-slurm`~~ | 가용 수량 → **지정 클러스터**(`cluster_id`)의 Slurm license 리소스 반영 — **미구현**| A-LM-03 | admin:access | 권장 |

## 14. 운영 설정 / 감사 (A-OP-03·04) `SettingRouter` `AuditRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/settings` | 포털 설정(폴링 주기·세션 타임아웃·SMTP/웹훅) | A-OP-04 | admin:access | 권장 |
| PUT | `/settings` | 포털 설정 수정 | A-OP-04 | admin:access | 권장 |
| GET | `/audit-logs` | 감사 로그 조회(기간·행위자·액션·클러스터 필터) | A-OP-03, C-05 | admin:access | 필수 |
| GET | `/audit-logs/actions` | 필터 드롭다운용 액션 종류 목록 | A-OP-03 | admin:access | 필수 |

---

## 미결/구현 시 확정
- U-JB-11(Job 알림)·A-LM-04(부족 알림): 알림 채널(Slurm mail vs 포털 인앱) 확정 후 엔드포인트 추가 — 수신 설정은 `/me/profile`에 선반영.
- ~~GPU 요청·배열 잡·의존성~~ — **2026-08-08 구현.** `tres_per_node`의 문자열 형식은
  `gres:gpu:N`으로 실측 확정했다(`gpu:N`은 TRES 파서가 거부). 다만 **GPU 노드가 없어
  "형식이 맞다"까지만 확인됐다** — 실제 할당은 L40 도입 후 재확인 →
  [gpu-simulation.md](gpu-simulation.md).
- A-US-06(자원 신청 승인): 선택 기능 — 수요 확인 후 설계. QOS 화면에 두었던 **빈 자리표시자
  카드는 제거**했다(2026-08-07) — 만들 것이 정해지지 않은 자리를 화면에 두면 "곧 된다"는
  잘못된 기대를 준다. 요구사항은 정의서 A-US-06에 남아 있다.
- **결정됨**: 업로드 한도는 `file_upload_max_mb`(기본 2048), WS 인증은 **subprotocol** `portal.token.<jwt>`(헤더를 못 붙이는 브라우저 WebSocket 제약 때문). **이어받기는 미구현** — 대용량은 scp/rsync를 권한다.
- **U-JB-12(예상 시작시간)**: `sbatch --test-only` 상당 기능이 slurmrestd v0.0.41 REST에 있는지 **미확인**. 있으면 `JobService.validate()`에 포함, 없으면 REST 미지원 폴백 원칙대로 CLI(SSH) 래핑. 확인 전까지 `/jobs/validate` 응답에 미포함.
- **클러스터 간 비교 추천**(job-submit.html의 "다른 클러스터가 더 빠릅니다" 제안): "운영 화면은 선택된 클러스터로 스코프" 원칙과 배치되어 **포함 여부 보류** — 재검토 후 별도 API 설계.
- ~~`/internal/gateway/dynamic-config` 보호 방식·Traefik 폴링 주기~~ — **해당 없음**(게이트웨이 미채택). 대신 미결로 남은 것은 **로그인 노드 → 워커 구간이 평문**이라는 점이다(세션 RFB). 현재는 두 노드가 같은 기계라 loopback이며, 분리 전에 재검토한다 → [session-transport-security.md](session-transport-security.md).
- OpenAPI 스키마(요청/응답 Pydantic 모델)는 `schemas/`에서 정의 — 본 문서는 경로·권한·기능 매핑의 SoT.
