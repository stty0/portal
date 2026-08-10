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
| 3 | A-US-06만 화면 미매핑(65개 중 유일) | **결정: 화면 추가** — qos.html에 "자원 신청 승인" 카드 + `resourceRequestModal` 신설 → **2026-08-07 철회, 카드 제거**(아래) |
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

### 세션 X 접근 제어 + `--exclusive` 문구 정정 (이미지 1.5)

사용자가 인터랙티브 앱 폼의 `--exclusive` 체크박스가 뭐냐고 물었다. 답을 검증하다
**설명이 두 가지를 섞고 있다는 것**을 사용자가 정확히 지적했다.

- `--exclusive`는 스케줄링 옵션이다. 그 노드에 다른 사용자 Job이 배정되지 않게 할 뿐이고
  접근 제어와 무관하다.
- 그런데 체크박스에는 "같은 노드의 다른 사용자가 이 세션에 접근할 수 없습니다"라고
  적혀 있었다 — **자원 옵션을 보안 기능처럼 설명**한 것이다.

문구가 결과적으로 틀리지 않았던 이유는 따로 있었다. `start-desktop.sh`가 Xvnc를 `-auth`
없이 띄워 **X 서버가 로컬 연결을 인증 없이 받고 있었다.** RFB 비밀번호는 VNC 프로토콜
인증이라 이 경로를 막지 못한다 — X에는 유닉스 소켓(`srwxrwxrwx`)이라는 별도 입구가 있다.

dev01 docker에서 실제로 공격해 확인했다(1.4).

```
intruder 계정 DISPLAY=:1 접속 → 성공, 화면 캡처 → 성공(191KB PNG),
키 입력 주입 → 성공, 활성 창 이름 조회 → "Welcome to ParaView"
```

즉 **스케줄링 옵션이 사실상 유일한 방어선**이었다. 인과가 뒤바뀐 상태다.

**조치** — Xvnc를 띄우기 전에 128비트 MIT-MAGIC-COOKIE를 만들어 `-auth`로 넘긴다.
쿠키는 노드 로컬(`$XDG_RUNTIME_DIR/Xauthority`, 600·디렉터리 700)에 두고 세션 종료 시
지운다. 포트 탐색 루프가 디스플레이를 바꿔가며 시도하므로 **루프 안에서** 시도할
디스플레이마다 등록한다 — 쿠키가 Xvnc보다 먼저 있어야 한다.

같은 공격을 1.5에 그대로 재현했더니 **네 경로 전부 거부**됐다(xdpyinfo·캡처·주입·쿠키
파일 읽기). 세션 본인은 정상이다(ParaView·marco·tint2·mate-session 기동 확인) —
`XAUTHORITY`를 export하므로 자식 프로세스가 전부 물려받는다. 이걸 못 물려받으면 GUI가
아예 안 뜨는 것이 이 변경의 주된 회귀 위험이라 양쪽 모드를 다 확인했다.

체크박스 문구는 보안 주장을 빼고 실제 동작과 대가로 바꿨다(성능은 안정적이지만 대기열이
길어진다). `docs/plan.md` §3.4에도 "자원 옵션이지 접근 제어가 아니다"를 명시했다.

**범위 밖(기록)**: Xvnc는 `-localhost no`라 클러스터 네트워크 어디서든 5901에 닿는다.
거기 방어선은 세션별 랜덤 VNC 비밀번호이고, `-AlwaysShared`라 비밀번호를 아는 사람은
사용자를 밀어내지 않고 조용히 같이 본다. 이번 변경은 이 경로를 바꾸지 않았다.

#### 디스크 사고의 진짜 원인을 찾았다

앞서 포털 pod이 evict된 건을 docker 빌드 캐시 탓으로 적었는데, 더 큰 것이 있었다 —
**`/root/.apptainer` 캐시 11.2GiB**. SIF 변환 시 `APPTAINER_TMPDIR`만 `/home`으로 돌리고
`APPTAINER_CACHEDIR`은 그대로 둬서 root 홈에 blob이 쌓였다. `apptainer cache clean -f`로
정리했다(31G 중 79% → **42%**). `/home`은 별도 NFS(100T)라 SIF 자체는 `/`와 무관하다.

앞으로 SIF 변환 시에도 `APPTAINER_CACHEDIR`을 `/home` 아래로 지정한다.

### 전송 구간 암호화 조사 — "현재 방식 유지" 결정 (코드 변경 없음)

`--exclusive` 질문에서 시작한 검토의 마지막 갈래다. X 인증(쿠키)은 1.5로 닫았고,
남은 것은 **로그인 노드 → 워커:5901 평문 구간**이었다.

**"패스워드로 막혀 있는데 평문이 왜 문제냐"** — 비밀번호는 *들어오는 것*을 막지
*들여다보는 것*을 막지 않는다.

- RFB 인증은 접속 시 1회다. 이후 프레임버퍼(=화면)와 `KeyEvent`(=키 입력)는 평문이라
  **인증을 통과할 필요 없이 관찰만으로** 읽힌다. 무결성 보호도 없어 주입도 가능하다.
- VncAuth는 DES 챌린지-응답이라 캡처하면 오프라인 대입이 된다. Xvnc의
  `UseBlacklist=on / BlacklistThreshold=5`(기본값, 실물 확인)는 **온라인 시도에만** 걸린다.
- 완화 요소는 비밀번호가 세션마다 새로 발급된다는 점이다 — 깨도 그 세션 하나뿐이다.

**"TLS로 암호화할 수 없나"** — noVNC로는 안 된다. `@novnc/novnc` 1.7 소스를 직접 확인했다.

```
core/rfb.js:1670  "VeNCrypt ... only supports version 0.2 and only Plain subtype"
지원  : None(1), VncAuth(2), RA2ne(6), Tight(16), VeNCrypt(19, Plain만)
미지원: TLSVnc·X509Vnc 등 TLS 서브타입, 세션을 암호화하는 RA2(5)
```

브라우저 JS가 WebSocket 안에서 TLS 핸드셰이크를 못 하기 때문이다. noVNC의 암호화 답은
WSS이고 **이미 쓰고 있다**. `RA2ne`는 양쪽 다 지원하지만 이름의 `ne`가 *no encryption* —
자격증명만 보호하고 세션은 평문이라 반쪽짜리다. **채택하지 않았다.**

**핵심은 평문 구간이 애초에 noVNC가 관여하는 구간이 아니라는 것이다.** 백엔드가 SSH
`direct-tcpip`을 열면 로그인 노드의 sshd가 워커로 평문 TCP를 건다. 그래서 유일한 깔끔한
해법은 **SSH를 워커까지 한 홉 연장**(`ssh -J login worker`)하는 것이고, 그러면 Xvnc를
`-localhost yes`로 묶어 5901 포트를 네트워크에서 없앨 수도 있다. 대가는 포털 서비스
계정의 워커 SSH 접근이며 §4.1 전제("로그인 노드 자격증명만 보유")를 조정하게 된다.

**결정: 현재 방식 유지.** 로그인 노드와 워커가 같은 기계라 그 구간은 loopback이고
네트워크에 나가지 않는다. 위험은 (1) 노드 분리 **와** (2) 그 구간 관찰 가능한 위치가
동시에 성립할 때 실현된다. `docs/plan.md` §3.4에 전제조건과 해법을 명시해 두었으니
**노드를 분리하기 전에 그 절을 먼저 읽는다.**

다시 조사하지 않도록 근거 위치를 남긴다 — noVNC 지원 목록은 `core/rfb.js:1551-1559`,
VeNCrypt 제약은 같은 파일 1670행 주석, Xvnc 옵션 기본값은 `Xvnc -help`.

결정과 조사 내용을 **[docs/session-transport-security.md](session-transport-security.md)** 로
따로 뽑았다(나중에 다시 꺼내볼 문서라 설계 문서 안에 묻어두지 않는다). 위에 적은 것에
더해 다음을 담았다.

- **판단 근거**: `/home`이 NFSv3 `sec=sys`다(`findmnt -no OPTIONS /home`으로 확인).
  같은 네트워크 위치의 공격자는 **이미 사용자 홈을 평문으로 읽고 쓸 수 있다.** 즉 VNC
  평문 구간은 새로운 종류의 노출이 아니고, **VNC만 감싸는 것은 보안 효과가 거의 없다** —
  내부망을 못 믿게 되면 NFS(krb5p)까지 함께 다뤄야 한다. 이 결정은 클러스터의 기존
  전제("내부망을 신뢰한다")와 일관된 것이다.
- **재검토 조건 3가지**: 노드 분리 / 규정·계약상 기밀 데이터 유입 / 비신뢰 테넌트 유입.
- **착수 시 제일 먼저 막힐 지점**: 계산 노드의 `pam_slurm_adopt`. Job이 없는 사용자의
  SSH를 거부하므로 포털 서비스 계정이 막힌다. 우회는 예외 등록, 또는 **두 번째 홉을
  세션 소유자 계정으로 붙는 것**(그 사용자는 해당 노드에 Job이 있어 통과하고, 로그인
  노드에서 이미 `sudo -u <user>`를 쓰는 흐름과도 맞는다).
- 무결성 항목을 명시했다 — 평문 구간에서는 **키 입력 주입**도 가능하다. 엿보기와 성격이
  다르고, 보통 수용 여부를 가르는 항목이다.

### 노드 독점이면 자원 지정을 하지 않는다 (U-IA-01)

사용자 질문: "16코어 노드를 독점하면서 2코어만 할당하면 14코어는 손해 아닌가?
아니면 남은 코어를 일반 batch job이 쓸 수 있나?"

**남은 코어를 다른 Job이 쓸 수는 없다** — 그게 `--exclusive`의 정의다. 그래서 지적이 맞다.
검토해 보니 "의미가 없다"보다 강한 결론이 나왔다.

- **CPU**: `--exclusive`면 Slurm이 노드의 CPU를 통째로 할당한다. 코어 수 지정은 무의미할
  뿐 아니라, `cgroup.conf`의 `ConstrainCores` 설정에 따라 **그 값으로 cpuset이 좁혀질 수
  있다** — 노드를 막아놓고 2코어만 쓰는 결과가 된다.
- **메모리**: 이쪽은 분명하다. `--mem`은 독점과 무관하게 **하드 캡**이다. 기본값 3GB로
  독점하면 64GB 노드를 잡아놓고 3GB만 쓴다. Slurm에서 "노드 메모리 전체"는 `--mem=0`이다.

**조치** — `exclusive`면 `cpus_per_task`를 보내지 않고 `memory_per_node=0`으로 연다.
REST 페이로드(`services/session.py:_job_properties`)와 `#SBATCH` 지시자
(`services/session_script.py`) **양쪽에 같은 규칙**을 넣었다. 한쪽만 고치면 손으로
sbatch할 때 결과가 갈린다. 프론트는 체크 시 CPU·메모리 입력을 "노드 전체"로 바꿔
비활성화한다. 테스트 2개 추가(238개 통과).

`schemas/session.py`의 `exclusive` 주석도 고쳤다 — 프론트 문구는 앞서 정정했는데
백엔드에는 "같은 노드의 다른 사용자가 VNC 포트에 접근하는 것을 막는다"는 옛 설명이
남아 있었다(자원 옵션 ↔ 접근 제어 혼동).

**실 클러스터에서 확인했다(Job 36, slurm01).** `exclusive: "true"` + `memory_per_node: 0`
으로 짧은 Job을 제출하고 tres를 읽은 뒤 즉시 취소했다.

```
memory_per_node = {'set': True, 'infinite': False, 'number': 0}   ← 0이 그대로 반영됨
tres_req_str    = cpu=1,mem=3915M,node=1,billing=1
tres_alloc_str  = cpu=2,mem=3915M,node=1,billing=2
slurm01 노드     : cpus=2, real_memory=3915
```

두 가지가 한 번에 증명됐다.

1. **`memory_per_node=0`은 "노드 전체"로 받아들여진다** — 미설정으로 떨어지지 않는다.
   할당 `mem=3915M`이 노드 `real_memory`와 정확히 일치한다.
2. **`--exclusive`는 노드의 CPU를 전부 할당한다** — 요청은 `cpu=1`(코어 수를 안 보냈으니
   기본 1)인데 할당은 `cpu=2`다. 2 vCPU 노드라 측정이 안 될 줄 알았는데, req와 alloc이
   갈리면서 오히려 명확히 드러났다. 코어 수를 보내지 않기로 한 결정이 옳았다.

`billing`도 1 → 2로 따라 올라간다. **독점하면 노드 전체가 과금 대상**이라, 자원을 적게
잡아 봐야 요금이 줄지 않는다는 점도 같이 확인됐다(Billing 규칙 설계 시 참고).

### 파일 관리자 조작 기능 (U-FM-02 업/다운로드 · U-FM-04 조작)

SCR-07에 업로드·다운로드·파일 생성·삭제·이름 변경·디렉터리 생성·옮기기를 구현했다.

**설계의 중심은 하나다 — 조회와 변경이 같은 경계를 쓴다.** `browse`는 이미 홈 + 실제로
존재하는 바로가기만 허용 루트로 삼는데(`FileService._roots`로 뽑아 공유), 변경 작업이
그보다 넓으면 **목록에 안 보이는 곳을 지울 수 있게 된다.** 그래서 모든 변경이 같은
루트 목록을 받아 `LoginNodeClient`의 경로 관문을 지난다.

관문은 둘이다.

- `_guard` — **있는** 경로: 서버 `realpath`로 정규화한 뒤 루트를 확인한다. 정규화 뒤에
  검사해야 `..`와 심볼릭 링크로 밖을 가리키는 경로가 걸린다.
- `_guard_new` — **없는** 경로(생성·이동 목적지): 없는 경로는 정규화 결과를 믿을 수
  없으니 **부모까지만** 서버에 묻고 이름을 이어 붙인다. 마지막 조각의 `..`는 부모를
  검사해도 밖으로 나가므로 이름 단계에서 직접 막는다.

그 밖에 안전장치로 넣은 것들.

- **홈 등 최상위 자체는 삭제·이동 불가**(`_reject_root`). 실수 한 번에 홈이 날아가지 않게.
- **덮어쓰지 않는다.** 파일 생성은 `x` 모드(배타), 이동은 `rename`(목적지가 있으면 실패).
- **재귀 삭제는 명시적으로 요청할 때만.** 프론트는 디렉터리 삭제 시 "안의 모든 항목"을
  경고한 뒤에야 재귀를 요청한다.
- **재귀 삭제는 링크를 따라가지 않는다.** `stat`이 아니라 `lstat`으로 판정한다 — 링크를
  따라가면 링크가 가리키는 바깥 디렉터리를 지우게 된다. 깊이 상한(64)도 뒀다.
- **업로드는 스트리밍**이다(256KB 청크). 서버 메모리에 통째로 담지 않고, 상한
  (`file_upload_max_mb`, 기본 2GB)을 넘으면 중단하고 **반쯤 쓰인 파일을 지운다.**
- **다운로드는 검증을 먼저 끝내고** 반복자를 돌려준다. 스트림이 시작된 뒤에는 오류를
  HTTP 상태로 바꿀 수 없다. SSH 연결은 반복자가 끝날 때 닫힌다.
- 파일 변경은 **감사 로그**에 남긴다(`FILE_MKDIR`·`FILE_UPLOAD`·`FILE_DELETE` 등) —
  사라진 파일의 경위를 나중에 확인할 수 있어야 한다.

`python-multipart`를 의존성에 추가했다. FastAPI의 `Form`/`File`은 이게 없으면 **기동
시점에** 죽는다.

**검증** — 백엔드 261개 통과. 라우터 테스트는 서비스가 루트를 넘기는지 보고,
`test_ssh_files.py`는 경로 관문 자체(접두사만 같은 `/home/jrpark2`, `..`, 밖을 가리키는
심볼릭 링크)를 따로 본다.

실 클러스터에서도 왕복 확인했다(전용 임시 디렉터리에서 작업 후 삭제, **17/17 통과**).

```
정상   : 디렉터리·하위 디렉터리·파일 생성, 업로드(13B), 다운로드(내용 일치),
         이름 변경, 옮기기, 파일 삭제, 재귀 삭제
차단   : 홈 밖 생성/다운로드, `..` 탈출, 홈 자체 삭제, 같은 이름 덮어쓰기,
         비어 있지 않은 디렉터리 비재귀 삭제, 디렉터리 다운로드
```

**남은 것**: U-FM-04의 복사·권한 변경·압축/해제와 U-FM-03 파일 편집은 이번 범위 밖이다.

### 공지사항 화면 (SCR-16, U-CL-03)

**백엔드는 이미 있었다.** SCR-15(A-OP-01) 작업 때 만든 `GET /notices`가 인증 사용자면
조회되도록 열려 있고, 저장소가 `cluster_id`를 주면 **그 클러스터 대상 + 전체 대상(NULL)**
을 함께 준다. 그래서 이번 작업은 프론트 전용이다.

- `NoticesView` — 자리표시자(`NotImplemented`)를 실제 목록으로 교체.
- `ClusterView`의 공지 카드도 같은 자리표시자였다. 같은 API를 쓰므로 함께 채웠다.
- 라우터 메타에서 `staticOnly`를 뺐다 — 사이드바의 "静"(백엔드 미연결) 배지가 사라진다.

**노출 기간으로 상태를 나눈 것이 이 화면의 요지다.** 지난 공지와 진행 중인 공지가 같아
보이면 **끝난 점검 안내를 보고 작업을 미루는 일이 생긴다.**

- `진행 중` / `예정` / `종료`로 나누고 그 순서로 정렬한다(같은 상태 안에서는 최신 우선).
- 종료된 공지는 흐리게 처리하되 **지우지는 않는다** — 지난 공지를 확인할 데가 필요하다.
- 시작·종료가 모두 비면 "상시"로 적는다. 빈 칸은 정보가 아니다.
- 클러스터 첫 화면(SCR-02)에는 **지금 유효한 것만** 짧게 보여주고 전체는 SCR-16로 넘긴다.
  파티션 조회와 공지 조회는 따로 처리했다 — 한쪽이 실패해도 다른 쪽은 보여야 한다.
  → **뒤에 철회했다.** 공지가 톱바 메뉴로 올라간 뒤 이 요약 카드는 중복이 됐다(아래 참조).

검증: 프론트 빌드 통과, 실 DB의 공지 3건이 API로 정상 조회됨(전역 공지 3건, 배너 1건).
백엔드 변경이 없어 테스트는 261개 그대로다.

**발견(수정하지 않음)**: 라우터 메타의 `staticOnly`가 **파일 관리자(SCR-07)·웹 터미널
(SCR-08)에도 남아 있다.** 둘 다 실제로 구현되어 있는데 사이드바에 "백엔드 미연결" 배지가
붙는다. 이번 요청 범위 밖이라 보고만 한다.

### 톱바 전역 검색창 제거

사용자 판단은 "범위나 화면 표시하기 애매하다"였는데, 코드를 보니 그보다 분명했다 —
**`v-model`도 핸들러도 없는 순수 장식**이었다. 타이핑해도 아무 일이 일어나지 않는다.
동작하지 않는 입력창은 없는 것보다 나쁘다. 사용자는 검색을 시도하고 반응이 없으면
고장으로 읽는다.

`TopBar.vue`에서 주석 + `div` 블록 14줄을 지웠다. **절대 배치**(`absolute left-1/2`)라
flex 흐름 밖에 있어 브랜드(좌)·클러스터/계정(우) 배치는 그대로다 — 빈 자리가 생기지 않는다.
연결된 상태·핸들러·키보드 단축키도 없었다.

**범위는 Vue 앱만**이다(사용자 결정). 정적 프로토타입 `design/`의 `.gnb-search`는 22개
파일에 있고 문구도 다른데(`Job ID, 파일, 앱 및 문서를 검색하세요.` + `[Alt+s]`), 최초 디자인
기록으로 그대로 뒀다. CLAUDE.md의 톱바 동기화 규칙과는 의도적으로 다르게 간 것이다.

검증: 잔여 참조 없음(grep), 프론트 빌드·배포 통과, 백엔드 261개 그대로.

### 사이드바 "静" 배지 정리

사용자 지적: 이제 제거해도 되지 않나. 확인해 보니 **8개 중 7개가 사실과 달랐다.**

| 화면 | 실제 |
|---|---|
| 파일 관리자·웹 터미널·노드/파티션·계정·통계/리포트·비용/Billing | 구현됨(실 API) |
| QOS | 주 기능 구현, "자원 신청 승인" 카드만 정의서 미설계 |
| **License 관리(SCR-17)** | **미구현** — 백엔드 API 자체가 없음 |

7개에서 `staticOnly`를 뺐고 **License 하나만 남겼다.** 거기는 배지가 정확한 정보다.

QOS를 뺀 이유: 주 기능이 도는데 메뉴에 "백엔드 미연결" 배지가 붙으면 화면 전체가 안 되는
것처럼 읽혀 **오히려 오해를 키운다.** 미구현 카드는 화면 안에서 `NotImplemented`가 이미
알려준다.

배지 메커니즘(`RouteMeta.staticOnly` + `SideNav`)은 그대로 둔다 — License가 쓰고, 앞으로
새 화면을 자리표시자로 먼저 올릴 때도 쓸 수 있다.

정리 중에 플래그를 빼면서 여러 줄로 남은 `meta` 세 개(nodes·accounts·qos)를 이웃과 같은
한 줄 형태로 되돌렸다.

### 문서 전면 현행화 (코드 기준, 코드 무변경)

코드를 정본으로 삼아 md 문서 전체를 대조·갱신했다. **코드는 한 줄도 바꾸지 않았다.**

**가장 심각했던 것은 프로젝트 정체성이었다.** `CLAUDE.md`·`AGENTS.md`·`notes.md`가
이 프로젝트를 "프레임워크·빌드도구 없는 정적 HTML/CSS 프로토타입"으로 서술하고 있었다.
매 세션 컨텍스트로 읽히는 파일이라 틀린 전제로 계속 작업하게 된다. 실제 스택(FastAPI +
Vue 3/TS/Tailwind + k3s)과 현재 구조 규칙(계층 강제·사용자 스코프·경로 관문)으로 교체하고,
검증 방법도 태그 균형/링크 grep에서 pytest·`vue-tsc`로 바꿨다. 서브에이전트 두 개
(`portal-verifier`·`portal-reviewer`)도 같은 이유로 정의를 다시 썼다.

**두 번째는 폐기된 설계가 현재형으로 남아 있던 것.** 인터랙티브 세션의 초기 설계
(Traefik HTTP provider 폴링 → 컴퓨트 노드 직결)를 plan.md §3.3에서 기각하고 백엔드
WebSocket 브리지로 갔는데, `Architecture.md`·`db-erd.md`·`backend-design.md`는 폐기된 쪽을
설명하고 있었다. 코드는 이미 자백하고 있었다 — `InteractiveSession` docstring이
"초기 설계의 잔재로 사용하지 않는다"라고 적혀 있었는데 ERD만 안 바뀌었다.
지우지 않고 **"채택하지 않음 + 이유 + 대체안"** 형태로 남겼다. 왜 안 갔는지가 자산이다.

**api.md는 라우터를 `ast`로 파싱해 대조했다.** 정규식으로는 여러 줄 데코레이터를 놓친다.

```
코드 84 · 문서 129(미구현 46 포함)
문서 누락 0 · 잘못 미구현표시 0 · 구현된 척 적힌 것 0
```

누락 17개를 추가하고(파일 조작 4, 세션 4, job-options, preview-script, accounts 4,
setup/probe, audit-logs/actions), 경로가 바뀐 것(`files/content|op|locations` →
`files/file|move|directory`)을 정정했다. 미구현 44행은 **지우지 않고 취소선 + "미구현"**
으로 표시했다 — 로드맵 가치가 있다.

**수치·상태 표기**: `78 tests`→261, `21개 엔티티`→20, "나머지 도메인 미구현" 목록,
"SSH/SFTP 경로 미구현", "slurmrestd를 실물로 검증하지 못해", `user/ 9개`→10,
exec-plan 수용 기준 19개 전부 미체크 → 완료 표시.

**정의서(SoT)** 에는 SSH 공개키 등록이 남아 있어, 요구사항은 보존하되 2026-08-06 제외
결정과 근거를 각주로 달았다. 그리고 **"구현 여부는 이 문서가 아니라 api.md·progress.md를
본다"** 는 원칙을 명시했다 — SoT를 진척 관리표로 만들지 않기 위해서다.

검증: 내부 링크 **0건 깨짐**(전 md 파일 스캔), api.md ↔ 코드 **차이 0**, pytest 261개 그대로.

`progress.md`의 과거 기록(예: 당시 "21테이블")은 **고치지 않았다** — 시간순 로그라
그때의 사실이 남아야 한다.

### 그룹 경로 = Slurm 계정 (U-FM-01)

사용자가 slurm01에 `/scratch`·`/groups`를 마운트하고 "반영하는 기능이 없는 것 같다"고 물었다.
확인해 보니 **설정 기능은 있었다** — 클러스터 관리(SCR-18)에 경로 템플릿 필드가 있고 값도
`/scratch/{user}`·`/groups/{group}`으로 들어가 있었다. 막고 있던 것은 두 가지였다.

**1. 코드 결함 — `{group}`이 치환되지 않았다.** `_resolve_shortcuts`가 `{user}`만 바꿨다.
그래서 그룹 바로가기는 `/groups/{group}`이라는 리터럴 경로를 찾다가 **영원히 "없음"** 이었다.
공교롭게도 **문서가 코드보다 앞서 있던 사례**다 — 정의서 §4.1·db-erd·api.md 모두
"`{user}`·`{group}` 치환"이라고 적혀 있었는데 구현이 반쪽이었다.

**2. 디렉터리가 없다.** `/scratch`·`/groups` 모두 비어 있다(실측). 마운트만 하고 하위
디렉터리를 안 만든 상태다. 포털은 **일부러 만들지 않는다** — 소유권·권한이 사이트 정책과
어긋난다(홈과 같은 원칙).

**치환 대상을 무엇으로 할지는 사용자가 정했다 — Slurm 계정이다.** AD posix 그룹은 이
사이트에서 `domain users` 하나뿐이라 워크스페이스 경계로 쓸모가 없고, 그룹=프로젝트 경계는
곧 계정이며 **계정↔사용자 매핑을 포털이 이미 관리한다**(A-US-02). 실측으로 `dt-hpc` 계정에
사용자가 매핑돼 있는 것을 확인하고 구현했다.

