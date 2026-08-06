# Progress: admin 등록/수정 입력 모달 전환

- 근거 exec-plan: docs/exec-plan.md
- 구현: Claude 직접 (Codex 위임 시도했으나 Windows 샌드박스 오류 `CreateProcessWithLogonW 1385`로 실행 불가 → 사용자 결정에 따라 Claude가 구현)

## Task 현황

| Task | 파일 | 상태 | 검증 |
|---|---|---|---|
| T-01 | license.html | 완료 | 태그균형·링크·트리거타깃 OK |
| T-02 | clusters.html | 완료 | OK |
| T-03 | nodes.html | 완료 | OK (모달 3) |
| T-04 | jobs.html | 완료 | OK |
| T-05 | users.html | 완료 | OK (모달 2) |
| T-06 | settings.html | 완료 | OK (모달 2) |
| T-07 | billing.html | 완료 | OK |
| T-08 | reports.html | 완료 | OK |

## 공통 구현
- 기존 `.modal-backdrop.hidden` + `.modal`(head/body/foot) 패턴 재사용. 신규 CSS·style.css 수정 없음.
- 트리거: 버튼에 `data-open-modal="<모달id>"`, 등록/수정 라벨 전환용 `data-modal-title`. 제목은 `<span class="m-title-text">`.
- 페이지 하단에 공통 open/close 스크립트 1블록 추가: 트리거 클릭 open, `.m-close`·`[data-close]`·배경 클릭·ESC로 close. (기존 sidebar/dropdown/cluster 스크립트는 미변경)
- 인라인 폼은 모달로 이전, fid 칩 동반 이동. license는 fid 매핑을 A-LM-01~04로 명시 추가(기존 1 → 5).

## 검증 결과 (기계적)
- 9개 admin 파일 태그 균형 OK, 내부 href/src 링크 깨짐 0, 트리거의 data-open-modal 타깃 모두 실제 모달 id로 존재.
- fid 커버리지 유지/증가, negative control(A-ZZ-99) 0건. dashboard.html 미변경(원래 clean).

## 유지(인라인) 처리
- settings 시스템 설정(전역), users AD 연결·계정/클러스터 매핑 매트릭스, billing SCP 연동, 각 페이지 검색/필터 바·읽기전용 테이블. (exec-plan 유지 대상과 일치)

## 후속: 사용자·계정·QOS 4개 탭 → 페이지 분리
- 한 페이지에 앵커 탭으로 쌓여 있던 4개 섹션을 페이지로 분리. 사이드바는 단일 메뉴 유지, 상단 탭 바를 페이지 링크(서브네비)로 전환(사용자 결정).
- users.html(사용자+AD 연결 A-US-01) 정리 · **신규** accounts.html(A-US-02·04) · qos.html(A-US-03·05, QOS/파티션ACL 모달 포함) · mappings.html(A-US-07·04).
- 검증: 12개 admin 파일 태그 균형·id 중복 없음·트리거↔모달 매칭·내부 링크(탭 4링크 포함) 전부 통과.

## 후속: 사용자 온보딩 승인(A-US-06) 제거 — AD 자동 프로비저닝
- 배경: AD 허용 그룹 + 사용자 식별 속성(uid/cn) 조건에 맞는 사용자는 승인 없이 자동으로 활성 사용자.
- 변경:
  - 톱바 알림 "계정 신청 승인 대기 2건" → "AD 동기화 완료 — 신규 사용자 1명 자동 등록" (admin 12개 파일 공통).
  - users.html: 승인 대기 배너(A-US-06) → AD 자동 프로비저닝 안내, 상태 필터 "승인 대기" 옵션 제거, 강세윤 행(AD 신규·미배정·승인/반려) → 활성 사용자(acct-vision·normal·수정/역할/비활성), 동기화 이력 문구 수정.
  - index.html 로그인: "사용 신청 후 관리자 승인" → "회사 AD 계정으로 로그인 · 접근 문의는 관리자".
- 유지(별개 기능): QOS "승인제"(high QOS 접근 승인), 헬프데스크 티켓, 자원 증설 신청.
- 검증: design 전체 태그 균형 OK, 사용자 온보딩 승인 잔여 문구 없음.
- **정의서 반영 필요**: 정의서.md A-US-06(승인 워크플로 — 사용자 가입/자원 신청)에서 "사용자 가입 승인"이 제거됨 → SoT 갱신 검토 필요(미반영).

## 후속: AD 연결 입력 폼 → 모달 (단일 AD)
- users.html의 인라인 "Active Directory 연결" 입력 폼 제거 → 현재 AD 정보를 읽기 전용 요약(dl)으로 표시 + 수정/삭제 버튼.
- 입력/수정은 `adConnModal`(전체 폼 · 단일 AD 서버)로 이동. 트리거: 페이지 헤드 "🔗 AD 연결 설정", 카드 "수정" 버튼. 삭제 버튼 추가.
- 동기화 상태/이력 카드는 유지. 검증: 균형 OK, adConnModal 트리거 매칭, 인라인 폼 0.

## 후속: AD 연결 탭 분리 + 매핑/Fairshare 제거
- AD 연결/관리를 별도 탭(**ad.html** 신규)으로 분리: AD 정보(읽기전용)+수정/삭제, 동기화 상태/이력, adConnModal. users.html은 사용자 목록 전용으로 정리.
- 탭 구조: 사용자 · AD 연결 · 계정 · QOS (users/accounts/qos 탭바 갱신).
- **사용자↔클러스터 매핑 제거**: mappings.html 삭제, Fairshare도 함께 제거(사용자 결정) — accounts 트리 share 표기·매핑 링크 정리.
- 정의서: A-US-04(Fairshare 설정) 행 삭제, SCR-13 매핑 "A-US-01~03, 05~06"으로 갱신, 화면명에 AD 연결 반영.
- 검증: 12개 admin 파일 균형·링크·트리거·id OK, mappings.html 잔여 참조 0.
- **참고(범위 밖)**: 사용자 포털 U-AC-02(계정별 fairshare 조회)·usage.html는 이번에 미변경 — fairshare 완전 제거 시 함께 정리 필요.

## 후속: Fairshare·매핑 원복 (Slurm 네이티브 확인)
- 판단: QOS·Fairshare·계정↔클러스터 매핑(association) 모두 Slurm 네이티브 기능 → QOS 유지, Fairshare/매핑도 원복.
- mappings.html 복원(계정·클러스터 매핑·Fairshare), 탭 5개로 통일: 사용자·AD 연결·계정·QOS·클러스터 매핑.
- accounts 트리 share 표기·매핑 안내 링크 복원.
- 정의서: A-US-04(Fairshare) 재추가, **A-US-07(계정·클러스터 매핑) 신규 명시**(기존 UI-only 갭 해소), SCR-13 = A-US-01~07·화면명 갱신.
- 검증: 13개 admin 파일 균형·링크·트리거·id OK.

## 후속: 사용자·계정·QOS 3개 메뉴 분리 + 계정 CRUD/N:M
- 사이드바 단일 "사용자·계정·QOS" → **3개 메뉴(사용자 / 계정 / QOS)** 로 분리(admin 13파일 공통 갱신).
- 사용자 메뉴: 서브탭 [사용자 목록 | AD 연결]. 계정 메뉴: 서브탭 [계정 관리 | 클러스터 매핑]. QOS: 단일(서브탭 없음).
- **계정 관리 개편**: 트리(조회 전용) → 관리 테이블 + `＋계정 생성`/수정/삭제(accountModal) + **구성원(AD 사용자) join 관리(memberModal, N:M)**.
- users 계정 컬럼: 단일 → **다중 계정 칩(N:M 표시)**.
- 정의서: A-US-02 "포털 Slurm 계정 생성/수정/삭제 + AD 사용자 N:M 매핑(join)"으로 갱신.
- settings 인증 힌트 링크 users.html → ad.html 정정.
- 검증: 13개 admin 파일 균형·링크·트리거·id·사이드바 3메뉴 OK.

## 후속: 계정 레벨 QOS 배정
- Slurm association 모델: 계정/사용자마다 허용 QOS 집합 + 기본 QOS(DefaultQOS)가 배정됨.
- 배정 UI를 **계정 레벨**에 추가: accountModal에 "허용 QOS(다중 체크) + 기본 QOS(select)", 계정 목록에 "QOS(기본/허용)" 컬럼. 소속 사용자 상속.
- 정의서 A-US-02: "계정별 허용/기본 QOS 배정(소속 사용자 상속)" 추가.

## 후속: 클러스터 매핑 화면 확장성 개편 (다수 클러스터 대응)
- 문제: 기존 매트릭스는 클러스터마다 열 2개(허용/share) → 10개면 20열, 가독성/스크롤 문제.
- 개편: **계정 목록 + 계정별 '매핑 관리' 모달**(clusterMapModal). 목록엔 매핑된 클러스터 칩(예: seoul-hpc·100), 모달에서 클러스터를 세로 나열(허용 토글+share), 클러스터 증가 시 세로 스크롤로 대응.
- 검증: 균형·트리거↔모달 OK.

## 후속: 클러스터별 독립 slurmdbd 모델로 전환 (per-cluster)
- 결정: 공유 slurmdbd → **클러스터별 독립 slurmdbd**. 계정·QOS·사용자 association이 클러스터마다 독립(account가 cluster에 종속).
- 매핑 개념 폐기: mappings.html 삭제, 계정 메뉴 서브탭 제거(단일 페이지). account↔cluster 매핑 불필요.
- 계정/QOS/사용자 화면에 **페이지 내 '관리 대상 클러스터' 선택기** 추가(선택 클러스터로 스코프).
- Fairshare(share)는 매핑 매트릭스 폐기에 따라 **계정(클러스터별)로 이동** — 계정 목록 Fairshare 컬럼 + accountModal share 필드.
- "전 클러스터 공통" 칩/문구 → "클러스터별"(선택 클러스터 칩)로 변경. clusters.html 안내 공유→독립 정정.
- 정의서: A-US-07(매핑) 제거, A-US-02/03/04 per-cluster 문구, SCR-13 A-US-01~06·화면명 갱신.
- 검증: 12개 admin 파일 균형·링크·트리거·id, mappings 잔여 참조 0, 잔여 공유 문구 0.

## 후속: 사용자별 QOS 배정 + Job 제출 QOS 선택
- Admin(users.html): 사용자 행에 'QOS' 액션 + userQosModal — 선택 클러스터에서 사용자별 허용/기본 QOS override(미설정 시 계정 상속). 모달 open/close 스크립트 재추가.
- User(job-submit.html): QOS select에 기본/우선순위/한도 표기 + '허용 QOS만 표시·미선택 시 기본' 힌트. 낡은 힌트 정정(매핑→계정 있는 클러스터, 공유 slurmdbd→클러스터별 독립).
- 검증: users/job-submit 균형·트리거 OK, user 포털 잔여 공유 slurmdbd 문구 0.

## 후속: 역할(RBAC) — 포털 authZ 테이블 방식 확정
- 결정: 인증은 AD 직접 조회(미러 동기화 없음), **역할(USER/ADMIN)은 포털 authZ 테이블(`ad_id → role`)에서 관리**. AD 그룹/스키마 미변경 — 기존 AD를 그대로 바라보며 이 포털 때문에 AD 그룹을 만들/바꾸지 않음(사용자 제약). AD와 DB 조인 아님(로그인 시 받은 식별자를 키로 lookup).
- AD 그룹 파생 방식(①)은 AD 그룹명 종속 이유로 기각, 로컬 admin 계정+암호화(백도어·비밀 관리 부담)도 기각. 비밀번호는 저장 대상 없음(있더라도 해시).
- **부트스트랩 순환 해소**: 최초 실행 **setup 모드**(1회용 토큰·로컬 접근 보호)에서 ①AD 연결→test bind ②첫 ADMIN AD 사용자명 검증→`user_role` 1행 seed ③setup 영구 종료. 이후 정상 AD 로그인 RBAC.
- 반영: 정의서 1.2(authN/authZ 분리 주석)·C-02·A-US-01 갱신. users.html `역할` dead-end 버튼 4개 → `userRoleModal`(현재 역할·USER/ADMIN 라디오·"AD 인증, 역할은 포털 관리" 안내). 실 DB·setup은 C-03 구현 사항, 프로토타입엔 문구/모달로만.
- 검증(portal-verifier): users.html 태그 균형·트리거 8건 매핑(userRoleModal×4/userQosModal×4)·역할 버튼 4개 배선·id 유일 전부 PASS.

## 후속: 부트스트랩 = 최초 AD 연결 설정 화면에 seed admin 지정 (순환 해소)
- 결정(사용자 제안): 별도 setup 위저드 없이 **최초 AD 연결 설정 화면이 곧 부트스트랩**. admin 0명일 때 첫 접속자가 AD를 연결하고, 그 화면에서 검증된 AD 사용자 1명을 첫 ADMIN(seed)으로 지정 → "AD 연결해야 admin / admin이어야 AD 연결" 순환 해소.
- 첫 접속 보호: **1회용 setup 토큰**(설치 시 서버 로그 출력) 또는 로컬 접근 제한. seed 영역은 최초 1회만 표시.
- 반영: ad.html `adConnModal`에 first-run 전용 블록 추가(`notice warn` "최초 실행 전용" + "최초 관리자 지정(seed ADMIN)" 필드 + "Setup 토큰" 필드). 정의서 C-02·A-US-01 문구를 "최초 AD 연결 설정 화면에서 지정"으로 명확화.

## 후속: Slurm 연동 경로 명시 (C-03 하이브리드)
- 결정: slurmrestd(REST) 주 경로 + SSH/SFTP 보조 경로 하이브리드(순수 SSH-CLI 스크린스크래핑 비채택). 원칙 — 구조화 조회/제어=REST, 파일시스템·PTY·인터랙티브·스트리밍=SSH/SFTP, REST 미지원 op만 CLI 래핑.
- 정의서: C-03 셀을 하이브리드로 갱신 + **§4.1 연동 경로 매핑** 신설(① REST ② SSH/SFTP ③ Slurm 외 연동, 기능 ID별 분류 + 버전 고정·JWT·비노출 구현 유의).
- 문서 변경만(코드 무변경).

