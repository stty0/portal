# Claude + Codex 협업 개발 워크플로

역할을 분리해 품질을 높인다. Claude는 요구사항·구현 방향을 정리하고, Codex는 그 계획을 기준으로 코드를 작성하며, 다시 Claude가 결과를 검증해 누락·과도한 변경·품질 문제를 별도로 점검한다.

## 역할

| 영역 | 담당 | 세부 |
|---|---|---|
| 계획 · 분석 · 검토 | **Claude** | 요구사항 분석, 구현 계획 수립, 코드 검토, 최종 승인 |
| 구현 · 수정 · Git | **Codex** | 코드 구현, 테스트 작성, 버그 수정, commit/branch/PR |

## 전체 흐름

```
1. 요구사항 분석 및 구현 계획          (Claude)
        │  → docs/plan.md, docs/exec-plan.md
        ▼
2. 코드 구현                          (Codex 고성능 모델)
        │  → docs/progress.md 갱신
        ▼
3. Diff 및 품질 검증                   (Claude)
        │
        ▼
4. 문제 발견?
   ├─ Yes → 코드 수정 (Codex) → 3으로
   └─ No  → 계속
        │
        ▼
5. Git 정리 및 PR 생성                 (Codex 저비용 모델)
        │
        ▼
6. 최종 검토                          (Claude)
```

## 단계별 모델 구성

| 단계 | 담당 | 기본 모델 | 주요 책임 |
|---|---|---|---|
| 계획 | Claude | claude-fable-5 | 요구사항 분석, 설계, plan.md·exec-plan.md 작성 |
| 구현 | Codex | gpt-5.6-terra | 승인된 Task 구현, 테스트, progress.md 갱신 |
| 검증 | Claude | claude-sonnet-5 | 계획 대비 diff, 테스트·품질 검증 |
| 고위험 검증 | Claude | claude-opus-4.8 | 보안, 권한, DB, 인프라, 대규모 변경 재검증 |
| Git 작업 | Codex | gpt-5.5 | commit 문안, push, PR 작성 등 정형 작업 |
| 독립 리뷰 | Codex | gpt-5.6-luna | 설계 가정·실패 경로·회귀 위험 독립 점검 |

## 작업 문서

| 파일 | 작성 | 라이프사이클 |
|---|---|---|
| `docs/plan.md` | Claude | 작업(에픽) 시작 시 작성, 요구사항 변경 시 갱신 |
| `docs/exec-plan.md` | Claude | plan 승인 후 Task로 분해, 구현 중 참조 |
| `docs/progress.md` | Codex | Task 구현마다 갱신, 검증 결과 반영 |

템플릿은 [templates/](templates/)에 있다. 새 작업을 시작할 때 복사해 채운다.

## Codex 위임 방법 (Claude → Codex)

Claude 세션에서 구현을 넘길 때:
- `/codex:rescue` — 조사·구현·수정 위임 (Codex 서브에이전트 실행)
- 또는 터미널에서 `codex exec "<지시>"`

위임 시 항상 **대상 exec-plan Task 번호와 수용 기준**을 함께 전달한다. Codex는 계획 범위를 벗어나면 확장하지 않고 progress.md에 기록해 Claude 검토로 되돌린다.

## 검증 체크 (정적 프로토타입 공통)
1. **태그 균형** — 모든 HTML 파일 열림/닫힘 태그 일치
2. **내부 링크 존재** — href/src가 실제 파일을 가리키는지
3. **기능 ID 커버리지** — 정의서 ID grep + negative control(없어야 할 ID가 안 잡히는지)