- `{account}`를 정식 자리표시자로 하고 **`{group}`은 별칭**으로 받는다(이미 설정된 값을
  깨지 않기 위해서다).
- 계정은 `get_associations()`에서 사용자로 걸러 뽑고, **그룹 템플릿이 실제로 필요할 때만**
  호출한다 — 탐색마다 REST 호출이 붙기 때문이다. 조회 실패는 오류로 올리지 않는다.
- 계정이 여럿이면 **계정마다 바로가기**를 만든다(`그룹 · proj-a`).
- 바로가기 계산을 `_shortcuts()` 한 곳으로 모았다. 조회(browse)와 변경(`_roots`)이 갈리면
  목록에 없는 곳을 지울 수 있게 된다.

**이 버그에서 배운 것을 구조로 남겼다.** 치환 후 `{...}`가 남아 있으면 `problem` 사유를
함께 내려보내고 화면이 "설정 확인"으로 구분해 표시한다. 그냥 `exists=false`로 두면
**"디렉터리가 없는 것"과 "설정이 틀린 것"을 구분할 수 없어** 원인을 오래 못 찾는다.

실 클러스터 확인: `/groups/{group}` → **`/groups/dt-hpc`** 로 정상 치환.
테스트 267개 통과(그룹 경로 6개 추가). 정의서 §4.1·db-erd·관리자 폼 힌트도 함께 갱신했다.

### 스크래치·그룹 공유 디렉터리를 포털 범위에서 제외 (마이그레이션 0006)

바로 위 항목의 후속이자 **철회**다. 사용자가 "마운트는 관리자가 수동으로 하더라도
**하위 디렉터리는 자동으로 생성되게** 하고 싶다"고 요구했고, 그 요구를 검토한 결과
**포털이 만들 수 없다**는 결론이 나와 기능 자체를 걷어냈다.

**만들 수 없는 이유는 두 가지다.**

1. **포털은 root로 아무것도 실행하지 않는다.** SSH 명령은 전부 `sudo -n -u <대상사용자>`
   형태다(`app/clients/ssh/client.py:160`, 정의서 §4.1 최소 권한, `docs/portal-sudoers.md`).
   root 소유 `/scratch` 아래에 디렉터리를 만들 방법이 없다.
2. **그룹 공유 디렉터리에는 유닉스 gid가 필요하다.** 이 사이트 AD에는 `domain users`
   하나뿐이라 그것으로 소유권을 주면 전원이 모든 그룹 디렉터리에 쓰게 되어 경계가
   사라진다. NFSv3 `sec=sys`는 숫자 gid로 매핑하므로 노드마다 로컬 그룹을 만드는
   편법도 gid가 어긋나면 깨진다.

그래서 이 기능은 **경로를 인식만 하고 만들 수는 없는 반쪽**이었다. 실제로 화면에는
늘 "없음"만 떴다. 관리자가 클러스터마다 채워야 하는 설정 두 칸을 남겨 두면
"채웠는데 왜 안 되냐"는 혼란만 만든다 — `0005`에서 SSH 공개키를 뺀 것과 같은 판단이다.

**선택지를 제시했고 사용자가 제거를 골랐다.** 제시한 대안은 (a) 전용 root 헬퍼
스크립트 + sudoers 화이트리스트 1줄, (b) `/scratch`를 1777로 열어 사용자 권한으로 생성
(단 그룹 공유는 불가)이었다. 둘 다 클러스터 쪽 선행 작업이 필요하다.

제거 범위:
- `cluster.group_path_tpl`·`scratch_path_tpl` 두 컬럼 (마이그레이션 `0006`,
  **downgrade가 그대로 복원한다**)
- `FileService`의 템플릿 해석 일체 — `_resolve_shortcuts`·`_needs_account`·`_accounts`
  (Slurm 계정 조회)·미치환 자리표시자 `problem` 보고
- `GET /clusters/{cid}/files` 응답의 `shortcuts` 필드. `roots`는 남는다 —
  경로 관문과 브레드크럼이 쓰고, 이제 값은 항상 `[home]`이다
- 관리자 클러스터 등록 폼의 경로 템플릿 입력 2개, 파일 관리자의 바로가기 칩 행
  (칩이 "홈" 하나뿐이면 바로 옆 브레드크럼과 중복이다)

허용 루트가 홈 하나로 줄었을 뿐 **경로 관문의 계약은 그대로다** — 조회와 변경이 같은
범위를 쓴다. 이를 고정하는 테스트를 `roots == [home]`으로 다시 썼다.

테스트 261개 통과(그룹 경로 6개 + 바로가기 1개 제거, 루트 계약 1개 추가).
사용자는 웹 터미널(U-SH-01)이나 직접 SSH로 `/scratch`·`/groups`에 접근한다.

### 클러스터 이미지 설정을 '파일 하나'에서 '저장소'로 (마이그레이션 0007)

사용자 요구: "데스크톱 이미지뿐 아니라 **여러 개의 이미지를 관리할 것**이다. 여기는
이미지가 저장되어 있는 repository만 입력하면 될 듯하다. 이미지 파일은 인터랙티브 앱을
실행할 때 필요한 것을 가져오게 하자."

바뀐 것은 **어디에 무엇이 사는가**다.

```
전:  cluster.desktop_image_ref = /home/portal/images/rocky9-mate-1.5.sif   (파일 하나)
후:  cluster.image_repository  = /home/portal/images                       (있는 곳)
     session_apps.APPS[*].image = rocky9-mate-1.5.sif                      (앱이 고른다)
```

**앱→이미지 매핑은 코드 카탈로그에 둔다**(사용자 선택). 앱을 하나 늘리려면 이미지 안의
기동 분기(`PORTAL_APP`)도 함께 만들어야 하므로 DB로 빼도 코드 배포는 어차피 따라온다.
대신 목록을 **한 곳에만** 두고 `GET /interactive-apps`로 내려보내, 프론트엔드가 갖고
있던 같은 배열(`AppsView.vue`의 `APPS`)을 없앴다. 예정된 앱(Jupyter·VS Code)까지 카탈로그에
넣은 이유가 이것이다 — 화면만 알고 있으면 "실행 가능한 앱이 무엇인가"에 대해 앞뒤가 갈린다.

저장소는 **공유 SIF 디렉터리와 OCI 레지스트리를 모두 받는다**(사용자 선택). apptainer가
둘 다 그대로 실행하므로 포털은 구분하지 않고 `{저장소}/{이미지}`로 잇는다. 다만 레지스트리는
기동마다 pull + SIF 변환이 일어나고 그 캐시가 사용자 홈(NFS)에 쌓인다 — 예전에 apptainer
캐시 11GB로 dev01이 DiskPressure에 걸린 적이 있어 문서에 명시해 두었다.

**제출 전에 막는 지점을 만들었다.** 저장소가 비었거나 아직 제공하지 않는 앱이면
`session_apps.image_ref()`가 422로 끊는다. 그냥 두면 Job이 워커까지 가서 죽고, 사용자
화면에는 "FAILED"만 남아 원인이 안 보인다.

마이그레이션 `0007`은 컬럼 이름만 바꾸지 않고 **값도 옮긴다.** `.sif`로 끝나는 기존 값은
마지막 조각을 떼어 디렉터리로 만든다 — 안 그러면 살아 있는 클러스터의 값이 파일 경로로
남아 `<파일>/<파일>` 참조가 만들어져 세션이 죽는다. SQL 방언에 의존하지 않도록 Python에서
처리했다(MySQL 운영 / SQLite 개발).

테스트 270개 통과(9개 추가). **두 앱이 지금 같은 이미지를 써서** 실제 카탈로그로는
'앱을 무시하는 구현'과 구분되지 않으므로, 카탈로그를 monkeypatch로 갈라 앱별 매핑이
살아 있는지 따로 고정했다 — 없으면 그 테스트는 통과해도 아무것도 증명하지 못한다.

### 홈 상위 경로를 클러스터 설정으로 받는다 (마이그레이션 0008)

사용자 요구: "사용자 home 디렉터리 지정을 만들어라. 이 프로젝트의 케이스는 `/home`만
입력받게 한다. 굳이 `/home/{user}`처럼 `{user}`는 입력하지 않아도 된다."

**먼저 사실 확인**: 홈 입력 칸은 원래 없었다(HEAD `e1193f1`의 `ClustersView.vue`에도
없다). 홈은 `getent passwd`로 자동 인식하고 있었고, 이번에 지운 것은 그룹·스크래치
템플릿 두 개뿐이다. 그러므로 이 항목은 복구가 아니라 **신규 기능**이다.

`cluster.home_base` 하나를 받는다. 사용자 홈은 `{home_base}/{사용자명}`이고,
**사용자명은 서버가 인증 정보에서 채운다** — 그래서 설정에 `{user}` 자리표시자를 두지
않는다(클라이언트가 대상 사용자를 고를 수 없다는 원칙과 같은 이유다). 비우면
지금까지처럼 NSS로 자동 인식하므로 기존 클러스터는 동작이 바뀌지 않는다.

**세 곳이 같은 값을 써야 한다.** 홈은 파일 브라우저(`FileService._roots`)와 세션
두 곳(`SessionService.create`의 로그 디렉터리, `_connection_file`의 접속 정보 경로)에서
따로 읽고 있었다. 갈리면 세션 산출물이 브라우저에 안 보이는 곳에 쌓인다. 그래서
`services/files.py`의 `home_dir_for()` 한 곳으로 모았다 — `ssh_target_for()`를 공유하는
것과 같은 방식이다. `LoginNodeClient.home_dir()`에는 "직접 부르지 말 것" 주석을 달았다.

**테스트가 실제로 검증하는지 확인했다.** 처음 쓴 테스트는 `home_base = "/home"`으로
설정했는데, SSH 대역의 `home_dir()`도 `/home/{user}`를 돌려주므로 **설정을 무시하는
구현에서도 통과**했다. 상위 경로를 `/nfs/home`으로 바꿔 NSS 값과 구분되게 한 뒤,
`home_dir_for()`의 설정 분기를 지워 2개가 깨지는 것을 확인했다.

테스트 273개 통과(3개 추가).

### 클러스터 이름은 slurmrestd가 정하고, 사람은 별칭을 붙인다 (마이그레이션 0009)

사용자 지적: "등록창에서 클러스터 이름을 꼭 써야 하나? 설명을 **별칭**으로 바꾸고 그걸
입력받는 게 어떤가. 실제 이름은 추가된 후 slurmrestd로 저장되고 포털에서 수정할 수 없다."

맞는 지적이었다. 등록 폼이 `name`을 **필수**로 받는데 그 값은 REST 연결 테스트가
`ClusterName`으로 덮어썼다. 관리자에게 곧 사라질 값을 반드시 입력하게 만드는 구성이었다.

- `cluster.name` → nullable. 등록 시점엔 없고 REST 연결 테스트가 채운다.
- `cluster.description` → `cluster.alias`. **화면은 이미 이 값을 표시명으로 쓰고 있었다**
  (`TopBar.vue`의 `c.description || c.name`). 실제 역할에 이름을 맞췄다.
- `ClusterCreate`에서 `name`을 없애고 `alias`를 필수로 받는다.

**중복 검사가 옮겨간 것이 이 변경의 실제 위험이었다.** 기존에는 등록 시 `name`으로
중복을 봤는데, 이름을 안 받으니 그 검사가 사라진다. 그대로 두면 REST 테스트가
`cluster.name = detected`를 하는 순간 UNIQUE 제약에 걸려 **500**이 난다. 그래서 검사를
`test_rest`로 옮겨 409로 돌려준다 — 사람이 지은 별칭이 아니라 실제 `ClusterName`이
겹치는지가 문제이고, 그건 연결해 보기 전에는 알 수 없으므로 시점도 여기가 맞다.
검사를 지우고 테스트를 돌려 `UNIQUE constraint failed`가 나는 것을 확인했다.

**이름이 없는 동안의 표시명**도 정리했다. 감사 로그·확인 대화상자·알림 문구가 `cluster.name`을
그대로 끼워 넣고 있어서, 비면 "undefined: 삭제했습니다" 같은 문구가 나온다. 백엔드는
`label_of()`, 프론트는 `label()`로 `별칭 → 이름 → 자리표시자` 순서를 한 곳에 두었다.
감사 기록에 빈 대상이 남으면 나중에 추적할 수 없으므로 마지막 폴백은 `cluster#<id>`다.

목록·선택기는 이름이 비면 "이름 미확인 — REST 연결 테스트 필요"라고 **말한다**.
그냥 숨기면 왜 없는지 알 수 없다. 수정 화면에는 읽기 전용으로 남겨 지금 값이 무엇인지
보여 준다.

테스트 275개 통과(2개 추가, 1개 대체).

### slurmrestd munge 인증 선택지 제거

사용자 지적: "slurmrestd 인증 방식에 munge도 있는데 이건 구현이 안 되어 있는 것 같다."

맞았다. `auth_method`는 **저장만 되고 아무 데서도 읽히지 않았다.** 모델·스키마에 필드가
있을 뿐 값으로 분기하는 코드가 한 줄도 없고, 클라이언트는 무조건 JWT 헤더만 붙인다
(`clients/slurm/client.py:38`). munge를 골라도 JWT를 보내고, JWT가 없으면 등록 시점에
막힌다 — **조용히 잘못 동작하는 게 아니라 애초에 쓸 수 없었다.**

**구현하지 않고 선택지를 없앴다**(사용자 결정). munge 인증은 포털 파드가 클러스터의
`/etc/munge/munge.key`를 가져야 하는데, 그 키는 **클러스터 전체를 사칭할 수 있다.**
웹에 노출된 서비스에 그런 키를 두는 것은 `docs/portal-sudoers.md`가 줄이려는 방향과
정반대다. slurmrestd의 munge 인증은 보통 유닉스 소켓 경유이지 원격 HTTP로는 쓰지 않는
점도 있다.

**화면만 고치면 반쪽이다.** 드롭다운을 없애도 `PATCH /clusters/{cid}`로 여전히 넣을 수
있고, 그러면 저장은 되는데 호출은 JWT로 나가는 앞뒤 안 맞는 상태가 된다. 그래서
`ClusterCreate`·`ClusterUpdate`의 `auth_method`에 `^jwt$` 패턴을 걸어 API도 422로 막고,
그것을 테스트로 고정했다.

컬럼은 남긴다 — 나중에 다른 인증 방식이 생기면 여기가 자리다. 기존 두 행은 이미 `jwt`라
값 마이그레이션은 필요 없었다(실측).

**스크래치·그룹 경로와 같은 종류의 문제다** — 고를 수 있는데 안 되는 UI는 관리자가
골라놓고 "왜 안 되냐"를 겪게 만든다. 근거를 정의서 §4.1에 남겨 나중에 "왜 없지?"가
반복되지 않게 했다.

테스트 276개 통과(1개 추가).

### 인증 방식 필드 제거 · API 버전은 서버가 주는 목록에서 고른다

사용자 지적: "인증 방식은 jwt 하나인데 굳이 표시할 필요가 없다. 제거한다. API 버전은
드롭다운으로 고르게 하고, 이 프로젝트는 v0.0.41 하나이므로 선택지는 1개로 한다."

바로 앞 항목에서 munge를 뺀 뒤 남은 것이 "jwt"라고만 적힌 읽기 전용 칸이었다. 값이
하나뿐이고 바꿀 수도 없으면 화면에 자리를 차지할 이유가 없다 — 폼에서 아예 뺐다.
서버 기본값(`ClusterCreate.auth_method="jwt"`)이 채운다.

API 버전은 반대다. **자유 입력이면 안 되는 값**이다. 응답 파싱이 버전에 묶여 있어서
(v0.0.41의 `time_limit`은 분 단위 정수 등) 다른 값을 저장하면 호출이 404를 맞거나
잘못 파싱된다. 그래서 드롭다운으로 좁히되, **여기서도 화면만 고치면 반쪽이다** —
`PATCH`로 여전히 넣을 수 있다. munge 때와 같은 처리를 했다:

- `SUPPORTED_API_VERSIONS` 상수 하나에서 pydantic 패턴을 **만들어 쓴다**(따로 적으면 어긋난다)
- `GET /cluster-api-versions`로 선택지를 내려보내 화면이 목록을 따로 갖지 않게 했다
  (앱 카탈로그와 같은 판단). 관리자 전용이다
- 지원하지 않는 버전은 등록·수정 모두 422

테스트 278개 통과(2개 추가 — 선택지 출처·권한, 미지원 버전 거부).

### 대기시간 79년 — slurmdbd 시각 센티넬을 못 걸렀다

화면에 `평균 52270.1시간 · 최대 696938.4시간`(79년)이 떴다. 중앙값은 0초인데 평균이
5만 시간이라 **소수의 극단값이 지배**한다는 신호였다.

원인을 값에서 역산했다. 696938.4시간 = 2,508,978,240초이고, `0xFFFFFFFF − 그 값`은
**2026-08-06** — 실제 활동이 있던 날이다. 즉 `time.start = 4294967295`였다.

**slurmdbd는 "값 없음"을 0이 아니라 센티넬로 준다** — `NO_VAL`=0xFFFFFFFE,
`INFINITE`=0xFFFFFFFF. 기존 가드는 `not submission or not start`라 0만 걸렀고,
시작하지 못한 Job(취소 등)의 센티넬이 그대로 통과해 "제출 → 2106년" 구간이 만들어졌다.

같은 결함이 **`_started_on`에도 있었다.** 센티넬을 날짜로 바꾸면 2106년이 되어 가동률
집계의 엉뚱한 버킷으로 간다. 지금은 조회 범위 밖이라 조용히 버려지고 있었을 뿐이다.

그래서 시각 해석을 `_epoch()` 한 곳으로 모았다 — 시각을 읽는 곳이 여럿이면 한 곳만
빠뜨려도 같은 버그가 되살아난다. 64비트 센티넬(`NO_VAL64` 등)은 32비트 값보다 크므로
같은 비교(`>= 0xFFFFFFFE`)에 함께 걸린다.

`elapsed`는 손대지 않았다 — 지속시간이라 0이 자연스러운 "없음"이고, 실측 합계(16.39
CPU-시간)도 정상이었다.

테스트 282개 통과(4개 추가). 수정을 되돌려 3개가 깨지는 것을 확인했다.

### 사용량 리포트 — 막대 제거, 컬럼 확충

사용자 지적: "CPU-시간 비중을 굳이 그래프로 표현하지 않아도 될 것 같다. 가로 길이가 긴
것에 비해 표현되는 데이터가 너무 없는데 더 넣을 컬럼이 있을까?"

막대는 **바로 옆 칸의 숫자를 그림으로 반복**하면서 표 폭의 절반을 쓰고 있었다. 게다가
최대값 기준 정규화라 1위가 항상 꽉 찬 막대여서 "비중"으로도 읽히지 않았다. 빼고 `%`로
바꿨다.

추가 컬럼은 **이미 받아 오는 Job 회계 데이터에서 뽑았다** — REST 호출이 늘지 않는다.

| 컬럼 | 왜 |
|---|---|
| 비중 % | 막대를 대체. 전체 CPU-시간 대비 |
| 노드-시간 | CPU-시간과 **다른 이야기**다. 노드를 통째로 잡고 코어를 조금만 쓴 Job은 CPU-시간이 작아도 노드-시간이 크다 — 한 값만 보면 그 낭비가 안 보인다 |
| Job당 CPU-시간 | 같은 사용량이라도 잔챙이 다수와 큰 Job 몇 개는 운영상 의미가 다르다 |
| 실패율 | 개수만으로는 심각도를 모른다. 37건 중 3건과 3건 중 3건은 다르다 |
| 최근 활동 | "누가 아직 쓰고 있나"는 누적 사용량만으로는 안 보인다 |

`tres.allocated`에서 종류별로 뽑는 `_allocated_cpus`를 `_allocated(job, kind)`로 일반화해
노드도 같은 경로로 읽는다. 날짜 변환은 `_as_date()` 하나로 모았다 — `_started_on`이
따로 갖고 있던 변환을 여기로 합쳤다(둘로 두면 한쪽만 고쳐진다).

**종료 시각에도 센티넬이 온다.** `last_active`가 2106년이 되지 않도록 `_epoch()`를 거치게
했고 그 회귀 테스트를 넣었다.

테스트 285개 통과(3개 추가).

### 비용 추이 — 세로 막대 + 빈 날짜 채우기

리포트의 가동률·대기시간에 이어 비용 추이도 X=날짜·Y=금액 세로 막대로 맞췄다.
세 차트가 같은 형태가 되면서 Y축 척도 규칙이 둘로 갈리는데, 근거를 코드에 남겼다:

- **가동률** → `0~100% 고정`. 용량 대비 비율이라 상한이 절대적이다
- **비용·대기시간** → `최대값 기준`. 금액과 건수는 절대 상한이 없다

Y축 라벨은 억/만으로 축약한다 — `45,448원`을 그대로 쓰면 눈금끼리 겹친다. 정확한 금액은
막대 툴팁과 상단 총액에 있다.

**응답이 데이터 있는 날만 주고 있었다.** "최근 30일"을 골랐는데 가로축이 9칸만 그려졌다.
`_daily_series()`로 구간의 모든 날짜를 채우고 청구가 없던 날은 0으로 둔다(가동률이
이미 쓰던 규칙). "비용이 0인 날"과 "데이터가 없는 날"을 화면에서 구분할 필요는 없다 —
둘 다 그날 쓴 돈이 없다는 뜻이다.

**테스트에 시한폭탄이 있어 함께 고쳤다.** 픽스처가 `2026-08-01`을 하드코딩하는데 조회
구간은 `오늘 − 30일`이라, 오늘이 8월 31일을 넘기면 그 날짜가 구간 밖으로 밀려나 깨진다.
오늘 기준 상대 날짜로 바꿨다.

테스트 285개 통과. 채우기를 되돌려 깨지는 것을 확인했다.

### AD 연결 화면을 사용자 화면에 병합 (SCR-13)

사용자 요구: "이 페이지를 사용자 페이지와 합친다. 사용자 메뉴 버튼은 유지하고 AD 연결은
제거한다. 빌링과 같은 비율로 좌측에 사용자 정보, 우측 위에 '현재 AD 연결', 그 아래에
'동기화 상태'."

**정의서가 원래 한 화면으로 규정하고 있었다** — SCR-13 "사용자/AD 연결/계정/QOS 관리".
구현만 `/admin/users`와 `/admin/ad`로 갈라져 있었다.

갈려 있어서 생기던 문제: **원인(연결·동기화)과 결과(사용자 목록)가 다른 페이지에 있었다.**
"동기화했는데 사용자가 왜 안 늘지?"를 두 화면을 오가며 확인해야 했다. 이제 `sync()`가
끝나면 AD 상태와 **사용자 목록을 함께 다시 읽는다** — 결과가 같은 화면에 있으므로.

배치는 Billing·Job 제출과 같은 `grid-cols-[1fr_420px]`를 그대로 썼다. 새 수치를 만들면
화면마다 미묘하게 어긋난다.

- 헤더 액션: `AD 연결` 링크 버튼 → `연결 테스트` · `지금 동기화` · `목록 새로고침`
- 우측 열의 `dl`은 `grid-cols-[96px_minmax(0,1fr)]` + `break-all`. 420px에서 LDAP URL·DN
  같은 긴 값이 카드 밖으로 밀려나던 문제를 Billing에서 겪어 같은 처방을 미리 적용했다.
- 라우터에서 `/admin/ad`는 **리다이렉트만 남겼다.** `meta.group`이 없으니 사이드바에서
  사라지고(메뉴는 라우터 meta에서 파생된다), 기존 링크·북마크는 계속 동작한다.
- `AdView.vue`는 삭제했다. 병합으로 내가 만든 dead code라 남길 이유가 없다(잔존 참조 없음).

### 노드 쓰기 계열 1단계 — 노드 상태 제어 (A-ND-01)

사용자가 "예약을 쓸 방법이 없다"고 지적했고, 확인해 보니 **예약만의 문제가 아니었다** —
노드/파티션 쓰기 계열(A-ND-01·03·04·05)이 통째로 미구현이었다. 사용자가 "계열을 통으로
구현"을 선택해 단계로 나눠 시작한다.

**권한 걱정은 이미 해결돼 있었다.** 처음엔 `scontrol`에 sudoers 화이트리스트가 필요하다고
봤는데, `clients/slurm/client.py`의 계정 쓰기 주석이 답을 갖고 있었다: 포털의 Slurm JWT는
**AdminLevel 권한**이라 계정을 만들고 지운다. 노드 제어도 같은 권한이라 **새 권한이 필요
없다.** 임퍼소네이션을 쓰지 않는 것도 같은 이유다(일반 사용자로 위장하면 거부된다).

1단계로 A-ND-01을 구현했다. 정의서 우선순위가 **필수**이고 REST 지원이 가장 확실하다.

- `POST /clusters/{cid}/nodes/{name}/state` — drain / resume / down / undrain
- **`drain`·`down`은 사유를 요구한다.** Slurm이 사유를 노드에 붙여 두고, 그게 나중에
  "왜 빠져 있지?"에 답하는 유일한 단서다. 서버에서 막고, 화면도 버튼을 잠근다.
- 허용 상태를 4개로 좁혔다. Slurm은 더 받지만 넓게 열면 오타 하나로 노드를 이상한
  상태에 빠뜨린다.
- 화면은 **이미 빠져 있는 노드에 '빼기'를 보여주지 않는다** — 누를 수 있는데 아무 일도
  안 나는 버튼이 된다. drain과 down의 차이(실행 중 Job이 끝까지 도는가 vs 즉시 죽는가)를
  확인 대화상자에 적었다.

테스트 290개 통과(5개 추가: 위장 안 함·사유 강제·resume은 사유 불필요·미지원 상태 거부·권한).

**실 클러스터 검증 완료** — 화면에서 slurm01을 drain(사유 "테스트")했다가 resume 했다.
`POST /slurm/v0.0.41/node/{name}`이 v0.0.41에서 **동작한다**(노드 쓰기는 REST로 가능하고
포털 JWT 권한으로 충분하다 — 예상대로 새 sudoers가 필요 없었다). 감사 로그에도 사유까지
남았다:

