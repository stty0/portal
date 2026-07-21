# Exec Plan: admin 등록/수정 입력 모달 전환

- 근거 plan: docs/plan.md
- 범위: Tier 1 + Tier 2 (경계 케이스 users AD 연결 / billing SCP 연동은 인라인 유지)
- 담당: 구현 Codex(gpt-5.6-terra) / 검증 Claude(portal-verifier, portal-reviewer)

## 공통 규칙 (모든 Task 적용)
- **기존 모달 패턴만 사용**(신규 CSS 컴포넌트 금지):
  `<div class="modal-backdrop hidden" id="{name}Modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="{name}Title">`
  → `.modal-head`(제목 + `.m-close` ✕) / `.modal-body`(폼) / `.modal-foot`(취소·저장 버튼).
- 입력 컨트롤은 기존 클래스 재사용: `.input`, `.select`, `.switch`, 라벨 스타일 기존과 동일.
- open/close JS는 페이지 하단 기존 `<script>` 컨벤션대로 추가: 트리거 클릭 → `modal.classList.remove('hidden')`; `.m-close`·배경 클릭·ESC → `add('hidden')`. 여러 모달이면 공통 헬퍼 하나로.
- 트리거: 페이지 액션 `＋등록/생성` = 빈 폼(제목 "…추가"), 행 `수정` = 예시값 프리필(제목 "…수정"). 정적이므로 프리필은 대표 예시값 하드코딩.
- **fid 칩/주석은 이동하는 폼과 함께 모달 안으로 그대로 옮긴다.**
- 사이드바/톱바/푸터·기존 스크립트 로직 **미변경**. 오직 본문 content의 해당 카드만 수정.
- 유지 대상(변경 금지): 검색/필터 바, 읽기전용 테이블·차트·타임라인, settings 시스템 설정(전역), users 계정·클러스터 매핑 매트릭스, users AD 연결, billing SCP 연동.

## Task 목록

### T-01 license.html — 라이선스 서버 추가/수정 모달 (Tier1)
- 인라인 "수집/연동 설정" 카드(L128–163) 제거 → `licenseServerModal` 신설.
- 모달 필드: 서버명, 유형(FlexNet/FlexLM), 접속주소(port@host), 벤더 데몬, 대상 SW, 3중화 여부 + (수집/연동 관련) 연결 Timeout, 대상 서버 수집 주기, Slurm Licenses 동기화 토글.
- 전역 성격 설정(lmutil 경로 등)은 모달 상단 "전역" 구획으로 포함(사용자 의도: 등록/수정 시 입력). 별도 인라인 카드로 남기지 않음.
- 트리거: `＋라이선스 서버 추가`(L84, 빈 폼), 각 행 `수정`(프리필). `Feature 사용 현황`·`사용 모니터링`(A-LM-05) 테이블은 유지.
- 검증: 태그 균형 / 내부 링크 / fid(A-LM-*) 보존.

### T-02 clusters.html — 클러스터 등록/수정 모달 (Tier1)
- 인라인 "클러스터 등록/수정" 폼(L136–161) → `clusterModal`. 트리거 `＋클러스터 등록`(L84)·행 `수정`(L117/127).
- "수집/장애 정책" 카드(L176–189)는 page-level 정책이므로 **유지**.

### T-03 nodes.html — 상태변경 + 파티션 + 예약 모달 (Tier1+2)
- 노드 상태 변경 인라인(L153–164) → `nodeStateModal`. 트리거: 행 `Drain`/`Resume`(대상 노드 프리필).
- `＋파티션 생성`(L85/188)·행 `수정` → `partitionModal`(신규 폼: 파티션명, 노드 구성, 시간제한, 우선순위, 접근 계정/그룹).
- `＋예약 생성`(L84/208) → `reservationModal`(신규 폼: 예약명, 대상 노드, 기간, 사유/전용 그룹).
- 파티션·예약 테이블은 읽기전용 유지. `점검 모드 시작`(L83)은 이번 범위 제외(유지).

### T-04 jobs.html — 우선순위 조정 모달 (Tier1)
- 인라인 "우선순위 조정" 카드(L159–172) → `jobPriorityModal`. 트리거: 행 `⇧Top`/`Hold`(L135 등, Job ID 프리필). 필터 바·제어 이력 테이블 유지.

### T-05 users.html — QOS 생성/수정 + 파티션 접근제어 모달 (Tier1+2)
- QOS 테이블(L246–258) 위 `＋QOS 생성`·행 `수정` → `qosModal`(신규 폼: QOS명, 최대 Job 수, 자원 한도, 우선순위).
- 인라인 "파티션 접근 제어" 서브폼(L259–271) → `partitionAclModal`(대상 파티션, AllowAccounts).
- AD 연결(L148–191)·계정 매핑 매트릭스(L276–324)는 **유지**.

### T-06 settings.html — 공지 / 앱·템플릿 모달 (Tier2)
- `＋공지 등록`·행 `수정` → `noticeModal`(제목, 대상, 노출 기간, 배너 여부, 본문).
- `＋등록`(앱/템플릿)·행 `파라미터`/`버전` → `appTemplateModal`(앱명, 유형, 버전, 파라미터 정의).
- 시스템 설정 카드(L143–171)는 전역 설정이므로 **유지**.

### T-07 billing.html — 자원 식별 필터 규칙 모달 (Tier2)
- `＋규칙 추가`·행 `수정` → `billingRuleModal`(구분, 조건, 매핑, 상태). "필터 밖 자원 처리" 기본 select는 page 설정으로 유지. SCP 연동 카드 **유지**.

### T-08 reports.html — 정기 리포트 설정 모달 (Tier2)
- `✉ 정기 리포트 설정`(L89) → `reportScheduleModal`(수신자, 주기, 형식, 범위). 나머지 분석 위젯 유지.

## 실행 순서 / 검증
- 순서: T-01(레퍼런스) → T-02 → … → T-08. T-01에서 모달 마크업/JS 컨벤션을 확정하고 나머지에 동일 적용.
- 각 Task 후 progress.md 갱신. 전체 완료 후 portal-verifier(태그 균형·내부 링크·fid 커버리지+negative control) 실행, portal-reviewer로 구조 규칙·정의서 정합성 검토.
- 성공 기준: plan.md §5. 코딩 가이드라인(최소·수술적 변경) 준수 — 요청 범위 밖 리팩터/스타일 변경 금지.