## 후속: 클러스터 이름 자동 조회 (등록 모달)
- clusters.html clusterModal(A-CL-02): 클러스터 이름 필드를 자유 입력 → **연결 테스트 시 slurmrestd에서 ClusterName 자동 조회(읽기 전용)** 로 변경. `readonly`·placeholder "연결 테스트 후 자동 입력"·`chip gray 자동`, 힌트 "slurm.conf와 자동 일치". 손 입력 불일치 위험 제거. (API 버전 "자동 감지"와 일관)
- 관찰(범위 밖, 미조치): ① 정의서에 A-CL 섹션 없음(clusters.html은 A-CL-01~04 fid 사용) — 기존 스펙 갭. ② line 198 "/home·/group 전 클러스터 공유 스토리지" 힌트는 storage 얘기(slurmdbd와 별개)라 유지, per-cluster와 충돌 아님으로 판단.

## 후속: 접속 노드 통합 + SSH 접속 정보 (등록 모달)
- clusterModal 접속 노드 섹션 개편: DTN 필드 제거(로그인 노드로 통합 — 웹 터미널·SFTP 공용), 섹션명 "접속 노드 (SSH)".
- 추가 필드: SSH 포트(기본 22), 접속 계정(서비스 계정), SSH 개인키(`Secret` 칩·`type=password`·Secret 저장).
- 보안 검토 반영: 요청은 "sudo 계정 SSH 키"였으나 **전체 root sudo 지양·제한적 sudo(least privilege)로 사용자 impersonation** 권장을 힌트/정의서에 명시. Slurm 제어는 REST+JWT라 sudo 불필요, SSH sudo는 파일(U-FM)·터미널(U-SH) impersonation 한정.
- 정의서 §4.1 ② SSH 경로에 접속 방식(서비스 계정+키·Secret·제한 sudo) 1줄 추가.

## 후속: 파일 브라우저 바로가기 경로 (스크래치 필드 개편, 옵션 A)
- 문제: "스크래치만" 필드 + "/home·/group 전 클러스터 공유" 힌트가 per-cluster 독립 전제와 불일치.
- 개편(A): clusterModal에 **"파일 브라우저 바로가기 (U-FM-01)"** 섹션 신설 — ① 홈은 SSSD/NSS(`getent passwd`·`$HOME`) 사용자별 자동 인식(필드 없음, 안내만) ② 그룹 경로 템플릿(`/group/{group}`) ③ 스크래치 경로 템플릿(`/scratch/{user}`, 비백업). `{user}`·`{group}` 세션 치환. 잘못된 "전 클러스터 공유" 힌트 제거.
- 정의서 §4.1 ②에 "경로 인식"(홈=SSSD 자동, 그룹·스크래치=템플릿) 1줄 추가.

## 후속: 연결 테스트 버튼 분리 (REST / SSH)
- clusterModal footer의 범용 '연결 테스트' 버튼 제거 → 연동(C-03) 섹션에 '🔌 REST 연결 테스트'(slurmrestd 응답·API 버전·ClusterName 조회), 접속 노드(SSH) 섹션에 '🔌 SSH 연결 테스트'(로그인 노드 접속·계정/키·sudo 확인) 각 배치. footer는 취소/저장만.
- 클러스터 이름 힌트 '연결 테스트 시' → 'REST 연결 테스트 시'로 정정(조회 주체 명확화).
- 검증(portal-verifier): 태그 균형(div 26/26·button 5/5)·트리거·id·버튼 구성 PASS.

## 후속: 시스템 설정에서 인증·연동 섹션 제거 (중복 정리)
- 문제: A-OP-04 시스템 설정 카드의 인증(C-01)·연동(C-03) 섹션이 실제 설정을 다른 화면(AD 연결, 클러스터 관리)에서 하는 것을 가리키기만 하는 중복.
- 제거: 인증(C-01) 섹션 전체(인증 방식 드롭다운 + 관리자 2FA), 연동(C-03) 섹션 전체(Slurm 엔드포인트 링크 + CLI 래핑 폴백 토글). 대신 상단에 안내 hint 1줄(인증→AD 연결, 엔드포인트→클러스터 관리, 2FA→AD/IdP 위임).
- 2FA 결정(사용자): **AD/IdP 위임** — 포털에 2FA 토글 미보유(AD가 유일 인증, MFA는 ADFS/Entra).
- 유지: 실시간성(C-04) 폴링/세션 타임아웃, 알림 채널(SMTP/웹훅).
- 정의서 A-OP-04: "인증(SSO/LDAP) 설정" 제거 → "세션 정책·알림 채널 설정, 인증은 AD 연결·엔드포인트는 클러스터 관리·2FA는 AD/IdP" 로 갱신.

## 후속: 클러스터 스코프를 톱바 단일 선택기로 통일
- 결정(사용자): 톱바 우측 상단 "클러스터" 선택기를 **전역 클러스터 스코프**로 사용. (이전에 톱바 제거+전 클러스터 컬럼 방식으로 갔다가 원복)
- 규칙: **클러스터 관리(clusters.html)** = 등록된 전 클러스터. **노드/파티션·전체 Job·계정·QOS·사용자 등** = 톱바에서 선택된 클러스터 기준.
- 조치: 톱바와 중복되던 **페이지 내 클러스터 선택기 5곳 제거** — accounts/qos 필터바("관리 대상 클러스터")→스코프 안내 노트, users 필터바 클러스터 select, jobs 필터바 클러스터 select, nodes 파티션 카드 클러스터 select. 클러스터 컬럼(nodes 파티션·jobs)은 유지(전체 선택 시 전 클러스터 표시).
- jobs 부제 "전 클러스터"→"선택한 클러스터(상단 스위처)·전체 선택 시 전 클러스터"로 정정(nodes와 일관).
- 미커밋이던 톱바 제거(12파일)+컬럼 개편(accounts/qos/users)은 git restore로 원복 후 재적용.

## 후속: 톱바 '전체 클러스터' 제거 + 운영 페이지 단일 클러스터 스코프
- 결정(사용자): 톱바에서 '전체 클러스터' 옵션 제거 → 항상 특정 클러스터 1개 선택(기본 seoul-hpc). 집계 페이지는 전 클러스터 유지.
- 톱바(12파일): '전체 클러스터' 옵션 삭제, seoul-hpc 기본 선택(sel)·버튼 라벨 seoul-hpc, 클릭 시 라벨 갱신 JS 추가.
- 운영 페이지 단일 클러스터 스코프:
  - jobs.html: pangyo 예시 행 제거, 클러스터 컬럼 제거, 통계 '전 클러스터'→'seoul-hpc', 부제 '전체 선택 시 전 클러스터' 문구 제거, 장기점유 공지 pangyo(choiyj) 제거.
  - nodes.html: 파티션 표 pangyo 행 2개 제거, 클러스터 컬럼 제거(seoul-hpc만).
  - accounts/qos/users: 이미 단일 클러스터 뷰(톱바 기본 seoul-hpc와 일관).
- 집계 페이지(dashboard 멀티클러스터 통합·reports sreport -M all·billing·license·settings 감사로그): 전 클러스터 유지, 페이지 내 '전체 클러스터' 필터 옵션도 유지(톱바 옵션만 제거). clusters.html 레지스트리도 전체 유지.

## 후속: user 파일 관리자 스토리지 정보 선택 클러스터 스코프
- files.html: 스크래치 quota 2개(seoul-hpc·pangyo-gpu 전 클러스터 표시) → 각 `.meter`에 `data-cluster` 부여, applyCluster에서 선택 클러스터 것만 표시(나머지 hide). 위치 카드 칩(id=locCluster)도 선택 클러스터 텍스트·색(cl/cl-b) 갱신.
- 결과: 파일 관리자가 선택 클러스터의 파일시스템 정보만 노출(전 클러스터 quota 미표시). /home 공유 안내 문구는 유지.
- user 톱바 클러스터 라벨(앞 커밋 cb2ed55)과 함께 동작.

## 후속: user 웹 터미널 접속 대상 선택 클러스터 스코프
- terminal.html: '접속 대상' select의 optgroup 2개(seoul-hpc/pangyo-gpu 전 클러스터 노드) → 각 optgroup에 data-cluster 부여, applyCluster에서 선택 클러스터 optgroup만 표시(hidden 토글) + 선택 항목이 숨겨지면 첫 표시 노드로 리셋. select에 id=termTarget.
- 결과: 웹 터미널이 선택 클러스터의 로그인/Job 노드만 노출(전 클러스터 노드 목록 미표시).

## 후속: 대시보드 스토리지 현황 FS타입 제거 + 선택 클러스터 스코프
- dashboard.html A-DB-05 스토리지 카드: 파일시스템 타입(Lustre/WekaFS/GPFS/NFS) 라벨 제거(NFS만 사용 예정). /home·/group은 전 클러스터 공유(항상 표시), /scratch 2개는 `data-cluster` 부여.
- admin applyCluster(dashboard)에 `.meter[data-cluster]` 필터 추가 + 로드 시 `applyCluster(saved||'seoul-hpc')` 호출 → 선택 클러스터의 /scratch만 표시(전 클러스터 스토리지 미표시).
- 이벤트 로그 'Lustre OST-07 사용률…' → 'scratch 볼륨 사용률…'로 일반화. design 전체 FS타입 언급 0.
- 참고: 'Top 사용자 (scratch)' 라인은 기본 seoul-hpc 사용자 기준(정적) — 필요 시 동적화.

## 후속: 허용 QOS 선택 UI 확장성 개편 (다수 QOS 대응)
- 문제: userQosModal·accountModal '허용 QOS'가 가로 나열 체크박스(4개 하드코딩) → QOS 늘면 레이아웃 깨짐. QOS 개수 제한은 비권장(Slurm 네이티브).
- 개편: 가로 flex-wrap → **검색 입력 + 세로 체크박스 목록 + 고정 높이(132px) 스크롤 컨테이너**(border 토큰). 개수 무관하게 모달 높이 일정. users.html·accounts.html 두 모달 동일 적용. 새 CSS 없음(인라인+토큰).

## 후속: 사용자 수정 모달 신설 (dead-end 해소)
- users.html 사용자 행 '수정' 버튼(dead-end) 4개 → `userEditModal` 배선.
- 모달 구성: AD 동기화 값(이름·uid·이메일)은 `readonly`(AD 칩), 포털 편집 항목만 — 소속 계정(N:M, 검색+스크롤 체크박스), 기본 계정(DefaultAccount select). 역할/QOS는 각 전용 버튼 안내.
- 검증(portal-verifier): 태그 균형·트리거→id(userEditModal/userQosModal/userRoleModal)·수정 버튼 4개 배선·id 유일 PASS.

## 후속: 대시보드 이름 변경 + 선택 클러스터 스코프
- '통합 대시보드' → '대시보드'로 개명: 사이드바 nav(12파일), dashboard crumbs·H1('멀티 클러스터 통합 대시보드'→'대시보드')·부제.
- dashboard 단일 클러스터(seoul-hpc) 스코프: 클러스터 요약 카드 pangyo 제거(seoul만), 현황 스탯 재라벨/seoul 값, 노드맵 페이지 내 클러스터 select 제거, 큐 현황·최근 이벤트 표 '클러스터' 컬럼+pangyo 행 제거, 부하 캡션·큐 경고 seoul화.
- 예외 유지: 톱바 클러스터 드롭다운, /home·/group(전 클러스터 공유), /scratch(pangyo, data-cluster로 숨김). 노드맵·부하차트가 seoul 전용 시각화라 완전 동적 전환은 C-03 데이터 바인딩 시(현재 기본 seoul-hpc 정적, jobs/nodes와 동일).
- 검증(portal-verifier): dashboard 태그 균형·표 컬럼 정합(큐 4/이벤트 4)·id 유일·잔여 문자열 0, 12파일 사이드바 '대시보드' 통일·균형 PASS.

## 후속: SCP Billing API 연동 인라인 폼 → 모달 (AD 연결과 동일 패턴)
- billing.html A-BL-01 카드: 인라인 입력 폼 → **읽기 전용 요약(dl)** + card-foot '수정' 버튼(→ billingApiModal). 입력 폼은 신규 `billingApiModal`로 이동(연결 테스트/저장 포함).
- 보안: Secret Key는 모달에서 값 미노출(placeholder "재입력 시에만 변경"), 요약엔 •••• (Secret 저장소 보관).
- 자원 식별 필터(A-BL-02·04)는 이미 billingRuleModal 사용 중 — 변경 없음. 모달 open/close 스크립트 기존 존재(범용)라 신규 모달 자동 동작.
- 검증(portal-verifier): 태그 균형·트리거→id(billingApiModal/billingRuleModal)·id 유일(baTitle 등)·카드 input 0/모달 폼 존재 PASS.

## 후속: SoT 불일치 5건 정리 (문서 stale · ID 갭 · A-US-06 화면)

프로젝트 전체 재파악 중 발견한 불일치 5건 수정. 2건은 사용자 결정 후 진행.

| # | 불일치 | 처리 |
|---|---|---|
| 1 | CLAUDE.md·AGENTS.md·portal-verifier가 admin을 "9개"로 기재(실제 12개) | 12개로 정정. CLAUDE.md·frontend/README.md의 `SCR-01~17`도 `~19`로 갱신 |
| 2 | A-CL-01~04·A-BL-01~04(8개)를 화면·api.md·db-erd.md가 쓰는데 정의서에 없음 | **결정: 정의서에 신규 섹션 추가** — §3.8 클러스터 관리·§3.9 비용/Billing 신설, §4.1 ③에 연동 경로 2줄, §5에 SCR-18·19 추가 |
| 3 | A-US-06만 화면 미매핑(65개 중 유일) | **결정: 화면 추가** — qos.html에 "자원 신청 승인" 카드 + `resourceRequestModal` 신설 |
| 4 | 정의서 A-US-05/A-US-06 행이 한 줄에 붙어 렌더링 시 A-US-06 소실 | 2행으로 분리 |
| 5 | 에이전트 정의 2개가 Windows 경로(`d:\workspace\portal`) 지시 | `/home/jrpark/workspace/portal`로 정정 |