```
07:03:43  ADMIN  NODE_STATE  slurm01  RESUME
07:03:40  ADMIN  NODE_STATE  slurm01  DRAIN — 테스트
```

drain 직후 잠깐 뜨는 `Not responding`은 slurmctld가 노드를 다시 보기 전까지의 정상 상태다.

**남은 것**: 예약(A-ND-04)·파티션(A-ND-03)·점검 모드(A-ND-05). 노드가 REST로 됐다고 해서
예약도 된다는 보장은 없다 — slurmrestd는 자원마다 여는 메서드가 다르다. openapi 스펙에서
`reservation`·`partition`의 메서드를 확인한 뒤 설계한다.

### 2단계 — API 버전 v0.0.43 상향 + 예약 생성·삭제 (A-ND-04, 마이그레이션 0010)

openapi 스펙 실측이 세 자원의 운명을 갈랐다.

| 자원 | 0.0.40~0.0.42 | 0.0.43 |
|---|---|---|
| 노드 | `GET` `POST` `DELETE` | 동일 |
| 예약 | `GET` · `DELETE` — **생성 없음** | **`POST /reservation`** |
| 파티션 | `GET`만 | **`GET`만** |

**예약 생성이 0.0.43에만 있어서 포털 전체를 0.0.43으로 올렸다**(사용자 결정). 호출마다
버전을 섞는 대안도 있었지만, 응답 파싱이 버전에 묶여 있어 "이 응답은 어느 스키마인가"가
흐려지고 그 혼동이 곧 버그가 된다.

**올리기 전에 응답 형태를 실측 비교했다** — 테스트는 fake를 쓰므로 버전 드리프트를 잡지
못한다. `nodes`·`associations`·`slurmdb/jobs`의 최상위 키와 필드 형태가 두 버전에서
완전히 일치하는 것을 확인한 뒤 올렸다.

**예약 요청의 숫자는 `{set, infinite, number}` 래퍼다.** 스펙의 `*_no_val_struct`가 그것이고,
맨 숫자를 보내면 거부된다. 추측했으면 틀렸을 지점이라 스펙을 먼저 뽑아 본 값어치가 있었다.

- **노드 지정을 강제한다** — `node_list`도 `node_count`도 없으면 Slurm이 클러스터 전체를
  잡아 버릴 수 있다. pydantic `model_validator`로 막는다(입력 검증의 제자리).
- 플래그는 4개만 열고 대문자로 정규화한다.
- 화면은 **로컬 시각**을 받아 epoch으로 바꿔 보낸다 — slurmrestd는 epoch만 받고 관리자는
  "8월 9일 22시"로 생각한다.
- 서비스는 원시값만 받는다(`name`·`desc`·`summary`). 다른 서비스가 스키마를 import하지
  않는 관례를 따랐다.

**파티션(A-ND-03)은 범위 밖으로 확정했다**(사용자 결정). 모든 버전에서 조회만 열려 있어
`scontrol` + `slurm.conf` 영속화가 필요한데, 웹 서비스가 클러스터 설정 파일을 고치는 것은
최소권한 방향과 정면으로 어긋난다. 근거를 정의서 §4.1과 api.md에 남겼다.

테스트 295개 통과(예약 5개 추가). 마이그레이션 0010이 기존 두 클러스터를 v0.0.43으로 옮긴 것을
DB에서 확인했다.

### 3단계 — 점검 (A-ND-05)

**이 기능의 존재 이유는 편의가 아니라 누락 방지다.** 실제로 자주 나는 사고는 "노드는
뺐는데 공지를 안 해서 사용자가 영문을 모르는" 것이다. 공지와 Slurm 조치를 한 동작으로
묶으면 그게 구조적으로 막힌다.

**예약과 drain은 배타적이다**(사용자와 확인한 지점). 처음 설명이 "둘을 같이 쓴다"로
읽혀 바로잡았다:

| 상황 | 수단 | 왜 |
|---|---|---|
| 예고된 점검 | **예약만** | Slurm이 구간과 겹치는 Job을 시작하지 않는다. 그때까지 짧은 Job은 계속 돌고 시간이 되면 노드가 자연히 빈다 |
| 긴급(하드웨어 장애) | **drain만** | 예약할 미래가 없다 |

예고된 점검에 drain까지 걸면 **그때까지의 용량을 통째로 버린다** — 예약으로 피하려던
문제를 도로 만드는 셈이다. 화면은 라디오로 두어 배타적임이 읽히게 했다.

**Slurm 조치를 먼저 하고 성공해야 공지를 만든다.** 공지만 남으면 "점검한다고 했는데 아무
일도 안 일어나는" 상태가 되는데, 그건 이 기능이 막으려는 사고와 같은 종류다. drain이
여러 노드에 걸쳐 부분 실패하면 어느 노드가 빠졌고 어느 노드가 남았는지 목록으로 보고한다.

**새 개념·새 테이블을 만들지 않았다.** 점검은 상태가 아니라 워크플로다 — 이미 있는 두
객체(예약·공지)를 만들 뿐이다. "점검 모드" 상태를 DB에 두면 예약을 직접 지웠을 때
불일치가 생긴다.

화면은 노드 표의 체크박스로 대상을 고른 뒤 시작한다 — 점검은 "어느 노드"가 출발점이다.
예약 기간 입력에는 **파티션 최대 walltime보다 일찍 잡아야 한다**는 안내를 붙였다.
그러지 않으면 이미 돌던 긴 Job이 구간을 침범한다.

테스트 300개 통과(점검 5개 추가 — 예약 경로·drain 경로·실패 시 공지 없음·모드별 필수값·권한).

### 예약 실패 두 건 — 실측으로 잡음

점검 폼이 502로 실패했다. 화면에는 `[EXTERNAL_SERVICE_ERROR] 외부 서비스 호출이
실패했습니다.`만 떠서 손쓸 수가 없었다.

**먼저 화면이 이유를 감추고 있던 것을 고쳤다.** `ErrorNote`가 `code`·`message`만 보여주고
`detail`을 버리고 있었다. 외부 서비스(slurmrestd·AD·SCP) 실패는 **본문에만 이유가 있는데**,
코드·메시지는 "호출이 실패했습니다"까지밖에 말해 주지 않는다. 이제 응답 본문이 함께
뜬다 — 앞으로 이 종류의 실패는 화면만 보고 진단할 수 있다.

클러스터에서 직접 재현해 원인 두 가지를 확인했다:

**1. Slurm은 예약에 대상을 요구한다.**

```
Either Users/Groups and/or Accounts must be specified.  No reservation created.  (2053)
```

점검 폼은 아무것도 안 보내고 있었다. 앞서 수동 예약이 성공한 것은 폼에서 사용자를
채웠기 때문이다. 점검 예약은 **아무도 못 쓰게 하는 것이 목적**이라 관례대로 `root`를
기본값으로 두고, 화면에서 바꿀 수 있게 했다. 예약 폼도 사용자/계정 중 하나를 필수로
바꿨다 — 서버까지 갔다가 502를 받는 것보다 입력 단계에서 막는 게 맞다.

**2. `node_list`는 배열이다.**

```
Expected OpenAPI type=array (Slurm type=list) but got type=string: "slurm02"
```

문자열도 받아 주지만 경고가 붙는다. 스펙대로 배열로 보낸다.

이 두 가지는 **openapi 스펙의 필드 목록만으로는 안 보였다** — 필수 조건은 스펙이 아니라
`validate_resv_create_desc`의 런타임 검증에 있고, 타입 불일치는 경고로만 나온다.
실제로 한 번 호출해 봐야 드러나는 종류였다.

테스트 301개 통과(예약 대상 필수 1개 추가, 기존 예약·점검 테스트를 배열·대상 기준으로 갱신).

### GPU 없는 파티션에서 GPU 입력 비활성화 (U-JB-01)

**파티션 응답이 아니라 노드에서 거슬러 올라간다.** 노드의 `gres`·`partitions`는 화면이
이미 렌더링하고 있어 형태가 확인된 값이다 — 파티션 쪽 GRES 필드는 실물로 본 적이 없어
추측이 된다. 오늘 예약에서 스펙만 보고 구현했다가 두 번 틀린 뒤라 확인된 것만 썼다.

**`null`(모름)과 빈 배열(GPU 없음)을 구분한다.** 노드 조회가 실패했을 때 빈 목록으로
뭉뚱그리면 그게 "GPU 없음"으로 둔갑해 **멀쩡한 제출을 막는다.** 고를 수 있어야 할 것을
못 고르게 만드는 쪽이, GPU 없는 파티션에 GPU를 요청해 Slurm이 거부하는 것보다 나쁘다.
그래서 `null`이면 화면은 허용 쪽으로 기운다.

파티션을 바꿔 GPU가 없어지면 남아 있던 값을 0으로 지운다 — 안 지우면 비활성 입력칸의
옛 값이 그대로 제출된다.

**테스트가 뒷 테스트를 깨뜨린 것을 잡았다.** 실패 경로를 흉내내려고
`type(slurm_client).get_nodes = boom` 후 `del` 했는데, 그 `del`이 **원본 메서드까지**
지워 이후 테스트가 AttributeError로 죽었다(단독 실행에서는 통과해 더 헷갈린다).
클래스가 아니라 인스턴스에 `monkeypatch.setattr`을 걸어 해결했다.

테스트 303개 통과(2개 추가).

### 공지에서 클러스터 스코프 제거 (마이그레이션 0011)

사용자 지적: "공지는 이 포털을 쓰는 사용자 전체 대상이므로 클러스터에 상관없이 하나로."

**이미 그렇게 쓰이고 있었다.** 관리자 공지 등록 폼(`SettingsView.vue`)은 대상 클러스터를
받지 않아 등록되는 공지가 전부 `NULL`(전체)이었다. 컬럼과 조회 필터만 남아 **"클러스터별
공지"라는 없는 개념을 코드가 계속 말하고** 있던 셈이다.

- `notice.target_cluster_id` 제거(FK를 먼저 끊어야 컬럼이 지워진다 — 제약 이름을 실 DB에서 확인)
- 조회 필터·라우터 쿼리 파라미터·스키마 필드 제거
- `CLUSTER_REFERENCES`에서 공지를 뺐다 — 공지가 클러스터를 참조하지 않으니 클러스터
  완전 삭제를 막을 이유도 없다
- 공지 화면이 클러스터 선택을 감시하던 것도 풀었다(부제목의 클러스터 이름 포함)

**점검 공지도 전체 대상이 된다.** 특정 클러스터 점검이라면 제목에 클러스터를 적어야
하므로 점검 폼에 그 안내를 넣었다 — 배너에는 대상이 드러나지 않는다.

**작업 중 사고 하나**: 컬럼 제거를 `str.replace`로 하면서 개수를 제한하지 않아
`AuditLog`의 **같은 이름 컬럼까지 지웠다**. import 단계에서 바로 드러나 복구했지만,
일괄 치환은 같은 문자열이 다른 곳에 있는지 먼저 봐야 한다.

테스트 303개 통과.

### 공지를 톱바 메뉴로 (SCR-16)

공지에서 클러스터 스코프를 뺀 뒤의 자연스러운 후속이다. 사이드바는 **클러스터 스코프
화면들**이 모인 곳인데(선택한 클러스터 기준으로 목록·상세가 바뀐다), 공지만 클러스터와
무관하니 거기 있으면 어긋난다. 톱바로 옮겨 **어느 화면에서도 같은 것**이 보이게 했다.

- `NoticeMenu.vue` — 톱바 드롭다운. 클러스터 선택기 왼쪽
- 배지는 **진행 중인 것만** 센다. 끝난 공지까지 세면 숫자가 줄지 않아 이내 무시하게 된다
- 기간별 구분(진행 중 / 예정 / 종료)과 "종료는 흐리게" 규칙은 화면에서 그대로 옮겼다 —
  지난 점검 안내를 보고 작업을 미루는 일을 막는 장치라 버릴 수 없다
- 공지 조회가 실패해도 톱바는 멀쩡하다. 못 읽었다는 표시만 남긴다
- `/notices` 라우트는 리다이렉트만 남겼다(`meta.group`이 없으니 사이드바에서도 사라진다).
  `NoticesView.vue`는 삭제했다 — 이관으로 내가 만든 dead code다

### 관리자 콘솔을 "포탈 설정 / 클러스터 관리" 둘로 분리

관리자 화면은 성격이 둘인데 한 사이드바에 섞여 있었다. 클러스터 등록·사용자·비용은 포털
전체 설정이고, 노드·Job·계정·QOS·리포트는 **톱바에서 고른 클러스터 하나**에만 적용된다.

**문제는 그 경계가 화면에 안 드러난 것이다.** 클러스터 선택기가 항상 떠 있어서, 비용/Billing을
보며 클러스터를 바꿔도 아무 일이 안 나는데 화면은 그 사실을 말해 주지 않았다. 프로필 메뉴를
`포탈 설정 / 클러스터 관리 / 사용자 포털` 3개로 나누고 **포탈 설정에서는 선택기를 감춘다.**

분류는 `clusters.selectedId` 사용 여부로 실측해 확정했다(사용자 제안과 정확히 일치).
빠져 있던 두 화면을 채웠다 — `대시보드`는 클러스터 종속, `포털 운영 설정`은 전역.

구현에서 지킨 것 셋:

- **`meta.admin`을 재활용하지 않았다.** 그건 라우터 가드가 쓰는 인가 플래그다. 콘솔 구분에
  겸용하면 메뉴를 옮기다가 권한이 열린다. `meta.console`을 따로 뒀다.
- **콘솔은 라우트에서 파생한다.** `/admin/billing`을 북마크로 열어도 포탈 설정 셸로 들어와야
  하는데, 별도 상태로 들고 있으면 새로고침·딥링크에서 어긋난다. `AppShell`이 이미 쓰던 방식이다.
- **이름 충돌을 먼저 풀었다.** 콘솔 `클러스터 관리`와 기존 메뉴 `클러스터 관리`(SCR-18)가
  같은 이름이 되는데, 그 메뉴는 **포탈 설정 쪽**이라 "클러스터 관리 콘솔에 클러스터 관리가
  없는" 상태가 된다. 메뉴를 `클러스터 등록`으로 바꿨다(정의서 A-CL-02의 표현에 더 가깝다).

**분리가 만든 구멍도 막았다.** 지금까지는 클러스터 등록과 대시보드가 같은 사이드바에 있어
문제가 없었는데, 나누면 아직 하나도 등록하지 않은 관리자가 클러스터 관리 콘솔에서 빈 화면만
보고 막힌다. 대시보드가 그 경우 포탈 설정의 클러스터 등록으로 안내한다.

**포탈 설정에서 선택기를 없앴다가 되돌렸다.** 없애니 옆 버튼(공지·프로필)이 통째로 밀려
콘솔을 오갈 때마다 톱바가 튀었다. 자리는 지키되 비활성 `Global`로 바꿨다 — 사라지는 것보다
**"고를 것이 없다"를 그 자리에서 말하는 편**이 낫고, 레이아웃도 안 흔들린다.

`meta.console`·`meta.group` 두 단계가 됐다 — 어느 사이드바인지와 그 안의 소제목이 갈린다.

### 점검(A-ND-05) 철회 — 예약 + 공지로 충분하다

사용자 판단: "관리자는 예약으로 노드를 잡고 공지를 수동으로 써도 된다."

맞는 지적이다. 예약(A-ND-04)과 공지(A-OP-01)가 각각 완성돼 있으니 점검은 **두 동작을 묶는
편의**일 뿐이었다. 그 편의 하나를 위해 화면(모달·노드 체크박스)과 API(`POST /maintenance`)를
유지할 이유가 없다.

**잃는 것은 "공지를 잊을 수 없다"는 강제뿐이다.** 만들 때 그게 존재 이유라고 봤지만,
운영 습관으로 대체 가능한 성질이고 코드로 강제할 만큼의 값은 아니라는 판단에 동의한다.
"Slurm 조치가 실패하면 공지를 만들지 않는다"는 보장도 함께 사라지지만, 예약이 실패하면
화면에 오류가 뜨므로 관리자가 공지를 안 쓰면 그만이다.

제거 범위: `POST /clusters/{cid}/maintenance`, `ClusterService.maintenance()`,
`MaintenanceIn`, 노드 화면의 점검 버튼·체크박스·모달, 관련 테스트 5개.
쓸모없어진 import(`OpsService`, `datetime`)도 함께 정리했다 — 파이썬은 빌드가 안 잡아 준다.

노드 상태 제어(A-ND-01)와 예약(A-ND-04)은 그대로다. 예약 폼의 `MAINT` 플래그도 그대로 —
그건 Slurm의 개념이지 포털 기능이 아니다.

테스트 298개 통과(5개 제거).

### Job 제출 — 템플릿을 번호 대신 목록에서 고른다 (U-JB-03)

사용자 지적: "사용자는 템플릿 ID를 모른다."

맞다. `템플릿 ID`가 숫자 입력칸이었는데 **관리자가 등록한 번호를 알 방법이 없다.**
`GET /templates`(공개 + 내 것)가 이미 있고 프론트 클라이언트도 있어, 드롭다운으로 바꾸는
것이 전부였다. 표시는 `이름 · v버전 · 종류`.

**미선택 제출을 함께 막았다.** 서버는 `template_id=null`을 그냥 무시하므로, 템플릿 탭에서
고르지 않고 제출하면 **템플릿 없이 나가고 사용자는 템플릿으로 낸 줄 안다.** 미리보기·제출
버튼을 잠근다.

템플릿 조회가 실패해도 폼·스크립트 제출은 그대로 된다 — 등록된 템플릿이 없으면 셀렉트를
비활성화하고 "관리자에게 요청하세요"로 사유를 말한다.

### 템플릿(U-JB-03)의 실체 — 인터랙티브 앱과 같은 문제였다

사용자 질문: "템플릿 배치는 solver s/w가 워커에 설치돼 있어야 하지 않나? 입력 파일이나
파라미터도 필요하지 않나?"

**둘 다 맞고, 파라미터 쪽은 지금 동작하지 않는다**는 것을 확인했다.

1. **solver 설치** — 템플릿은 스크립트 본문일 뿐이다. Slurm은 아무것도 설치하지 않으므로
   그 파티션 노드에 solver가 이미 있어야 하고, 없으면 런타임에 죽는다. 포털은 노드 안에
   무엇이 깔렸는지 몰라 **검증할 방법이 없다.**
2. **파라미터** — 백엔드에 `{{key}}` 치환기가 있는데 **프론트가 `template_params: null`을
   고정으로 보낸다.** 입력 UI가 없고, 관리자 등록 폼에도 파라미터 정의 칸이 없다.
   `{group}` 미치환 버그와 같은 종류다 — 뒤쪽 기능은 있는데 앞쪽이 안 이어져 있었다.
3. **입력 파일** — 연결 고리가 전혀 없다. 파일 관리자로 올린 뒤 상대 경로로 참조하는 수밖에.

**사용자 결론: 인터랙티브 앱처럼 solver가 든 컨테이너 이미지가 필요하고, solver 특성에 맞는
입력 인터페이스가 있어야 한다.** GROMACS 사용법을 먼저 알아야 제대로 짤 수 있어 보류한다.

기록해 둘 설계 방향 — **앱 쪽에서 이미 푼 것을 재사용한다.** 병렬 구조를 만들 이유가 없다:

```
인터랙티브 앱  image_repository + APPS[].image  →  apptainer exec <이미지> start-desktop.sh
배치 템플릿    image_repository + 템플릿의 이미지 →  apptainer exec <이미지> gmx mdrun …
```

차이는 화면을 붙이느냐(VNC)와 배치로 돌리느냐뿐이다. 템플릿이 들고 있어야 할 것은
**이미지·명령·파라미터 정의(이름/라벨/타입/기본값/필수)·필요 입력 파일**이고, 입력 파일
선택은 파일 관리자가 이미 목록을 주므로 이어붙일 수 있다.

**보류와 별개로 새는 구멍은 막았다.** 치환되지 않은 `{{...}}`가 남으면 제출을 거부한다.
값 없이 내보내면 **제출은 성공하고 워커에서 이상하게 돌다 실패하는데 원인이 화면에 안
보인다.** 파라미터 입력 UI가 생기기 전까지 이 검사가 유일한 방어선이다.

테스트 301개 통과(3개 추가). 가드를 되돌려 깨지는 것을 확인했다.

### 스크립트 모드에 함정이 있었다 — 지시자가 조용히 무시됐다 (U-JB-02)

사용자 지적: "스크립트는 폼하고 인터페이스가 똑같다."

증상은 화면이었지만 원인은 더 나빴다. `_slurm_job_properties`가 **모드와 무관하게 폼 값으로**
REST 자원을 정하는데, 코드 주석이 실측으로 못박고 있었다 — **slurmrestd 제출에서 `#SBATCH`는
적용되지 않는다(REST 속성이 이긴다).**

즉 잘 돌던 sbatch 스크립트를 붙여 넣어도 `--partition=gpu --nodes=4`가 **조용히 무시되고**
폼 기본값(cpu, 1노드)으로 돌았다. "직접 작성"이라는 이름이 거짓말이었고, 화면이 폼과
똑같아 보인 것은 실제로 자원을 폼이 정하고 있었기 때문이다.

**스크립트를 정본으로 만들었다**(사용자 결정).

- `parse_sbatch()` — `#SBATCH`를 REST 속성으로 옮긴다. `--key=value`·`--key value`·`-N 4`·
  `-N4`·한 줄 여러 개를 모두 받는다. 매핑: partition·account·qos·nodes·cpus-per-task·
  mem(K/M/G/T → MB)·time(walltime 파서 재사용)·job-name·chdir.
- **옮기지 못한 지시자는 목록으로 돌려준다**(`ignored_directives`). 조용히 버리면 사용자는
  안 먹은 줄 모른다. 값이 이상해 파싱에 실패한 것도 "적용했다"고 하지 않고 여기 담는다.
- 화면은 스크립트 모드에서 **자원 입력을 감춘다.** 폼까지 두면 어느 쪽이 이기는지 화면이
  말하지 못한다. 남는 것은 Job 이름·작업 디렉터리·스크립트뿐이다.

**드러난 기존 결함 하나** — `--gres`가 무시 목록에 뜬다. `_slurm_job_properties`에 GPU가
없어서 **폼 모드의 GPU 수도 같은 이유로 적용되지 않고 있다.** v0.0.43의 GPU 요청 필드
(`tres_per_node` 등)를 실측으로 확인해야 고칠 수 있어 이번에는 손대지 않았다 — 오늘 예약에서
스펙만 보고 두 번 틀린 뒤라 추측하지 않는다. 현재 클러스터에 GPU가 없어 드러나지 않았다.

테스트 305개 통과(4개 추가 — 지시자 매핑·폼 값보다 우선·무시 목록 보고·폼 모드 미파싱).

---

### 클러스터 화면(SCR-02) 정리 — 중복 카드 2개 제거

톱바에 클러스터 선택기와 공지 메뉴가 생긴 뒤, 이 화면의 카드 두 개가 **같은 일을 두 번**
하고 있었다. 화면에서 지웠다.

**`등록된 클러스터` 카드 — U-CL-01을 달고 있었지만 U-CL-01이 아니었다.**
정의서 U-CL-01은 *노드 수·idle 노드·GPU 가용량 요약*을 요구한다. 카드에 실제로 있던 것은
별칭·이름·정상 배지와 `이 클러스터 선택` 버튼뿐이었다 — 요약은 하나도 없고, 선택은 톱바가
이미 한다. 요약 API(`GET /clusters/{cid}/overview`)는 `docs/api.md`에 취소선(미구현)으로
남아 있다. 즉 **처음부터 잘못 라벨링된 빈 껍데기**였고 나중에 중복이 됐다.

**`공지사항` 요약 카드 — 톱바 공지 메뉴와 중복.** 게다가 `전체 보기` 링크가 `/notices`로
가는데 그 라우트는 `/cluster`로 리다이렉트한다 — **같은 화면으로 돌아오는 고리**였다.
공지를 톱바로 옮기면서 남은 흔적이다. 카드를 지우면서 함께 사라졌다.
`/notices` 리다이렉트 자체는 남겼다 — 옛 북마크가 살아 있어야 한다.

남은 SCR-02는 **파티션별 가용 자원(U-CL-02) 한 장**이다. 카드가 하나뿐이라
`grid lg:grid-cols-2`를 걷어내고 전체 폭을 쓰게 했다 — 2단 그리드에 카드 하나면 오른쪽
절반이 빈 채로 남는다.

정의서 SCR-02의 매핑(`U-CL-01~02`)은 **그대로 뒀다.** 정의서는 요구사항의 SoT이지 진척표가
아니다 — 요약 API를 만들면 되살릴 자리다. 대신 §2.1 아래 미구현 목록에 U-CL-01을 넣고,
이번에 구현한 노드/파티션 쓰기(A-ND-01·03·04·05)를 뺐다. 목록이 `2026-08-06`에 멈춰 있었다.

**배포 사고 하나.** 첫 배포에서 이미지를 `hpc-portal-frontend:latest`로 빌드했는데 Deployment는
**`:0.1.0`**을 참조한다. 롤아웃은 "성공"했지만 **옛 이미지를 다시 띄운 것**이라 변경이 나가지
않았다. `curl` 200만 보고 배포 완료라고 판단한 것이 잘못이다 — **200은 nginx가 살아 있다는
뜻이지 내 코드가 그 안에 있다는 뜻이 아니다.** 이후로는 pod 안 번들에서 제거 대상 문자열을
직접 확인한다:

```
k3s kubectl -n hpc-portal exec deploy/portal-frontend -- \
  grep -rl "이 클러스터 선택" /usr/share/nginx/html/assets   # → 없어야 한다
```

검증: 프론트 빌드 통과. 백엔드 무변경(테스트 305개 그대로).

---

### 자원 신청 승인(A-US-06) 빈 카드 제거 — 추적성 규칙보다 정직함

QOS 화면(SCR-13)의 `자원 신청 승인` 카드를 제거했다. **기능이 아니라 자리표시자였다.**

이 카드가 생긴 경위가 요점이다. 위 "SoT 불일치 5건 정리"에서 **"65개 기능 중 A-US-06만
화면에 매핑되지 않았다"**가 걸렸고, 그 구멍을 메우려고 카드를 놓았다. 즉 **수요가 아니라
추적성 규칙이 만든 화면**이다. `docs/api.md`는 같은 항목을 `선택 기능 — 수요 확인 후 설계`로
적고 엔드포인트를 하나도 정의하지 않았다.

