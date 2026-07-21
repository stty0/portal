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

## 미해결 / 참고
- 정적 프로토타입이므로 수정(edit) 시 실제 값 프리필은 미구현(대표 예시값). 실데이터 바인딩(C-03) 도입 시 처리.
- 점검 모드 시작(A-ND-05)은 이번 범위 제외(버튼 유지).
- CLAUDE.md의 "현재 JS 없음" 문구는 실제와 달라 정정함(바닐라 JS 존재).