### A-US-06 화면 배치 근거
qos.html에 이미 `high` QOS의 "승인제(신청 후 관리자 승인)" 개념이 있어(L100·L135) 신청 승인 대기 목록의 자연스러운 자리. 정의서 A-US-06은 §3.4(A-US-*) 소속이고 SCR-13 매핑이 이미 `A-US-01~06`이라 화면 목록 변경 불필요.
- 카드: 신청번호·내용·신청자·계정·신청일·상태(대기/승인/반려)·검토 버튼. card-foot에 sacctmgr 반영·감사로그(C-05)·AD 자동 프로비저닝 예외(A-US-01) 안내.
- 모달: 신청 정보 readonly + 처리 결과 라디오(승인/반려) + 처리 사유(감사 로그). 기존 `.modal-backdrop.hidden`·`data-open-modal` 패턴 재사용, 신규 CSS 0.

### 정의서 신규 섹션 근거
- A-CL: clusters.html의 fid 4종(목록·등록/수정·연결이력·수집/장애정책)과 api.md §3의 우선순위를 그대로 반영.
- A-BL: billing.html fid 4종 + db-erd.md `billing_config`/`billing_rule`/`billing_snapshot` + api.md §12 기준. A-RP-05(내부 chargeback)와 출처가 다름을 각주로 명시.
- CRLF 파일이라 줄바꿈 보존해 편집(정의서.md는 CRLF 유지).

### 검증 (직접 실행, portal-verifier 패턴)
- 태그 균형: design 22개 파일 불균형 0 — PASS
- 내부 href/src 링크: 깨짐 0 — PASS
- fid 커버리지: 정의서 ID 73개 중 화면 미매핑 **0개**, 정의서에 없는 화면 ID **0개** — 양방향 100% PASS (이전: 미매핑 1·정의서 밖 8)
- Negative control(U-ZZ-99·A-ZZ-99·SCR-99): 미검출 — PASS
- qos.html 트리거↔모달 id 매칭 3/3, id 중복 0 — PASS

### 미조치 (관찰만)
- **§4.1에 A-LM 경로 누락**: License(A-LM-01·02·05 FlexLM 직접 TCP, A-LM-03만 클러스터 REST)가 Architecture.md §2.3에는 있으나 정의서 §4.1 ③에는 없다. 이번 요청 범위(A-CL·A-BL) 밖이라 미수정.
- notes.md의 `SCR-01~15`는 2026-07-15 시점 히스토리 기록이라 의도적으로 유지.

## 후속: Backend 구현 — 기반 + 인증/클러스터/Job 수직 슬라이스

- 근거: [plan.md](plan.md) / [exec-plan.md](exec-plan.md) (범위=수직 슬라이스, 검증=pytest+fake — 사용자 결정)
- 스택: FastAPI 0.141 · SQLAlchemy 2.0.51 · Pydantic 2.13 · Alembic · Python 3.14

### Task 현황
| Task | 대상 | 상태 | 비고 |
|---|---|---|---|
| T-01 | core(config·errors·security·secrets·redis)·db | 완료 | `{code,message,detail}` 오류 형식 |
| T-02 | models 21개 | 완료 | db-erd.md와 1:1, SQLite/MySQL 양립 |
| T-03 | alembic 0001 스키마 + 0002 RBAC seed | 완료 | role 2·permission 1·매핑 1 |
| T-04 | clients(base_http·slurmrestd·ad·factory·token_provider) | 완료 | 멱등 op만 재시도, 401→SLURM_UNAUTHORIZED |
| T-05 | repositories(identity·cluster·audit) | 완료 | |
| T-06 | require_permission·AuditService | 완료 | 고위험 — 재검증 수행 |
| T-07 | Auth(부트스트랩·AD 로그인·JIT) | 완료 | 고위험 — 재검증 수행 |
| T-08 | Users/AD(+동기화 배치) | 완료 | |
| T-09 | Clusters(등록·자격증명·REST 테스트) | 완료 | |
| T-10 | Jobs(목록·제출·상세·취소·재제출·제어·이력) | 완료 | 고위험 — 재검증 수행 |
| T-11 | main.py 조립·OpenAPI | 완료 | 엔드포인트 28개 |
| T-12 | tests + fake | 완료 | 78개 통과 |

### 검증 결과
- `pytest` **78개 전량 통과**(외부 의존 0 — SQLite in-memory + FakeRedis/FakeAd/FakeSlurm).
- 실제 uvicorn 기동 확인: `/healthz` 200 · `/api/v1/auth/setup-status` 200 · `/docs` 200.
- `alembic upgrade head` → 21 테이블 + RBAC seed 생성 확인.
- 계층 규약을 테스트로 강제([tests/test_layering.py](../backend/tests/test_layering.py)): router→repository/client 직접 호출 금지, client→db/service 금지, 라우터 내 role 문자열 비교 금지, service/router 내 원문 SQL 금지 — 전부 통과.

### 고위험 재검증에서 **발견·수정한 취약점**
1. **세션 탈취 가능(수정됨)** — 세션 키가 username이라, sAMAccountName이 재사용되면 옛 소유자의 유효한 JWT가 같은 username의 **다른 사람**으로 인증될 수 있었다. 1차로 토큰의 `guid` 대조를 넣었고, 이후 **세션 ID 방식으로 재설계**해 원인을 제거했다(아래 절). 회귀 테스트: `test_stale_token_cannot_ride_username_reuse`.
2. **setup 토큰 타이밍 공격(수정됨)** — `!=` 비교를 `hmac.compare_digest`로 교체.
3. 그 밖에 확인한 것: JWT의 `role` 클레임으로 권한 상승 불가(권한은 DB/캐시 조회로만 결정), 남의 Job은 404로 존재 은닉, Secret 원문이 응답·DB·감사 로그에 없음, 내부 예외 메시지 미노출 — 각각 테스트로 고정.

## 후속: 세션 키를 username → 난수 세션 ID(sid)로 재설계

- 계기: 사용자 제안("session key를 uuid 같은 unique key로 관리하면 안될까?"). 앞선 `guid` 대조는 약한 기본형에 덧댄 패치였고, 키 자체를 바꾸면 **버그 종류가 사라진다**는 판단.
- 변경:
  - `session:{username}` → **`session:{sid}` → `{guid, username}`**. `sid`는 `secrets.token_urlsafe(32)` 난수, JWT의 `sid` 클레임으로 전달.
  - **신원의 정본이 세션 레코드**가 됐다 — 사용자 조회를 `get_by_username(payload["sub"])`가 아니라 `get_by_guid(session.user_guid)`로 한다. JWT의 `sub`·`guid`·`role`은 로그·디버깅용이며 인가에 쓰지 않는다.
  - 사용자 단위 강제 로그아웃을 잃지 않도록 역인덱스 `user_sessions:{guid}` → `{sid...}` 추가(`revoke_all`).
  - `deps.get_current_session`(세션 조회)과 `get_current_user`(사용자 로드) 분리. 로그아웃은 `revoke(sid)`로 **해당 기기만** 종료.
  - `UserService.update(is_active=False)`가 `revoke_all`을 호출 — 비활성화가 기존 세션까지 즉시 끊는다(이전엔 다음 요청의 DB 체크에 의존).
- 얻은 것: 이름 재사용 충돌 원천 제거, 기기별 개별 로그아웃, 세션 메타 저장 여지. 비용: 역인덱스 키 1종.
- 문서 동기화(SoT): backend-design §4.1 코드 예시·근거 갱신, db-erd.md Redis 노트, Architecture.md §3 SessionStore 설명, class_diagram.puml `SessionStore`/`SessionData`·`AuthService.logout` 시그니처.
- 검증: **80개 통과**. 신규 테스트 — `test_token_with_unknown_sid_is_rejected`, `test_identity_comes_from_session_not_jwt_claims`(같은 sid에 남의 신원·ADMIN role을 실어 재서명해도 세션의 guid로 조회돼 USER로 판정), `test_logout_ends_only_that_session`, `test_revoke_all_ends_every_session`.

### api.md 대비 차이 (의도적, 기록용)
- `POST /clusters/{cid}/jobs/validate`(api.md §5) **미구현** — 대신 스크립트 생성 확인용 `POST /clusters/{cid}/jobs/preview-script`를 추가했다. validate의 파티션 권한·walltime 한도 검증은 Account/QOS/Partition 서비스가 있어야 해서 이번 범위 밖.
- Node/QOS/Account/Usage/File/Session/Content/Billing/License/Audit 라우터는 미구현(exec-plan 제외 범위).

### 남은 제약
- `EnvSecretStore.put()`은 프로세스 내 오버레이라 **멀티 replica 간 공유되지 않는다** — 런타임에 등록한 클러스터 JWT가 다른 Pod에서 안 보인다. backend-design §9(Secret 저장소 구체) 확정 시 `SecretStore` 구현체 교체로 해소된다. 호출부는 인터페이스에만 의존하므로 영향 없음.
- slurmrestd v0.0.41 실물 응답 스키마 미검증 → 어댑터가 방어적으로 파싱(`_as_job_list`·`_extract_cluster_name`). 실환경 연결 시 재확인 필요.
- SQLite 테스트 호환을 위해 BIGINT PK에 `with_variant(Integer, "sqlite")` 적용(MySQL은 BIGINT 유지).

## 후속: k3s에 개발 인프라(MySQL·Redis) 배포 + 시드 데이터

- 대상: 단일 노드 k3s `dev01`(192.168.1.100), 네임스페이스 `hpc-portal`. 매니페스트는 [deploy/k8s/](../deploy/k8s/).
- 구성(backend-design §5.3·§5.4 준수):
  - **MySQL 8.4** — StatefulSet 1 replica + PVC 10Gi + liveness/readiness probe. k3s 기본 local-path가 `reclaimPolicy: Delete`라 §5.3 요건대로 **`local-path-retain` StorageClass 신설**.
  - **Redis 7.4** — Deployment 1 replica, 영속성 없음(emptyDir). §5.4의 "캐시/세션은 유실 허용" 판단 그대로.
  - 자격증명은 **매니페스트에 없다** — 난수 생성 후 K8s Secret으로만 존재. 백엔드용 `.env.dev`는 gitignore 처리.
  - 개발용 NodePort 30306/30379 노출(백엔드가 아직 클러스터 밖에서 실행되므로). 운영 시 제거 대상으로 매니페스트에 명시.
- 데이터:
  - `alembic upgrade head` → 실 MySQL에 21테이블 + RBAC seed. `audit_log.id`가 MySQL에서 `bigint auto_increment`로 생성됨을 확인(SQLite variant가 MySQL 타입을 훼손하지 않음).
  - [backend/scripts/seed_dev.py](../backend/scripts/seed_dev.py) 신설 — **멱등** 개발 시드(재실행 시 신규 0건 확인). 18개 테이블 45행: 사용자 5(opadmin=ADMIN)·클러스터 2(seoul-hpc/pangyo-gpu)·자격증명 참조 4·공지 3·템플릿 4·티켓 3·세션 1·라이선스 4·Billing 8·감사로그 5 등. 값은 `design/` 프로토타입 화면과 일치시켜 프론트/백엔드가 어긋나지 않게 했다.
  - 마이그레이션 seed(운영 필요)와 `seed_dev.py`(개발 전용)를 명시적으로 분리. `--reset`은 role/permission·alembic_version을 보존한다.
- 검증:
  - 호스트에서 MySQL 8.4.11 / Redis 7.4.10 접속 OK.
  - 앱을 실 MySQL·Redis에 붙여 기동 → `/auth/setup-status`가 **`bootstrap_required:false`** 반환(시드된 `ad_connection.seed_admin_guid`를 실제로 읽음), 무토큰 요청은 401.
  - 실 Redis에서 세션 생성·조회·역인덱스·`revoke_all`·권한 캐시·분산락 전부 정상, 정리 후 잔여 키 0.

### 실 AD 연동 완료 (dt-hpc.net)
- **원인이었던 것**: Windows Server 2025(build 26100)의 **신규 정책 "Domain controller: LDAP server signing requirements enforcement"**. 기존 "LDAP server signing requirements"와 **별개**이며 기본값 Not Configured = Enabled이고 **기존 정책을 덮어쓴다**. 그래서 `LDAPServerIntegrity=1`·GPO·NTDS 재시작·재부팅이 전부 정상 동작했는데도 결과가 안 바뀌었다. 이 신규 정책을 **Disabled**로 바꾸자 해결([Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/identity/manage-ldap-signing-group-policy)).
  - 진단 과정에서 SASL DIGEST-MD5가 `strongerAuthRequired`가 아닌 `invalidCredentials`를 반환한 것이 "서버가 실제로 서명 요구 상태로 동작 중"이라는 직접 증거였다.
- **AdClient 실환경 결함 2건 수정**:
  1. `objectGUID`가 **16바이트 이진값**(혼합 엔디언)으로 오는데 `str(bytes)`로 변환해 `"b'\\x88zd*...'"`가 저장될 뻔했다 → `uuid.UUID(bytes_le=...)`로 정규화. 단순 hex 변환은 Windows 표시값과 달라 **신원이 어긋난다**.
  2. 검색 필터가 `(sAMAccountName=*)`뿐이라 **그룹·컴퓨터 계정까지 57건** 반환 → `(objectClass=user)(objectCategory=person)` + **ACCOUNTDISABLE 비트 제외**(`1.2.840.113556.1.4.803:=2`)로 실제 사용자 3명만. 비활성 AD 계정이 자동 활성 사용자로 프로비저닝되던 문제도 함께 해소(A-US-01).