다른 미구현 자리와 성격이 다르다는 점이 판단 근거였다. 나머지 셋(`GET /license/servers`,
`GET /license/features`, 로그 SSE)은 **만들 API 이름이 적혀 있다** — 백엔드만 없다는 뜻이다.
A-US-06만 `정의서 미설계 항목 — 승인 흐름 설계 후 구현`이었다. **무엇을 만들지가 없다.**

기능 자체의 값도 크지 않다. 관리자는 계정·QOS를 **지금도 직접 바꾼다**(A-US-02·03). 이
워크플로가 더하는 것은 권한이 아니라 신청 기록·승인 근거다. 그러려면 신청 테이블, 사용자
쪽 신청 화면(정의서에 대응하는 U- 기능이 아예 없다), 승인 시 `sacctmgr` 반영, 알림까지
필요하다 — 우선순위 `선택`에 비해 큰 일이다. 원래 포함이던 **가입 승인**은 AD 자동
프로비저닝(A-US-01)을 쓰기로 하며 이미 빠졌고, 남은 절반이 이것이다.

**규칙보다 정직함을 택했다.** 이걸 지우면 "모든 기능 ID가 화면에 매핑된다"는 규칙이 다시
깨진다. 그러나 **빈 카드로 규칙을 만족시키는 것은 매핑이 아니라 매핑처럼 보이는 것**이고,
관리자에게 "곧 된다"는 잘못된 기대를 준다. 미구현은 화면이 아니라 목록에 적는다.

요구사항 행(정의서 A-US-06)과 SCR-13 매핑(`A-US-01~06`)은 **남겼다** — 정의서는 요구사항의
SoT이지 진척표가 아니다. 대신 §2.1 아래 미구현 목록과 `docs/api.md` 미결 항목에 적었다.
U-CL-01 때와 같은 처리다.

검증: 프론트 빌드 통과. 백엔드 무변경.

---

### Job 템플릿 제출(U-JB-03) 탭 제거 — 폼·스크립트 둘만 남긴다

Job 제출 화면의 `템플릿` 탭을 제거했다. 남은 제출 방식은 **폼(U-JB-01)·스크립트(U-JB-02)**다.

앞서 "템플릿에는 solver s/w가 설치된 컨테이너 이미지와, 그 s/w에 입력값을 제출할 인터페이스가
필요하다"로 결론이 났고 GROMACS 사용법 조사까지 미뤄 둔 상태였다. **그 설계가 나오기 전까지
탭은 고를 수는 있는데 되는 일이 없는 자리**였다 — 템플릿을 골라도 이미지도, 입력 파일도,
파라미터 입력 UI도 없다. 화면에서 내리고, 필요해지면 설계를 마친 뒤 되살린다.

제거 범위:

| 층 | 내용 |
|---|---|
| 화면 | 탭 버튼·템플릿 드롭다운·`missingTemplate` 가드·`templateLabel`·목록 조회(`onMounted`) |
| 스키마 | `mode` 패턴 `^(form\|script\|template)$` → `^(form\|script)$`, `template_id`·`template_params` 삭제 |
| 서비스 | `build_script`의 템플릿 분기, `_render_template`, `_PLACEHOLDER_RE`, `JobSpec` 템플릿 필드 |
| 타입 | `JobSubmitRequest`의 `mode` 유니온과 템플릿 두 필드 |

**조건식이 하나로 접혔다.** 모드가 셋일 때는 `mode !== 'script'`(파티션·계정·QOS·Walltime)와
`mode === 'form'`(노드·CPU·GPU·메모리)이 서로 다른 집합이었다. 둘만 남으니 두 조건이 **같은
뜻**이 되어 블록을 하나로 합쳤다. 남겨 두면 다음 사람이 차이를 찾느라 시간을 쓴다.

`mode="template"`은 이제 스키마가 422로 거부한다(확인함) — 옛 클라이언트가 보내도 조용히
폼으로 처리되지 않는다.

**남은 것 — 관리자 템플릿 등록(A-OP-02)은 그대로다.** `job_template` 테이블, `GET/POST/PATCH/
DELETE /templates`, 포털 운영 설정의 등록 카드가 살아 있다. 요청 범위가 사용자 탭이었기
때문에 손대지 않았다. 다만 **지금은 등록해도 쓰는 곳이 없다** — 처리 여부는 별도 판단이
필요하다(DB 마이그레이션이 따라온다). `docs/api.md`의 `GET /templates` 행에 이 사실을 적었다.

검증: 테스트 301개 통과(템플릿 테스트 4개 제거 — 렌더링·자리표시자 3종). 프론트 빌드 통과.

---

### 관리자 템플릿 관리(A-OP-02 템플릿 부분)까지 제거 — 표 포함

제출 탭을 걷어내자 관리자 등록 화면만 남아 **등록해도 쓰는 곳이 없는 상태**가 됐다.
반쪽 경로를 남겨 두면 관리자는 템플릿이 동작한다고 믿는다. 표까지 함께 지웠다.

| 층 | 제거 대상 |
|---|---|
| 화면 | 포털 운영 설정의 `Job 템플릿` 카드, `templateForm`, `addTemplate`/`removeTemplate`, `load()`의 병렬 조회 |
| API | `frontend/src/api/ops.ts`의 `JobTemplate` 타입·`templates`·`createTemplate`·`removeTemplate` |
| 라우터 | `GET/POST/PATCH/DELETE /templates` 4개 |
| 스키마 | `TemplateOut`·`TemplateCreate`·`TemplateUpdate` |
| 서비스 | `list/create/update/delete_template`, `OpsService.templates` |
| 리포지토리 | `JobTemplateRepository` |
| 모델·DB | `JobTemplate`, `job_template` 표 (마이그레이션 `0012`) |
| 기타 | `seed_dev.py`의 `TEMPLATES` 상수·시딩 루프, 테스트 2개 |

**애초에 이 표는 요구된 기능을 담기에 모자랐다.** 템플릿이 쓸모 있으려면 solver s/w가 설치된
컨테이너 이미지와 그 s/w에 값을 넣는 입력 인터페이스가 필요한데, 여기 있던 것은
`params.script` 문자열과 `{{key}}` 치환뿐이었다. 되살릴 때는 이 스키마가 아니라 **인터랙티브
앱 카탈로그와 같은 모양**(`session_apps.py` + 클러스터 `image_repository`)이어야 한다.
마이그레이션 docstring에 그렇게 적어 뒀다.

**운영 DB에 4행이 있었다.** 전부 `seed_dev.py`가 넣은 샘플이고 사용자가 만든 것은 없었다 —
지우기 전에 확인했다. 내용은 아래와 같다(되살릴 때 참고용):

| name | type | version | script |
|---|---|---|---|
| Python (single node) | batch | 1.0 | `module load python/3.12` + `python {{entry}}` |
| MPI (multi node) | batch | 1.0 | `module load openmpi/5.0` + `mpirun -np {{np}} {{binary}}` |
| GROMACS | batch | 2025.2 | `module load gromacs/2025.2` + `gmx mdrun -deffnm {{prefix}}` |
| JupyterLab | interactive | 4.2 | `jupyter lab --no-browser --ip=0.0.0.0 --port=$PORT` |

#### 마이그레이션을 실 MySQL에서 확인했다

SQLite로는 전체 체인이 돌지 않는다 — `0006`이 `ALTER TABLE … DROP COLUMN`을 쓰는데 SQLite가
받지 않는다. 그래서 **운영과 같은 MySQL에 임시 DB(`portal_migtest`)를 만들어** 처음부터 올렸다.

- `0011 → 0012` 적용 후 `job_template` 없음, 표 **19개**
- `downgrade 0011`로 표가 **컬럼 9개·FK `fk_job_template_created_by_user`까지 그대로 복원**
- 다시 `upgrade head` 정상, 임시 DB 삭제

`job_template`을 참조하는 표는 없어(나가는 FK만 있다) `0011`처럼 FK를 먼저 떼는 절차가
필요 없었다.

#### 문서 수치 두 개가 낡아 있었다

- `test_models_match_erd_entity_count`가 **20 → 19**로 바뀌어 실패했다. 이 테스트가 문서와
  코드의 어긋남을 잡아 준 셈이다. `db-erd.md`에서 `job_template` 엔티티·관계선·설명 행을
  지우고 기대값을 고쳤다.
- `api.md` 머리말의 `84개 엔드포인트`는 **이미 낡은 수치**였다(노드 쓰기·예약 추가분이
  반영되지 않았다). 지금 세어 **83개**로 고치고, 셈하는 명령을 함께 적어 다음에 검증할 수
  있게 했다.

검증: 테스트 **299개 통과**(템플릿 테스트 2개 추가 제거). 프론트 빌드 통과.

---

### 설계 메모: GPU 시뮬레이션·렌더링 도입 검토 (Isaac Sim / Omniverse)

구현이 아니라 **결정과 근거의 기록**이다. 분량이 많아 별도 문서로 옮겼다 —
**[docs/gpu-simulation.md](gpu-simulation.md)** 가 정본이다(세션 전송 보안 때와 같은 방식).

요지만 적으면:

- Omniverse/Nucleus는 **별도 k8s**, Isaac Sim은 **포털의 배치 solver 전용**(GUI 없음).
- 두 시스템을 **묶지 않는다** — 홈 NFS 공유 안은 검토 후 철회(UID/GID 정합·격리 약화·
  Nucleus가 파일시스템이 아니라는 점). 데이터는 사람이 복사한다.
- **A100/H100은 RT 코어가 없어 Isaac Sim 공식 미지원.** L40 계열이 필요하고,
  **파티션 분리는 선택이 아니라 필수**다 — 포털은 GPU 종류를 구분하지 못하고
  파티션 이름이 그것을 표현하는 유일한 수단이다.
- 파이프라인 엔진은 만들지 않는다. Slurm 배열·의존성 위에 Snakemake를 얹는다.
- 포털 미구현 4건: **GPU 요청(`tres_per_node`)·배열 잡·의존성**·API 토큰.
  앞 셋은 장비 없이 지금 고칠 수 있고, `tres_per_node`의 **문자열 형식만 실측이 남았다.**
- solver 카탈로그는 **실제로 한 번 돌려본 뒤에** 설계한다. 건너뛰면 2026-08-07에 지운
  `job_template` 표를 다시 만들게 된다.

---

### GPU 요청·배열 잡·의존성 구현 (U-JB-01·02)

렌더링 워크플로에 필수인 셋이 빠져 있었다. 셋 다 `#SBATCH` 지시자가 `ignored_directives`로
빠지는 형태로 드러났다 — 스크립트 모드를 고치며 넣은 그 경고가 없었으면 한참 찾았을 것들이다.

| 항목 | 없을 때 |
|---|---|
| GPU (`tres_per_node`) | **GPU 노드를 사도 Job이 GPU를 요청하지 않는다.** 폼의 GPU 수도 무효였다 |
| 배열 (`array`) | 240 프레임 렌더를 냈는데 **1장만 나온다** |
| 의존성 (`dependency`) | 시뮬 → 렌더 → 재조합 단계가 이어지지 않는다 |

#### `tres_per_node` 형식을 실측으로 정했다 — 추측하지 않았다

예약에서 스펙만 보고 두 번 틀린 뒤라, GPU가 없는 상태에서도 형식을 가릴 방법을 먼저 찾았다.
**세 후보를 실제 클러스터에 제출해 에러 번호를 비교했다**(전부 거부되므로 Job이 생기지 않는다):

| 보낸 값 | 에러 | 해석 |
|---|---|---|
| `gpu:1` | **2115** `Invalid Trackable RESource (TRES) specification` | TRES 파서가 못 알아봄 |
| `gres:gpu:1` | **2072** `Invalid generic resource (gres) specification` | **gres 파서까지 도달** |
| `gres/gpu:1` | 2072 | 위와 동일 |

2072는 gres 파서에 닿아 이름 조회에서 실패했다는 뜻이다. `--gres=gpu:N`이 노리는 경로가
그쪽이므로 **`gres:gpu:N`**을 쓴다(`sbatch --gres=gpu:N`도 `TresPerNode=gres:gpu:N`으로 남긴다).

**정직하게 남길 한계**: 지금은 "형식이 맞다"까지만 확인됐다. 2072/2115가 갈린 이유가 형식
차이가 아니라 **이 클러스터에 `gres/gpu` TRES 자체가 없어서**일 가능성을 완전히 배제하지는
못했다. `gres_gpu()` docstring과 [gpu-simulation.md](gpu-simulation.md)에 적어 뒀고,
**L40 도입 후 성공 제출로 재확인해야 한다.**

#### 구현

- `gres_gpu(count)` — 형식을 한 곳에서 만든다. 실측 근거를 docstring에 남겼다.
- `_slurm_job_properties` — `tres_per_node`·`array`·`dependency` 추가. **GPU가 0이면 아예 넣지
  않는다** — 0은 "GPU 0개 요청"이 되어 거부될 수 있다.
- `#SBATCH` 파서 — `--gres`·`--gpus`·`--gpus-per-node`·`--gpus-per-task`·`--array`·
  `--dependency`와 짧은 형태(`-G`·`-a`·`-d`)를 매핑. `--gres=gpu:a100:4`처럼 **타입이 끼어도
  개수만** 뽑는다(`_GRES_GPU`).
- **`--gres`의 gpu 아닌 자원은 옮기지 않는다.** license·mps 등은 대응 필드를 모르므로
  추측하지 않고 `ignored_directives`로 알린다.
- `build_script`에도 `--array`·`--dependency`를 적는다 — 미리보기와 제출이 어긋나면 안 된다.
- 폼에 **배열 인덱스·의존성** 입력을 추가했다. 형식 검사는 Slurm에 맡긴다 — 포털이 문법을
  다시 정의하면 Slurm이 받는 표기와 어긋난다.

#### 기존 테스트 하나를 고쳤다

`test_unmapped_directives_are_reported_not_dropped`가 `--gres`를 무시 목록에서 기대하고 있었다.
이제 옮겨지므로 **실제 동작에 맞게** 고치고, `tres_per_node`가 실리는지까지 확인하도록 넓혔다.

검증: 테스트 **305개 통과**(6개 추가). 비어 있지 않음을 확인 — `gres_gpu`를 `gpu:{n}`으로
되돌리고 `tres_per_node`를 빼자 **4개가 실패**했고, 복구하니 전부 통과했다.

---

### 자격증명 분리 — HttpOnly 쿠키(브라우저) + Bearer(기계), 액세스 30분 / refresh 2주

토큰이 `localStorage`에 있었다. **XSS 하나면 토큰을 꺼내 간다** — 그 뒤로는 공격자 기계에서
8시간 동안 Job 제출·파일 삭제·관리자 API가 전부 가능했고, 사용자가 창을 닫아도 계속됐다.

**전환이 아니라 분리로 갔다.** 쿠키 하나로 통일하면 CLI·워크플로 엔진이 쿠키 항아리와 CSRF
헤더를 다뤄야 한다 — 방금 확정한 "외부 시스템에서 API로 batch job 제출"과 정면으로 부딪힌다.

```
브라우저(SPA)  → HttpOnly + Secure + SameSite=Strict 쿠키
기계(CLI·API)  → Authorization: Bearer   (지금 방식 유지)
```

이 구조가 잘 맞은 이유: **토큰이 이미 "세션을 가리키는 표"였다**(`sid` → Redis). 자기완결형
JWT가 아니라서 **담는 그릇만 바꾸면 됐고** 검증 로직은 그대로다.

#### HttpOnly가 막는 것과 막지 못하는 것

과대평가하지 않는다. HttpOnly여도 **XSS는 그 페이지에서 요청을 보낼 수 있다**(쿠키가 자동으로
붙으므로). 바뀌는 것은 **"토큰 절도(이식 가능·오래감)" → "세션 편승(그 브라우저·그 순간만)"**
이다. 큰 개선이지만 XSS 대책 자체는 아니다.

#### 대신 생기는 CSRF를 두 겹으로 막았다

1. `SameSite=Strict` — 다른 사이트에서 온 요청에는 쿠키가 아예 안 붙는다.
2. **double-submit** — `portal_csrf`(유일하게 읽을 수 있는 쿠키)를 `X-CSRF-Token` 헤더로
   되돌려 보내게 한다. 다른 오리진은 쿠키를 **읽지** 못하므로 이 헤더를 만들 수 없다.

**Bearer 요청은 CSRF 검사에서 제외한다** — 헤더는 브라우저가 자동으로 붙이지 않으므로 애초에
CSRF가 성립하지 않는다.

#### 액세스 30분 / refresh 2주

- 액세스가 짧으면 유출돼도 창이 좁다. 대신 화면을 오래 켜 두면 반드시 만료되므로,
  **프런트가 401에서 한 번 갱신하고 재시도한다** — 안 하면 30분마다 로그인 화면으로 쫓겨난다.
- 갱신은 **하나만 돌린다**(single-flight). 401이 동시에 여럿 나면 refresh 회전이 겹쳐 서로를
  무효로 만들고, 서버가 그걸 탈취로 보고 세션을 끊는다.
- refresh는 **원문을 저장하지 않는다**(sha256만). Redis가 새어도 되살릴 수 없다.
- **회전한다.** 쓴 토큰은 즉시 폐기하고 새것을 준다. 이미 쓴 토큰이 다시 오면 사본이
  돌아다닌다는 뜻이므로 거부한다.
- refresh 쿠키는 **`/api/v1/auth/refresh` 경로에만** 실린다. 다른 요청에 딸려 다닐 이유가 없다.
- 계정이 비활성화되면 갱신도 막고 **세션까지 끊는다** — 막았는데 갱신되면 막은 의미가 없다.
- 세션 레코드 TTL을 refresh 수명(2주)에 맞췄다. 액세스보다 오래 살아야 갱신이 성립한다.

#### WS 인증을 쿠키로 정리했다

터미널·원격 데스크톱이 토큰을 subprotocol(`portal.token.<jwt>`)로 보냈다 — **JS가 토큰을 읽을
수 있어야 가능한 방식**이라 HttpOnly와 양립하지 않는다. 같은 오리진 handshake에는 쿠키가
실리므로 그것을 읽는다. 헤더·subprotocol 경로는 **기계 클라이언트용으로 남겼다**(쿠키 항아리를
쓰지 않는다).

#### 테스트 전제가 하나 무너졌다 — 제품 버그는 아니다

**로그인이 쿠키를 남기므로, 이후 요청은 헤더가 없어도 익명이 아니다.**
`test_settings_require_admin`이 "Authorization 없음 = 401"을 전제했는데 이제 비관리자로
인증돼 403이 됐다. **서버는 정확히 맞게 답했다** — 인증됐지만 권한이 없으니 403이다.
깨진 것은 테스트의 전제다.

이게 실패로 드러난 것은 운이 좋았다. **위험한 쪽은 반대다** — 익명이어야 할 요청이 쿠키로
인증되면서 **테스트가 조용히 계속 통과**하는 경우다. 그러면 권한 검사가 뚫려도 모른다.
확인 결과 `auth_headers(...)`를 쓰는 테스트는 **헤더가 쿠키보다 우선**이라 영향이 없었고,
자격증명 없이 401을 기대한 테스트는 이것 하나뿐이었다.

**구조로 막았다.** 처음에는 그 테스트에서 `client.cookies.clear()`를 부르게 고쳤는데, 그러면
앞으로 익명 검사를 쓸 때마다 사람이 기억해야 한다 — 잊으면 조용히 통과한다. 대신 길목인
**`login()` 헬퍼가 쿠키를 남기지 않게** 했다. 이 헬퍼의 계약은 "Bearer 토큰을 하나 준다"이지
세션을 열어 두는 것이 아니다. 쿠키 자체를 검증하는 테스트는 헬퍼를 쓰지 않고 엔드포인트를
직접 부른다(`tests/test_auth_cookies.py`).

그 성질이 다시 깨지지 않도록 **회귀 테스트를 하나 두었다**
(`test_login_helper_leaves_no_session_cookie`).

검증: 테스트 **314개 통과**(9개 추가). 비어 있지 않음 확인 — CSRF 검사를 빼자 1개, refresh
회전(폐기)을 빼자 1개, `login()`의 쿠키 정리를 빼자 2개가 각각 실패했고 복구하니 전부
통과했다.

---

### 사용자별 API 토큰 (C-01, SCR-20) — 세 번째 자격증명

액세스 토큰을 30분으로 줄이자 **자동화가 쓸 수 있는 자격증명이 없어졌다.** 브라우저 쿠키는
스크립트가 못 쓰고, 로그인 토큰은 30분이며, AD 비밀번호를 박으면 **반복 실패로 계정이 잠긴다.**

```
브라우저   → HttpOnly 쿠키 (액세스 30분 / refresh 2주)
사람 + CLI → 로그인 Bearer  (30분, refresh로 갱신)
자동화     → API 토큰 hpcp_… (장수명·폐기 가능)   ← 이번에 추가
```

#### 설계에서 지킨 것

- **원문을 저장하지 않는다.** sha256만 둔다(마이그레이션 `0013`). 분실은 재발급이지 복구가
  아니다. 발급 응답에만 한 번 담기고, 목록 스키마에는 `token` 필드가 아예 없다.
- **접두사 `hpcp_`로 구분한다.** JWT 해독을 시도조차 하지 않는다 — 실패 예외로 분기하면
  "세션 토큰이 유효하지 않다"처럼 원인이 엉뚱하게 보고된다. 시크릿 스캐너에도 잡힌다.
- **폐기가 즉시 먹는다.** 조회 때마다 `revoked_at`·`expires_at`을 본다.
- **권한은 소유자의 역할을 그대로 따른다.** 토큰별 스코프는 없다 — 필요해지면 permission
  목록을 붙인다(라우터가 이미 permission 문법을 쓴다).
- **남의 토큰은 404다.** 403이면 "그 번호의 토큰이 있다"는 사실이 샌다.
- **개수 상한 20개.** 목록이 관리 불가능해지면 폐기도 안 한다.
- `last_used_at`은 **5분 간격으로만** 쓴다. 매 요청 갱신하면 요청마다 DB 쓰기가 생긴다.

#### 마이그레이션 downgrade가 실 MySQL에서 깨졌다

`0013`의 downgrade가 인덱스를 먼저 지우고 표를 지우게 돼 있었는데, **`user_guid`는 FK가
걸려 있어 MySQL이 인덱스 삭제를 거부한다**(1553). 인덱스를 따로 지울 이유가 없다 — 표를
지우면 함께 사라진다.

더 나쁜 것은 그 다음이었다. **MySQL은 DDL이 트랜잭션이 아니라 중간에 실패해도 앞 단계가
되돌아가지 않는다.** 첫 시도가 `token_hash` 인덱스만 지우고 멈춰서, 두 번째 시도는 "그런
인덱스 없다"(1091)로 **다른 에러**를 냈다 — 원인을 한 번 더 헷갈리게 만들었다.

SQLite로는 애초에 잡을 수 없는 문제다(`0006`이 `ALTER … DROP COLUMN`을 써서 체인이 안 돈다).
**실 MySQL 임시 DB에서 upgrade → downgrade → upgrade 왕복**을 돌려 확인했다.

#### ERD 대조 테스트가 또 잡았다

`test_models_match_erd_entity_count`가 19 → 20으로 깨졌다. `db-erd.md`에 엔티티·관계선·설명
행을 더하고 기대값을 고쳤다. 이 테스트가 문서와 코드의 어긋남을 두 번째로 잡아 줬다.

검증: 테스트 **324개 통과**(10개 추가 — 원문 1회 노출·인증·CSRF 면제·즉시 폐기·만료·
남의 토큰 불가시·권한 상속·개수 상한·접두사 위조). 마이그레이션은 실 MySQL에서 왕복 확인.

---

### 세션 수명 — 유휴 슬라이딩 + 절대 상한 (C-01, A-OP-04)

"1시간 무활동이면 자동 로그아웃"을 refresh 토큰 수명으로 만들려다 **시계가 둘이 되는 함정**을
발견했다.

**refresh 토큰은 활동할 때 갱신되지 않는다.** 액세스 토큰이 30분이라, 그동안 아무리 많이
클릭해도 `/auth/refresh`는 한 번도 불리지 않는다. refresh TTL을 유휴 시계로 쓰면:

```
t=0    로그인 → refresh 발급(t=60 만료)
t=0~29 활발히 사용 → refresh는 안 불림, 여전히 t=60 만료
t=29   마지막 클릭
t=31   ← 로그아웃 (마지막 활동 후 겨우 2분)
```

유휴 시간이 **31~60분 사이로 들쭉날쭉**하고 사용자는 이유를 알 수 없다.

**유휴 시계는 세션 레코드에 건다.** `SessionStore.get()`은 인증된 모든 요청마다 불리므로
여기가 활동이 지나가는 길목이다. `touch(sid, ttl)`로 Redis TTL을 되감는다.

#### 수명을 코드에 박지 않았다

`portal_setting.session_timeout_min`(기본 480분)이 **이미 있는데 아무 데도 쓰이지 않고
있었다.** 이걸 연결해 관리자가 화면에서 조절하게 했다.

- 매 요청 DB를 읽으면 요청마다 SELECT가 생긴다 → **Redis에 60초 캐시**.
- 관리자가 값을 바꾸면 **캐시를 즉시 비운다.** 안 비워도 60초 뒤 반영되지만, 그동안
  관리자는 "안 먹었나" 하고 다시 누른다.
- 설정 행을 **읽기 경로에서 만들지 않는다**(`get_or_create`가 아니라 `first()`). 읽기가
  쓰기를 부르면 요청마다 INSERT 시도가 생긴다. 테스트로 못 박았다.

#### 절대 상한을 따로 둔다

유휴 연장만 있으면 세션이 사실상 영구히 산다 — 비밀번호를 다시 확인하는 지점이 영영 오지
않는다. 세션 레코드에 `created_at`을 넣고 **14일이 지나면 활동과 무관하게 끊는다.**
유휴 연장으로 젊어지지 않는 값이다.

#### fake Redis의 `expire()`가 껍데기였다

`return True`만 하고 아무 일도 안 했다. **그 상태로는 슬라이딩을 테스트할 수 없다** —
만료가 밀렸는지 확인할 방법이 없다. 실제로 만료 시각을 다시 잡도록 고쳤다. 테스트 3개가
그 전까지 통과할 수 없었다.

