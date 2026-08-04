# API 목록 — Slurm HPC Portal Backend

FastAPI 라우터로 제공할 REST API 목록(= Swagger/OpenAPI에 노출될 면).
기능 SoT는 [정의서.md](../정의서.md)(U-/A- ID·우선순위), 계층 설계는 [backend-design.md](backend-design.md)·[Architecture.md](Architecture.md).

> 상태: 설계(구현 전). 경로·스키마는 구현 시 확정하며, 우선순위는 정의서 기준(필수=MVP).

## 공통 규약

| 항목 | 규약 |
|---|---|
| Base URL | `/api/v1` (아래 경로는 모두 이 프리픽스 생략) |
| 인증 | `Authorization: Bearer <포털 세션 JWT>` — 로그인(AD bind) 시 발급, Redis 세션 검증(backend §4) |
| 권한 표기 | `인증` = 로그인 사용자 전체, `admin:access` = ADMIN 전용(초기 유일 permission). 라우터는 `require_permission("...")` 문법으로 작성 — 향후 `job:cancel` 등 세분화 시 무수정(backend §3.4) |
| 클러스터 스코프 | Slurm 종속 자원은 `/clusters/{cid}/...` (`cid`=Portal DB cluster.id). 클러스터별 독립 slurmdbd |
| Impersonation | Slurm 호출의 대상 사용자명은 **서버가 인증된 본인으로 강제** — 요청 본문으로 받지 않음(backend §2.3) |
| USER 범위 강제 | Job·사용량 등 USER 호출은 본인 소유 데이터로 서버측 필터(관리자는 전체) |
| 오류 형식 | `{ "code": string, "message": string, "detail": any }` + HTTP 상태코드. Slurm 401 → 클러스터 토큰 재등록 안내(backend §2.2) |
| 목록 공통 | `?page=&size=` 페이지네이션, 도메인별 필터 쿼리. 실시간 화면 폴링 주기 ≤30초(C-04) |
| 스트리밍 | (SSE)·(WS) 표기는 Server-Sent Events/WebSocket — Swagger에는 경로만 노출 |
| 감사 로그 | 모든 제어성 액션(POST/PATCH/DELETE)은 audit_log 기록(C-05) |

---

## 1. Auth — 인증/세션 (C-01·C-02) `AuthRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/auth/setup-status` | 부트스트랩 필요 여부(`{bootstrap_required: bool}`) — Vue 라우터가 최초 설정 화면/로그인 화면 분기에 사용 | C-02 | 없음(공개) | 필수 |
| POST | `/auth/setup` | 최초 실행 부트스트랩: AD 연결 검증 + seed ADMIN 1명 지정 (1회용 setup 토큰 보호). `bootstrap_required=false`가 된 뒤엔 서버가 하드 거부(재실행 불가) | C-02 | setup 토큰 | 필수 |
| POST | `/auth/login` | AD bind 인증 → JIT 프로비저닝 → 포털 JWT 발급 + Redis 세션 등록 | C-01, A-US-01 | 없음 | 필수 |
| POST | `/auth/logout` | 세션 무효화(Redis revoke) | C-01 | 인증 | 필수 |
| GET | `/auth/me` | 내 정보(username, display_name, role, permissions, 기본 클러스터) | C-02 | 인증 | 필수 |

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
| GET | `/me/profile` | 내 프로필(AD 신원 read-only + 알림 수신 설정) | U-AC-03 | 인증 | 권장 |
| PUT | `/me/profile` | 알림 수신 설정 변경(Job 이메일·포털 푸시·SMS) | U-AC-03 | 인증 | 권장 |
| GET | `/me/ssh-keys` | 내 SSH 공개키 목록 | U-AC-03 | 인증 | 권장 |
| POST | `/me/ssh-keys` | SSH 공개키 등록 | U-AC-03 | 인증 | 권장 |
| DELETE | `/me/ssh-keys/{id}` | SSH 공개키 삭제 | U-AC-03 | 인증 | 권장 |