- **E2E 검증(실 AD·MySQL·Redis, 실 uvicorn)**: 부트스트랩(`setup-status` → `setup` seed ADMIN=SYSADMIN → 재실행 409 BOOTSTRAP_LOCKED) · 로그인(오답 401 / 정답 200, `/auth/me` role=ADMIN·permissions=[admin:access]) · RBAC(`/users` 200, 무토큰 401) · **AD 동기화**(신규 2·갱신 1·비활성 5) · 로그아웃 후 401. 전 구간 통과.
- **seed_dev.py 재작성** — AD 연동 후 드러난 충돌 해소:
  - **사용자를 만들지 않는다.** 가상 사용자 5명을 넣었더니 첫 AD 동기화가 "AD에 없음"으로 판단해 전부 soft delete 했다(동작은 정상). 사용자의 SoT는 AD이므로 시드는 콘텐츠 소유자를 **실제 사용자에서 조회**해 연결하고, 사용자가 없으면 해당 콘텐츠를 건너뛴다.
  - **부트스트랩을 완료 처리하지 않는다** — `seed_admin_guid`를 비워 두어 운영자가 실제 `POST /auth/setup` 경로를 타게 한다.
  - `--reset` 대상에서 **user·ad_connection 제외**(AD 소유 데이터·실 접속 설정 보호). `user_ssh_key`는 포함(FK가 user 삭제를 막음).
  - AD 기본값을 실제 개발 AD(dt-hpc.net)로 갱신. bind 암호는 여전히 `PORTAL_SECRET_AD_BIND`에만.
- 현재 상태: 포털 사용자 3명(SYSADMIN=ADMIN, Administrator·cloudbase-init=USER), 콘텐츠 36행, 고아 참조 0, 단위 테스트 80개 통과.

### 전 엔드포인트 점검 (28개 API, 실 스택)
- 방법: 실 MySQL·Redis·AD + **목 slurmrestd**(검증 전용, 저장소 미포함) 위에서 ADMIN/USER 두 토큰으로 정상·경계·권한·오류 경로를 태움.
- 결과: **1차 70/70**(Auth 9 · Users/AD 20 · Clusters 14 · Jobs 24 · Health/OpenAPI 2 · impersonation 1), **2차 14/14**(외부 장애 경로 3 · 목록 일관성 2 · 세션 6 · 감사 3).
- 확인된 동작: USER의 `?username=` 필터가 스코프를 넓히지 못함 · 타인 Job은 404로 존재 은닉 · `X-SLURM-USER-NAME`이 36건 모두 인증된 본인(`SYSADMIN`/`Administrator`) · Secret 원문이 응답·감사 로그에 없음 · slurmrestd 401 → `SLURM_UNAUTHORIZED`(502), 연결 불가 → `EXTERNAL_SERVICE_ERROR`(502) · 기기별 로그아웃 격리 · 제어성 액션 11종 감사 기록.

#### 발견·수정한 결함: 캐시된 slurm client가 죽은 세션의 ORM 객체를 참조
- 증상: `POST /clusters/{cid}/test-rest`가 slurmrestd 401에 **500** 반환(다른 엔드포인트는 502로 정상).
- 원인: `ClusterClientFactory.slurm()`이 `token_provider=lambda: ...token(cluster.id, ...)`로 **요청 단위 세션의 ORM 엔티티를 클로저에 가뒀다**. 풀은 앱 lifespan 동안 살아남으므로, 앞선 요청이 오류로 rollback하며 속성을 만료시키고 세션이 닫히면 캐시된 client가 detached 인스턴스를 참조하게 된다.
- 영향(중요): 오류 경로에 한정되지 않는다. **한 번 rollback이 나면 그 클러스터의 이후 모든 요청이 500이 되고 앱 재시작 전까지 복구되지 않는다.**
- 수정: 세션이 살아 있는 시점에 `cluster_id`·`base_url`·`api_version`을 평범한 값으로 복사하고 클로저는 그 값만 붙잡도록 변경.
- 회귀 테스트: `test_client_factory_survives_detached_cluster` — 수정을 되돌리면 `DetachedInstanceError`로 실패함을 확인(테스트 유효성 검증 완료). `test_deactivate_keeps_row_and_is_audited`에 감사 기록 단언도 추가.
- 이 결함은 fake만으로는 드러나지 않았다 — 실제 세션 수명주기와 클라이언트 풀링이 함께 있어야 재현된다.

## 후속: 백엔드 컨테이너 배포 + Traefik 외부 노출 (www.dt-hpc.net)

- **접속 URL**: `https://www.dt-hpc.net:9443/api/v1` (Swagger `/api/v1/docs`, OpenAPI `/api/v1/openapi.json`). HTTP `:9080`은 9443으로 301.
- **포트를 9080/9443으로 쓴 이유**: 이 서버의 80/443은 **기존 nginx**가 점유하고 `osmo.dt-hpc.net`·`keycloak.dt-hpc.net`의 TLS를 종단 중이었다. 뺏으면 그 서비스가 죽으므로 사용자 지시에 따라 Traefik에 별도 포트를 부여했다. **nginx 설정은 전혀 수정하지 않았다.**
- 구성:
  - `backend/Dockerfile` 신설(python:3.13-slim, 비루트 UID 10001, `--proxy-headers`). `pyproject.toml`에 `[build-system]` 추가.
  - `30-backend.yaml` — Deployment + Service. **initContainer가 `alembic upgrade head`** 실행. DB/Redis는 개발용 NodePort가 아니라 **클러스터 내부 DNS**(`mysql.hpc-portal.svc`, `redis.hpc-portal.svc`)로 접근.
  - `40-ingress.yaml` — Traefik IngressRoute. `Host(www.dt-hpc.net) && PathPrefix(/api)`만 백엔드로. `/healthz`는 probe 전용이라 외부 미노출.
  - `50-traefik-ports.yaml` — k3s 내장 Traefik의 HelmChartConfig로 hostPort 9080/9443.
  - `main.py` — Swagger/OpenAPI 경로를 `/api/v1` 아래로 이동. 프론트엔드와 도메인을 공유할 때 프록시가 `/api` 하나만 넘기면 되도록.
- **TLS**: certbot 인증서(SAN에 www 포함, 2026-11-01 만료)를 Secret `dt-hpc-tls`로. 갱신 시 Secret이 낡아 **조용히 만료 인증서를 제공**하므로 `certbot-deploy-hook.sh`를 작성해 `/etc/letsencrypt/renewal-hooks/deploy/`에 설치·동작 확인했다.
- **해결한 함정 — hostPort + RollingUpdate 교착**: hostPort는 노드당 하나만 바인딩되므로 새 Traefik 파드가 옛 파드와 포트를 다투다 **Pending으로 영구 정지**했다(갱신 훅의 `rollout restart`가 촉발). 훅에서 불필요한 재시작을 제거하고(Traefik CRD provider가 Secret 변경을 자동 감시함), HelmChartConfig에 `updateStrategy: Recreate`를 고정했다.
- **감사 IP 확인**: 프록시 뒤 클라이언트 IP가 `10.42.0.1`로 찍혀 조사했으나 결함 아님 — loopback→hostPort 경로에서 portmap이 SNAT한 결과였다. LAN IP 경유 시 실제 IP(`192.168.1.100`)가 정확히 기록됨을 확인. 위조된 `X-Forwarded-For`를 Traefik이 무시하는 것도 감사 무결성상 올바른 동작이다.
- 검증: setup-status·docs·login·`/users`(인증)·무토큰 401 전부 정상, TLS는 Let's Encrypt 공인 체인으로 `-k` 없이 검증 통과.

#### 사고 기록 — HelmChartConfig 적용이 기존 nginx 서비스를 중단시킴 (복구 완료)
- **무슨 일**: Traefik hostPort를 열려고 HelmChartConfig를 적용했더니, 차트 기본값인 `service.spec.type: LoadBalancer`가 함께 적용되면서 k3s **servicelb가 `svclb-traefik` 파드(hostPort 80/443)** 를 띄웠다. 그 결과 호스트로 오는 80/443이 iptables DNAT으로 **nginx 대신 Traefik으로 흘러** `osmo.dt-hpc.net`·`keycloak.dt-hpc.net`이 중단됐다(약 10분).
- **왜 늦게 발견했나**: 사고 직후 확인에서 osmo/keycloak이 404를 반환했는데 이를 "상위 백엔드 응답"으로 잘못 읽었다. 실제로는 **Traefik의 라우트 없음 404**였다. 응답 헤더(`server:`)를 보지 않은 것이 원인 — 복구 후에는 `server: nginx/1.20.1` + 302로 판정했다.
- **원인이 아니었던 것**: 애초에 traefik svc가 ClusterIP였던 건 우연이 아니라 **누군가 80/443을 nginx에 내주려고 그렇게 둔 상태**였고, 내 HelmChartConfig가 그 설정을 차트 기본값으로 되돌렸다.
- **복구**: 즉시 `kubectl patch svc traefik --type=ClusterIP`로 DNAT 제거 → nginx 정상화 확인. 이후 선언적으로 고정.
- **함정 하나 더**: traefik 차트 v40은 `service.type`이 아니라 **`service.spec.type`** 이다(k3s 자체 값이 `service.spec.ipFamilyPolicy`를 쓰는 것과 같은 구조). 처음 `service.type: ClusterIP`로 넣었을 때 조용히 무시돼 LoadBalancer가 유지됐고, 차트 tarball의 values.yaml을 직접 열어 확인한 뒤 교정했다.
- **재발 방지**: `50-traefik-ports.yaml`에 ClusterIP 강제 + 이유를 주석으로 명시. 이 파일을 수정할 때 `service.spec.type`을 빠뜨리면 같은 사고가 재현된다.
- **교훈**: 공유 호스트에서 k3s의 LoadBalancer 서비스는 servicelb를 통해 **호스트 포트를 조용히 점유**한다. 다른 프로세스가 쓰는 포트가 있으면 서비스 타입까지 명시적으로 못 박아야 한다.

### 미해결 (운영 전 필수)
- **평문 LDAP 전송** — DC에 LDAPS 인증서가 없어 389 평문이고, 사용자 비밀번호가 네트워크에 노출된다. 사용자 결정에 따라 서명 요구를 끈 상태다. DC에 인증서를 설치하면 `AdClient`가 **StartTLS를 먼저 시도**하므로 포털 설정 변경 없이 암호화 전송으로 자동 전환된다.
- **`allowed_group` 미설정(NULL = 전 AD 사용자 허용)** — AD에 HPC 전용 그룹이 없고 기본 그룹뿐이라 정할 수 없었다. 정의서 A-US-01대로 `HPC-Users` 같은 그룹을 만들어 지정해야 한다. 현재는 `cloudbase-init` 같은 서비스 계정까지 포털 사용자로 올라온다.
- **로그인 불가 — AD 서버 없음**. `/auth/login`은 AD bind가 전제라 현재 토큰을 발급받을 수 없고, 시드 데이터는 DB 직접 조회로만 확인 가능하다. 개발용 LDAP(예: OpenLDAP)을 같은 네임스페이스에 띄우면 해소된다 — 이번 요청 범위(MySQL·Redis) 밖이라 미조치.
- **DB 정기 백업 미구현** — §5.3이 요구하는 `CronJob → S3`가 없다. PVC 손상 시 복구 수단 없음.
- local-path는 단일 노드 전용이라 §5.3의 "네트워크 스토리지" 요건 미충족.
- `billing_config`의 SCP 계정/키는 placeholder — 실제 연동 전 교체 필요.

## 후속: 실 AD(dt-hpc.net) 연동 — 진단 완료, DC 설정 대기

- 대상: `192.168.1.10` / 도메인 `dt-hpc.net` / base DN `DC=dt-hpc,DC=net` / DC `WIN-7CUUJHSK57G` (functionality 10 = Windows Server 2016+)
- **막힌 지점(진단 완료)**: DC가 `strongerAuthRequired` 반환 — 진단 메시지 원문 *"The server requires binds to turn on integrity checking if SSL\TLS are not already active"*.
  - 636(LDAPS)은 TCP는 열리지만 TLS ClientHello에서 **RST** → DC에 LDAPS 서버 인증서 없음.
  - StartTLS도 `unavailable` (같은 원인).
  - ldap3의 **NTLM은 인증만 하고 서명을 협상하지 않아** 역시 거부됨(순수 python MD4로 Rocky 9의 OpenSSL3 MD4 제거 문제를 우회해 확인). → NTLM 경로 불가.
  - 남은 경로는 ①DC에 인증서 설치 ②Kerberos GSSAPI ③DC 서명 요구 해제. **사용자 결정: ③**.
- 결정 기록: ③은 사용자 비밀번호가 평문으로 전송된다는 점을 제시했고 사용자가 재확인함(폐쇄 개발망 전제). 코드는 `ldap://`일 때 **StartTLS 승격을 먼저 시도**하므로, 이후 DC에 인증서가 생기면 **설정 변경 없이 자동으로 암호화 전송으로 전환**된다.
- 이번에 한 작업(경로 선택과 무관하게 필요한 것):
  - `AdClient` 실환경 대응 — 스킴/포트 해석(`ldaps://`·`ldap://`), TLS 검증 옵션(`ad_tls_verify`·`ad_ca_cert_file`), **StartTLS 기회적 승격**, bind 실패를 실행 가능한 안내로 변환(`_bind_hint`: `strongerAuthRequired`를 "비밀번호 틀림"으로 뭉뚱그리지 않음).
  - [backend/scripts/check_ad.py](../backend/scripts/check_ad.py) 신설 — 도달성→RootDSE→전송보안→bind→검색→objectGUID 형식을 순서대로 짚는 진단 CLI. DB의 `ad_connection`을 그대로 사용해 포털 밖에서 원인을 격리할 수 있다.
  - `ad_connection` 행을 실제 값으로 갱신(`ldap://192.168.1.10:389`, base DN, `Administrator@dt-hpc.net`). bind 암호는 `PORTAL_SECRET_AD_BIND` 환경변수로만 — DB엔 참조만.