#### 남은 제약 두 가지 (문서에만 남긴다)

- **폴링이 활동으로 잡힌다.** 이 포털은 실시간 화면을 폴링한다(C-04, ≤30초). **탭만 열어두면
  자리를 비워도 세션이 안 끊긴다** — 유휴 타임아웃이 가장 위험한 상황에서 무력하다. 막으려면
  폴링 요청을 활동에서 제외하거나 클라이언트가 실제 입력을 감지해야 한다.
- **이미 열린 WebSocket은 안 끊긴다.** 터미널·원격 데스크톱은 handshake 때 한 번만
  인증하고, 그 뒤 중계 루프에는 재검사가 없다. 토큰이 만료돼도, 로그아웃해도 이미 열린
  세션은 계속 붙어 있다.

검증: 테스트 **330개 통과**(6개 추가). 비어 있지 않음 확인 — 슬라이딩을 빼자 3개,
절대 상한 검사를 빼자 1개가 실패했고 복구하니 전부 통과했다.

---

### 웹 터미널이 끊긴 사고 — import 누락 + 테스트 공백

쿠키 인증으로 옮긴 뒤 **웹 터미널이 접속되지 않았다.** 원인은 단순했다.

```
NameError: name 'ACCESS_COOKIE' is not defined
  File "/app/app/routers/terminal.py", line 33, in ws_access_token
```

WS 인증을 쿠키로 바꾸면서 `sessions.py`와 `terminal.py` 두 파일에 같은 헬퍼를 넣었는데,
**스크립트가 import를 한쪽에만 넣었다.** 조건이 `'from app.core.cookies import' not in s`라
이미 다른 경로로 그 문자열이 있던 파일은 건너뛰었다.

**진짜 문제는 그게 아니라 아무도 못 잡았다는 것이다.**

- 테스트 330개가 전부 통과했다. `test_terminal.py`가 **아예 없었기 때문**이다.
  세션 WS(`test_sessions.py`)만 테스트가 있어서 같은 실수가 그쪽에서는 드러났을 텐데,
  터미널은 검사하는 눈이 없었다.
- import 누락은 **모듈 로드 시점이 아니라 그 줄이 실행될 때** 드러난다. 함수 안에서
  참조하는 이름이라 `import app.routers.terminal`은 멀쩡히 통과한다.
- 배포 검증도 통과했다. `front: 200`·`api: 401`은 WS 경로를 지나가지 않는다.

`tests/test_terminal_ws.py`를 새로 만들었다. 인증 경로(쿠키·Bearer·자격증명 없음)와 함께,
**WS 인증을 하는 라우터가 쓰는 이름을 실제로 해석해 보는 테스트**를 넣었다 —
이런 종류는 요청이 올 때까지 숨어 있으므로 미리 부딪혀 봐야 한다.

검증: 테스트 **334개 통과**(4개 추가). 비어 있지 않음 확인 — import를 다시 빼자 1개가
실패했다. 배포된 pod에서 두 라우터 모두 `ACCESS_COOKIE=portal_access`로 해석되는 것을
직접 확인했다.

---

### Batch 앱 (U-JB-13, SCR-21) — 해석 solver를 배치 Job으로

인터랙티브 앱 아래에 `Batch 앱` 메뉴를 만들었다. 앱(해석 s/w)을 고르고 **그 앱이 요구하는
입력값**을 넣으면 배치 Job으로 나간다. s/w는 컨테이너 이미지로 제공한다.

**2026-08-07에 지운 `job_template`의 후신이다.** 그때 지운 이유가 "solver 이미지도 입력
인터페이스도 없이 `params.script` 문자열과 `{{key}}` 치환만 있었다"였다. 이번에는 셋이
한 몸이다:

```
이미지  +  실행 커맨드  +  파라미터 스키마     ← batch_apps.py 한 곳
```

#### 왜 DB가 아니라 코드인가

셋은 **함께 바뀐다.** 커맨드를 고치면 파라미터가 따라 바뀌고, 이미지를 올리면 둘 다 바뀐다.
DB에 넣으면 코드 배포와 데이터가 따로 놀아 **화면은 새 필드를 묻는데 이미지는 옛 커맨드**인
상태가 생긴다. 인터랙티브 앱 카탈로그(`session_apps.py`)와 같은 판단이다.

#### `{{key}}` 치환이 `job_template`과 다른 점

**치환 대상이 사용자 입력이 아니다.** 커맨드 틀은 코드에 있고 사용자는 값만 넣는다.
값은 전부 `shlex.quote`로 감싸므로 `;`나 `$(…)`를 넣어도 명령이 되지 않고 **값으로 남는다**
(테스트로 못 박았다).

커맨드에 있는데 파라미터 목록에 없는 자리표시자는 **앱 정의의 버그**다 — 그대로 나가면
워커에서 `{{missing}}`이 인자로 들어가 조용히 이상하게 돈다. 제출 전에 막는다.

#### 제출은 기존 경로를 그대로 탄다

스키마가 `JobSubmitRequest`를 **물려받는다.** 파티션·노드·GPU·walltime·배열·의존성이 여기서도
그대로 필요한데, 따로 정의하면 한쪽에만 필드가 추가되어 화면이 갈린다. 서버는 `mode="form"`
으로 제출하므로 `#SBATCH` 지시자도 함께 적히고, 그 스크립트를 그대로 `sbatch`로 재실행할 수
있다.

**요청의 `script`·`mode`는 무시한다.** 사용자가 바꿀 수 있으면 카탈로그를 두는 의미가 없다.

#### 경로 파라미터

절대 경로 + `..` 금지. 폼이 홈 하위만 만들지만 API를 직접 부르는 길도 있어 서버에서도 막는다
(`work_dir`와 같은 규칙). 실제 접근 권한은 Job이 **본인 권한으로** 돌아 OS가 판정한다 —
여기서 거르는 것은 오타·경로 조작이다.

입력 파일은 **홈 하위 경로로 지정**한다. 업로드는 파일 관리자(U-FM-02)가 이미 하고,
수 GB 입력은 scp/rsync가 맞다. 업로드 경로를 두 곳으로 만들지 않았다.

#### 지금은 앱이 전부 `ready=False`다

이미지가 없다. GROMACS 항목의 커맨드·파라미터는 **가정이지 실측이 아니다.** 화면은 준비 중인
앱도 보여주되 고를 수 없게 한다 — 숨기면 "언젠가 되나?"를 물을 데가 없다.

실제 이미지가 생기면 **손으로 한 번 돌려본 뒤** 카탈로그를 맞춰야 한다. 그 순서를 건너뛰면
`job_template`을 다시 만드는 것과 같다([gpu-simulation.md](gpu-simulation.md) §8).

검증: 테스트 **346개 통과**(12개 추가 — 카탈로그 노출·준비 전 차단·값 인용·기본값·필수 누락·
경로 검사·숫자 검사·정의 불일치·`--nv`·이미지 참조·요청 script 무시).

---

### Batch 앱 첫 대상을 OpenFOAM으로 (U-JB-13)

GROMACS 대신 **OpenFOAM**으로 바꿨다. 이유는 **고리가 닫히기 때문**이다.

```
Batch 앱(OpenFOAM) → 홈에 결과 → 인터랙티브 앱(ParaView)에서 열기
```

ParaView는 이미 인터랙티브 앱으로 있고(`rocky9-mate-1.5.sif`), **OpenFOAM 리더가 ParaView에
내장**되어 있어 시각화 쪽에 OpenFOAM을 깔 필요가 없다. 두 앱이 **같은 홈**을 보므로 파일을
옮길 일도 없다. GROMACS에는 이 고리가 없었다.

#### 이름만 바꾸는 작업이 아니었다

GROMACS는 파일 하나(`.tpr`)를 받지만 OpenFOAM은 **케이스 디렉터리**를 받고, 병렬 실행이
**분해 → 풀이 → 재조합** 3단계다. 그래서 카탈로그에 `AppStep`을 도입했다 — 단계마다
컨테이너 안/밖과 병렬 여부가 다르다.

| 단계 | 실행 |
|---|---|
| `decomposePar -force` | 컨테이너, 직렬, **체크박스로 끌 수 있음** |
| 랭크 수 검사 | **호스트**(컨테이너 불필요) |
| `{{solver}} -parallel` | 컨테이너, **`srun`** |
| `reconstructPar` | 컨테이너, 직렬, 체크박스 |
| `touch {{case}}/case.foam` | 호스트 |

**`srun apptainer exec …`로 띄운다.** 컨테이너 안에서 `mpirun`을 부르면 호스트 Slurm이
랭크를 모른다.

#### 조용히 실패하는 지점을 막았다

`decomposeParDict`의 `numberOfSubdomains`와 MPI 랭크 수가 다르면 **원인이 안 보이게**
실패한다. 그 값은 케이스 파일 안에 있어 화면에서 보이지 않는다. 그래서 분해 뒤에
`processor*` 디렉터리를 세어 보고 다르면 **사유를 적고 멈춘다.**

`touch case.foam`도 작지만 중요하다 — **ParaView는 이 표식이 있어야 케이스를 연다.**
없으면 결과가 다 나왔는데도 "안 열린다"가 된다. 인터랙티브 앱으로 이어지는 고리의 마지막
한 칸이다.

스크립트는 `set -euo pipefail`로 시작한다. 앞 단계가 실패했는데 다음이 도는 것이 가장 나쁘다.

#### `--ntasks`가 없어서 함께 추가했다

MPI는 **랭크 수가 정본**인데 `JobSpec`에 노드·CPU만 있었다. v0.0.43의 대응 필드를
실측으로 확인해(`tasks`, integer) 폼·스크립트·`#SBATCH` 파서(`-n`/`--ntasks`)에 모두 넣었다.
Job 제출 화면에도 같은 칸을 더했다 — MPI Job은 Batch 앱 밖에서도 낸다.

#### 남은 최대 위험 (문서에만)

**컨테이너 안의 MPI.** 호스트 Slurm의 PMI와 컨테이너 MPI 빌드가 호환돼야 한다. 안 맞으면
랭크가 전부 0번으로 뜨거나 멈춘다 — 원인이 아주 안 보인다. **단일 노드 직렬부터 돌려 보고
병렬로 넓히는** 순서를 권한다.

앱은 여전히 `ready=False`다. **커맨드·파라미터는 가정이지 실측이 아니다.** 배포판
(`openfoam.org` / `.com`)에 따라 solver 이름이 갈리므로, 실제 이미지가 정해지면 목록을
맞춰야 한다.

검증: 테스트 **352개 통과**(18개로 확대 — 단계 조건부 실행·`srun` 분기·호스트 단계·
랭크 검사·`.foam` 표식·`select` 강제·주입 방어 포함).

---

### OpenFOAM 이미지 준비 + Batch 앱 활성화

`docker://opencfd/openfoam-default:2512`(ESI, 2026-01 릴리스)를 SIF로 변환해
`/home/portal/images/openfoam-2512.sif`(443MB)에 넣었다. 카탈로그를 `ready=True`로 켰다.

**Docker를 거치지 않았다.** `apptainer build docker://…`로 레지스트리에서 바로 받으면
레이어가 `APPTAINER_CACHEDIR`로 가므로 `/data`(docker) 용량과 무관하다. `/home`이 NFS
100T라 여기서 끝났다.

```bash
export APPTAINER_CACHEDIR=/home/jrpark/.apptainer/cache
export APPTAINER_TMPDIR=/home/jrpark/.apptainer/tmp
apptainer build openfoam-2512.sif docker://opencfd/openfoam-default:2512
```

이미지 안에 카탈로그가 부르는 것이 다 있는지 **실행으로 확인**했다 —
`simpleFoam`·`pimpleFoam`·`interFoam`·`rhoPimpleFoam`·`potentialFoam`·`decomposePar`·
`reconstructPar`, `WM_PROJECT_VERSION=v2512`.

빌드 로그에 `destination filesystem does not support xattrs` 경고가 있다. NFS라 확장
속성이 안 붙었다 — 실행에는 문제없었으나 권한 관련 이상이 나오면 여기를 의심한다.

**커맨드·파라미터는 여전히 실측이 아니다.** 이미지가 생겼을 뿐, 실제 케이스로 한 번
돌려봐야 인자가 맞는지 안다.

테스트 2개가 OpenFOAM의 `ready=False`에 묶여 있어 깨졌다. **실제 앱 상태에 의존하지
않도록** 고쳤다 — 합성 앱으로 "준비 안 된 앱은 막힌다"를 검사한다. 앱 하나 켤 때마다
테스트가 깨지면 안 된다.

### 외부 접속 장애 — 진단이 틀렸던 기록

포털이 밖에서 안 열린다는 신고에 서버 안에서 `curl`로 검사해 `127.0.0.1`·`192.168.1.100`
모두 200이 나오자 **"서버는 정상, 바깥 문제"라고 단정했다. 틀렸다** — Traefik을 재시작하니
바로 복구됐다.

원인은 검사 방법이었다. hostPort DNAT은 **PREROUTING(외부 유입)과 OUTPUT(자기 자신)
두 체인**에 걸리는데, 서버 안에서 쏜 `curl`은 목적지가 자기 IP라도 **OUTPUT만 탄다.**
즉 외부 클라이언트가 타는 경로를 한 번도 검사하지 못한 채 "정상"이라고 말한 것이다.

**교훈: 외부 접속 문제는 서버 안에서 검사할 수 없다.** 다른 기계에서 접속해 보는 것이
유일하게 의미 있는 검사다. Traefik pod이 다시 뜨면 pod IP가 바뀌고 CNI portmap이 규칙을
다시 까는데, 그 과정이 어긋나면 **안에서는 200, 밖에서는 무응답**이 된다.

검증: 테스트 353개 통과.

---

### OpenFOAM 입력값을 실측으로 다시 정했다 (U-JB-13)

"격자 사이즈 같은 입력값이 필요하다"는 요청에, **추측으로 폼을 만들지 않고 실제 케이스를
돌려 보고** 정했다(`pitzDaily`, ESI v2512). 그 과정에서 알게 된 것이 설계를 바꿨다.

#### ① 격자 해상도는 화면에서 못 받는다

`blockMeshDict`의 격자 수는 이렇게 생겼다:

```
blocks ( hex ( 0 3 4 1 11 14 15 12 ) ( 18 30 1 ) simpleGrading ( 0.5 (...) 1 ) ... )
```

**중첩 리스트 안**이라 `foamDictionary -entry blocks -set`으로 바꿀 수 있는 값이 아니다.
격자는 **케이스 파일이 정한다.** 포털은 `blockMesh` 실행 여부만 다루고, 그 사실을 힌트에
적었다. 이걸 억지로 받으면 "화면에서 바꿨는데 안 바뀐다"가 된다.

#### ② 대신 시간 제어는 주입할 수 있다

`foamDictionary <파일> -entry X -set V`가 동작하는 것을 확인했다. 그래서 `endTime`·
`deltaT`·`writeInterval`·`startFrom`을 화면에서 받아 케이스에 **주입**한다.
**비우면 단계 자체가 빠져** 케이스 설정을 건드리지 않는다.

#### ③ `writeInterval > endTime`이면 결과가 하나도 안 나온다

실제로 당했다. `endTime 50` / `writeInterval 100`으로 돌리니 **조용히 끝나고 시간
디렉터리가 하나도 안 생겼으며**, `reconstructPar`가 `No times selected`로 실패했다.
`writeInterval`을 25로 낮추자 `0 25 50`이 나오고 재조합도 성공했다.

사용자가 시험 삼아 `endTime`만 줄이면 정확히 이 함정에 빠진다. 그래서 저장 간격을
**화면에 노출하고 힌트로 경고**한다.

#### ④ 튜토리얼 케이스에 `decomposeParDict`가 없다

`pitzDaily`에 없었다. 앞서 만들어 둔 "분해 수와 랭크 수가 다르면 멈춘다" 방식은
**평범한 케이스에서 바로 실패했을 것**이다. 바꿨다 — 없으면 만들고,
`numberOfSubdomains`를 **자원 칸의 랭크 수로 맞춘다**. `method scotch`는 계수 없이 임의
개수를 분해하므로 안전하다(`simple`은 `n (2 2 1)` 곱이 개수와 맞아야 한다).
**이미 있으면 만들지 않는다** — 케이스가 정한 것을 존중한다.

#### ⑤ 직렬/병렬 갈래를 나눴다

`-parallel`을 랭크 1개로 주면 실패한다. `AppStep`에 `unless`를 더해 분해를 끄면
`srun` 없이 직렬로 돈다.

#### ⑥ 이스케이프가 한 겹 사라져 스크립트가 깨졌다

`decomposeParDict`를 만드는 `printf "…\n…"`가 여러 겹(파이썬 소스 → 파일 → 셸)을
지나며 역슬래시를 한 겹 잃어, **한 단계가 세 줄로 깨졌다.** `set -e`가 뒷줄을 별도
명령으로 실행하므로 조용히 이상하게 돈다. 역슬래시가 필요 없는 `echo` 방식으로 바꾸고,
**줄 수를 세는 테스트**를 넣었다.

#### 검증 — 포털이 만든 스크립트를 그대로 실행했다

`build_body()`가 만든 10줄 스크립트를 `srun`만 `mpirun`으로 바꿔(dev01에 Slurm 없음)
실제로 돌렸다. **blockMesh → checkMesh → decomposePar → 병렬 simpleFoam → reconstructPar
→ case.foam 까지 전부 성공**했고 시간 디렉터리 `0 25 50`이 나왔다.

**남은 미확인은 `srun` + PMI 하나다.** 컨테이너 안 MPI 자체는 도는 것을 확인했지만
(mpirun 2랭크), 호스트 Slurm이 랭크를 띄우는 경로는 클러스터에서 확인해야 한다.

검증: 테스트 **358개 통과**(Batch 앱 24개로 확대).

### 화면 다듬기 3건 — 원격 데스크톱 최대화 · 사용량 시간축 · 파티션 CPU 가용량

#### ① 원격 데스크톱 최대화 (U-IA-02)

`fixed inset-0` 오버레이로 브라우저 창을 덮는다. **재연결이 필요 없다** — noVNC 1.7이
컨테이너에 `ResizeObserver`를 걸어 두어 `scaleViewport`가 새 크기로 알아서 다시 맞춘다.
브라우저 Fullscreen API는 쓰지 않았다(권한·이탈 이벤트 처리가 붙는다). ESC 탈출도 넣지
않았다 — ESC는 VNC로 넘어가야 하는 키라 화면이 제멋대로 줄어드는 편이 더 나쁘다.

#### ② 내 사용량 일별 그래프의 X축을 시간축으로 (U-AC-01)

가로 막대 나열 → **X축=날짜, Y축=CPU·h** 세로 막대로 바꿨다. 핵심은 모양이 아니라
**빈 날 채우기**다: 응답의 `daily`에는 Job이 있던 날만 오므로(`account.py`) 그대로
가로로 늘어놓으면 8/5와 8/6 사이 간격이 실제 날짜 간격과 달라진다 — 조회 기간을 하루도
빠짐없이 채우고 없는 날은 0으로 둔다(Billing은 이미 서버에서 `_daily_series(start,end)`로
같은 일을 한다). 행마다 있던 숫자는 자리가 없어 hover 툴팁으로 옮겼다.

#### ③ 파티션별 CPU 할당/가용 (U-CL-02)

**파티션 응답에는 CPU 총량만 있다**(v0.0.41). 할당량은 노드의 `alloc_cpus`에만 있고,
`/clusters/{cid}/nodes`는 관리자 전용이라 사용자 화면이 직접 부를 수 없다. 그래서
`ClusterService.partitions()`가 노드를 한 번 더 읽어 **파티션별로 합산**해 `cpu_usage`
(`allocated`/`available`/`total`)로 붙인다. 노드 조회가 실패하면 그 필드만 빠지고 목록은
그대로 나간다.

셈법은 sinfo와 같다 — DOWN·DRAIN 노드의 남은 CPU는 **가용이 아니다**(일을 받지 못한다).
돌던 Job의 CPU는 노드가 빠지는 중이어도 할당으로 센다. 그래서 `할당 + 가용 ≤ 전체`이고,
한 노드가 여러 파티션에 속하면 파티션마다 잡힌다.

비용은 파티션 조회마다 slurmrestd 호출 1회 추가다.

검증: 테스트 **359개 통과**, 프론트 빌드 통과, 백엔드·프론트 이미지 재배포.

### Batch 앱에 Isaac Sim 추가 (U-JB-13) — data factory용 합성 데이터 생성

조사·실측 기록은 [gpu-simulation.md §8-1](gpu-simulation.md)에 남겼다. 여기에는 코드에
남은 것만 적는다.

`BatchApp`에 **`env`** 를 더했다(`--env K=V`). Isaac Sim은 `ACCEPT_EULA` 없이 시작하지
않는데, 배치에는 동의를 물었을 때 대답할 사람이 없다. 이미지·커맨드·파라미터가 한 몸이라는
원칙 그대로 **환경변수도 앱이 정한다** — 사용자 입력이 아니다.

`isaac-sim` 앱은 **`ready=False`** 다. 이미지도 GPU 노드도 없다(현재 파티션은 `cpu`
하나뿐이다). 커맨드는 NVIDIA 문서·비공식 클러스터 가이드에서 왔고, `--env`·호스트
환경변수 전달·커맨드 형태는 openfoam SIF로 실행해 확인했다. **확인 못 한 것은 Isaac Sim
자체뿐이다.**

파라미터는 둘뿐이다(`script`·`config`). 프레임 수·해상도·출력 경로는 **CLI 인자가 아니라
config 파일의 키**여서, 폼을 만들어도 넘길 자리가 없다 — 만들었으면 `job_template`을 다시
만드는 것이었다.

두 가지가 실측으로 걷혔다:

1. **Apptainer가 이미지의 `ENV HOME`을 사용자 홈으로 덮어쓴다.** 그래서 NVIDIA가
   `docker run`에서 잡는 캐시 bind 6개가 필요 없다(그 마운트는 컨테이너 HOME이
   `/isaac-sim`이라 생기는 Docker 사정이다). gpu-simulation.md §4가 "최대 불확실성"으로
   적었던 것의 절반이다.
2. **Apptainer는 호스트 환경변수를 그대로 넘긴다.** 사용자 SDG 스크립트가
   `SLURM_ARRAY_TASK_ID`를 읽으면 배열 잡이 곧 샤딩이다 — 포털이 `--shard` 같은 규약을
   발명할 이유가 없다.

검증: 테스트 **363개 통과**(Batch 앱 +4), 백엔드 이미지 재배포.

### 코드 검토 지적 16건 수정 (결함 8 · 불필요 5 · 문서 3)

전수 검토에서 나온 지적을 전부 고쳤다. 판단이 갈렸던 두 건만 적는다.

#### 비용 추이는 **쓰기를 없애지 않았다** — 행 생성만 막았다

"GET이 DB에 쓴다"를 그대로 없앴더니 `test_account_id_comes_from_api_not_manual_input`이
깨졌다. 그 동작은 사고가 아니라 **의도이고 테스트로 잠겨 있었다**(손 입력 계정 ID를 응답에서
확인된 값으로 정정한다 — 클러스터 이름을 slurm.conf에서 가져오는 것과 같은 원칙).

진짜 결함은 쓰기 자체가 아니라 **행이 없을 때 조회가 행을 만드는 것**이었다. 동시에 두 번
들어오면 "단일 행"이 둘이 되고, 그 뒤로는 `LIMIT 1`이 어느 행을 집을지가 운에 달린다.
그래서 `conf is None`이면 아무것도 하지 않게 바꾸고 `_config()`에 `order_by(id)`를 붙였다.
**테스트가 설계 의도를 지켜 준 사례다.**

#### 세션 상태는 pure로 만들지 않고 **커밋을 붙였다**

`_view()`가 조회 중에 대장 상태를 고치는데 커밋이 없어, 뒤에 다른 커밋이 따라오는 경로
(웹소켓 접속)에서만 우연히 저장되고 있었다. 두 갈래가 있었다 — 쓰기를 없애거나(대장이
영원히 `active`로 남는다), 커밋을 붙이거나. **붙였다.** `api_token._touch()`가 이미
같은 방식(읽기 중 멱등한 상태 정정)을 쓰고 있어 태도가 일관된다. `self.session.dirty`일
때만 커밋하므로 평상시 조회에는 쓰기가 없다.

#### 나머지

- **walltime 오타가 500이었다.** 폼 모드에는 형식 검사가 없어 `walltime_minutes()`가 유일한
  관문인데 `int()`의 `ValueError`가 그대로 새어 나갔다. 스크립트 모드는 `_apply_directive()`가
  잡아 주어 무사했다 — **한쪽만 막혀 있었다.**
- **refresh 재사용 탐지가 문서에만 있었다.** docstring 두 곳이 "세션 전체를 끊는다"고 적었지만
  `consume()`이 키를 지워 버려 재사용인지 만료인지 구분할 방법 자체가 없었다. 삭제 대신
  `used:<sid>` 표식을 남기고 `reused_session()`을 더해 실제로 끊게 했다.
- **`_number()`가 두 벌이었고 답이 반대였다.** `account.py`는 맨 숫자를 `None`(=무제한)으로
  접고 `cluster.py`는 그대로 받았다 — QOS 한도가 판본에 따라 "무제한"으로 뒤집힐 수 있었다.
  `clients/slurm/adapters.py` 한 곳으로 모으고 `report.py`의 생 `int()`도 여기로 보냈다.
- **`parse_sbatch()`가 sbatch보다 많이 읽었다.** 실제 `sbatch`는 첫 실행 줄에서 멈추는데
  스크립트 전체를 훑어, 본문 뒤의 `#SBATCH`까지 적용됐다(같은 파일을 손으로 내면 다른
  파티션으로 도는 갈림).
- `df`·`quota` 파싱 실패가 500이 되던 것을 줄 단위로 건너뛰게 했다(docstring이 약속한
  "실패해도 빈 목록"이 명령 실패에만 적용되고 있었다).
- 죽은 코드: `LoginNodeClient.exists()`·`InteractiveSessionRepository.list_active()` 삭제,
  미사용 import 7건 제거, `open_stream()`의 중복 조회 제거.