## 3. Clusters — 클러스터 등록/연동 (A-CL, C-03) `ClusterRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters` | 클러스터 목록(사용자: 선택용 요약 / 관리자: 설정 포함) | C-03 | 인증 | 필수 |
| POST | `/clusters` | 클러스터 등록(이름은 slurmrestd에서 자동 조회) | A-CL | admin:access | 필수 |
| GET | `/clusters/{cid}` | 클러스터 상세(Secret 마스킹) | A-CL | admin:access | 필수 |
| PATCH | `/clusters/{cid}` | 수정(엔드포인트·SSH·경로 템플릿·기본 여부) | A-CL | admin:access | 필수 |
| DELETE | `/clusters/{cid}` | 삭제(비활성화) | A-CL | admin:access | 필수 |
| PUT | `/clusters/{cid}/credentials` | JWT/SSH 키 등록·교체(kind=SLURM_JWT/SSH_KEY, 무중단 교체) | C-03 | admin:access | 필수 |
| POST | `/clusters/{cid}/test-rest` | slurmrestd 연결 테스트(ping) | A-CL | admin:access | 필수 |
| POST | `/clusters/{cid}/test-ssh` | 로그인 노드 SSH 연결 테스트 | A-CL | admin:access | 필수 |

## 4. Cluster 현황/대시보드 (U-CL, A-DB) `DashboardRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/overview` | 상태·노드 수·idle·GPU 가용 요약 | U-CL-01, A-DB-01 | 인증 | 필수 |
| GET | `/clusters/{cid}/partitions` | 파티션별 idle/alloc·CPU/GPU/메모리 가용 | U-CL-02 | 인증 | 필수 |
| GET | `/clusters/{cid}/queue-stats` | 파티션별 Running/Pending 수·평균 대기시간 | A-DB-03 | admin:access | 필수 |
| GET | `/clusters/{cid}/events` | 노드 down/drain·스케줄러 이상 이벤트 | A-DB-04 | admin:access | 필수 |
| GET | `/clusters/{cid}/metrics` | CPU/GPU/메모리/네트워크 시계열(Prometheus 프록시) | A-DB-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/storage` | 파일시스템 사용률·top 사용자(df/quota) | A-DB-05 | admin:access | 권장 |

## 5. Jobs (U-JB, A-JB) `JobRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/jobs` | Job 목록 — USER는 본인만, ADMIN은 전체(+사용자 필터). 상태·파티션·기간·검색 | U-JB-04, A-JB-01 | 인증 | 필수 |
| POST | `/clusters/{cid}/jobs` | Job 제출(폼 파라미터 or 스크립트 or 템플릿+파라미터 → 서버가 스크립트 생성·sbatch) | U-JB-01·02·03 | 인증 | 필수 |
| POST | `/clusters/{cid}/jobs/validate` | 제출 전 검증(연결성·`#SBATCH` 파싱·파티션 권한·walltime 한도) — 기존 서비스 조합, 신규 Slurm 호출 없음. **대기시간 예측·클러스터 추천 미포함**(§미결) | U-JB-01·02·03 | 인증 | 필수 |
| GET | `/clusters/{cid}/jobs/{job_id}` | 상세(할당 노드·자원·스크립트·작업 디렉토리·대기 사유·예상 시작) | U-JB-05·10·12 | 인증 | 필수 |
| DELETE | `/clusters/{cid}/jobs/{job_id}` | 취소(복수는 반복 호출 or `?ids=`) — USER는 본인 Job만 | U-JB-07, A-JB-02 | 인증 | 필수 |
| POST | `/clusters/{cid}/jobs/{job_id}/resubmit` | 동일 설정 재제출(설정 오버라이드 허용) | U-JB-08 | 인증 | 필수 |
| PATCH | `/clusters/{cid}/jobs/{job_id}` | hold / release / priority 변경 | A-JB-02·03 | admin:access | 필수·권장 |
| GET | `/clusters/{cid}/jobs/{job_id}/logs` | stdout/stderr 실시간 tail (SSE) | U-JB-06 | 인증 | 필수 |
| GET | `/clusters/{cid}/jobs/history` | 완료 Job 이력(sacct — 기간·자원 사용량·종료 코드) | U-JB-09, A-JB-04 | 인증 | 필수 |

