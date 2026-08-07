# 프로젝트 노트 — Slurm HPC Portal

> 이 파일은 **초기 히스토리**다. 현재 상태·스택은 [CLAUDE.md](CLAUDE.md),
> 구현 경위와 실측 기록은 [docs/progress.md](docs/progress.md)를 본다.

## 2026-08-04 이후: 제품 구현으로 전환

정적 프로토타입을 원본 삼아 **FastAPI 백엔드 + Vue 3 프론트엔드**로 이관했다.
현재는 실 클러스터(slurm01·slurm02)에 연동되어 동작한다. 아래 2026-07-15 항목의
"정적 사이트" 전제는 더 이상 유효하지 않다 — `design/`는 디자인 원본으로만 남는다.

진행 경위·설계 판단·실측 결과는 전부 `docs/progress.md`에 시간순으로 있다.

---

## 2026-07-15: 기능 정의서 v0.1 기반 정적 프로토타입 완성 (히스토리)

- **요약**: SCR-01~15를 순수 HTML/CSS로 구현. JS 없음 — 탭은 CSS radio 트릭(`#tab-a~c`),
  나머지는 정적. 이후 화면이 SCR-19까지 늘었고 디렉터리는 `design/`으로 정리됐다.
- **디자인 기준**: Samsung SDS Cloud 서비스포털 look & feel → 토큰화
  (`design/css/style.css` 상단 `:root`). 브랜드 블루 `--brand-700: #1428A0`,
  배경 `#f4f6fa`, 사이드바 네이비 `#131a3a`, 히어로 그라데이션 `--grad-hero`.
  → **현재 제품의 토큰은 `frontend/src/assets/main.css`의 `@theme`로 옮겨졌다.**
- **당시 구조 규칙**: 사이드바/톱바 마크업이 페이지마다 복붙되어 있어 메뉴 변경 시 전
  파일을 수정해야 했다. Vue 이관 후에는 `components/layout/`의 단일 컴포넌트가 담당한다.
- **당시 검증 방법**: python 스크립트로 (1) 태그 균형 (2) 내부 href/src 링크 존재
  (3) 기능 ID grep 커버리지 + negative control. **`design/`를 손볼 때만 유효한 패턴이다.**
  제품 검증은 pytest + `vue-tsc`가 대신한다.