- **쓰이지 않는 표 6개는 남겼다** — 전부 정의서에 있는 기능의 선행 스키마다(`job_template`과
  다른 점이 이것이다). 대신 `models/ops.py` 머리말에 목록과 근거를 적고,
  `test_tables_without_code_are_the_documented_ones`로 목록의 표류를 막았다. CLAUDE.md의
  미구현 목록도 실제와 맞췄다(License·티켓 외에 A-RP-04·A-RP-05·billing_snapshot이 더 있었다).

검증: 테스트 **373개 통과**(+10), 프론트 빌드 통과, 백엔드·프론트 재배포.

### Job 취소가 조용히 실패하던 버그 (U-JB-08)

화면에서 "취소"를 눌러도 Job이 안 죽는다는 제보. 로그를 보니 포털은 **200 OK를 세 번**
돌려주고 있었다.

#### 원인 둘 — 실측으로 갈랐다

**① 남의 Job을 요청자 이름으로 취소하려 했다.** `cancel()`이 `as_user=요청자`로 보내는데,
관리자는 남의 Job도 목록에서 본다(`is_admin`이면 소유자 필터가 없다). 실제로 문제의 Job 53은
`jooyeong.lee` 소유였고 요청자는 `jungryul0515.park`였다.

**② Slurm은 그 거부를 알려주지 않는다.** 시험용 Job으로 재현했다:

```
남으로 위장한 DELETE  → HTTP 200 · errors [] · 상태 RUNNING 유지   ← 조용한 거부
소유자로  보낸 DELETE → HTTP 200 · errors [] · 상태 CANCELLED       ← 성공
```

**응답만으로는 성공과 실패를 구분할 수 없다.** `errors`도 비어 있다. 그래서 포털은 성공으로
믿고 "취소했습니다"를 돌려줬고, 목록을 새로고침해도 Job은 그대로였다 — 몇 번을 눌러도 같다.

#### 고친 것

- **소유자로 위장해 취소한다.** 남의 Job에 닿는 것은 `_assert_visible`을 통과한 관리자뿐이고
  (A-JB-01), 본인 Job이면 값이 같다 — "대상 사용자는 언제나 요청자 본인" 규칙을 넓히는 것이
  아니다.
- **상태로 확인한다**(`_assert_cancelled`). 취소는 즉시 반영된다(실측: DELETE 직후
  `["CANCELLED","COMPLETING"]`) — 기다리지 않고 한 번만 다시 읽는다. 아직 살아 있으면 502로
  "Slurm이 취소를 받아들이지 않았습니다"를 돌려준다. 조회가 실패하면 판단하지 않는다.
- **상태를 집합으로 읽는다**(`_all_states`). Slurm이 `["CANCELLED","COMPLETING"]`처럼 겹쳐
  주므로 첫 칸만 보면 취소를 놓친다.
- **대역도 실물처럼 고쳤다** — `FakeSlurmClient.cancel_job`이 소유자가 아니면 조용히 거부한다.
  항상 성공하는 대역이었기 때문에 이 갈래가 테스트에 아예 없었다.

#### 아직 안 고친 것 — 같은 뿌리

`control()`(hold/release/priority, A-JB-02·03)도 `as_user=요청자`로 남의 Job을 건드린다.
같은 조용한 거부가 날 수 있다. **소유자 위장으로 바꾸지 않았다** — hold는 소유자도 할 수
있지만 **우선순위 상향은 operator 권한이 필요해서**, 소유자로 위장하면 지금 되던 것이 깨질
수 있다. GPU 노드처럼 실측할 수 있을 때 확인하고 정한다.

검증: 테스트 **377개 통과**(+4), 실 클러스터에서 시험 Job으로 취소 경로 재확인, 백엔드 재배포.

### Job 제출이 기본값 그대로는 실패하던 문제 (U-JB-01)

`2014 Requested node configuration is not available`. 원인은 두 겹이었다.

#### ① 폼 기본값이 클러스터와 무관한 상수였다

`JobSubmitView`의 기본값은 `partition: 'gpu'` · `cpus_per_task: 8` · `gpus: 1` ·
`memory_gb: 32`였다. 이 클러스터의 노드는 **CPU 2개 · 메모리 3915MB**다. 어느 값이
걸리는지 시험 제출로 갈랐다:

```
cpus_per_task=8, mem=32G  -> 2014
mem=32G 만                -> 2014
cpus_per_task=8 만        -> 2014
cpu 2 · mem 3G            -> OK
```

**둘 다 넘쳤다.** 즉 "GPU 파티션이 없어서"가 아니라 폼을 열자마자 들어 있는 값이
노드보다 컸다.

`job-options`에 **파티션별 노드 한 대의 최대치**(`capacity`)를 실었다. 합계가 아니라
최대치인 이유: `--cpus-per-task`·`--mem`은 노드 경계를 넘지 못한다. 노드 조회는
`gpu_partitions`가 이미 하고 있어서 **호출은 늘지 않았다**(`_fetch_nodes`로 합쳤다).
화면은 파티션이 정해지면 자원 값을 그 안으로 **끌어내리기만** 한다 — 사용자가 올린 값을
임의로 깎지 않는다. 못 읽으면 빈 dict이고 그때는 상한을 강제하지 않는다
(`gpu_partitions`의 `None`과 같은 태도).

#### ② Slurm이 적어 준 사유를 버리고 있었다

화면에는 `[EXTERNAL_SERVICE_ERROR] 외부 서비스 호출이 실패했습니다` 뒤에 **응답 JSON이
통째로** 찍혔다. `BaseHttpClient._map_status`가 4xx/5xx를 한 문장으로 뭉갠 탓이다.
그런데 slurmrestd는 `errors[].description`·`error`·`error_number`에 사유를 정확히 적어 준다.

`SlurmrestdClient._map_status`가 그걸 풀어 쓰도록 했다. 사용자가 스스로 고칠 수 있는
번호에는 안내를 덧붙인다 — 특히 **2014는 CPU·메모리·GPU 중 무엇이 넘쳤는지 말해 주지
않는다**.

```
전: 외부 서비스 호출이 실패했습니다 {"status":500,"body":{"errors":[{...}]}}
후: Slurm이 요청을 거부했습니다: Batch job submission failed (Requested node
    configuration is not available) — 요청한 CPU·메모리·GPU가 이 파티션의 노드 한
    대보다 큽니다. 자원 값을 줄여 보세요.
```

Batch 앱 화면도 같은 폼·같은 API라 같은 상한을 쓴다(기본 `memory_gb: 32`가 동일했다).

검증: 테스트 **380개 통과**(+3), 실 클러스터에서 `capacity = {'cpu': {2, 3915}}` 확인,
백엔드·프론트 재배포.

### 의존성을 화면에 드러냈다 (U-JB-07·05) — 파이프라인 엔진은 여전히 안 만든다

[gpu-simulation.md §6](gpu-simulation.md)의 "엔진을 만들지 않는다"는 그대로 두고,
**이미 되는 기능이 안 보이던 것**만 고쳤다. Slurm의 `--dependency`는 오늘도 동작한다
(실측: `afterok:67` → 선행 COMPLETED 5초 뒤 후행 RUNNING).

#### ① 대기 사유가 화면에 없었다

`state_reason`·`dependency`는 **목록 응답에도 이미 실려 온다**(실측). 그런데 화면이
읽지 않아, 영원히 시작되지 않는 Job이 순서를 기다리는 Job과 **똑같이 보였다**.

```
job 74  PENDING  state_reason=DependencyNeverSatisfied  dependency='afterok:73(failed)'
```

이 상태는 선행 Job이 실패·취소되면 생기고, **Slurm이 자동으로 치우지 않는다** — 사람이
취소해야 큐에서 사라진다. 그래서 목록·상세에서 빨갛게 띄우고 "직접 취소해야 합니다"를 적었다.

실측으로 알게 된 함정 둘:
- 사유가 없으면 빈 문자열이 아니라 **문자열 `"None"`** 이 온다. 그대로 쓰면 "None"이라고
  적힌 칸이 생긴다(`waitReason()`이 걸러낸다).
- **없는 Job 번호에 `afterok`을 걸면 대기 상태로도 못 간다** — 제출 자체가 2038로 거부된다.
  그 번호도 오류 안내에 넣었다.

사유 문구는 아는 값만 사람 말로 바꾸고 **모르는 값은 원문 그대로 둔다** — 추측해서 옮기면
Slurm이 실제로 말한 것과 어긋난다.

#### ② Job ID를 손으로 옮겨야 했다

Job ID는 제출해 봐야 알 수 있어서, 다단계를 걸려면 번호를 눈으로 읽어 폼에 타이핑해야 했다.
Job 상세에 **"이 Job 다음에 실행"** 을 두고 `/jobs/submit?dependency=afterok:<id>`로 넘긴다.
제출 화면은 그 값을 폼에 넣기만 한다 — **포털이 의존성 문법을 해석하지 않는다**는 규칙은 여기서도 같다.

#### 안 만든 것

다단계 일괄 제출·DAG 시각화·파이프라인 템플릿. 지금 유일한 실사용(OpenFOAM)은 분해→풀이→
재조합을 **한 Job 안에서** 처리하고 있어 Job 간 파이프라인 수요가 아직 실측되지 않았다.
첫 실사례는 Isaac Sim data factory(sim → render 배열 → composite)인데 GPU 노드가 있어야
손으로라도 돌려볼 수 있다. 그 전에 폼을 만들면 2026-08-07에 지운 `job_template`을 다시 만드는 것이다.

검증: 테스트 380개 통과(백엔드 변경은 2038 안내 한 줄), 프론트 빌드 통과, 재배포.

#### 후속 — 의존성을 별도 컬럼으로 빼고 앞 Job을 링크했다

첫 판에서 대기 사유·의존성을 **상태 칸에 몰아넣었다.** 상태 배지가 안 읽혔다.

- **상태 칸은 상태만.** 대기 사유는 `title`(hover)로 남긴다 — 자원·우선순위 대기처럼
  의존성과 무관한 사유는 여기가 제자리다.
- **의존성은 별도 컬럼.** `afterok`·앞 Job 번호·처지(대기/실패)를 나눠 적고,
  영원히 막힌 경우만 아래에 빨간 한 줄을 붙인다.
- **앞 Job을 누르면 그 Job으로 간다.** 번호만 적어 두면 목록을 다시 뒤져야 한다.
  이름은 **지금 목록에 있을 때만** 덧붙인다 — 번호마다 조회하면 목록 그리기에 요청이
  N개 붙고, 끝난 Job은 Slurm이 잊기도 한다(`MinJobAge`).

`parseDependency()`가 Slurm 표기를 그대로 푼다 — `,`(AND)·`?`(OR)로 갈리고 한 항목에 Job이
여럿 붙을 수 있다(`afterany:11:12`). 실측 문자열 9종으로 확인했다. **모르는 표기는 버리지
않고 종류만 담는다** — 원문을 잃으면 무엇에 걸렸는지 알 방법이 없어진다.

#### 후속 — 진행 중엔 수행 시간, 이력엔 시작·종료

**시간 필드가 두 출처에서 완전히 다르다**(실측 2026-08-08):

```
slurmctld(진행 중) : 평평한 키 + {set,infinite,number} 래퍼
                     start_time · end_time · submit_time, elapsed 없음
slurmdbd(이력)     : 중첩 time 객체 + 맨 정수
                     time.start · time.end · time.elapsed
```

이력 탭은 slurmdbd가 끊기면 slurmctld로 대체되므로 **한 탭에 두 형태가 섞여 들어온다.**
그래서 화면이 아니라 `utils/job.ts`에서 흡수한다(소유자 `user_name`/`user`와 같은 처리).

실측으로 걸러낸 함정 셋:

1. **`0`은 1970년이 아니라 "아직 없음"이다.** 대기 중 Job의 `start_time`, 실행 중 Job의
   `time.end`가 0으로 온다. 그대로 변환하면 1970-01-01이 찍힌다.
2. **도는 Job의 slurmctld `end_time`은 *예상* 종료다**(시작 + 제한시간). 실측값은
   `start=1786188759`인 Job에 `end_time=1817724759`(1년 뒤)였다 — 그대로 쓰면 끝나지도
   않은 Job에 종료 시각이 박힌다. 그래서 `jobEndedAt()`은 **끝난 Job의 값만** 돌려준다.
3. **0초 실행도 사실이다.** `time.elapsed`를 truthy로 검사하면 0초 Job이 '—'가 된다.

수행 시간은 도는 중이면 흐른다 — `now`를 1초마다 갱신하되 **도는 Job이 있을 때만** 돈다
(인터랙티브 앱 목록의 폴링과 같은 태도). 어댑터는 두 출처 6가지 경우로 확인했다.

컬럼도 탭마다 다르게 뒀다. **이력 응답의 `dependency`는 항상 `null`이라**(실측) 이력
탭에서는 의존성 칸을 빼고 시작·종료를 넣는다. Job 상세에도 같은 값을 넣었다 — 시간 필드가
래퍼(객체)라서 원문 목록 필터(`typeof v !== 'object'`)에 걸려 **상세에 시간이 하나도 안
보이고 있었다.**

### JupyterLab·VS Code Server (U-IA-01·03) — 1단계: 이미지와 컨테이너 기동

**"기존과 같은 방법"이 성립하지 않는 지점이 하나 있다.** 지금 있는 접속 경로는
`sessions/{sid}/connect` 하나이고, 그것은 **RFB 바이트를 WebSocket↔TCP로 중계**하는
루프다(docs/plan.md §3.3). 데스크톱·ParaView는 화면을 VNC로 내보내지만 JupyterLab과
code-server는 **HTTP 서비스**다 — 브라우저가 저 터널로 HTTP를 말할 수 없다.

재사용되는 것과 아닌 것:

| | 재사용 |
|---|---|
| 세션 수명(제출 → connection.json → 상태 추적 → 종료) | **그대로** |
| 이미지·카탈로그·`PORTAL_APP` 분기 | **그대로** |
| 접속 경로 | **불가** — VNC 바이트 중계 ↔ HTTP 리버스 프록시 |

#### 실측 — JupyterLab은 경로 접두사 아래에서 깨끗하게 돈다

`--ServerApp.base_url`을 주고 컨테이너를 실제로 띄워 확인했다:

```
GET /                            -> 404   ← base_url을 지킨다
GET /api/v1/session-apps/9999/lab-> 200
GET …/api/status                 -> 200
GET …/api/status (토큰 없이)      -> 403   ← 워커 포트도 스스로 막는다
HTML 에셋 링크                    -> /api/v1/session-apps/9999/static/…
```

**HTML을 고쳐 쓸 필요가 없다** — Jupyter가 접두사를 스스로 붙인다. 그래서 포털 프록시는
바이트만 옮기면 된다. base_url에는 **Slurm Job ID**를 쓴다: 포털 세션 ID는 Job 제출 뒤에
생겨서 제출 시점에 알 수 없지만, Job ID는 컨테이너가 스스로 안다.

VNC 세션과 달리 **X 서버가 없다** — Xvnc·xauth·dbus가 전부 빠진다. `start-jupyter.sh`는
포트 경쟁을 bind로 해결하고(`--port-retries=0`이라야 조용히 옆 포트로 옮기지 않는다),
토큰을 발급해 connection.json에 적고, `exec` 없이 `wait`으로 돌아 cleanup trap을 지킨다 —
전부 `start-desktop.sh`에서 이미 데인 함정들이다.

산출물: `rocky9-mate-1.6.sif`(1.4GB, JupyterLab 4.6.2 / Python 3.11.13)를 저장소에 넣었다.
데스크톱·ParaView도 그대로 들어 있어 나중에 카탈로그를 한 번에 1.6으로 올리면 된다.

#### VS Code Server는 막혀 있다 — code-server에 base path가 없다

code-server는 **base path 지원을 오래전에 제거했고**, 에셋 일부가 절대 경로로 링크돼
하위 경로 프록시에서 루트로 새어 나간다. Jupyter의 `base_url`에 해당하는 것이 없다.

선택지는 셋이고 **전부 포털 밖 결정이 필요하다**:
1. 세션마다 서브도메인 — 와일드카드 DNS + 와일드카드 TLS 인증서가 필요하다(인프라 변경).
2. 루트 경로 하나를 code-server에 내주고 쿠키로 세션을 가르기 — 포털 SPA와 충돌한다.
3. 포털이 호스팅하지 않고 **VS Code Remote-SSH**를 안내 — 사용자 기계에서 로그인 노드로
   붙는다. HPC에서 가장 흔한 구성이고 포털이 만들 것이 없다.

그래서 `code-server`는 `ready=False`로 둔다. **이미지에도 넣지 않았다** — 쓸 경로가
정해지기 전에 200MB를 넣을 이유가 없다.

#### 다음 (JupyterLab)

`session-apps/{job_id}/**` 리버스 프록시(HTTP+WebSocket)가 남았다. 터널은 요청마다 새
SSH 연결을 열면 페이지 한 장에 수십 번 핸드셰이크가 나므로, **세션당 로컬 포트포워딩**을
띄우고 그 위로 프록시하는 구성이 맞다. 소유권은 `slurm_job_id`로 세션을 찾아 확인한다.

### JupyterLab 완성 (U-IA-01) — HTTP 리버스 프록시

컨테이너(1단계)에 이어 포털 쪽을 만들었다. **VNC 경로를 재사용하지 않는다** — 새 경로다.

```
브라우저 → 포털 /api/v1/session-apps/{job_id}/**
        → 백엔드 127.0.0.1:<임시포트>  (LocalPortForward)
        → SSH direct-tcpip (로그인 노드가 목적지를 해석)
        → 워커의 Jupyter 포트
```

#### 왜 로컬 포트포워딩인가

`TcpTunnel`은 스트림 하나를 웹소켓에 잇는 구조라 VNC에는 맞지만 HTTP에는 안 맞는다 —
**페이지 한 장에 요청이 수십 개**고 브라우저가 동시에 연다. 요청마다 SSH 연결을 새로 열면
핸드셰이크만 수십 번이다. 그래서 `ssh -L`과 같은 구조를 만들어 SSH 연결 하나를 잡아 두고
채널만 요청마다 연다. **127.0.0.1에만 bind한다** — 0.0.0.0이면 같은 네트워크에서 남의 세션
포트에 인증 없이 닿는다.

포워딩은 세션당 하나를 캐시하고 5분 놀면 거둔다(브라우저 탭을 닫아도 Job은 살아 있다).

#### 판단 두 가지

**CSRF 검사를 이 경로에서만 뺀다.** Jupyter의 자바스크립트는 포털의 `X-CSRF-Token`을
모른다 — 노트북 저장·커널 생성이 전부 401이 된다. 빼도 되는 근거는 `SameSite=Strict`다:
다른 사이트에서 온 요청에는 액세스 쿠키가 **애초에 실리지 않는다**. double-submit은 그 위의
두 번째 겹이었다. 게다가 Jupyter가 자기 XSRF 검사와 토큰을 따로 갖고 있다.

**앱 토큰은 브라우저에 내보내지 않는다.** `connection.json`에만 두고 포털이 요청마다 헤더로
붙인다. 주소창에 실으면 접속 로그·리퍼러·북마크에 남는다(웹 터미널에서 쿼리스트링을 피한
것과 같은 이유). 라우터가 `SessionConnectInfo`로 추려 내보내므로 응답에도 안 실린다.

#### 실측 (2026-08-08, 실 클러스터)

세션 Job 80을 띄우고 포털 백엔드 안에서 관통시켰다:

```
프록시 대상 → local_port=34065  base_url=/api/v1/session-apps/80/  토큰 있음
  /api/status            -> 200  122B
  /lab                   -> 200  4926B   (HTML에 접두사 포함)
  /api/status (토큰 없이)  -> 403          ← 워커 포트가 스스로 막는다
```

앱 종류는 카탈로그의 `transport`가 정본이다(`vnc` / `http`) — **화면이 앱 id로 분기하지
않는다**. 앱을 늘릴 때마다 화면을 고쳐야 하기 때문이다. HTTP 앱은 새 탭으로 연다:
JupyterLab은 자기 단축키와 레이아웃을 통째로 쓰는 앱이라 포털 화면 안에 끼우면 서로 방해한다.

#### VS Code는 Remote-SSH로 간다 (U-IA-03)

code-server는 base path 지원이 없어 하위 경로 프록시가 불가능하다(§이전 기록). 카드에
**안내를 띄우고** "준비 중"이 아니라 "포털 밖에서 사용"으로 표시한다 — 기다려도 생기지
않는 것을 기다리게 두면 안 된다. 정의서 U-IA-03도 그에 맞게 고쳤다.

검증: 테스트 **384개 통과**(+3), 프론트 빌드 통과, 실 클러스터 관통 확인, 재배포.

#### 느렸던 이유 — 요청마다 DB + SSH를 다시 탔다