## 6. Nodes / Partitions / Reservations (A-ND) `NodeRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/nodes` | 노드 목록·상태 맵 | A-ND-02, A-DB-01 | admin:access | 필수 |
| GET | `/clusters/{cid}/nodes/{name}` | 노드 상세(스펙·실행 Job·상태 이력) | A-ND-02 | admin:access | 필수 |
| POST | `/clusters/{cid}/nodes/{name}/state` | drain / resume / down + 사유(reason) | A-ND-01 | admin:access | 필수 |
| PATCH | `/clusters/{cid}/partitions/{name}` | 파티션 수정(REST update — slurm.conf 영속화는 별도, §4.1) | A-ND-03 | admin:access | 필수 |
| GET | `/clusters/{cid}/reservations` | 예약 목록 | A-ND-04 | admin:access | 권장 |
| POST | `/clusters/{cid}/reservations` | 예약 생성(점검·전용) | A-ND-04 | admin:access | 권장 |
| DELETE | `/clusters/{cid}/reservations/{name}` | 예약 삭제 | A-ND-04 | admin:access | 권장 |
| POST | `/clusters/{cid}/maintenance` | 점검 모드(공지 등록 + 대상 노드 일괄 drain 워크플로) | A-ND-05 | admin:access | 선택 |

## 7. Accounts / QOS / Slurm 사용자 (A-US-02~05) `AccountRouter` `QosRouter`