- 현재 진단 결과: TCP OK · RootDSE OK · StartTLS WARN(불가) · **bind FAIL**(DC 정책). bind 이후 단계는 정책 해제 후 검증 예정.
- **DC 정책 해제 시도 경과(미해결)**:
  - SYSVOL 직접 확인 — Default Domain Controllers Policy `{6AC1786C-016F-11D2-945F-00C04fB984F9}`의 `GptTmpl.inf`에 `LDAPServerIntegrity=4,1`(REG_DWORD=1, None) 기록됨. **GPO 편집 내용은 정확**.
  - `gpupdate` + **DC 재부팅 후에도** DC 응답이 글자 그대로 동일(`strongerAuthRequired`, DSID-0C09035C) → GPO가 DC에 적용되지 않고 있음(링크 누락/우선순위 또는 로컬 보안 정책이 유효값을 지배하는 것으로 추정). 유효 레지스트리 값 확인 필요.
  - 다른 경로 탐색 결과: 636·3269는 재부팅 후에도 TLS 핸드셰이크 RST(인증서 없음), GC 3268 평문도 동일 거부.
  - **SASL DIGEST-MD5는 `invalidCredentials` 반환** — 즉 SASL은 DC의 integrity 요구를 **통과**했고 자격증명 단계까지 도달했다. 실패 원인은 AD가 계정의 DIGEST 해시를 저장하지 않기 때문(realm 5종·계정 2종 모두 동일). 사용하려면 "가역 암호화로 암호 저장"이 필요해 **보안상 더 나쁜 교환**이라 채택하지 않음.
  - bind 계정은 사용자 요청으로 `Administrator@dt-hpc.net` → `sysadmin@dt-hpc.net` 변경(전용 서비스 계정이 원칙적으로 맞음). 비밀번호는 미검증 — 전송 정책 거부가 자격증명 검증보다 먼저 일어나 확인 불가.
- 미결: `allowed_group`을 NULL로 뒀다(= 전 AD 사용자 허용). bind 성공 후 실제 그룹을 조회해 A-US-01의 허용 그룹으로 지정해야 한다.

## 후속: Frontend 구현 — Vue 3 + TypeScript + Tailwind (22화면)

- 근거: [plan.md](plan.md) / [exec-plan.md](exec-plan.md). 범위=**22화면 전부**(사용자 결정).
- 스택: Vite 6 · Vue 3.5(`<script setup>`) · TypeScript(strict) · Tailwind v4 · Pinia · vue-router. 파일 52개 / 약 3,800줄.

### 결과
- 화면 23개(SCR-01~19 + 최초설정), 라우트 26개. `vue-tsc` 타입체크 통과, `npm run build` 성공(화면별 코드 스플리팅).
- **실 백엔드 연동 검증**: 개발 서버 프록시로 `setup-status` 200 · 로그인 토큰 발급 · `/auth/me`가 `SYSADMIN/ADMIN/[admin:access]` 반환 · `/clusters` 200.

### 정적 프로토타입에서 해소된 부채
- **사이드바/톱바 복붙 제거** — 22개 파일에 복제돼 있던 마크업이 `AppShell` 한 벌이 됐다. CLAUDE.md 구조 규칙("메뉴 변경 시 21개 파일 모두 수정")이 사라진 지점이다. 메뉴는 **라우터 meta에서 파생**시켜 두 곳에 적지 않는다.
- 디자인 토큰(`design/css/style.css` `:root`)을 Tailwind `@theme`로 이관 — 색·간격 하드코딩 금지 규칙을 그대로 승계.
- fid 칩을 `<Fid id="U-JB-01" />` 컴포넌트로 유지해 기능 정의서 추적성 보존.

### 동작 화면 vs 정적 화면 구분
백엔드는 4개 도메인만 구현돼 있어 **12화면이 정적**이다. 섞이면 이후 작업에서 사고가 나므로 두 겹으로 표시했다:
- 화면 상단 `StaticNotice` 배너에 미연결 API 경로 명시
- 사이드바 메뉴에 `静` 배지

| 실 API | 로그인·최초설정 · 클러스터 현황(일부) · Job 목록/제출/상세 · 대시보드(Job 통계) · 전체 Job · 사용자 · AD 연결 · 클러스터 관리 |
|---|---|
| **정적** | 공지 · 인터랙티브 앱 · 파일 · 터미널 · 사용량 · 노드/파티션 · 계정 · QOS · 리포트 · Billing · License · 운영설정 |

### 설계 판단
- 권한 판정은 서버가 준 `permissions`만 근거로 한다 — role 문자열로 분기하지 않는다(백엔드 원칙과 동일).
- 401은 `client.ts`가 한 곳에서 처리해 세션을 비우고 로그인으로 보낸다. 화면마다 개별 처리하지 않는다. 단 로그인 401은 자격증명 오류이므로 예외.
- slurmrestd 응답 형태가 버전마다 달라 `utils/job.ts`가 방어적으로 파싱한다(백엔드와 같은 태도).
- OpenAPI 자동생성 미도입 — 엔드포인트 28개 규모에 빌드 파이프라인을 늘릴 이유가 없다.

### 미해결
- 실시간 폴링·SSE·WebSocket 미구현(C-04) — Job 로그 tail·웹 터미널은 화면만.
- i18n(C-06) 미도입, 한국어 하드코딩.
- (해소됨) 프론트엔드 배포 — 아래 절 참조.
- 정적 12화면은 해당 백엔드 도메인이 생기면 다시 손봐야 한다(사용자 인지·승인됨).

## 후속: 프론트엔드 배포 + Traefik 경로 분기

- `https://www.dt-hpc.net:9443/` 이 **프론트엔드**로 가도록 요청받아 처리. 같은 도메인·포트에서 경로로 가른다:
  - `/api/**` → `portal-backend` (priority 100)
  - 그 외 전부 → `portal-frontend` (priority 1, SPA catch-all)
  - Traefik은 규칙 길이로 우선순위를 정하므로 **`priority`를 명시**해 API가 catch-all보다 먼저 매칭되게 못 박았다.
- `frontend/Dockerfile` 신설 — 멀티스테이지(node 빌드 → nginx 서빙), **비루트 8080**.
- `frontend/nginx.conf` — SPA 폴백 `try_files $uri $uri/ /index.html`. 없으면 `/jobs` 직접 진입·새로고침이 404가 된다. 해시 자산은 1년 immutable, `index.html`은 no-store(배포 즉시 반영).
- `60-frontend.yaml` — Deployment + Service + probe.
- 기존 루트→API문서 리다이렉트(`root-to-docs` Middleware)는 역할이 끝나 제거.

### 겪은 문제
비루트 nginx가 `/run/nginx.pid` 권한 오류로 CrashLoopBackOff. 이미지의 pid 경로가 `/var/run`이 아니라 `/run`이라 sed가 빗나갔다. 경로 문자열에 의존하지 말고 `pid` 지시자를 통째로 치환하고, 빌드 단계에서 `grep`으로 치환 성공을 검증하도록 고쳤다.

### 검증
- SPA: `/` `/jobs` `/admin/users` 전부 200 + `<title>HPC Portal</title>` (직접 진입·새로고침 폴백 동작)
- 자산: JS/CSS 200, `cache-control: max-age=31536000, immutable` / index는 `no-store`
- API: `/api/v1/auth/setup-status` 200, 로그인 → `/auth/me` ADMIN, `/clusters` 200
- HTTP 9080 → `https://…:9443/jobs` 301 (경로 보존)
- 기존 nginx 무영향: osmo·keycloak 302 (`server: nginx/1.20.1`)

## 후속: 최초 접속 AD bind 부트스트랩 + 정적 데이터 전면 제거

사용자 지시: "실제 구현이므로 html 그대로 하면 안 된다. 연동되지 않는 화면은 빈 공간으로.
sysadmin 쓰지 않고 처음 접속할 때 AD bind만 되게 하고, AD bind 할 때 admin을 지정한다."

### 1) 부트스트랩을 2단계 AD bind 플로우로
- **신규 `POST /auth/setup/probe`** — setup 토큰으로 보호, AD에 bind해서 **실제 조회되는 계정 목록**을 돌려준다. DB·Secret 저장소에 아무것도 쓰지 않는 검증 전용.
- 관리자 계정명을 손으로 받아치던 것을 **목록에서 고르는 방식**으로 바꿨다. 오타로 실패하지 않고, 그 계정이 허용 그룹 안에서 실제로 보이는지 먼저 증명된다.
- 프론트 `SetupView`를 3단계 위저드로 재작성: AD 연결 → 관리자 선택 → 완료.
- 보호 방식은 **1회용 setup 토큰 유지**(사용자 결정, 정의서 C-02). 토큰 검증·부트스트랩 잠금을 `_assert_setup_allowed()` 한 곳으로 모아 setup/probe가 같은 관문을 통과하게 했다.
- 부트스트랩 후에는 probe도 409로 막는다 — 완료 뒤에 AD 계정 목록이 새어 나가면 안 된다.

#### 발견·수정한 결함: 지정한 계정이 관리자가 되지 않음
- 증상: 실 AD로 `jungryul0515.park`를 seed ADMIN으로 지정했는데 **USER로 남았다**. `seed_admin_guid`는 그 사람을 가리키는데 권한이 없어 **관리자 없는 포털**이 된다.
- 원인: `provision()`이 기존 사용자의 role을 보존한다(개명이 권한을 바꾸면 안 되므로 — 의도된 규칙). 이미 AD 동기화로 USER로 등록돼 있던 계정이라 그 규칙에 걸렸다.
- 수정: `setup()`이 프로비저닝 후 **명시적으로 ADMIN 승격 + 활성화**. 부트스트랩의 목적 자체가 "이 계정을 관리자로 만든다"이므로 보존 규칙의 예외다.
- 회귀 테스트: `test_setup_promotes_existing_user_to_admin` — 기존 USER를 지정해도 ADMIN이 되고 실제로 `/users`(admin 전용)가 200인지까지 확인.
- 실 AD 재검증: 전원 USER로 초기화 → 지정 → `jungryul0515.park`=ADMIN, `sysadmin`=USER, sysadmin의 `/users` 호출 403.

### 2) 정적(가짜) 데이터 전면 제거
- 실제 구현이므로 값을 지어내지 않는다. `StaticNotice`(가짜 데이터 배너)를 삭제하고 **`NotImplemented`** 컴포넌트로 교체 — 해당 영역을 비우고 어떤 API가 생기면 채워지는지만 표시한다.
- 대상 12화면 전부 재작성(공지·앱·파일·터미널·사용량·노드·계정·QOS·리포트·Billing·License·설정) + 부분 정적이던 클러스터 현황·대시보드·Job 상세 로그.
- 가짜 숫자는 운영 판단을 틀리게 만들고 "동작하는 화면"으로 오인된다 — 빈 상태가 정직하다.
- 대시보드는 실 API로 계산 가능한 **Job 통계만** 남겼다.

### 검증
- 백엔드 테스트 **86개 통과**, 프론트 `vue-tsc` 통과 + 빌드 성공, 가짜 데이터 참조 0.
- 실 스택 E2E: 부트스트랩 필요 → 로그인 차단(FORBIDDEN) → AD bind로 후보 4명 조회 → 관리자 지정 → 잠금(409) → 역할 반영 확인.
- 화면 도달성: `/` `/setup` `/login` `/jobs` `/admin/dashboard` `/admin/users` 전부 200.

## 미해결 / 참고
- 정적 프로토타입이므로 수정(edit) 시 실제 값 프리필은 미구현(대표 예시값). 실데이터 바인딩(C-03) 도입 시 처리.
- 점검 모드 시작(A-ND-05)은 이번 범위 제외(버튼 유지).
- CLAUDE.md의 "현재 JS 없음" 문구는 실제와 달라 정정함(바닐라 JS 존재).

---

# 인터랙티브 앱 — 원격 데스크톱 (SCR-06)

근거: [plan.md](plan.md) / [exec-plan.md](exec-plan.md) (2026-08-06)

## T-01 Rocky 9 + MATE + TigerVNC 이미지 — 완료

- `deploy/images/rocky9-mate/` (Dockerfile · start-desktop.sh · README.md)
- dev01에 apptainer 1.5.3 설치 → `docker-daemon://`로 SIF 변환
- 산출물: `/home/portal/images/rocky9-mate-1.0.sif` (387MB, docker 이미지 1.25GB)

### 겪은 문제

1. **EPEL9에 "MATE Desktop" 그룹이 없다** (EPEL7/8과 다름, Xfce만 있음).
   → 세션 구성 패키지를 직접 나열.
2. **스크립트가 출력 없이 rc=141로 죽었다.** `tr < /dev/urandom | head -c 8`에서
   head가 먼저 끝나 tr이 SIGPIPE → `set -o pipefail`이 잡아 조용히 종료.
   → 유한 바이트를 먼저 읽고(`head -c 512`) bash 슬라이스로 자른다. 진단용 `trap ... ERR` 추가.
3. `pkill -f 'mate-session'`이 같은 문자열을 포함한 자기 셸을 죽여 정리가 안 됐다.
   → `pkill -f '[m]ate-session'`.

### 검증 (실 노드)

```
apptainer exec / --writable-tmpfs / --fakeroot   전부 동작
Xvnc TigerVNC 1.15.0 → 0.0.0.0:5901 LISTEN, mate-session 기동
connection.json 생성 (node/ip/port/password/view_password)
포털 → SSH(로그인 노드) → direct-tcpip("slurm01", 5901) → "RFB 003.008"
```

마지막 줄이 핵심 — **프록시 설계 전체가 코드 작성 전에 실측으로 검증됐다.**
목적지를 Slurm 노드명으로 지정해도 로그인 노드가 해석한다(워커 분리 대비).

