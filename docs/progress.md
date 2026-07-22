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

## 미해결 / 참고
- 정적 프로토타입이므로 수정(edit) 시 실제 값 프리필은 미구현(대표 예시값). 실데이터 바인딩(C-03) 도입 시 처리.
- 점검 모드 시작(A-ND-05)은 이번 범위 제외(버튼 유지).
- CLAUDE.md의 "현재 JS 없음" 문구는 실제와 달라 정정함(바닐라 JS 존재).