slurmdbd 대상(= sacctmgr). Portal DB에 미러링하지 않음.

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/accounts` | 계정 목록(+소속 사용자·QOS·share) | A-US-02 | admin:access | 필수 |
| POST | `/clusters/{cid}/accounts` | 계정 생성(허용/기본 QOS·fairshare share 포함) | A-US-02·04 | admin:access | 필수 |
| PATCH | `/clusters/{cid}/accounts/{name}` | 계정 수정(QOS·share) | A-US-02·04 | admin:access | 필수 |
| DELETE | `/clusters/{cid}/accounts/{name}` | 계정 삭제 | A-US-02 | admin:access | 필수 |
| PUT | `/clusters/{cid}/accounts/{name}/users` | 계정↔사용자 N:M 매핑(association 추가/제거) | A-US-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/qos` | QOS 목록 | A-US-03 | admin:access | 필수 |
| POST | `/clusters/{cid}/qos` | QOS 생성(한도·우선순위) | A-US-03 | admin:access | 필수 |
| PATCH | `/clusters/{cid}/qos/{name}` | QOS 수정 | A-US-03 | admin:access | 필수 |
| DELETE | `/clusters/{cid}/qos/{name}` | QOS 삭제 | A-US-03 | admin:access | 필수 |
| PUT | `/clusters/{cid}/slurm-users/{username}/qos` | 사용자 허용/기본 QOS 배정(`sacctmgr modify user set qos+=`) | A-US-03 | admin:access | 필수 |
| GET | `/clusters/{cid}/slurm-users/{username}` | Slurm 사용자 조회(associations·기본 계정/QOS) | A-US-02·03 | admin:access | 필수 |
| PATCH | `/clusters/{cid}/slurm-users/{username}` | 사용자 기준 계정 join/해제(N:M) + 기본 계정(DefaultAccount) 변경 — userEditModal 대응 | A-US-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/partitions/{name}/access` | 파티션 허용 계정/그룹 조회(AllowAccounts) | A-US-05 | admin:access | 권장 |
| PUT | `/clusters/{cid}/partitions/{name}/access` | 파티션 허용 계정 설정 — slurm.conf 반영 + reconfigure(CLI 래핑, §4.1) | A-US-05 | admin:access | 권장 |

## 8. Usage / Reports (U-AC-01·02, A-RP) `UsageRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/me/usage` | 내 기간별 CPU/GPU 시간·Job 수(차트용) | U-AC-01 | 인증 | 필수 |
| GET | `/clusters/{cid}/me/fairshare` | 내 계정 fairshare·QOS 한도/잔여 | U-AC-02 | 인증 | 권장 |
| GET | `/clusters/{cid}/reports/usage` | 기간·사용자·계정별 사용량 리포트(sreport) | A-RP-01 | admin:access | 필수 |
| GET | `/clusters/{cid}/reports/utilization` | 가동률·파티션별 사용률 추이 | A-RP-02 | admin:access | 필수 |
| GET | `/clusters/{cid}/reports/wait-time` | 파티션/QOS별 평균 대기시간 추이 | A-RP-03 | admin:access | 권장 |
| GET | `/clusters/{cid}/reports/export` | CSV/Excel/PDF 내보내기(`?format=`) | A-RP-04 | admin:access | 권장 |
| GET | `/reports/schedule` | 정기 리포트 설정 조회(수신자·주기·형식·범위·활성화) | A-RP-04 | admin:access | 권장 |
| PUT | `/reports/schedule` | 정기 리포트 설정 저장(단일 설정, 배치 발송) | A-RP-04 | admin:access | 권장 |
| GET | `/reports/chargeback/rates` | 과금 요율 조회(CPU 원/core·h, GPU 원/gpu·h) | A-RP-05 | admin:access | 선택 |
| PUT | `/reports/chargeback/rates` | 과금 요율 설정 | A-RP-05 | admin:access | 선택 |
| GET | `/clusters/{cid}/reports/chargeback` | 사용량 × 요율 과금 산출(기간·계정별) | A-RP-05 | admin:access | 선택 |

## 9. Files (U-FM) `FileRouter` — SSH/SFTP 경유

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/clusters/{cid}/files/locations` | 바로가기 경로(home=SSSD 자동, group/scratch=템플릿 치환) | U-FM-01, §4.1 | 인증 | 필수 |
| GET | `/clusters/{cid}/files` | 디렉토리 목록(`?path=`, 정렬·검색) | U-FM-01 | 인증 | 필수 |
| POST | `/clusters/{cid}/files/upload` | 업로드(multipart → SFTP) | U-FM-02 | 인증 | 필수 |
| GET | `/clusters/{cid}/files/download` | 다운로드(`?path=`, SFTP 스트리밍) | U-FM-02 | 인증 | 필수 |
| GET | `/clusters/{cid}/files/content` | 텍스트 파일 내용(에디터용) | U-FM-03 | 인증 | 필수 |
| PUT | `/clusters/{cid}/files/content` | 텍스트 파일 저장 | U-FM-03 | 인증 | 필수 |
| POST | `/clusters/{cid}/files/op` | 복사/이동/삭제/이름변경/권한변경/압축/해제(`{op, src, dst}`) | U-FM-04 | 인증 | 필수 |

## 10. Terminal / Interactive (U-SH, U-IA) `TerminalRouter` `SessionRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| WS | `/clusters/{cid}/terminal` | 로그인 노드 셸 (WS·PTY, 본인 계정 impersonation) | U-SH-01 | 인증 | 권장 |
| WS | `/clusters/{cid}/terminal/node/{name}` | 본인 Job 실행 중 컴퓨트 노드 접속 | U-SH-02 | 인증 | 선택 |
| GET | `/sessions` | 내 인터랙티브 세션 목록 | U-IA-04 | 인증 | 필수 |
| POST | `/sessions` | 세션 실행(app_type=jupyter/vnc/code-server + 자원 스펙 → sbatch). `connect_url`은 Job이 준비 콜백(내부 API)을 보낸 뒤에야 채워짐(즉시 반환 안 됨 — `status: starting`) | U-IA-01~03 | 인증 | 필수·권장 |
| GET | `/sessions/{id}` | 세션 상태·접속 정보(connect_url, Traefik 동적 라우트) | U-IA-04 | 인증 | 필수 |
| DELETE | `/sessions/{id}` | 세션 종료(scancel + 상태 변경 — Traefik 라우트는 다음 폴링에 자연 소멸, 명시적 삭제 호출 없음) | U-IA-04 | 인증 | 필수 |
| POST | `/sessions/{id}/share` | View-only 공유 링크 발급(같은 라우트에 view 스코프 프록시 토큰) | U-IA-05 | 인증 | 선택 |