테스트 세션은 정리했다(Xvnc 0, 59xx LISTEN 없음).

### T-01 추가 — 컨테이너 AD 연계 / 홈 마운트 (사용자 질문)

Apptainer는 **호출한 사용자 그대로** 실행하므로 AD 신원·홈은 설정 없이 들어온다.
실 AD 계정으로 컨테이너 안에서 확인:

```
id      : uid=201106(jungryul0515.park) gid=200513(domain users)
whoami  : jungryul0515.park
HOME    : /home/jungryul0515.park   목록·쓰기 OK (NFS 공유 홈)
```

본인 이름이 풀리는 건 Apptainer가 호출자의 passwd/group 항목을 컨테이너에 주입하기
때문이다(sssd 불필요). 그러나 **다른 AD 사용자는 안 풀려** 공유 디렉터리에서 숫자 UID로 보인다.

→ 이미지에 `sssd-client` 추가 + `--bind /var/lib/sss/pipes`. 소켓이 `srw-rw-rw-`라
추가 권한이 필요 없다. 결과적으로 **호스트와 `getent passwd` 결과가 완전히 일치**한다.
`domain users` 그룹 멤버 목록도 정상 조회된다.

양쪽 모두 안 나오는 `sysadmin`은 SSSD 검색 범위(`OU=people`) 밖이라 컨테이너와 무관하다.

T-02 반영 사항: SSSD가 없는 호스트도 있으므로 **Job 스크립트는 `/var/lib/sss/pipes`가
존재할 때만** 바인드를 붙인다.

## T-02 세션 Job 스크립트 + connection.json 규약 — 완료

- `backend/app/services/session_script.py` — `SessionSpec` + `build_session_script()`,
  경로 규칙 헬퍼(`session_dir` / `log_dir` / `log_path`)
- `backend/tests/test_session_script.py` — 12개 통과

스크립트에 값을 끼워 넣으므로 해상도·앱 이름은 정규식으로 검증하고 전부 `shlex.quote`한다
(해상도는 사용자 입력, 이미지 참조는 관리자 설정값).

### 겪은 문제 — scancel 후 connection.json이 남았다

죽은 세션에 접속을 시도하게 되는 버그. 원인을 두 단계로 좁혔다.

1. `start-desktop.sh` 마지막의 `exec dbus-launch ...` — **exec이 셸을 대체하면서 정리
   trap이 사라졌다.** 백그라운드 + `wait`으로 변경.
2. 그래도 안 지워졌다. 컨테이너 안 bash에 **직접 SIGTERM을 주면 정상 동작**하는 것을
   확인 → trap은 멀쩡하고 **신호가 안 닿는 것**이 문제.
   `ps -eo pgid`로 보니 apptainer가 별도 프로세스 그룹(pgid=apptainer)을 만들어
   `scancel`이 보내는 신호가 컨테이너 안까지 전달되지 않았다.

→ 접속 정보 삭제 책임을 **호스트 쪽 Job 스크립트**로 올렸다(Slurm이 직접 신호를 주는
대상). 컨테이너 안의 trap은 로그아웃 대비로 남겨 둔다.

**T-04 반영 사항**: 파일 존재 여부만으로 세션 생사를 판단하지 않는다. 노드 장애 시에도
파일이 남으므로 **Slurm Job 상태를 권위 있는 출처로** 쓰고 connection.json은
"어디로 붙을지"만 제공한다.

### 검증 (실 클러스터, AD 계정 `jungryul0515.park`)

```
sbatch 제출 → job 8/9/10/11 RUNNING (partition=cpu, node=slurm01)
connection.json 생성: node=slurm01 ip=192.168.1.201 port=5901 job_id=8
Xvnc 0.0.0.0:5901 LISTEN, XDG_RUNTIME_DIR=/tmp/portal-rt-201106-8 (AD uid 반영)
포털 → SSH(로그인 노드) → direct-tcpip("slurm01", 5901) → "RFB 003.008"
scancel → connection.json 삭제 확인, 포트 해제 확인
```

테스트 잔여물은 정리했다(Job 0, Xvnc 0, `~/.portal` 비움).

## T-03 DB 모델·마이그레이션 — 완료

`interactive_session` 테이블은 **이미 존재했다**(초기 ERD 설계분). 새로 만들지 않고 재사용한다.
다만 docstring이 폐기된 설계(“Traefik이 폴링해 라우트를 만든다”)를 설명하고 있어 바로잡았다.

- `node_host`/`node_port`/`connect_url`은 그 초기 설계의 잔재로 **채우지 않는다** —
  채우면 접속 정보의 출처가 둘이 되어 어긋난다. 컬럼은 남겨 두고 이유를 모델에 적었다.
- 새 마이그레이션 `0004_desktop_image_ref` — `cluster.desktop_image_ref` 추가.
  Apptainer가 SIF 경로·`oras://`·`docker://`를 같은 자리에서 받으므로 이 값 하나로
  레지스트리 전환이 끝난다(plan §3.5). 스키마 3곳(Create/Update/Out)에도 반영.
- `backend/app/repositories/session.py` — `owned()`는 **소유자 조건을 조회에 붙인다**.
  id로 꺼낸 뒤 비교하면 그 검사를 빠뜨린 호출부가 생긴다.

검증: `alembic upgrade head` 정상. `downgrade`는 sqlite가 `DROP COLUMN`을 못 해 실패하는데
0003과 같은 패턴이고 실제 대상은 MySQL 8이라 문제되지 않는다.
컨테이너(Python 3.13) `import app.main` 통과 — 3.14 dev venv와 애노테이션 평가가 달라 필수 확인.

## T-04 SessionService — 완료

`backend/app/services/session.py` + 테스트 16개.

두 출처를 섞지 않는 것이 설계의 핵심이다.
- **살아 있는가** → Slurm Job 상태 (노드 장애 시 파일이 남으므로)
- **어디로 붙는가** → `connection.json` (포트·비밀번호를 DB에 복제하지 않는다)

SSH 클라이언트에 `read_text()`(없으면 None — 준비 중/종료는 정상 상태다)와
`makedirs()`(Slurm은 로그 파일만 만들고 상위 디렉터리는 안 만든다)를 추가했다.

테스트로 고정한 규칙:
- 남의 세션은 조회·접속·종료 전부 `NotFound` (없는 세션과 구분해 주지 않는다)
- **접속 대상 host는 `connection.json`의 워커 노드이고 `cluster.login_node`가 아니다**
- Slurm이 모르는 Job은 종료로 간주, slurmrestd가 죽어도 목록은 나온다
- 자원은 REST 페이로드로 간다(메모리 MB 정수, time_limit 분 정수, environment 비우지 않음)

## T-05 SSH direct-tcpip 터널 — 완료

`backend/app/clients/ssh/tunnel.py` + 테스트 10개.

목적지를 **인자로만** 받는다. `SshTarget.host`(로그인 노드)에서 유도하는 경로를 만들지
않았고, 그것을 테스트로 고정했다. 이름 해석은 로그인 노드가 하므로 포털이 못 푸는
클러스터 내부 이름도 그대로 넘어간다.

읽기는 PtySession과 같은 비블로킹 방식이며, `b""`(읽을 것 없음)와 `None`(EOF)을 구분한다 —
RFB는 스트림이라 EOF를 idle로 오해하면 연결이 끊긴 줄 모른다.

## T-06 세션 REST + WS 브리지 라우터 — 완료

`app/routers/sessions.py`, `app/schemas/session.py` + 테스트 9개. 전체 **204개 통과**,
컨테이너(3.13) import 및 라우트 등록 확인.

```
POST   /api/v1/clusters/{cid}/sessions    세션 시작        U-IA-01·02
GET    /api/v1/clusters/{cid}/sessions    내 세션 목록      U-IA-04
GET    /api/v1/sessions/{sid}             상태
GET    /api/v1/sessions/{sid}/connection  RFB 접속 정보
DELETE /api/v1/sessions/{sid}             종료(scancel)    U-IA-04
WS     /api/v1/sessions/{sid}/connect     RFB 바이트 중계
```

**응답에 호스트·포트가 없다.** OnDemand는 `/node/<host>/<port>/`로 라우팅해서 인증된
사용자면 임의 호스트로 프록시할 수 있는 통로가 생기는데, 우리는 불투명한 세션 ID만
노출하고 목적지는 백엔드만 안다. 테스트로 고정했다(응답 본문에 node/ip/port 문자열 부재).

비밀번호는 소유자에게 내려간다 — 브라우저가 RFB 인증을 직접 하기 때문이다. 백엔드가
핸드셰이크를 대신하면 감출 수 있으나 DES 챌린지 구현이 붙는다(향후 강화 여지, 스키마에 기록).

### 곁다리 수정

- 웹소켓 토큰 검증이 터미널·데스크톱 두 곳에 필요해져 `app/services/ws_auth.py`로 뺐다.
  웹소켓만 검증이 느슨해지면 그쪽이 우회 경로가 되므로 한 곳에 둔다. `TerminalService`는
  이제 이 함수를 호출한다(동작 동일).
- 레이어링 가드 `test_no_raw_sql_outside_repositories`가 `read_text(` 안의 `text(`를
  원문 SQL로 오탐했다. 단순 부분 문자열이라 `get_text(`·`plaintext(`도 걸리는 상태여서
  단어 경계(`\btext\(`)로 고쳤다. 이름을 피해 가는 대신 가드를 정확하게 만들었다.

## T-07 프론트엔드 — 완료

- `src/api/sessions.ts`, `views/user/AppsView.vue`(런처+세션 목록), `views/user/DesktopView.vue`(noVNC)
- `@novnc/novnc` 1.7 추가. 타입이 없어 `src/types/novnc.d.ts`에 **쓰는 표면만** 선언했다
  (전체를 흉내 내면 업스트림이 바뀔 때 거짓말이 된다). RFB 이벤트 map으로 detail 타입 고정.
- 라우터: `/apps` `staticOnly` 제거, `/apps/:sid` 데스크톱 화면 추가(메뉴에는 안 올림)
- 관리 화면 클러스터 폼에 **데스크톱 이미지** 필드 추가 — 이 값 하나로 레지스트리 전환

### 겪은 문제

`vite build` 실패: noVNC 1.7이 **top-level await**를 쓰는데(WebCodecs H.264 지원 감지)
기본 타깃 es2020이 지원하지 않는다. `build.target: 'es2022'`로 올렸다
(Chrome 89+ · Firefox 89+ · Safari 15+).

## T-08 실 클러스터 통합 검증 — 완료

### 겪은 문제 — Job이 제출 직후 FAILED (1:0)

```
/var/spool/slurmd/job00012/slurm_script: line 10: HOME: unbound variable
```

**slurmrestd 제출은 environment를 통째로 교체한다.** 우리가 `environment`에 PATH만 넣었으니
`$HOME`이 비었고 `set -u`에서 즉사했다. T-02에서 수동 `sbatch`로 검증할 때는 사용자 환경을
그대로 물려받아 이 차이가 드러나지 않았다 — **제출 경로가 다르면 환경도 다르다.**

두 겹으로 고쳤다.
1. 제출 시 `environment`에 `HOME`·`USER`·`LOGNAME`을 넣는다(홈은 이미 조회한 값).
2. 스크립트가 `: "${HOME:=$(getent passwd "$(id -un)" | cut -d: -f6)}"`로 한 번 더 복구한다.
   `${SLURMD_NODENAME:-?}`도 방어했다.

둘 다 회귀 테스트로 고정했다.

### E2E 결과 (실 클러스터, AD 계정)

```
[1] 세션 제출            job_id=13 session_id=5
[2] RUNNING + connection.json   3초 내 준비됨
[3] 접속 대상 host=slurm01 port=5901
    login_node=192.168.1.201   <- 목적지가 이 값이 아니다 = 워커 분리 대비 정상
[4] 터널 RFB 배너        b'RFB 003.008\n'
[5] 소유자 격리          jooyeong.lee 조회 차단 (NotFound)
[6] 세션 종료            CANCELLED
```

[3]이 이 에픽의 핵심 검증이다 — 목적지가 Slurm 노드명(`slurm01`)에서 왔고
로그인 노드 주소(`192.168.1.201`)가 아니다. 지금은 같은 기계지만 코드 경로가 갈라져 있다.

정리 확인: 잔여 Job 0, Xvnc 0, 59xx LISTEN 0.

백엔드 테스트 **206개 통과**, 프론트 `vue-tsc` + 빌드 통과, 양쪽 배포 완료.

## 남은 것

- **브라우저 실사용 확인** — 화면이 실제로 뜨고 마우스·키보드가 동작하는지는 사용자 확인 필요
- 노드 사양(2 vCPU / 3.8GB, 클러스터당 1대)이라 데스크톱 세션이 사실상 클러스터를 점유한다
- Jupyter(U-IA-01)·VS Code(U-IA-03)는 세션/프록시 계층을 그대로 쓰므로 앱 정의만 추가하면 된다
- U-IA-05 세션 공유: view-only 비밀번호는 이미 발급된다(토큰 발급만 추가하면 됨)

## T-08 후속 — 홈 디렉터리 상태에 따른 실패 두 가지 (사용자 보고)

`jungryul0515.park`은 정상 동작하는데 다른 계정들이 실패했다. 원인이 서로 달랐다.

### ① `jooyeong.lee` — 홈 소유자가 AD UID와 다름 (환경 문제)

```
/home/jungryul0515.park  201106:200513   AD uid와 일치 (정상)
/home/jooyeong.lee         2002:2000     dev01 로컬 계정 소유
/home/jrpark               2001:2000     dev01 로컬 계정 소유
AD jooyeong.lee = uid 201110
```