첫 배포는 **되긴 했지만 느렸다.** 로그가 원인을 그대로 보여줬다:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached
GET /api/v1/interactive-apps -> 500
```

프록시가 요청마다 DB 세션을 열고, `SessionProxyService.target()`이 **SSH로 접속해
connection.json을 다시 읽고 있었다.** JupyterLab은 한 페이지에 요청을 수십 개 동시에
던진다 — 커넥션 풀(5+10)이 마르면서 **프록시와 무관한 다른 API까지 500**이 났다.

실측한 비용:

```
해석 — 최초(DB+SSH): 828.9 ms
해석 — 캐시 적중   :   0.001 ms
터널 통과 요청     :    40.4 ms   ← 로그인 노드 경유의 고유 비용
```

**요청 하나당 829ms를 물고 있었다.** 페이지 한 장이 50요청이면 그게 전부 곱해진다.

고친 것:
- **해석 결과를 캐시한다**(`TARGETS`, 60초). 키에 **소유자를 넣는다** — 남의 캐시를 타지 못한다.
- **인증은 캐시와 무관하게 매 요청 확인한다** — JWT 서명 + Redis 세션 조회다. 캐시가
  건너뛰는 것은 "어디에 붙는가"이지 "누구인가"가 아니다. 로그아웃은 즉시 먹는다.
- httpx 클라이언트를 **하나 재사용한다**. 요청마다 만들면 루프백 연결도 매번 새로 맺는다.

남은 40ms는 SSH 터널의 고유 왕복 비용이라 구조를 바꾸지 않는 한 줄지 않는다.

#### 후속 — 모든 인터랙티브 앱을 새 탭으로 연다

JupyterLab만 새 탭이었고 데스크톱·ParaView는 SPA 안에서 열렸다. **셋 다 새 탭으로 통일했다.**

인터랙티브 앱은 화면 전체와 키보드를 통째로 쓴다 — 데스크톱·ParaView는 창 관리자와 단축키가
있고 JupyterLab도 자기 단축키 체계를 갖는다. 포털 레이아웃(사이드바·톱바) 안에 끼워 두면
화면도 좁고 단축키도 서로 먹는다. 세션을 여러 개 띄우고 오가기도 탭 쪽이 편하다.

어디로 보낼지는 카탈로그의 `transport`가 정한다(`vnc` → `/apps/{sid}`,
`http` → `/api/v1/session-apps/{job_id}/`) — **화면이 앱 id로 분기하지 않는다.**
인증은 둘 다 쿠키가 나르므로 같은 오리진의 새 탭에 그대로 실린다.

#### RUNNING과 "붙을 수 있다"는 같지 않다

세션을 만들고 바로 접속하면 `[VALIDATION_FAILED] 세션이 아직 준비 중입니다`가 떴다.
세션은 멀쩡했다 — Slurm이 RUNNING으로 바꾼 뒤 컨테이너가 Xvnc·MATE를 띄우고
`connection.json`을 쓰기까지 **10~20초가 더 걸린다**(실측: Job 85는 정상이었고 로그도
정상이었다). 그 사이를 오류로 던지니 사용자는 세션이 깨진 줄 알고 다시 만들게 된다.

**기다릴 일과 실패를 구분한다.** 서버가 `detail.reason = "starting"`을 붙이고,

- 원격 데스크톱 화면은 2초 간격으로 최대 80초까지 다시 물으며 "세션이 시작되는 중입니다…
  (n초)"를 보여준다. 다른 오류는 그대로 올린다 — 전부 재시도하면 진짜 실패가 묻힌다.
- HTTP 앱 프록시는 **스스로 새로고침하는 대기 페이지**(503)를 돌려준다. 새 탭에 오류
  문자열만 뜨면 사용자가 할 수 있는 일이 없다. 외부 자원을 참조하지 않는다 — 아직 붙지도
  못한 상태에서 CSS·폰트를 더 부르지 않는다.

#### 새 탭은 **화면만** 보여준다

새 탭으로 열긴 했는데 포털 껍데기(사이드바·톱바·카드)가 그대로 따라와서, 정작 데스크톱이
그 안의 작은 상자에 들어갔다. JupyterLab은 자기 탭을 꽉 채우는데 VNC만 그러지 못했다.

`route.meta.bare`를 더했다 — App.vue가 이미 로그인 화면용으로 갖고 있던 껍데기 제외
장치를 재사용한다. **인증과는 무관하다**: 라우터 가드는 `public`만 보고 `bare`는 그리는
방식만 정한다.

DesktopView도 화면 전용으로 다시 짰다. 카드·머리말을 없애고 VNC가 창을 통째로 쓰며,
조작 버튼은 화면 위에 띄우되 **마우스를 올릴 때만 진해진다**(35% → 100%). 이제 화면 안에
또 화면 껍데기를 그리지 않으므로 **최대화 버튼도 없앴다** — 탭 자체가 최대화다.

"닫기"는 `window.close()`다(목록에서 연 탭이라 먹는다). 주소를 직접 열어 안 닫히면
**전체 새로고침으로** 목록에 보낸다 — SPA 내부 이동으로 가면 이 라우트가 `bare`라
사이드바 없는 목록이 뜬다. 세션이 끝났을 때의 복귀도 같은 경로를 쓴다.

#### 화면 위 버튼을 줄였다

정상일 때 보이는 것은 **Ctrl+Alt+Del 하나**다. 끊겼을 때만 재연결이 나타난다.

- **연결 상태 배지 제거** — 재연결 버튼과 같은 말이다(끊겼을 때만 나타난다).
- **연결 끊기·닫기 제거** — 탭을 닫으면 되는 일이라 화면만 가렸다. 세션은 탭을 닫아도
  살아 있고 종료는 목록에서 한다(U-IA-04) — 여기 두면 "닫기"가 세션 종료로 오해된다.

**최대화 기능은 이미 남아 있지 않다**(화면 전용으로 다시 짤 때 사라졌다 — 탭 자체가
최대화라 의미가 없다). 코드·문서 전체 검색으로 확인했다.

#### 오버레이가 앱의 메뉴를 가로챘다

툴바를 `fixed top-0 inset-x-0`로 두었더니 **화면 폭 전체를 덮는 띠**가 되어, 그 높이의
클릭이 전부 오버레이로 갔다 — ParaView의 File·Edit 메뉴를 누를 수 없었다(실측).
앱의 메뉴·툴바는 하필 화면 맨 위에 있다.

**오버레이는 클릭을 가로채면 안 된다.**

- 바깥 컨테이너는 `pointer-events-none` — 표시용 글자(Job·상태)는 끝까지 투명하게 지나간다.
- **버튼만** `pointer-events-auto`로 이벤트를 받는다. 막는 넓이가 버튼 자기 크기뿐이다.
- 버튼을 **아래쪽 구석**으로 옮겼다. 메뉴·툴바가 있는 위쪽을 피한다.
- 끊긴 상태의 재연결 버튼은 진하게 둔다 — 그때는 화면이 죽어 있어 가려도 상관없다.

### 파티션을 펼치면 노드가 보인다 (U-CL-02)

파티션 행을 누르면 그 파티션의 노드 목록이 아래로 펼쳐진다.

**노드 정보는 관리자 API에만 있었다** — `/clusters/{cid}/nodes`는 `AdminUser` 전용이라
사용자 화면이 부를 수 없다. CPU 가용량을 붙일 때와 같은 방법을 썼다: 파티션 응답에
**필요한 필드만 추려** 싣는다(`node_list`).

관리자 응답을 그대로 흘리지 않는다 — `reason`(운영자가 적는 drain 사유) 같은 운영 정보가
섞여 있다. 담는 것은 이름·상태·CPU(사용/전체)·메모리(사용/전체)·GRES뿐이고, 테스트가
`reason`이 새지 않는지 확인한다. 노드 조회 자체는 이미 하고 있어서 **호출은 늘지 않았다**.

화면 쪽:
- 요약 행과 펼친 노드 행이 한 파티션이라 `<template v-for>`로 묶는다 — 따로 두면 두 번째
  행에서 `v-for` 변수를 못 쓴다.
- 노드 표는 파티션 표와 컬럼 폭이 달라 **한 칸(colspan)을 통째로 쓰고** 그 안에 따로 그린다.
  같은 표에 억지로 맞추면 두 표가 서로의 폭을 흔든다.
- **한 번에 하나만 펼친다.** 여러 개를 열면 표가 길어져 정작 파티션 비교가 안 된다 —
  이 화면의 목적은 "어느 파티션에 자리가 있나"다.
- 행 클릭은 마우스 편의이고, 파티션 이름은 `<button>`이라 키보드로도 펼쳐진다.

실 클러스터 확인: `cpu` 파티션 → `slurm01 · IDLE · CPU 0/2 · 메모리 3915MB · GRES 없음`.

검증: 테스트 **387개 통과**(+1), 프론트 빌드 통과, 재배포.

#### CPU만 있던 자리에 메모리·GPU를 함께 (U-CL-02)

파티션 요약이 CPU만 보여줬다. **세 자원을 한 번에 센다** — 따로 돌면 offline 판정 같은
규칙이 갈릴 수 있어 `_usage_by_partition()` 하나로 합쳤다.

읽는 곳(실측한 노드 필드):

```
CPU    : cpus / alloc_cpus
메모리 : real_memory / alloc_memory        (MB)
GPU    : gres / gres_used                  ← 문자열이라 파서가 필요하다
```

`gres`는 `gpu:a100:2`, `gres_used`는 `gpu:a100:1(IDX:0)`처럼 온다. 같은 형식이라 하나로
읽고 `(IDX:...)`만 떼어낸다. `mps:100`처럼 GPU가 아닌 GRES는 세지 않는다.

화면은 **자원마다 칸 하나**를 쓰고 `사용/가용/전체`를 한 줄에 적는다. 셋을 각각 세 칸으로
벌리면 아홉 칸이 되어 정작 파티션 비교가 안 된다. **가용을 굵게** 해서 "지금 자리가 있나"가
먼저 읽히게 했다(`ResourceUsage` 컴포넌트). 메모리 표기는 노드 목록과 같은 함수를 쓴다 —
같은 값이 두 곳에서 다르게 보이면 안 된다.

실 클러스터: `cpu` 파티션 → CPU 0/2/2 · 메모리 0/3915/3915MB · GPU 0/0/0.

#### 노드를 파티션과 같은 컬럼에 그린다

펼친 노드를 별도 표로 그렸더니 열이 어긋나 같은 값을 위아래로 비교할 수 없었다 —
펼치는 이유가 그 비교인데. 노드를 **같은 표의 행**으로 바꿨다.

그러려면 노드도 파티션과 **같은 모양의 수치**를 가져야 한다. 계산 규칙이 두 곳에 있으면
파티션 합계와 노드 숫자가 어긋나므로 `_node_amounts()`·`_triple()`로 한 곳에 모으고,
집계와 노드 행이 그것을 **같이 쓴다**. 실 클러스터에서 합계와 노드가 일치하는 것을 확인했다:

```
파티션 합계 : cpu (0,2,2)  memory (0,3915,3915)  gpu (0,0,0)
노드 slurm01: cpu (0,2,2)  memory (0,3915,3915)  gpu (0,0,0)
```

노드 행은 이름 앞에 `└`를 두고 배경을 깔아 요약과 구분한다. GRES 문자열은 이름 옆에
작게 붙인다 — 컬럼을 하나 더 만들 만큼 자주 보는 값이 아니다.

### Helm 차트 (deploy/helm/hpc-portal)

`deploy/k8s/`의 매니페스트를 차트로 옮겼다. **동작은 그대로**이고 손으로 치던 Secret 생성
절차만 차트가 흡수했다. 그 흡수가 이 작업의 위험한 부분 전부다.

#### 렌더해 보고 잡은 설치 실패 버그

첫 판은 lint를 통과하고도 **첫 설치부터 깨졌을 것이다**:

```
PORTAL_DATABASE_URL: "mysql+pymysql://portal:@hpc-portal-mysql:3306/..."   ← 비밀번호가 비었다
```

`randAlphaNum`은 부를 때마다 다른 값을 준다. MySQL Secret과 백엔드의 DATABASE_URL이 각자
부르니 서로 다른 비밀번호를 갖게 됐다(신규 설치라 `lookup`은 빈 값이다). `.Values`가 모든
템플릿이 공유하는 같은 map이라는 점을 이용해 **한 렌더 안에서 한 번만 정하도록**
메모이즈했다(`hpc-portal.credential`).

#### 지켜야 하는 것 둘

1. **비밀번호를 업그레이드마다 새로 만들면 안 된다.** MySQL 볼륨에 옛 비밀번호가 남아 있어
   파드가 뜨지 못한다. `lookup`으로 기존 Secret을 먼저 읽는다.
2. **`portal-backend-env`에는 차트가 모르는 키가 있다.** `PORTAL_SECRET_CLUSTER_13_SLURM_JWT`
   같은 클러스터 자격증명은 운영 중에 손으로 넣는다 — `EnvSecretStore.put()`이 프로세스
   안에만 두고 영속화는 배포 수단의 몫이기 때문이다. 기존 키를 통째로 물려받고 차트가 아는
   키만 덮어쓴다. **이 병합이 없으면 `helm upgrade` 한 번에 모든 클러스터 연결이 끊긴다.**

라이브 네임스페이스에 서버 dry-run을 돌려 그 7개 키가 렌더 결과에 남는 것을 확인했다.

#### 차트가 만들지 않는 것

- **TLS Secret** — 개인키가 values에 남으면 안 된다. 이름만 받는다(certbot 훅이 갱신).
- **StorageClass·Traefik HelmChartConfig** — 클러스터 전역이라 기본이 꺼져 있다. 여러
  릴리스가 공유하므로 처음 한 번만 켠다.

#### 인수는 아직 하지 않았다

`deploy/k8s/`로 올린 리소스에는 Helm 소유권 표시가 없어 그대로는 못 가져온다(dry-run이
`invalid ownership metadata`로 막았다 — 이것도 확인했다). Helm 4의 `--take-ownership`과
`fullnameOverride=portal`로 이름을 맞추면 되지만, **MySQL StatefulSet은 selector를 바꿀 수
없어 삭제·재생성이 필요하다**(`app: mysql` → `app.kubernetes.io/*`). 살아 있는 배포를
건드리는 일이라 절차만 README에 적고 실행하지 않았다.

검증: `helm lint` 통과, `helm template` 렌더 확인, 실 클러스터 서버 dry-run 통과.

---

## 2026-08-09 — 앱 사용 허용: 배정된 계정에 속한 사용자만 앱을 쓴다 (U-IA-01 · U-JB-13, A-US-02)

요청: "인터랙티브앱이나 Batch앱이 선택된 slurm의 account에 속해 있는 AD사용자만 보여서
사용이 가능하도록 개선할 수 있을까?"

### 없던 것은 하나였다

"이 사용자가 어느 계정에 속하나"는 이미 있었다 — `JobService.options()`의 `accounts()`가
`/associations`를 본인 것만 걸러 돌려주고, **두 앱 화면이 그 목록을 이미 받아 놓고 있었다.**
없던 것은 **앱 → 허용 계정 매핑**뿐이라 새 조회를 만들 필요가 없었다.

그 소속 파싱은 이제 `services/app_access.py:user_accounts()` 한 곳에 있다. 앱 허용 판정과
제출 폼 선택지가 **같은 소속을 봐야** 하는데, 둘이 따로 풀면 화면에는 보이는데 제출은
거부되는 상태가 생긴다.

### 배정이 없으면 전원 허용

`app_access`는 **허용 목록이고 행이 없으면 열려 있다**(마이그레이션 0014). 기본을 잠김으로
두면 표를 만든 순간 모든 앱이 멈추고, 앱을 새로 넣을 때마다 배정이 따라와야 한다. 그래서
0014는 **동작을 바꾸지 않는다** — 배정하기 전까지 지금과 같다.

배정이 하나도 없으면 slurmdbd를 **부르지도 않는다**(소속을 볼 이유가 없다). 기능을 안 쓰는
동안은 비용이 0이다.

### 목록에서 잠그는 것으로는 제한이 되지 않는다

두 가지를 모두 해야 실제 제한이 된다:

1. **제출에서 막는다** — `AppAccessService.resolve_account()`가 세션 생성과 Batch 제출
   양쪽에서 소속을 확인한다. 화면을 거치지 않는 호출이 있다.
2. **그 계정으로 돌린다** — 계정을 안 골랐으면 서버가 채운다. 두 앱 화면은 그동안
   account를 **아예 보내지 않았고**(폼에 칸이 없었다) Job은 Slurm 기본 계정으로 돌았다.
   이걸 안 고치면 "OpenFOAM은 cfd 계정만"이라고 걸러 놓고 정작 과금은 엉뚱한 계정에 붙는다
   — 제한이 이름뿐이 된다. 두 화면에 계정 칸을 넣고, 배정된 앱이면 **그 계정으로 선택지를
   좁힌다**(고를 수 없는 값을 보여주면 제출에서 거부당하고 이유는 화면에 없다).

### 목록 엔드포인트가 클러스터에 매였다

계정은 클러스터별 slurmdbd 소유라 `/interactive-apps`·`/batch-apps`를
`/clusters/{cid}/…` 아래로 옮겼다. **깨지는 변경**이지만 클러스터 없이는 판정할 수 없다.
프론트는 이미 클러스터를 고른 상태라 화면 변경은 없었다.

### 잠긴 앱은 숨기지 않는다

`ready=false`(포털이 아직 제공하지 않음)와 같은 방식으로 **보이되 잠근다**. 숨기면
사용자는 그 앱의 존재를 모른 채 "안 보인다"고 묻게 된다 — 카드에 어느 계정이 필요한지와
관리자에게 요청하라는 말을 적는다.

### 소속 조회가 실패하면 잠근다

slurmdbd가 안 되면 소속을 알 수 없다. 그때 열어 주면 배정이 무의미하므로 **잠근 채로**
둔다. 다만 목록 전체를 실패시키지는 않는다(화면이 통째로 비면 이유를 알 수 없다) —
배정이 없는 앱은 그대로 열려 있다.

### 포털 밖은 막지 못한다

여기서 거르는 것은 **화면에서 고를 수 있는 것**이다. 웹 터미널·SSH로 직접 `sbatch`를
치는 것은 포털의 범위가 아니다. 진짜 강제는 Slurm 쪽(파티션 `AllowAccounts`, A-US-05)이
맡는다. 관리 화면 각주에 그렇게 적었다.

### 관리

계정 관리 화면(SCR-13)에 "앱 사용 허용" 카드를 붙였다. 배정 대상이 계정이라 이 화면에
둔다. QOS 배정과 **같은 규칙**이다 — 칩을 눌러 고르고 저장하면 덮어쓴다. 비우면 그 앱이
다시 전원에게 열리므로, 빈 값을 `—`가 아니라 **"전원 허용"**이라고 적는다(`—`는
"아무도 못 쓴다"로 읽힌다). 변경은 감사 로그(`APP_ACCESS_SET`)에 남는다.

검증: 테스트 **399개 통과**(+12, `tests/test_app_access.py`), 프론트 빌드 통과.
배포는 하지 않았다.

### 배포 중 발견 — `/data` 디스크 이관이 절반만 끝나 있었다 (2026-08-09)

앱 사용 허용을 배포하려는데 `CREATE TABLE app_access`가 실패했다:

```
(1030, "Got error 168 - 'Unknown (generic) error from engine' from storage engine")
```

**마이그레이션 문제가 아니었다.** MySQL이 새 파일을 만들 수 없는 상태였고, 이 표가
그걸 처음으로 건드렸을 뿐이다.

#### 원인

8월 8일 15:26에 `/data` 확장을 위해 새 디스크(`disk01-data`)를 `/data`에 마운트했다.
그런데 **k3s의 data-dir가 `/data/k3s`다**(`--data-dir=/data/k3s`). 그 전까지
`/data/k3s`는 루트 디스크(vda4) 위의 디렉터리였다.

새 디스크를 그 위에 덮어 마운트하자, **그 전부터 돌던 파드들의 볼륨이 가려진 옛
디렉터리를 계속 붙들었다.** 마운트 정보가 그대로 말해 준다:

```
mysqld의 /var/lib/mysql  →  252:4 (/dev/vda4)  …/pvc-eab9372f…//deleted
호스트의 /data           →  253:0 (/dev/mapper/disk01-data)
```

`//deleted` — 컨테이너 안 `/var/lib/mysql`은 비어 있었고, mysqld는 **열어 둔 파일
디스크립터 45개만으로** 메모리에서 돌고 있었다. 그래서 읽기는 되는데 새 파일은
못 만들었다(`mkdir returned OS error 71`). redo 로그 열기 실패가 8월 9일 10:03부터
초당 한 번씩 쌓여 있었다.

파일 복사 자체는 성공했고 데이터도 멀쩡했다 — **빠진 것은 파드 재시작 하나뿐이었다.**

#### 왜 위험했나

새 디스크의 사본은 복사 시점(8월 8일 14:44)에 멈춰 있는데 포털은 그 뒤로도 계속 썼다.
살아 있는 데이터는 **삭제된 inode에만** 있어서, 파드가 어떤 이유로든 죽으면 그대로
사라진다. 실측한 차이:

| | 디스크 사본 | 실제 | 차이 |
|---|---|---|---|
| `audit_log` | 445 | 608 | **163** |
| `interactive_session` | 49 | 73 | **24** |

#### 복구 순서

1. **먼저 논리 백업.** 파일시스템을 못 믿으므로 네트워크로 붙어 `mysqldump`
   (`/home/jrpark/portal-db-rescue-20260809.sql`, NFS라 노드와 무관하게 남는다).
   컨테이너가 이미 좀비라 `kubectl exec`로는 `mysqldump`는커녕 `ls`도 없었다 —
   파드 IP로 직접 붙었다.
2. 디스크 사본을 `_backup-20260809`으로 한 벌 더 복사(212M).
3. `mysql-0` 재시작 → 새 디스크로 정상 기동(crash recovery 통과).
4. 덤프 복원 → `audit_log 445→608`, `interactive_session 49→73`으로 원상 복구.
5. `redis`도 같은 상태라 재시작(세션·캐시라 손실 무의미).

#### 복원이 마이그레이션을 되돌렸다

MySQL이 쓰기 가능해지자 백엔드 initContainer가 **스스로** 0014를 적용했다. 그런데 그
직후에 덤프를 복원해서 `alembic_version`이 **0013으로 되돌아갔다** — 덤프는 0014 이전에
뜬 것이다. `app_access` 표는 덤프에 없어서 살아남았고, 표는 있는데 버전은 0013인
어긋난 상태가 됐다. `alembic stamp 0014`로 맞췄다.

**순서가 반대였으면 좋았다** — 복원을 먼저 끝내고 백엔드를 롤아웃했어야 한다.
DB를 복원할 때는 마이그레이션이 도는 파드를 먼저 세운다.

#### 남는 것

- `/data/k3s/storage/pvc-eab9372f…_backup-20260809` (212M) — 사본. 확인 뒤 지우면 된다.
- `/home/jrpark/portal-db-rescue-20260809.sql` — 복구에 쓴 덤프.
- **교훈: `/data`처럼 k3s data-dir를 품은 경로를 다시 마운트하면 그 전부터 돌던 파드는
  전부 재시작해야 한다.** 마운트 시점에는 아무 증상이 없어 며칠 뒤에야 드러난다.

검증: `alembic current` = **0014 (head)**, `curl` 배포 확인 200/401 정상,
`docker builder prune -af` 완료.

---

### 앱 관리를 별도 화면으로 분리 (A-OP-02, SCR-22)

포털 운영 설정(SCR-15) 안의 카드였던 앱 관리를 **포탈 설정 콘솔의 독립 메뉴**로 뺐다.
추가·수정은 **모달**로 바꿨다.

#### 왜 뺐나

SCR-15가 성격이 다른 넷을 담고 있었다 — 세션·알림 정책, 공지, **앱 관리**, 감사 로그.
그중 앱 관리만 **폼이 크고(9개 필드) 목록이 길다.** 한 화면에 인라인 폼으로 두니
설정을 보러 왔다가 앱 폼을 지나쳐야 했고, 반대로 앱을 고치러 오면 다른 카드가 방해했다.

#### 인라인 폼 → 모달

기존 폼은 **목록 위에 항상 펼쳐져** 있었다. 문제는 "지금 무엇을 편집 중인가"가
`editingApp` 상태로만 드러나서, 목록에서 `수정`을 누르면 화면 위쪽 폼이 조용히 바뀌었다 —
**스크롤이 아래에 있으면 아무 일도 안 일어난 것처럼 보인다.**

모달은 그 문제가 없다. 제목이 `앱 수정 — JupyterLab`으로 대상을 말하고, 연결 키
(종류·앱 ID)는 수정 시 잠기며 **왜 잠기는지 힌트에 적었다**("연결 키라 수정할 수 없습니다").

추가와 수정이 **같은 모달**을 쓴다. 다른 점은 연결 키를 잠그는지 뿐이라 화면을 둘로
나눌 이유가 없다.

#### 바뀌지 않은 것

엔드포인트(`GET/POST/PATCH/DELETE /apps`, 아이콘 업로드)는 그대로다. 화면만 옮겼다.
**실행 방식은 여전히 코드 카탈로그가 정본**이고(`session_apps.py`·`batch_apps.py`),
이 화면은 아이콘·벤더·버전·이미지 위치 같은 **정보**만 다룬다 — 카드 하단에 그 사실을
다시 적었다.

검증: 프론트 빌드 통과. 백엔드 무변경.

---

### 감사 로그도 별도 화면으로 (A-OP-03, SCR-23)

앱 관리에 이어 감사 로그도 포탈 설정 콘솔의 독립 메뉴로 뺐다. SCR-15에는 이제
**세션·알림 정책과 공지** 둘만 남는다.

감사 로그는 **성격이 특히 달랐다.** 나머지 카드는 "설정을 바꾸러" 오는 곳인데 이것은
**"무슨 일이 있었는지 찾으러"** 오는 곳이다. 614건이 쌓여 있고 페이지네이션·필터가
붙는데, 설정 화면 맨 아래에 있으면 매번 스크롤해서 내려가야 했다.

옮기면서 두 가지를 고쳤다.

- **`w-full`/`w-auto` 충돌.** 필터 입력이 `inputClass`(안에 `w-full`)에 `w-auto`를
  덧붙이고 있었다. 둘 다 남아 **CSS 생성 순서가 이기는 쪽을 정한다** — 클래스 순서로는
  못 이긴다. 공통 부분만 뽑고 폭은 각자 명시하도록 바꿨다(이 프로젝트에서 세 번째로
  만난 같은 함정이다).
- **필터 초기화 버튼.** 필터를 걸어 둔 채 잊고 "왜 로그가 없지?"가 되는 일이 잦다.
  걸려 있을 때만 버튼이 나타난다.

처음에는 카드 하단에 "포털을 거치지 않은 행위는 남지 않는다"는 주의를 적었다가 **뺐다.**
감사 로그의 범위는 **포털의 행적**이고 그 밖은 애초에 대상이 아니다 — 당연한 것을 화면에
적으면 읽을 것만 늘고, 오히려 이 기능이 무언가 부족한 것처럼 보인다.

검증: 프론트 빌드 통과(타입체크가 남은 참조 3개를 잡아 줬다). 백엔드 무변경.

---

### 정합성 검토 후속 — 문서 현행화 + 검증 공백 6건 처리

전체 검토에서 나온 6건을 모두 고쳤다.

#### ① WS 인증 서술이 코드와 반대였다 (보안 서술 오류)

`api.md`·`plan.md`·`exec-plan.md`가 **"WS 인증은 subprotocol `portal.token.<jwt>`"**로
적혀 있었다. 2026-08-08에 **쿠키로 바꿨는데** 공통 규약 한 줄만 고치고 개별 행·미결
항목·계획 문서는 그대로였다. 문서만 보고 클라이언트를 만들면 **동작하지 않는 방식**을
구현한다. 네 곳을 모두 고치고, subprotocol이 **기계 클라이언트용으로만 남았다**는 사실을
명시했다.

#### ② `proxy_ws`가 자기 파일이 금지한 패턴을 쓰고 있었다

`session_apps.py` 머리말은 "설정은 주입받는다 — `get_settings()`를 직접 부르면 import
시점에 이름이 묶여 **테스트가 갈아끼운 설정이 안 먹는다**"고 적어 두고, **정작 `proxy_ws`가
그것을 했다.** HTTP 쪽만 주입받고 WS만 어긋나 있었다.

운영에서는 문제가 없지만 **테스트로 덮을 수 없다.** 실제로 프록시 테스트가 HTTP(401/404)만
있고 **WS 경로는 하나도 없었다** — Jupyter 커널이 웹소켓으로 오가므로 "노트북은 열리는데
실행이 안 되는" 회귀를 아무도 못 잡는 상태였다.

주입으로 바꾸고 WS 테스트 3개를 넣었다. **종료 코드로 검사한다** — 처음에는
`pytest.raises(Exception)`으로 썼다가 고쳤다. 그러면 아무 이유로 실패해도 통과해서
**테스트가 있다는 착각만 준다.** 4401(인증 없음)과 4400(대상 없음)을 구분해야
"인증은 지났다"가 확인된다.

#### ③ 세션 프록시가 api.md에 아예 없었다

`/session-apps/{job_id}/{path}`의 HTTP·WS 두 경로 모두 누락이었다. JupyterLab을 실제로
여는 핵심 경로인데 API 문서에 존재하지 않았다. 추가하면서 **CSRF를 빼는 근거**와
**앱 토큰을 주소창에 싣지 않는 이유**도 함께 적었다.

#### ④ 수치 현행화

`api.md` 머리말 83개 → **99개**(그 뒤 앱 카탈로그·앱 접근·세션 프록시가 늘었다),
`CLAUDE.md` 테스트 399개 → **411개**.

#### ⑤ ERD 설명 표 2행 누락 · `UsageView` 클래스 충돌

`permission`·`role_permission`이 엔티티 그림에는 있는데 설명 표에 없었다(22개 중 20개).
`UsageView`의 `[inputClass, 'w-auto']`는 이 프로젝트에서 **네 번째로 만난 같은 함정**이다.

#### ⑥ `inputClass` 14곳 중복 — 그리고 **두 갈래로 갈라져 있었다**

단순 중복이 아니었다. 8곳은 `border-line-dark`, 6곳은 `border-line`을 쓰고 있어
**같은 입력이 화면마다 다르게 보였다.** 입력 경계는 카드 구분선(`line`)보다 진해야
눈에 잡히므로 `line-dark`(다수·최신 화면)로 통일했다.

`utils/form.ts`로 뺐고, **`inputBase`에는 폭을 넣지 않았다** — 폭이 필요한 곳이 각자
붙이면 `w-full`/`w-auto` 충돌이 구조적으로 생기지 않는다. `BillingView`의
`.replace('w-full','w-auto')` 우회도 이걸로 정리했다.

**보이는 변화**: `border-line`을 쓰던 6개 화면(사용량·인터랙티브 앱·QOS·계정·운영 설정·
비용)의 입력 테두리가 아주 조금 진해진다.

검증: 테스트 **411개 통과**(3개 추가). 비어 있지 않음 확인 — 설정 주입을 되돌리자
WS 테스트가 실패했다. 프론트 빌드 통과, `inputClass` 중복 정의 **0**, `w-auto` 덧붙이기 **0**.

---

### T-01·T-02 이미지 위치를 클러스터의 `home_base`에서 파생 (`.portal` 이동)

계획: [plan.md](plan.md) · [exec-plan.md](exec-plan.md)

이미지가 있는 곳이 포털 설정 하나(`settings.app_image_dir`)였다. 그게 성립한 이유는
dev01·slurm01·slurm02가 **같은 NFS export**(`198.19.64.8:/scp_users_tl8g1s`)를 마운트하고
있어서다 — 구조가 아니라 그때의 사실이었다. **향후 클러스터마다 다른 NFS를 쓴다**(사용자
확인)라서 가정이 깨진다.

**새 컬럼을 만들지 않았다.** 클러스터별 공유 경로가 이미 있다 — `cluster.home_base`
(SCR-18 "홈 상위 경로"). 여기서 파생하면 설정이 늘지 않고, 무엇보다 **공유되지 않는
경로가 들어갈 여지가 없다**: `home_base`는 파일 관리자가 매일 쓰는 값이라 "모든 노드가
보는 경로"임이 계속 검증된다. 따로 칸을 만들면 로컬 경로를 적어 넣을 수 있다.

```
home_base 있음   →  {home_base}/.portal/images
home_base 비었음 →  settings.app_image_dir      (폴백, /home/.portal/images)
```

폴백이 필요한 이유는 `home_base`가 선택 입력이라서다 — 비우면 `getent passwd`로
**사용자별** 홈을 찾는 모드라 공용 자리가 정해지지 않는다.

`resolve()`에 클러스터를 넘기는 변경은 호출부가 둘뿐이었고 **둘 다 이미 클러스터를 들고
있었다.** `session.py`의 `image_ref(self, cluster, app)`는 받아 놓고 안 쓰고 있었다 —
이음매가 미리 나 있던 셈이다.

**`/home/portal` → `/home/.portal`로 옮겼다.** `{home_base}` 아래는 사용자명이 오는
자리라 `portal`은 유효한 사용자명이다. AD에 그 계정이 생기면 홈 프로비저닝이 이미지
저장소 위로 떨어진다. 앞에 점이 붙으면 POSIX/AD 사용자명이 될 수 없어 충돌이 구조적으로
불가능해진다. 같은 파일시스템 안 `mv`라 8.9GB는 움직이지 않았고 inode가 유지되어 돌고
있는 세션의 mmap도 끊기지 않는다. 사용자 홈에 이미 `.portal/logs`를 쓰고 있어 이름도
일관된다.

아이콘도 같은 자리에 있어 함께 옮겼다 — 같은 이유로 같은 위험을 지고 있었다.
hostPath·mountPath·`app_icon_dir`을 모두 `.portal`로 맞췄다. `type: Directory`라 경로가
어긋나면 파드가 안 뜨므로 **이동과 롤아웃을 한 번에** 했다.

마이그레이션 없음(기존 컬럼에서 파생).

검증: 테스트 **413개 통과**(2개 순증). 비어 있지 않음 확인 — 파생 분기를 빼자 3개가
실패했다. 배포 후 파드에서 `IMAGE_SUBDIR=.portal/images`, 폴백 `/home/.portal/images`,
`home_base=/nfs/home` → `/nfs/home/.portal/images` 확인. 마운트가 NFS의 `.portal` 아래로
바뀌었고 SIF 8개가 그대로 보인다. `front: 200`, `/api/v1/app-images: 401`.

**남은 것**: 관리자 화면의 이미지 목록(`GET /app-images`)은 아직 **파드의 파일시스템**을
읽는다. 클러스터별 경로가 되면 성립하지 않는다 — T-03에서 로그인 노드 SSH로 옮긴다.

---

### T-03·T-04 이미지 목록을 파드가 아니라 클러스터에 묻는다

`GET /app-images`는 **백엔드 파드의 파일시스템**을 읽었다. 그게 맞아떨어진 이유는 dev01이
클러스터와 같은 NFS를 마운트하고 있어서고, 경로가 클러스터마다 갈리면 성립하지 않는다 —
**파드 마운트는 Deployment에 정적으로 박혀 있어 클러스터를 등록해도 생기지 않는다.**

`GET /clusters/{cid}/app-images`로 옮기고 로그인 노드 SSH `ls`로 읽는다. 파일 관리자가
이미 쓰는 경로라 새 인프라가 아니다. Redis 60초 캐시를 뒀다 — 앱 목록을 그릴 때마다
물으면 화면 한 번에 SSH가 여러 번 열린다. **빈 목록도 캐시한다**(디렉터리가 없는
클러스터에 매번 SSH를 여는 것이 제일 아깝다).

부수 효과로 **파드의 `app-images` hostPath 마운트를 지웠다.** 파드가 더는 안 읽는다.

관리 화면의 선택기는 **전 클러스터 합집합**을 보여준다. 이 화면은 포탈 스코프라 클러스터
선택기가 없고, 선택기의 목적은 *유효한 파일명을 고르게 돕는 것*이다. 어느 클러스터에
실제로 있는지는 T-06이 사용자 화면에서 `installed`로 답한다.

#### 좁은 except가 실 클러스터에서 새어 나갔다

`except (PortalError, OSError)`로 뒀는데 **paramiko는 `SSHException`을 그대로 던지고 그건
둘 다 아니다.** 테스트는 `ExternalServiceError`(=PortalError)로만 확인해서 통과하고 있었다 —
**맞는 것을 확인하지 않는 테스트**였다. 실 클러스터에 붙여 보고서야 드러났다.

이 메서드의 계약이 "무슨 일이 있어도 목록을 돌려준다"이므로 경계는 예외 종류가 아니라
호출 자체다. `except Exception` + 경고 로그로 바꾸고, 테스트를 세 종류(PortalError,
paramiko, 예상 못 한 것)로 파라미터화했다.

#### 운영 주의

목록은 **요청한 관리자 본인으로** SSH 임퍼소네이션한다(포털의 구조 규칙). 그래서 그 관리자가
**해당 로그인 노드에 프로비저닝되어 있지 않으면 목록이 빈 채로 뜬다.** 실측에서 `ubuntu`로는
SIF 8개가 나오고, 없는 사용자로는 `[]` + 경고 로그가 남았다(500 아님).

검증: 테스트 **422개 통과**(9개 추가). 좁은 except로 되돌리면 3개가 실패한다. 실 클러스터
두 대에 붙여 목록을 실제로 읽었다 — cluster 13(`home_base=/home`)과 14(`home_base=None`,
폴백) 모두 `/home/.portal/images`에서 SIF 8개. 파드 마운트에 `app-images`가 없고
`/api/v1/app-images`는 **404**, `/api/v1/clusters/13/app-images`는 401.

**지운 엔드포인트에는 테스트가 하나도 없었다** — 지워도 아무것도 깨지지 않았다. 새 것은 9개다.

---

### T-05 클러스터 등록 시 이미지 디렉터리 확인

`GET /clusters/{cid}/image-dir` — `{path, ok, images, message}`. 등록·수정 직후 화면이
부르고, 문제가 있으면 **경고 배너**(초록도 빨강도 아닌 `warn` 토큰)로 알린다.

**등록을 막지 않는다.** 순서를 강요하면 클러스터를 먼저 등록할 수 없다 — 디렉터리는
클러스터 쪽 작업이고 등록은 포털 쪽 작업이다. `ok=false`도 200이다.

**포털은 디렉터리를 만들지 않는다.** `{home_base}`는 root 소유라 만들려면 권한 상승이
필요하고, 그건 "허용 루트는 홈뿐"이라는 경계를 깨는 첫 사례가 된다. 게다가 만들어 줘도
SIF는 여전히 손으로 넣어야 하고, 변환 잡(T-08)이 쓰려면 그룹 쓰기 권한까지 필요해서
`mkdir` 한 번으로 끝나지도 않는다. 그래서 **무엇을 해야 하는지 말하는 쪽**을 골랐다.

실패를 두 갈래로 가른다 — **할 일이 다르기 때문**이다:

| 상황 | 문구 |
|---|---|
| 디렉터리 없음 | `이미지 디렉터리가 없습니다: {경로} — 클러스터에서 만들고 관리자 그룹에 쓰기 권한을 주세요.` |
| 로그인 노드 못 붙음 | `이미지 디렉터리를 확인할 수 없습니다: {경로} — 로그인 노드 접속과 '{계정}' 계정을 확인하세요.` |

목록(`available`)은 캐시를 쓰지만 **진단(`check`)은 안 쓴다.** 고친 뒤 다시 눌렀는데
옛 답이 나오면 진단이 아니다.

검증: 테스트 **426개 통과**(4개 추가). 실 클러스터에서 **세 갈래 모두** 확인했다 —
정상(`ok=True, images=8`), 없는 경로(`/home/nowhere.../.portal/images`로 "없습니다"),
못 붙는 계정("확인할 수 없습니다"). 문구가 상황마다 다르게 나온다.

문서: `api.md` 엔드포인트 수 99 → **100**(문서 자신의 카운트 명령 기준), CLAUDE.md
테스트 수 411 → **426**.

---

### T-06 잠금 셋 — `ready` · `installed` · `allowed`

앱이 열려 있는지를 **코드 상수**(`ready`)가 정하고 있었다. SIF를 만들어 올려도
`batch_apps.py`를 고쳐 재배포해야 앱이 열렸다 — **파일이 있는지는 파일이 안다.**

목록 응답에 `installed`를 더해 셋으로 갈랐다. 셋은 서로 다른 질문이고, 무엇보다
**사용자가 할 수 있는 일이 다르다**:

| 잠금 | 질문 | 누가 답하나 | 사용자가 할 일 |
|---|---|---|---|
| `ready` | 실행 방식(커맨드·파라미터)이 확정됐나 | 코드 | 기다린다 |
| `installed` | 이 클러스터에 SIF가 있나 | 클러스터 | 관리자에게 설치 요청 |
| `allowed` | 내가 쓸 수 있나 | 계정 배정 | 관리자에게 계정 연결 요청 |

`ready`를 없애지 않고 **의미를 좁혔다.** Isaac Sim이 좋은 예다 — `ready=False`인 이유가
둘이었는데(이미지 없음 + 커맨드가 실측이 아님) 앞의 것은 `installed`로 옮겨 갔다.
이미지가 생겨도 `ready=False`가 맞다.

**숨기지 않고 잠근다.** 숨기면 A 클러스터에서 쓰던 앱이 B에서 사라졌을 때 물을 데가 없다.
카드에 "이 클러스터에 컨테이너 이미지가 없습니다 — 다른 클러스터에서는 쓸 수 있을 수
있습니다"라고 적는다.

제출 경로도 막는다(`resolve_installed`). 목록에서 잠그는 것만으로는 제한이 아니다 —
화면을 거치지 않는 호출이 있고, 무엇보다 여기서 안 막으면 Job이 워커까지 가서 죽고
사용자 화면에는 "FAILED"만 남는다. 문구에 **파일명을 넣었다**(무엇을 넣어야 하는지).

#### 실패는 캐시하지 않는다

캐시 키가 클러스터라 **여러 사용자가 나눠 쓴다.** 로그인 노드에 프로비저닝되지 않은
사용자 하나가 목록을 불러 실패가 캐시되면, 그 60초 동안 **모두의 앱이 잠긴다.**
성공만 캐시한다 — 빈 디렉터리는 사실이지만 실패는 사실이 아니다.

#### `SessionService.image_ref` 제거

제출 경로가 `AppImageService.resolve_installed`로 옮겨 가면서 쓰는 곳이 없어졌다.
남겨 두면 "이미지를 구하는 길이 둘"이 되고 그중 하나만 존재 확인을 한다.

검증: 테스트 **432개 통과**(6개 추가). 존재 검사를 무력화하면 제출 차단 테스트가 실패한다.
실 클러스터(13번)에서 `installed_map` 실측:

```
interactive  desktop/paraview  rocky9-mate-1.5.sif   True
             jupyter           rocky9-mate-1.6.sif   True
             code-server       (없음)                 False
batch        openfoam          openfoam-2512.sif     True
             isaac-sim         isaac-sim-5.1.0.sif   False
```

**Isaac Sim이 `installed=False`로 정확히 나온다** — 이제 SIF를 넣기만 하면 코드 배포
없이(최대 60초 뒤) 열린다. 그것이 이 Task의 목적이다.

**대가**: 앱 목록마다 SSH가 붙는다(클러스터당 60초 캐시). 그리고 SIF를 넣은 뒤 최대
1분 늦게 열린다 — 테스트가 그 사실을 캐시 키를 지워서 명시한다.

---

### T-07 `app_catalog.image_ref` — 이미지의 출처를 DB에

`image_file`은 **무엇을 실행하는지**(`openfoam-2512.sif`)만 말하고 **어디서 왔는지는 말하지
않는다.** 그 출처는 `progress.md` 본문에만 있었다 — 버전을 올리거나 다른 클러스터에 같은
이미지를 만들려면 문서를 뒤져야 했다.

마이그레이션 `0018`, nullable `VARCHAR(255)`. 값은 `docker://opencfd/openfoam-default:2512`.

**스킴을 요구한다.** apptainer가 출처 종류를 그것으로 판정하고(`docker://`·`oras://`·
`docker-daemon://`), 요구하지 않으면 **로컬 경로를 붙여 넣어도 통과한다.** 문자 집합도
좁게 잡았다 — 이 값이 T-08에서 `apptainer build`에 넘어간다.

**레지스트리 호스트를 따로 두지 않는다.** 지금도 OpenFOAM은 Docker Hub, Isaac Sim은
`nvcr.io`다. `{호스트} + {경로}`로 쪼개면 앱마다 호스트를 고르는 칸이 하나 더 생기고
`//`·스킴 혼동만 남는다.

코드 카탈로그에도 `image_ref`를 뒀다 — `image`와 **같은 모양**이다(등록이 이기고 없으면
코드 값). 그래서 등록 없이도 아는 것을 답한다:

```
batch  openfoam   docker://opencfd/openfoam-default:2512
batch  isaac-sim  docker://nvcr.io/nvidia/isaac-sim:5.1.0
```

데스크톱 계열은 레지스트리가 아니라 `deploy/images/rocky9-mate`에서 직접 만들어 비어 있다 —
그 사실 자체가 정보다.

**테스트 픽스처에 `image_location`이 남아 있었다** — 마이그레이션 `0017`에서 사라진 필드다.
pydantic이 모르는 키를 무시해서 조용히 통과하고 있었고, 그 자리를 `image_ref`로 바꿨다.

검증: 테스트 **435개 통과**(3개 추가). MySQL에서 마이그레이션 **up → down → up 왕복**을
확인했다(DDL이 트랜잭션이 아니라 이 검증이 중요하다). 배포 후 `SHOW COLUMNS`에
`image_ref varchar(255) NULL`, 라이브 `list_apps()`가 위 두 참조를 그대로 답한다.

---

### T-08 변환을 Slurm 잡으로 — 빌드 → 배치

관리자가 앱 관리에서 [변환]을 누르면 두 걸음이 돈다.

1. **빌드** — `POST .../build`. OCI 참조를 `apptainer build`로 SIF를 만드는 **Slurm 잡**을
   제출한다. 결과는 **요청자 홈** `~/.portal/build/`에 떨어진다.
2. **배치** — `POST .../install`. 포털이 로그인 노드 SSH로 `sudo mv`한다.

파드에서 돌리지 않는 이유는 셋이다 — apptainer가 없고, 메모리 제한(1Gi)이 있고, 무엇보다
**캐시가 쌓여 파드가 스스로 evict된 전례**가 있다. 클러스터에서 돌리면 스크래치도 네트워크도
거기 것이고 진행 상황은 기존 Job 화면이 답한다.

**두 걸음으로 나눈 이유는 백그라운드 워커가 없어서다**(`scheduler_enabled: False`).
잡이 끝났는지는 Job 화면이 말해 주고 관리자가 그때 [배치]를 누른다. 폴링을 흉내 내느니
두 걸음이 정직하다.

#### 왜 잡이 직접 못 쓰나 — 그리고 그게 왜 옳은가

Slurm 잡은 **요청한 관리자 계정**으로 돈다. 그런데 클러스터에 관리자 그룹이 없다 —
포털 사용자 전원이 `domain users` 하나뿐이다(실측). 디렉터리를 그 그룹에 열면
**아무나 남이 실행할 이미지를 바꿔 놓을 수 있다.** 컨테이너 이미지는 모든 사용자가
실행하는 코드이고 `allow setuid = yes`인 환경이다. 그래서 목적지는 root 소유로 두고,
포털이 **딱 한 지점에서만** 권한을 올린다(사용자 결정).

#### 선행 확인 (실측)

| 항목 | slurm-cluster-1 | slurm-cluster-2 |
|---|---|---|
| DNS·HTTPS (docker.io / nvcr.io) | 401 = 도달 | 401 = 도달 |
| apptainer | 1.5.3 | 1.5.3 |
| user namespaces | 15524 | 15524 |
| 서비스 계정 → root | 가능(NOPASSWD) | — |

레지스트리 도달은 **포털 구성의 전제조건**으로 한다(사용자 결정). 지금 확인한 곳은
로그인 노드다 — 워커를 분리하면 그쪽에도 같은 경로가 필요하다.

#### 실 클러스터가 잡아낸 결함 셋

테스트 26개가 통과하는데도 세 번 깨졌다. 전부 **실제로 돌려 보고서야** 나왔다.

1. **`current_working_directory` 누락** — Slurm이 제출 자체를 거부한다("Job cannot be
   submitted without the current working directory specified"). 홈을 함께 돌려주도록 고쳤고,
   해석은 파일 브라우저·세션과 **같은 함수**(`home_dir_for`)를 쓴다.
2. **`$HOME` unbound** — Slurm 배치 환경에 그 변수가 없다. `set -u`와 만나 첫 줄에서 죽었다.
   이미 홈을 알아냈으므로 **절대경로를 박았다**. 테스트가 `"$HOME" not in script`를 고정한다.
3. **`mv`가 소유권을 가져온다** — 배치된 파일이 `jungryul0515.park domain users` 소유로
   남았다. 디렉터리가 root 소유라 삭제는 못 해도 **내용은 덮어쓸 수 있다** — 목적지를
   root 소유로 둔 이유가 통째로 무너진다. `chown root:root`를 더했고, 그 줄을 지우면
   테스트가 실패한다.

#### 전 구간 실측

`docker://alpine:3.20`으로 자기검사를 돌렸다(실제 앱을 건드리지 않으려고 작은 이미지).

```
빌드 Job 100 → COMPLETED, ~/.portal/build/portal-selftest.sif (3.5MB)
install     → /home/.portal/images/portal-selftest.sif
             -rw-r--r-- 1 root root 3559424
목록         → 캐시 무효화로 **즉시** 반영, installed_map True
```

검사 후 SIF·빌드 디렉터리·임시 등록 행·잡 로그를 모두 지웠다.

#### 남은 것

- **큰 이미지로는 아직 안 돌려 봤다.** alpine은 3.5MB, OpenFOAM은 443MB, Isaac Sim은 수 GB다.
  시간·디스크가 실제로 어떻게 되는지는 그때 봐야 한다.
- `nvcr.io`는 익명 pull이 안 된다(NGC 계정 + API 키). 사설 레지스트리 자격증명은 이 계획의
  **제외 항목**이다 — 필요해지면 기존 Secret 저장소에 붙인다.

검증: 테스트 **442개 통과**(7개 추가). `chown`을 지우면 배치 테스트가 실패한다.
`api.md` 100 → **102**, CLAUDE.md 435 → **442**.

---

### 데스크톱 이미지를 레지스트리로 — 큰 이미지 변환 실측

`rocky9-mate:1.5`를 Docker Hub(`stty0/rocky9-mate:1.5`)에 올렸다. 그래서 데스크톱 계열도
`image_ref`를 갖게 됐고, **손으로 SIF를 복사하던 앱들이 변환 경로에 들어왔다.**

```
desktop      rocky9-mate-1.5.sif    docker://stty0/rocky9-mate:1.5
paraview     rocky9-mate-1.5.sif    docker://stty0/rocky9-mate:1.5
jupyter      rocky9-mate-1.6.sif    (없음)  ← 1.6은 아직 안 올라갔다
code-server  (없음)                  (없음)  ← 포털이 호스팅하지 않는다
```

**비어 있는 것도 정보다.** 비면 화면에 [변환]이 뜨지 않는다 — 무엇을 받아올지 모르는 채로
잡을 던지지 않는다. 테스트가 그 집합(`{jupyter, code-server}`)을 고정한다.

#### 워커 노드에 Docker가 없어도 된다 (실측)

```
cluster 13·14   docker 없음 · podman 없음 · containerd 없음 · apptainer /usr/bin/apptainer
```

`docker://`는 **프로토콜 이름일 뿐** Docker 데몬이 아니다 — apptainer가 OCI Distribution
API로 레이어를 직접 받아 SIF로 조립한다. 데몬이 필요한 것은 `docker-daemon://`(로컬
데몬에서 읽기)뿐이다.

#### 큰 이미지 변환 — T-08의 미확인 항목이 채워졌다

alpine 3.5MB로만 확인했던 것을 실물로 돌렸다(Job 101).

| 항목 | 값 |
|---|---|
| 원본 (Docker Hub) | 2.62GB |
| **소요 시간** | **9분 3초** |
| 산출 SIF | **1.3GB** (기존 손빌드 SIF와 같은 크기) |
| 스크래치 피크 | cache 1.4G + tmp 987M ≈ **2.4G** |
| 빌드 후 잔여 | cache 1.4G (tmp는 스스로 비운다) |

`/home`이 100T라 여유는 문제가 아니었다. 검사물(SIF·캐시·잡 로그·임시 등록 행)은 모두 지웠다.

⚠️ **남은 문제: apptainer 캐시가 관리자 홈에 쌓이고 아무도 지우지 않는다.** 이번엔 1.4G였고
Isaac Sim은 수 GB다. 노드 디스크가 아니라 100T NFS라 당장 위험하지는 않지만, 이 프로젝트에는
**캐시 11GB로 dev01이 DiskPressure에 걸려 포털 파드가 evict된 전례**가 있다. 빌드 뒤
`apptainer cache clean`을 넣을지는 별도 판단이 필요하다(넣으면 재빌드가 매번 느려진다).

#### 이미지 파일명 칸을 드롭다운에서 입력으로

**드롭다운이면 새 버전의 첫 빌드가 불가능했다.** `openfoam:2606`으로 올리려 해도
`openfoam-2606.sif`는 아직 없는 파일이라 목록에 안 뜨고, 고르기만 가능하니 그 이름을 넣을
방법이 없었다. T-08을 DB에 값을 직접 넣어 검사해서 화면 경로로는 안 걸렸다.

`<input list>` + `<datalist>`로 바꿨다 — 기존 파일은 **제안**으로 남고 새 이름도 쓸 수 있다.
출처를 입력하고 포커스를 벗어나면 **파일명이 비어 있을 때만** 채워 준다
(`docker://stty0/rocky9-mate:1.5` → `rocky9-mate-1.5.sif`). 손으로 넣은 값은 덮지 않는다.

이유는 두 칸이 어긋날 수 있어서다 — 출처만 `:2606`으로 바꾸고 파일명을 두면 새 이미지가
`…-2512.sif`라는 이름으로 저장돼 **이름이 거짓말을 한다.**

검증: 테스트 **444개 통과**(2개 추가 — 카탈로그 참조의 모양, 출처 없는 앱 집합).

---

### T-07·T-08 철회 — 포털이 레지스트리에서 이미지를 받지 않는다

**관리자가 포털 밖에서** 이미지를 받아 SIF로 변환한 뒤 클러스터의 `{home_base}/.portal/images`에
올려 놓는 방식으로 정해졌다(사용자 결정). 그러면 OCI 참조를 읽는 코드가 **하나도 남지
않는다** — 이 프로젝트는 그런 표를 남기지 않는다(`job_template` 제거 근거와 같다).

지운 것: `app_catalog.image_ref`(마이그레이션 `0019`) · `POST .../build` · `POST .../install` ·
`AppImageService`의 `_plan`·`build_script`·`install` · `IMAGE_REF`·`BUILD_SUBDIR`·`_catalog_ref` ·
코드 카탈로그의 `image_ref` 필드와 값 4개 · 화면의 [변환] 버튼·모달 · 관련 테스트 12개.

**출처를 적어 두려면 `description`에 쓴다.** 이미 있는 칸이고 관리자가 채우는 값이라
새 컬럼 없이 같은 정보가 남는다.

**T-01~T-06은 그대로 유효하다** — 클러스터별 경로 파생, 목록 조회(SSH), 등록 시 디렉터리
확인, 잠금 셋(`ready`·`installed`·`allowed`). 관리자가 SIF를 올려놓으면 최대 60초 뒤 앱이
열린다는 성질도 그대로다.

이미지 파일명 칸은 **입력(+datalist)으로 남긴다.** 드롭다운으로 되돌리면 파일을 올리기
전에 앱을 등록할 수 없다 — 클러스터 등록에서 순서를 강요하지 않는 것과 같은 이유다.
아직 없는 파일명은 `installed=false`로 잠기고 화면이 사유를 말한다.

#### 남는 판단 근거 (되살릴 때를 위해)

레지스트리 경로가 값을 하는 조건은 **클러스터마다 NFS가 갈릴 때**다. 그때 선택은
1.3GB를 클러스터마다 손으로 나르느냐, 버튼 한 번(9분, 무인)이냐다. 구현과 실측은
git 이력에 남아 있다(`a99170d`·`f825a96`·`1efc96c`) — 되살리려면 그 세 커밋을 보면 된다.

실측값도 남긴다: `stty0/rocky9-mate:1.5` 2.62GB → **9분 3초** → SIF 1.3GB, 스크래치 피크 2.4G.
워커 노드에 docker·podman·containerd가 **없어도** apptainer만으로 변환된다는 것도 확인됐다.

#### 향후: enroot(squashfs) 지원 시의 분해 (사용자와 합의, 미구현)

확장자로 **런타임**을 정하고, 자원은 이미 있는 `needs_gpu`가 정한다.

| 축 | 무엇이 정하나 | 결과 |
|---|---|---|
| 런타임 | 확장자 | `.sif` → `apptainer exec`, `.sqsh` → enroot |
| 자원 | `needs_gpu` | `--gres=gpu:N`, apptainer면 `--nv` |

**확장자로 CPU/GPU를 가르면 안 된다** — Isaac Sim이 SIF + `--nv`로 GPU를 쓰도록 이미
작성돼 있고 테스트가 그것을 고정한다. 두 축을 나누면 네 조합이 다 성립한다.
현재 클러스터에 enroot·pyxis는 **둘 다 없다**(`PlugStackConfig = null`, 실측).

검증: 테스트 **432개 통과**(12개 감소). MySQL에서 마이그레이션 up→down→up 왕복 확인,
`SHOW COLUMNS`에 `image_ref` 없음. `POST .../build`는 **404**, 목록·진단은 그대로 401/200.