### 10.1 내부 전용 (Swagger 비노출, `include_in_schema=False`)
| Method | Path | 설명 | 인증 |
|---|---|---|---|
| POST | `/internal/sessions/{id}/ready` | Job(sbatch)이 자신의 `host`/`port`를 보고 — 백엔드가 `interactive_session.node_host/node_port`에 기록(DB 갱신만, 라우트 push 없음) | Job 전용 1회성 토큰(제출 시 env 주입) |
| GET | `/internal/sessions/{id}/authorize` | Traefik `forwardAuth` Middleware 대상 — 프록시 토큰(full/view 스코프) 검증 | 프록시 토큰(쿼리) |
| GET | `/internal/gateway/dynamic-config` | **Traefik HTTP provider가 주기 폴링**하는 대상 — 상태=running인 세션 전체를 라우터/서비스(`url: http://{node_host}:{node_port}`)로 조합해 반환. K8s API·RBAC 불필요(pull 방식) | 공유 시크릿 헤더 또는 네트워크 정책(Traefik만 접근) |

## 11. Templates / Notices / Tickets (U-JB-03, U-CL-03, U-AC-04, A-OP-01·02·05) `ContentRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/templates` | 템플릿 목록(공개 + 내 것) | U-JB-03 | 인증 | 필수 |
| POST | `/templates` | 템플릿 등록(버전·파라미터 정의) | A-OP-02 | admin:access | 필수 |
| PATCH | `/templates/{id}` | 템플릿 수정 | A-OP-02 | admin:access | 필수 |
| DELETE | `/templates/{id}` | 템플릿 삭제 | A-OP-02 | admin:access | 필수 |
| GET | `/notices` | 공지 목록(배너 활성 포함, `?banner=true`) | U-CL-03 | 인증 | 필수 |
| POST | `/notices` | 공지 등록(대상 클러스터·배너·기간) | A-OP-01 | admin:access | 필수 |
| PATCH | `/notices/{id}` | 공지 수정 | A-OP-01 | admin:access | 필수 |
| DELETE | `/notices/{id}` | 공지 삭제 | A-OP-01 | admin:access | 필수 |
| GET | `/tickets` | 티켓 목록 — USER 본인, ADMIN 전체 | U-AC-04, A-OP-05 | 인증 | 선택 |
| POST | `/tickets` | 티켓 제출(Job ID 자동 첨부) | U-AC-04 | 인증 | 선택 |
| PATCH | `/tickets/{id}` | 응답/상태 변경(담당자 배정) | A-OP-05 | admin:access | 선택 |

## 12. Billing (A-BL) `BillingRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/billing/config` | SCP Billing API 연동 설정 조회(Secret Key 재표시 안 함) | A-BL-01 | admin:access | 필수 |
| PUT | `/billing/config` | 연동 설정 등록/수정 | A-BL-01 | admin:access | 필수 |
| POST | `/billing/config/verify` | 연결 확인 | A-BL-01 | admin:access | 필수 |
| GET | `/billing/rules` | 자원 식별 규칙 목록(Tag/Type) | A-BL-02 | admin:access | 필수 |
| POST | `/billing/rules` | 규칙 추가 | A-BL-02 | admin:access | 필수 |
| PATCH | `/billing/rules/{id}` | 규칙 수정(활성·순서) | A-BL-02 | admin:access | 필수 |
| DELETE | `/billing/rules/{id}` | 규칙 삭제 | A-BL-02 | admin:access | 필수 |
| GET | `/billing/summary` | 기간 요약(`?period=YYYY-MM`) | A-BL-03 | admin:access | 필수 |
| GET | `/billing/trend` | 추이·Tag별 집계(snapshot 기반) | A-BL-03·04 | admin:access | 필수 |