`/home` NFS를 **dev01 로컬 계정과 클러스터 AD 계정이 공유**한다. dev01에 동명 로컬 계정
(uid 2002, group developers 2000)이 있어 홈이 먼저 자리를 잡았고, AD 계정(201110)이
자기 홈에 못 쓴다. 인터랙티브 앱만이 아니라 **파일 관리자·터미널·Job 제출도 같이 막힌다.**

포털 코드 문제가 아니라 소유권을 바꿔야 해결된다(그러면 dev01 로컬 계정이 홈을 잃는다).
근본 해결은 dev01의 `/home`을 클러스터와 분리하는 것 — 이름이 겹칠 때마다 재발한다.

### ② `saeyoun.kang` — 홈이 아예 없음 (**코드 결함이었다**)

```
saeyoun.kang:*:201112:200513:...:/home/saeyoun.kang:/bin/bash
ls: cannot access '/home/saeyoun.kang': No such file or directory
/home  drwxr-xr-x root root
```

노드에 한 번도 로그인한 적이 없어 `pam_mkhomedir`가 홈을 만들지 않았다.
그런데 `makedirs()`가 **루트부터 훑으며 없는 경로를 전부 만들려 해서 사용자 홈까지
만들려 했다.** 홈 생성은 시스템의 몫이고, 포털이 만들면 소유권·권한이 사이트 정책과
어긋난다.

→ `makedirs(user, base, relative)`로 바꿔 **base(홈) 자체는 만들지 않는다.** 없으면
"한 번 로그인하면 만들어집니다"라고 그대로 알린다. 두 조건 모두 회귀 테스트로 고정했다.

오류 분류도 고쳤다: `EXTERNAL_SERVICE_ERROR`(포털 장애처럼 보임) → `VALIDATION_FAILED`
+ 확인할 곳 안내. 권한 문제면 Job을 제출하지 않는다 — 어차피 Slurm이 로그를 못 쓴다.

백엔드 **208개 통과**, 배포 완료.

---

# 내 사용량 / 프로필 (SCR-09, U-AC-01·02·03)

- 백엔드: `services/account.py`, `routers/account.py`, `schemas/account.py` + 테스트 12개
- 프론트: `api/account.ts`, `views/user/UsageView.vue` (`staticOnly` 제거)
- SSH 클라이언트에 `fairshare()` 추가(`sshare` 래핑)

## 설계 판단

**slurmrestd v0.0.41 association에는 계산된 fairshare가 없다** — 실측으로 확인했다
(키: account·user·partition·shares_raw·qos·max·min·priority·accounting. `usage`·`level_fs`·
`fairshare` 키가 아예 없음). 정의서 U-AC-02가 지정한 `sshare`를 SSH로 래핑했고,
§4.1의 "REST 미지원 op 한정 CLI 래핑"에 해당한다. 실패해도 REST에서 얻은 부분은 그대로 준다.

**QOS 한도는 `{set, infinite, number}` 삼중항**이다. `set=false`거나 `infinite=true`면
한도 없음이라 `None`으로 접는다 — 0으로 만들면 화면에서 "0개 제한"으로 읽힌다.
화면에는 "무제한"으로 표시한다.

GPU-시간은 `tres.allocated`에서 `type=gres, name=gpu`를 찾는다. 현 클러스터는 GRES가
없어 0이 나오며 **그게 사실이다**(가짜 값을 만들지 않는다).

SSH 공개키는 형식을 검사해 **개인키 붙여넣기를 거부**한다. 감사 로그에는 라벨만 남기고
키 본문은 남기지 않는다.

## 실 클러스터 검증

```
사용량   2026-07-07~08-06  Job 12건  CPU 0.14h  GPU 0.0h  실패 2건
         일자별 08-05 6건 / 08-06 6건, 파티션 cpu
Fairshare  dt-hpc (기본) shares_raw=1, qos=[normal, short, portal-qos-test]
QOS        normal(무제한) / short(60분, 제출 4개) / portal-qos-test(60분)
sshare     norm_shares=1.0  effective_usage=0.0  fairshare=1.0
```

백엔드 **220개 통과**, 프론트 빌드 통과, 배포 완료.

## SSH 공개키(U-AC-03) 전면 제거 — 사용자 결정

**등록만 받고 클러스터에 반영하는 경로가 없어** 사용자가 등록해놓고 SSH가 안 되는 혼란만
만든다. 그리고 지금 필요하지도 않다는 점이 논의에서 드러났다.

- 로그인 노드가 `PasswordAuthentication yes` → AD 비밀번호로 `ssh`·`scp`·`rsync`가 이미 된다
- 포털이 터미널·파일 관리자·데스크톱·Job 제출을 모두 덮는다
- 남는 용도(외부 자동화 / IDE 원격 개발 / `PasswordAuthentication no` 전환)는 아직 없다

제거 범위: 서비스 메서드·라우터 3개·`schemas/account.py`·테스트, 프론트 카드/폼/API,
`UserSshKey` 모델, `scripts/seed_dev.py` 참조, `db-erd.md`·`class_diagram.puml` 엔티티,
마이그레이션 `0005`로 `user_ssh_key` 테이블 drop(제거 전 행 수 0 확인).
엔티티 수 테스트 21 → 20으로 갱신.

되살릴 때는 `0005`의 downgrade가 표를 그대로 복원한다.

## 서비스 계정 sudo 최소 권한 가이드

[docs/portal-sudoers.md](portal-sudoers.md) 작성. **적용은 클러스터 관리자가 한다.**

발견: `ubuntu`가 `(ALL) NOPASSWD: ALL` — 무제한 root다. 정의서 §4.1의
"제한적 sudo(least privilege) … 전체 root sudo 지양"과 정면으로 어긋난다.
포털이 이 계정 키를 갖고 있으므로 **포털 침해 = 클러스터 root**다.

포털이 실제로 필요한 것은 6가지뿐이다(코드에서 도출): `sftp-server`, 로그인 셸(`-i`),
`getent passwd`, `df -P -k`, `quota`, `sshare`. Job·노드·계정·QOS는 전부 REST라 sudo가
관여하지 않고, 데스크톱 터널도 서비스 계정 자신의 권한으로 열려 sudo를 쓰지 않는다.

가이드의 핵심은 명령 목록이 아니라 **`Runas_Alias`로 대상 사용자를 AD `domain users`
(gid 200513)로 한정**하는 것이다. 명령을 아무리 좁혀도 대상에 root가 들어가면 의미가 없다.
웹 터미널용 셸 권한은 좁힐 수 없지만(그게 기능 자체), root를 배제하면 권한 상승 경로는 아니다.

### sudoers 가이드 자체 보안 검토 — 결함 발견 후 개정

가이드대로 적용해도 안전해지지 않는 것이 확인되어 문서를 고쳤다.

1. **가장 큰 결함: 기존 권한 회수를 빠뜨렸다.** `/etc/sudoers.d/90-cloud-init-users`의
   `ubuntu ALL=(ALL) NOPASSWD:ALL`과 `%sudo` 그룹 멤버십이 살아 있어, 새 파일을 추가해도
   **목록에 없는 명령은 여전히 root로 실행된다.** sudoers.d는 전부 읽고 마지막 매치가 이긴다.
   → §2.5 신설(회수 절차 + 잠김 방지 경고), §5 검증에 `sudo -n id` 추가.
2. **Runas 대상이 `domain users` 전체였다.** 현재 AD 사용자에겐 sudo가 없어 안전하지만,
   관리자에게 AD 그룹으로 sudo를 주는 순간
   `포털 → sudo -u <관리자> bash → 그 계정의 sudo → root` 경로가 열린다.
   → 포털 이용 전용 AD 그룹(`hpc-portal-users`)으로 한정하도록 변경.
3. **`ubuntu`는 공용 계정이다.** cloud-init 기본 계정이라 관리자도 쓴다.
   → 전용 서비스 계정(`portalsvc`) + `authorized_keys`의 `from=` 제한 권고.
4. **OS 레벨 감사가 없었다.** 포털 DB 감사 로그는 포털 침해 시 함께 넘어간다.
   → `log_output`/`log_input` 추가(보관 정책 선결 조건 명시).

sudoers로 막을 수 없는 것도 명시했다: 셸 허용은 대상 사용자의 SSH 개인키·Kerberos 티켓을
열고 `authorized_keys`에 백도어를 심을 수 있다(포털 키 교체로도 안 지워진다).
**sudoers는 "포털이 침해돼도 root는 아니다"까지만 보장하며, 실질 통제선은 포털의 인가 로직이다.**

### sudoers 가이드 — 서버별 런북 추가 및 순서 오류 정정

§8을 "서버별 조치 런북"으로 다시 썼다. 어떤 서버에서 무엇을 하는지 단계마다 명시한다.

**정정한 순서 오류**: 이전 판은 `포털 계정 전환 → sudoers 배치` 순서였는데, 그러면
`portalsvc`에 sudo 권한이 없는 상태로 전환되어 **파일 관리자·터미널·사용량이 즉시 실패**한다.
`sudoers 배치 → 포털 전환 → 기존 권한 회수` 순으로 바로잡았다.

**설계 개선**: 서비스 계정 홈을 `/home/portalsvc`가 아니라 `/var/lib/portalsvc`로 둔다.
`/home`이 NFS 공유라 두 노드가 같은 디렉터리를 보고, 노드별 UID가 다르면 소유권이 어긋난다.
노드 로컬 경로면 이 문제가 아예 없다.

**실측 반영**: 포털의 SSH 출발지는 파드 IP가 아니라 **k3s 노드 IP(192.168.1.100)**다
(`SSH_CONNECTION=192.168.1.100 ... 192.168.1.201 22`). `from=` 제한에 이 값을 쓴다.
추측으로 파드 대역을 적었다면 포털이 잠겼을 부분이다.

런북에 포함: 대상 서버 표, 단계별 검증 명령, 롤백 표, 흔한 실패 5가지와 대처.
중복이던 §5는 §8 포인터로 축약했다.

### sudoers 문서에 Slurm JWT 조치 추가 (§9)

문서 범위를 "sudo"에서 "sudo + Slurm JWT" 두 경로로 넓혔다. SSH만 잠그면 REST 경로가
그대로 열려 있기 때문이다.

**실측으로 확정한 것**: impersonation은 `slurm`/root 토큰에서만 된다.
일반 사용자 토큰(AdminLevel 없음)으로 시험한 결과 —
본인 Job 조회/제출 성공, slurmdb 계정 조회 성공, **남의 이름으로 제출은 1007
Protocol authentication error**. AdminLevel을 줘도 impersonation은 안 되므로
**`slurm`을 대체할 계정은 없다**는 것이 결론이다.

그래서 §9의 목표는 능력 축소가 아니라 노출 축소로 잡았다.
- 조치 B(§9.3): 관리 작업(A-US-02·03)용 토큰을 `portalsvc`(AdminLevel=Administrator)로 분리.
  이 토큰은 impersonation이 안 되므로 유출 피해가 작다. 차단 확인 curl까지 문서화.
- 조치 A(§9.4): `slurm` 토큰을 저장하지 않고 `sudo -u slurm scontrol token ... lifespan=600`으로
  온디맨드 발급. sudoers는 `token` 하위 명령과 인자까지 명시(통째 허용 금지).
  포털 코드 변경분을 파일별 표로 정리(미구현).

**정직하게 적은 한계(§9.5)**: `scontrol token username=*` 허용은 임의 사용자 토큰 발급과
같으므로 **힘은 `slurm` 토큰 보유와 동등**하다. 줄어드는 건 at-rest 자격증명·유효기간·감사
부재이지 능력이 아니다. 능력까지 없애려면 Job 제출을 `sudo -u <user> sbatch`로 옮겨야 하는데
JobService 전면 재작성이라 지금은 권하지 않는다.

**가용성 트레이드오프도 명시**: 조치 A 후에는 SSH가 끊기면 Slurm 조회까지 멈춘다.

§7에 V8 항목을 추가해 취약점 목록과 상호참조를 맞췄다.

---

# 포털 운영 설정 (SCR-15, A-OP-01·02·03·04)

- 백엔드: `repositories/content.py`, `services/ops.py`, `routers/ops.py`, `schemas/ops.py` + 테스트 18개
- 프론트: `api/ops.ts`, `views/admin/SettingsView.vue` (`staticOnly` 제거)
- 모델(`Notice`·`JobTemplate`·`PortalSetting`·`AuditLog`)과 `AuditLogRepository.search()`는
  **이미 있어서** 그대로 썼다. 마이그레이션 없음.

```
GET/PUT    /settings                 A-OP-04
GET        /notices                  U-CL-03 (인증)   POST/PATCH/DELETE  A-OP-01 (admin)
GET        /templates                U-JB-03 (인증)   POST/PATCH/DELETE  A-OP-02 (admin)
GET        /audit-logs               A-OP-03 (admin)
GET        /audit-logs/actions       필터 드롭다운용
```

## 설계 판단

**설정 변경 감사에 값을 남기지 않는다.** SMTP 호스트·웹훅 URL이 감사 로그로 새면 안 되므로
**바뀐 필드 이름만** 기록한다(`target="webhook_url"`). 테스트로 고정했다 —
비밀 경로가 포함된 URL을 저장한 뒤 로그 전체에 그 문자열이 없는지 확인한다.
값이 안 바뀌면 아예 기록하지 않는다.

**폴링 주기에 C-04를 강제한다.** 정의서 비기능 요구가 30초 이하인데 화면에서 300초로
바꿀 수 있으면 요구가 의미를 잃는다. 스키마(5~30)와 서비스 양쪽에서 막는다.

**전체 공지는 클러스터 필터에도 포함시킨다.** `cluster_id`로 조회할 때
`target_cluster_id IS NULL`(전체 대상)을 함께 준다 — 전체 공지가 클러스터를 고른
사용자에게 안 보이면 공지의 의미가 없다.

**감사 로그의 actor를 서버가 이름으로 바꾼다.** GUID는 화면에서 쓸모가 없다.
행마다 조회하지 않도록 `UserRepository.by_guids()`를 추가해 한 번에 받는다(N+1 회피).
없는 사용자로 필터하면 **0건**을 준다 — 필터를 무시하고 전체를 주면 안 된다(테스트로 고정).

