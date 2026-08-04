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