## 13. License (A-LM) `LicenseRouter`

> A-LM-01·02·05는 `LicenseClient`가 백엔드에서 FlexLM 벤더 서버로 **직접 TCP 접속**(SSH 아님, 클러스터 무관). A-LM-03만 예외로 **대상 클러스터**의 `SlurmrestdClient`(REST/CLI 폴백)를 사용 — `cluster_id`를 지정해야 함.

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/license/servers` | 라이선스 서버 목록 | A-LM-01 | admin:access | 필수 |
| POST | `/license/servers` | 서버 등록(host/port·벤더 데몬) | A-LM-01 | admin:access | 필수 |
| PATCH | `/license/servers/{id}` | 서버 수정 | A-LM-01 | admin:access | 필수 |
| DELETE | `/license/servers/{id}` | 서버 삭제 | A-LM-01 | admin:access | 필수 |
| POST | `/license/servers/{id}/test` | 연결 테스트(lmstat 직접 접속) | A-LM-01 | admin:access | 필수 |
| GET | `/license/features` | Feature별 총/사용/가용(수집 스냅샷) | A-LM-02 | admin:access | 필수 |
| GET | `/license/features/{name}/usage` | 체크아웃 현황(사용자·Job 매핑) | A-LM-05 | admin:access | 권장 |
| POST | `/license/servers/{id}/sync-slurm` | 가용 수량 → **지정 클러스터**(`cluster_id`)의 Slurm license 리소스 반영 | A-LM-03 | admin:access | 권장 |

## 14. 운영 설정 / 감사 (A-OP-03·04) `SettingRouter` `AuditRouter`

| Method | Path | 설명 | 기능 ID | 권한 | 우선순위 |
|---|---|---|---|---|---|
| GET | `/settings` | 포털 설정(폴링 주기·세션 타임아웃·SMTP/웹훅) | A-OP-04 | admin:access | 권장 |
| PUT | `/settings` | 포털 설정 수정 | A-OP-04 | admin:access | 권장 |
| GET | `/audit-logs` | 감사 로그 조회(기간·행위자·액션·클러스터 필터) | A-OP-03, C-05 | admin:access | 필수 |

---

## 미결/구현 시 확정
- U-JB-11(Job 알림)·A-LM-04(부족 알림): 알림 채널(Slurm mail vs 포털 인앱) 확정 후 엔드포인트 추가 — 수신 설정은 `/me/profile`에 선반영.
- A-US-06(자원 신청 승인): 선택 기능 — 수요 확인 후 설계.
- 파일 업/다운로드 대용량 한도·이어받기, SSE/WS 인증(쿼리 토큰 vs 쿠키)은 구현 시 결정.
- **U-JB-12(예상 시작시간)**: `sbatch --test-only` 상당 기능이 slurmrestd v0.0.41 REST에 있는지 **미확인**. 있으면 `JobService.validate()`에 포함, 없으면 REST 미지원 폴백 원칙대로 CLI(SSH) 래핑. 확인 전까지 `/jobs/validate` 응답에 미포함.
- **클러스터 간 비교 추천**(job-submit.html의 "다른 클러스터가 더 빠릅니다" 제안): "운영 화면은 선택된 클러스터로 스코프" 원칙과 배치되어 **포함 여부 보류** — 재검토 후 별도 API 설계.
- `/internal/gateway/dynamic-config` 보호 방식(공유 시크릿 vs 네트워크 정책) 및 Traefik 폴링 주기(지연-부하 트레이드오프) 확정 필요 — 배포 설계(backend-design §5)에서 결정.
- OpenAPI 스키마(요청/응답 Pydantic 모델)는 `schemas/`에서 정의 — 본 문서는 경로·권한·기능 매핑의 SoT.
