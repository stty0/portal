# AGENTS.md — Slurm HPC Portal (Codex 실행 규칙)

Codex가 이 프로젝트에서 구현·수정·Git 작업을 수행할 때 따르는 규칙이다.
Claude가 계획·검토를 담당하므로, Codex는 **승인된 계획(`docs/exec-plan.md`)의 범위 안에서만** 구현한다.

## 담당 범위
- 승인된 Task 구현, 테스트 작성/실행, 버그 수정·개선
- Git 작업: commit 문안 작성, branch 관리, push, PR 생성

## 반드시 지킬 구조 규칙
- 사이드바/톱바 마크업은 각 페이지에 복붙되어 있다(정적 사이트, include 없음).
  메뉴/네비게이션 변경 시 `design/user/`(9개)·`design/admin/`(12개) 파일을 **모두** 동일하게 수정한다.
- 디자인 토큰은 `design/css/style.css` 상단 `:root`에만 정의한다. 색상·간격을 인라인 하드코딩하지 말고 토큰(`var(--brand-700)` 등)을 쓴다.
- 새 UI 요소에는 기능 정의서 ID를 `<span class="fid">U-XX-00</span>` 칩 또는 HTML 주석으로 매핑한다.
- 화면/기능 ID의 단일 출처는 `정의서.md`다. 새 ID를 임의로 만들지 말고 정의서를 따른다.
- 현재 JS·빌드 도구·프레임워크 없음. 정적 HTML/CSS 원칙을 유지하고, 도입이 필요하면 계획 단계로 되돌려 Claude 승인을 받는다.

## 구현 절차
1. `docs/exec-plan.md`에서 배정된 Task와 수용 기준을 확인한다.
2. 구현 후 검증을 실행한다(태그 균형 / 내부 링크 존재 / 기능 ID grep 커버리지 + negative control).
3. `docs/progress.md`에 Task별 진행·결과·미해결 이슈를 갱신한다.
4. 계획을 벗어나는 변경이 필요하면 임의로 확장하지 말고 progress.md에 기록하고 Claude 검토로 넘긴다.

## Git 규칙
- 커밋은 Task 단위로 작게, 명령형·한 줄 요약 + 필요 시 본문.
- 사용자가 명시적으로 요청하기 전에는 push/PR을 만들지 않는다.
- 검토 미승인 변경을 기본 브랜치에 직접 커밋하지 않는다.
