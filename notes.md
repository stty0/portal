# 프로젝트 노트 — Slurm HPC Portal 프론트엔드

## 2026-07-15: 기능 정의서 v0.1 기반 정적 프로토타입 완성
- **요약**: SCR-01~15 전체 15화면을 순수 HTML/CSS로 구현 (`portal/`). JS 없음 — 탭은 CSS radio 트릭(`#tab-a~c`), 나머지는 정적.
- **디자인 기준**: Samsung SDS Cloud 서비스포털 look & feel → 토큰화해 둠 (`portal/css/style.css` 상단 `:root`).
  - 브랜드 블루 `--brand-700: #1428A0`, 배경 `#f4f6fa`, 사이드바 네이비 `#131a3a`, 히어로 그라데이션 `--grad-hero`.
- **구조 규칙 (수정 시 유지할 것)**:
  - 사이드바/톱바 마크업은 페이지마다 복붙되어 있음(정적 사이트라 include 불가). 메뉴 변경 시 user 8개 / admin 6개 파일 모두 수정 필요.
  - 각 화면 UI 요소에 기능 정의서 ID를 `<span class="fid">U-XX-00</span>` 칩 또는 HTML 주석으로 매핑해 둠 → 리뷰/추적용.
- **검증 방법 (재사용 가능)**: python 스크립트로 (1) 태그 균형 (2) 내부 href/src 링크 존재 (3) 기능 ID 62종 grep 커버리지 + negative control. 전부 통과 확인함.
- **다음 단계 후보**: 실제 데이터 바인딩 시 slurmrestd(v0.0.41) 연동 전제(C-03), 폴링 30초(C-04). 다국어(C-06)는 현재 한국어 하드코딩 — i18n 도입 시 텍스트 추출 필요.