**필터 드롭다운을 하드코딩하지 않는다.** `/audit-logs/actions`가 실제로 기록된 액션만
돌려준다. 코드에 목록을 박으면 새 액션이 생길 때마다 어긋난다.

## 검증

백엔드 **234개 통과**, 프론트 빌드 통과, 배포 완료.
운영 DB에 이미 감사 로그 176건이 쌓여 있어 화면에서 바로 보인다
(LOGIN 29 · TERMINAL_OPEN/CLOSE 각 19 · SESSION_CREATE 13 · AD_SYNC 10 …).

## 범위 밖

A-OP-05 헬프데스크(티켓)는 정의서에서 "선택"이고 `Ticket` 모델만 있다. 이번 범위에서 제외했다.

## ParaView 추가 (인터랙티브 앱 두 번째 버튼)

이미지 `rocky9-mate:1.1` / `/home/portal/images/rocky9-mate-1.1.sif` (387MB → **1.3GB**).

**이미지를 나누지 않고 하나로 유지**하고 `PORTAL_APP`으로 분기한다. 클러스터 설정의
`desktop_image_ref`가 필드 하나라 앱마다 SIF를 나누면 운영이 복잡해진다.

- `Dockerfile`: EPEL9의 paraview 5.11.1 + glx-utils. 의존성 `python3-pygments`가
  **CRB 저장소**에 있어 `dnf config-manager --set-enabled crb`가 먼저 필요했다.
- `start-desktop.sh`: `case "$PORTAL_APP"` 분기. paraview는 **marco(창 관리자)를 함께** 띄운다 —
  없으면 파일 열기 대화상자를 옮기거나 닫을 수 없어 세션이 그 창에 갇힌다.
- 프론트: 앱 카드를 눌러 고르는 방식으로 바꾸고 ParaView 카드 추가. 자원 폼·제출 버튼은 공유.
- **백엔드는 변경 없음** — `SessionSpec.app`·`_APP_RE`·`PORTAL_APP` 경로가 이미 앱을 받고 있었다.
  회귀 테스트만 추가(`test_app_selection_reaches_the_container`).

### 실측 (노드에서 실제 기동)

```
PORTAL_APP=paraview → connection.json app=paraview, paraview·marco 프로세스 확인
OpenGL renderer : llvmpipe (LLVM 21.1.8, 256 bits)
OpenGL version  : 4.5 (Compatibility Profile) Mesa 25.2.7   ← ParaView 요구(3.2+) 충족
direct rendering: Yes
```

GPU가 없어 소프트웨어 렌더링이다. **동작하지만 2 vCPU에서 큰 데이터셋은 실용적이지 않다.**
GPU 노드가 생기면 VirtualGL을 얹는 것이 정석이다.

두 클러스터의 `desktop_image_ref`를 1.1로 갱신했다. 1.0 SIF는 롤백용으로 남겨 둔다.
백엔드 **235개 통과**.

### ParaView 단일 앱 모드 — 최소화 함정 수정 (이미지 1.2)

사용자 보고: 창을 최소화하면 되살릴 방법이 없다. 작업표시줄이 없는 단일 앱 모드라
세션이 사실상 잠긴다.

`start-paraview.sh`가 세 경로를 막는다 — 버튼(`button-layout ":maximize,close"`),
단축키(`minimize "disabled"`), 제목표시줄 우클릭 메뉴(`action-right-click-titlebar
"toggle-maximize"`).

**겪은 문제 둘.**

1. 처음에 `minimize "[]"`로 썼더니 marco가
   `"[]" found in configuration database is not a valid value for keybinding "minimize"`로
   무시했다. 키바인딩의 "끔" 값은 빈 배열이 아니라 **`"disabled"`** 다.
2. gsettings는 **사용자 dconf(NFS 홈)에 영구 저장**된다. 그대로 두면 여기서 끈 최소화가
   다음 데스크톱 세션까지 따라간다. → `start-mate.sh`를 만들어 MATE 기본값을 명시적으로
   되돌린다. 앱마다 자기 창 정책을 쓰는 구조가 됐다.

검증(slurm02, 이미지 1.2): 세션 기동 후 `~/.config/dconf/user`에
`button-layout=:maximize,close`, `minimize=disabled`가 실제로 기록됨. marco 경고 없음.

**사용자 화면에 반영이 안 된 진짜 이유는 따로 있었다** — 클러스터
`desktop_image_ref`가 아직 1.1을 가리키고 있었다. 이미지를 만들고 참조를 안 바꿨다.
두 클러스터를 1.2로 갱신했다. 실행 중인 세션은 재시작해야 적용된다.

작업표시줄을 원하면 `tint2`(EPEL9)를 넣고 이 설정을 빼는 선택지도 README에 적어 뒀다.

### ParaView 창 버튼 전면 제거 + 시작 시 최대화 (이미지 1.3)

사용자 보고 둘. (1) X 버튼으로 닫아도 최소화와 같은 문제가 난다 — 앱이 끝나면 세션이
그대로 종료되고 화면만 남는다. (2) 처음 뜰 때 해상도에 맞는 최대 크기여야 한다.

**버튼은 셋 다 없앴다.** `button-layout ":"` 로 제목표시줄을 비우고, 단축키도
`minimize "disabled"` + `close "disabled"`로 막았다. 제목표시줄 자체는 남긴다 —
대화상자를 옮기려면 필요하다. `start-mate.sh`에도 `close "<Alt>F4"` 복원을 추가했다
(dconf가 NFS 홈에 남아 데스크톱 세션까지 따라가므로 대칭이 유지돼야 한다).

닫기까지 막으면 **대화상자를 못 닫는 것 아닌가**가 유일한 위험이었다. 화면 캡처로
확인 — ParaView Welcome 창은 자체 `Close` 버튼을 갖고 있다. 세션 종료는 포털에서 한다.

**최대화**는 `wmctrl`(EPEL9)을 이미지에 넣고, 창이 뜬 뒤 백그라운드에서 최대화한다.
ParaView가 지난 세션의 창 크기를 자기 설정에 저장했다가 복원하는데, 홈이 NFS라 그 값이
노드를 넘어 따라온다. 스플래시가 먼저 뜨므로 **제목이 붙은 첫 창**을 최대 60초 기다린다.

검증은 dev01 docker에서 화면을 직접 캡처해서 했다(노드 SSH 없이 창 정책 전체 확인).

```
wmctrl -l -G -x
0x00a00006  0 0 56 1280 772  paraview.ParaView  ParaView 5.11.1   ← 1280x800 가득
0x00a00022  0 267 144 748 535 paraview.ParaView  Welcome to ParaView

PORTAL_APP=paraview → button-layout ':' / minimize 'disabled' / close 'disabled'
PORTAL_APP=desktop  → 'menu:minimize,maximize,close' / '<Alt>F9' / '<Alt>F4' 복원 확인
```

두 클러스터의 `desktop_image_ref`를 1.3으로 갱신했다. 실행 중인 세션은 재시작해야 적용된다.

### 방향 전환 — 창 버튼 원복 + 작업표시줄(tint2) (이미지 1.4)

사용자가 `File → Exit` 스크린샷을 보내왔다. **버튼을 막는 접근 자체가 틀렸다** — 최소화·
닫기 버튼을 다 지워도 메뉴의 Exit는 막을 수 없다. 막는 대신 **되살릴 수단을 준다**로 바꾼다.

- 창 버튼(최소화·최대화·닫기)은 **전부 원복**한다.
- 앱을 닫으면 세션(Slurm Job)이 종료되는 지금 동작은 **그대로 둔다**(사용자 결정).
- 최소화 복구는 컨테이너 안 **작업표시줄(tint2, EPEL9)** 이 맡는다. Alt+Tab은 브라우저·
  호스트 OS가 가로채는 경우가 많아 의존할 수 없다.

포털(백엔드·프론트엔드) 변경은 **없다**. 컨테이너 이미지만 바뀌었다. 테스트 235개 그대로 통과.

**설정을 빼는 것으로는 원복이 안 된다.** gsettings는 사용자 dconf(NFS 홈)에 영구 저장되므로
1.2/1.3을 써 본 사용자 홈에는 `button-layout=':'`, `minimize/close='disabled'`가 남아 있다.
기본값을 명시적으로 다시 쓰는 `reset-window-policy.sh`를 만들고 두 앱 스크립트가 함께 부른다
(같은 값을 두 곳에 두면 한쪽만 고쳐진다).

`tint2rc`는 이미지에 넣고 `-c`로 지정한다 — 지정하지 않으면 tint2가 사용자 홈에 기본 설정을
만들고 그것이 세션·노드를 넘어 따라온다. 설정에서 중요한 것은 **`strut_policy = follow_size`**
하나다. 없으면 최대화한 앱이 막대를 덮어 복구 수단 자체가 사라진다.

**최대화 대상 선택도 고쳤다.** tint2 막대가 `wmctrl` 목록에 나오므로 제목만 보고 첫 창을
고르면 막대를 최대화할 수 있다 → 클래스가 `paraview`인 창만 고르도록 바꿨다.

검증(dev01 docker + 화면 캡처):

```
paraview : 'menu:minimize,maximize,close' / '<Alt>F9' / '<Alt>F4' / 'menu'  ← 네 값 원복
           작업 영역 WA 1280x776 (=800-24), 메인 창 높이 748 → 막대를 안 덮는다
           xdotool로 최소화 → 캡처에 막대의 "ParaView 5.11.1" 버튼 확인
           → 활성화하니 최대화 상태 그대로 복귀
desktop  : 같은 네 값 기본값, tint2 안 뜸(mate-panel 상·하단만)
```

두 클러스터의 `desktop_image_ref`를 1.4로 갱신했다. 실행 중인 세션은 재시작해야 적용된다.

#### 사고 기록 — 이미지 빌드가 dev01 디스크를 채워 포털 pod이 evict됨

1.4 SIF 변환 직후 `kubectl exec`이 `pod mysql-0 does not have a host assigned`로 실패했다.
원인은 **내가 쌓아 둔 빌드 산출물**이다. `/` 31GB 중 docker가 이미지 10.9GB + 빌드 캐시
10.0GB를 쓰고 있었고, 90%를 넘기며 kubelet이 `DiskPressure`를 올려 포털 pod을 전부 evict했다.

조치.

```
docker builder prune -af        빌드 캐시 10GB 회수
docker image prune -f           dangling 이미지 정리
docker rmi rocky9-mate:1.0 1.1 1.2 1.3   → 90% → 66%
```

SIF는 `/home`(다른 파일시스템)에 있어 **롤백용 1.0~1.4는 그대로 남아 있다.** docker 쪽
태그만 지웠고 필요하면 Dockerfile로 다시 만든다.

**여파가 하나 더 있었다.** DiskPressure 상황에서 kubelet의 이미지 GC가 containerd에서
`hpc-portal-backend:0.1.0`·`hpc-portal-frontend:0.1.0`을 지워 버려, 압박이 풀린 뒤에도
pod이 `ErrImageNeverPull`로 못 떴다(`imagePullPolicy: Never`라 받아올 곳이 없다).
`deploy/k8s/README.md`의 import 절차로 되살렸다.

```
sudo docker save hpc-portal-backend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
sudo docker save hpc-portal-frontend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
```

복구 확인: pod 4개 Running, 프론트 200, API 401(미인증 정상). 현재 `/` 사용률 71%.

**교훈**: 이미지 빌드 뒤에는 반드시 `docker builder prune`을 돌린다. 빌드 캐시가 이미지만큼
쌓이고, 이 노드는 포털 운영과 이미지 빌드를 같은 31GB 디스크에서 한다.

### 앱을 닫으면 화면도 자동으로 정리된다 (U-IA-02·04)

사용자 확인: ParaView를 끄면 Slurm Job이 cancel된다. 그런데 **브라우저는 그걸 몰랐다.**
원인은 백엔드에 있었다.

`WS /sessions/{sid}/connect`의 출력 펌프는 원격이 EOF를 주면 루프만 빠져나오고 **웹소켓을
닫지 않았다.** 입력 루프는 계속 `receive_bytes()`를 기다리므로 연결이 그대로 살아 있고,
noVNC는 멈춘 화면을 붙잡은 채 `disconnect` 이벤트조차 내지 않는다.

**백엔드** — EOF에서 웹소켓을 닫는다. 닫은 뒤 `receive`를 부르면 starlette이 `RuntimeError`를
내므로 예외 목록에 추가했다. 회귀 테스트(`test_websocket_closes_when_the_session_dies`)는
즉시 EOF를 주는 가짜 터널을 물려 `WebSocketDisconnect`를 확인한다 — 수정을 되돌리면 이 테스트는
**응답 없이 멈춘다**(실제로 확인함). 테스트 236개 통과.

**프론트(DesktopView)** — 끊긴 이유를 웹소켓만 보고 단정하지 않는다. 예상치 못한 끊김이면
`GET /sessions/{sid}`로 **Slurm 상태를 확인**하고(2초 간격 4회 — 상태 전이에 몇 초 걸린다),
`is_running=false`면 안내 후 목록으로 보낸다. 아직 살아 있으면 재연결 버튼을 남긴다.

세 가지를 구분해야 해서 표시를 두 개 뒀다.

- `expected` — 사용자가 누른 "연결 끊기", 인증 실패, 화면 이탈. 종료로 오해하면 안 된다.
- `generation` — 재연결하면 **이전 연결의 뒤늦은 disconnect 이벤트**가 따라온다. 세대가
  다르면 무시한다. 이걸 안 넣으면 재연결할 때마다 종료 판정 로직이 헛돈다.

배포: 백엔드·프론트 이미지 재빌드 → containerd import → rollout. 이번엔 빌드 후
`docker builder prune -af`까지 붙였다(앞선 디스크 사고의 후속).
