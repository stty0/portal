# CLAUDE.md — Slurm HPC Portal

Claude가 이 프로젝트에서 세션마다 읽는 기본 컨텍스트 파일이다.

## 프로젝트 개요
- **대상**: Slurm 기반 HPC 클러스터 웹 포털 프론트엔드
- **현재 상태**: SCR-01~17 화면을 순수 HTML/CSS로 구현한 정적 프로토타입 (`design/`)
- **기능 정의서**: [정의서.md](정의서.md) — 화면(SCR)·기능(U-/A-) ID의 단일 출처(SoT)
- **개발 노트**: [notes.md](notes.md) — 구현 히스토리·검증 방법

## 구조 규칙 (수정 시 반드시 유지)
- 사이드바/톱바 마크업은 페이지마다 복붙되어 있음(정적 사이트라 include 불가).
  메뉴 변경 시 `design/user/` 9개 + `design/admin/` 9개 파일을 **모두** 수정해야 한다.
- 디자인 토큰은 [design/css/style.css](design/css/style.css) 상단 `:root`에 정의 (Samsung SDS Cloud 포털 look & feel).
  - 브랜드 블루 `--brand-700: #1428A0`, 배경 `#f4f6fa`, 사이드바 네이비 `#131a3a`.
- 각 UI 요소는 기능 정의서 ID를 `<span class="fid">U-XX-00</span>` 칩 또는 HTML 주석으로 매핑 (리뷰/추적용).
- 바닐라 JS만 사용(프레임워크·빌드도구 없음): 페이지별 사이드바 접기·톱바 드롭다운·클러스터 선택 스크립트, 등록/수정 **모달 open/close**(`.modal-backdrop.hidden` 토글, `data-open-modal` 트리거). 한국어 하드코딩. i18n(C-06)·데이터 바인딩(slurmrestd v0.0.41, C-03)은 미도입.

---

# Claude + Codex 협업 개발 워크플로

역할을 분리해 품질을 높인다. **Claude는 계획·분석·검토**, **Codex는 구현·수정·Git 작업**을 담당한다.
전체 흐름과 상세 규칙은 [docs/workflow.md](docs/workflow.md) 참조.

## Claude의 책임 (이 세션)
1. **요구사항 분석** — 정의서 기준으로 핵심 기능·제약 파악
2. **계획 수립** — `plan.md`(무엇을/왜) + `exec-plan.md`(Task 단위 실행 계획) 작성
3. **코드 검토** — Codex 구현 결과의 diff·품질·보안·회귀 검증
4. **최종 승인** — 변경 종합 검토 후 승인

## Codex에게 위임하는 것 (구현·Git)
- 승인된 Task 구현, 테스트 작성/실행, 버그 수정, commit/branch/PR 작업
- **위임 방법**: `/codex:rescue` 스킬 또는 `codex exec` 로 넘긴다. 위임 시 관련 `exec-plan.md` Task 범위를 명시한다.

## 코딩 가이드라인 (Karpathy) — 상시 적용
구현·수정·리뷰·리팩터링 작업을 시작할 때 **`andrej-karpathy-skills:karpathy-guidelines` 스킬을 먼저 invoke**한다. 핵심 4원칙:
1. **Think Before Coding** — 가정을 명시하고, 해석이 여럿이면 제시하고, 불명확하면 멈추고 질문한다.
2. **Simplicity First** — 요청된 것만, 최소 코드로. 투기적 추상화·설정·불가능 시나리오 예외처리 금지.
3. **Surgical Changes** — 요청과 직결되는 라인만 수정. 인접 코드 임의 개선·리팩터·기존 dead code 삭제 금지(발견 시 보고만).
4. **Goal-Driven Execution** — 검증 가능한 성공 기준 정의 후 통과까지 반복. 다단계는 `단계 → 검증` 계획 명시.

> Codex 위임 시에도 이 원칙(특히 최소·수술적 변경)을 지시에 포함한다. 사소한 작업은 판단껏 생략 가능.

## 작업 문서 (docs/ 하위 working 파일)
| 파일 | 작성 | 내용 |
|---|---|---|
| `docs/plan.md` | Claude | 요구사항·설계·범위·수용 기준 |
| `docs/exec-plan.md` | Claude | 승인된 Task 목록(구현 단위, 의존성, 검증 방법) |
| `docs/progress.md` | Codex | Task별 구현 진행·결과·미해결 이슈 |

템플릿: [docs/templates/](docs/templates/)

## 권장 모델 구성
| 단계 | 담당 | 기본 모델 |
|---|---|---|
| 계획 | Claude | claude-fable-5 |
| 구현 | Codex | gpt-5.6-terra |
| 검증 | Claude | claude-sonnet-5 |
| 고위험 검증(보안·권한·DB·인프라·대규모) | Claude | claude-opus-4.8 |
| Git 작업 | Codex | gpt-5.5 |
| 독립 리뷰 | Codex | gpt-5.6-luna |

## 검증 방법 (재사용)
notes.md의 검증 스크립트 패턴 유지: (1) 태그 균형 (2) 내부 href/src 링크 존재 (3) 기능 ID grep 커버리지 + negative control.

## 프로젝트 전용 서브에이전트 (.claude/agents/)
Claude의 검토·검증을 돕는 에이전트. Agent 툴로 호출한다.
| 에이전트 | 용도 |
|---|---|
| `portal-verifier` | 기계적 검증(태그 균형·내부 링크·ID 커버리지+negative control) 실행·보고 |
| `portal-reviewer` | 변경을 정의서·구조 규칙 대비 검토, 계획 이탈·고위험 신호 지적 |

구현·Git 위임은 플러그인 에이전트 `codex:codex-rescue`를 사용한다.
