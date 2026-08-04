# Claude 개발 워크플로

Claude가 계획·구현·검증을 모두 담당한다. 계획 수립 후 스스로 구현하고, 별도 검증 단계에서 diff·품질·회귀를 재점검한다.

## 역할

| 영역 | 담당 | 세부 |
|---|---|---|
| 계획 · 구현 · 검토 | **Claude** | 요구사항 분석, 구현 계획 수립, 코드 구현, 코드 검토, 최종 승인, Git 작업 |

## 전체 흐름

```
1. 요구사항 분석 및 구현 계획          (Claude)
        │  → docs/plan.md, docs/exec-plan.md
        ▼
2. 코드 구현                          (Claude)
        │  → docs/progress.md 갱신
        ▼
3. Diff 및 품질 검증                   (Claude)
        │
        ▼
4. 문제 발견?
   ├─ Yes → 코드 수정 (Claude) → 3으로
   └─ No  → 계속
        │
        ▼
5. Git 정리 및 PR 생성                 (Claude)
        │
        ▼
6. 최종 검토                          (Claude)
```

## 단계별 모델 구성

| 단계 | 담당 | 기본 모델 | 주요 책임 |
|---|---|---|---|
| 계획 | Claude | claude-opus-5 | 요구사항 분석, 설계, plan.md·exec-plan.md 작성 |
| 구현 | Claude | claude-sonnet-5 | 승인된 Task 구현, 테스트, progress.md 갱신 |
| 검증 | Claude | claude-sonnet-5 | 계획 대비 diff, 테스트·품질 검증 |
| 고위험 검증 | Claude | claude-opus-5 | 보안, 권한, DB, 인프라, 대규모 변경 재검증 |
| Git 작업 | Claude | claude-haiku-4.5 | commit 문안, push, PR 작성 등 정형 작업 |
| 코드 리뷰 | Claude | claude-opus-5 | 설계 가정·실패 경로·회귀 위험 점검 |

## 작업 문서

| 파일 | 작성 | 라이프사이클 |
|---|---|---|
| `docs/plan.md` | Claude | 작업(에픽) 시작 시 작성, 요구사항 변경 시 갱신 |
| `docs/exec-plan.md` | Claude | plan 승인 후 Task로 분해, 구현 중 참조 |
| `docs/progress.md` | Claude | Task 구현마다 갱신, 검증 결과 반영 |

템플릿은 [templates/](templates/)에 있다. 새 작업을 시작할 때 복사해 채운다.

## 검증 체크 (정적 프로토타입 공통)
1. **태그 균형** — 모든 HTML 파일 열림/닫힘 태그 일치
2. **내부 링크 존재** — href/src가 실제 파일을 가리키는지
3. **기능 ID 커버리지** — 정의서 ID grep + negative control(없어야 할 ID가 안 잡히는지)
