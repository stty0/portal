# AGENTS.md — Slurm HPC Portal (에이전트 실행 규칙)

이 프로젝트에서 구현·수정·Git 작업을 수행할 때 따르는 규칙이다.

> **역할**: 현재는 **Claude가 계획·구현·검증을 모두 담당**한다([docs/workflow.md](docs/workflow.md)).
> 이 문서는 "누가 하느냐"와 무관하게 지켜야 할 **구조 규칙**을 정의한다.
> 프로젝트 컨텍스트·스택은 [CLAUDE.md](CLAUDE.md)를 먼저 읽는다.

## 스택 (요약)

FastAPI + SQLAlchemy + MySQL/Redis 백엔드, Vue 3 + TypeScript + Tailwind v4 프론트엔드,
k3s 배포. 외부 연동은 slurmrestd v0.0.41 · AD(LDAP) · 로그인 노드 SSH/SFTP · SCP Billing.

`design/`는 최초 정적 HTML 프로토타입으로 **디자인 원본**일 뿐이다. 제품은 `frontend/`이고,
둘을 동기화할 의무는 없다.

## 반드시 지킬 구조 규칙

- **계층 방향** `router → service → repository/client`. 라우터에 비즈니스 로직을 두지 않고
  repository/client를 직접 부르지 않는다 — [backend/tests/test_layering.py](backend/tests/test_layering.py)가 강제한다.
- **대상 사용자는 언제나 요청자 본인.** 사용자명을 요청 본문·쿼리로 받지 않는다.
  Slurm impersonation 헤더는 서버가 인증된 본인으로만 채운다.
- **파일 조작의 경로 관문**: 서버 `realpath`로 정규화한 **뒤에** 허용 루트를 확인한다.
  조회 범위와 변경 범위가 같아야 한다.
- **세션 접속 위치(워커 host/port)를 응답에 담지 않는다.** 담으면 열린 프록시가 된다.
- **Secret은 `SecretStore`에만.** DB에는 `secret_ref`, 응답·감사 로그에는 값이 남지 않는다.
- 디자인 토큰은 [frontend/src/assets/main.css](frontend/src/assets/main.css)의 `@theme`에만
  정의한다. 색상·간격을 컴포넌트에 하드코딩하지 않는다.
- 새 UI 요소에는 기능 정의서 ID를 `<Fid id="U-XX-00" />`로 매핑한다.
- 화면/기능 ID의 단일 출처는 [정의서.md](정의서.md)다. 새 ID를 임의로 만들지 않는다.
- 한국어 하드코딩을 유지한다. i18n(C-06) 도입은 계획 단계로 되돌린다.

## 구현 절차

1. [docs/exec-plan.md](docs/exec-plan.md)에서 Task와 수용 기준을 확인한다.
2. 구현 후 검증을 실행한다.
   ```bash
   cd backend  && .venv/bin/python -m pytest -q   # 261개
   cd frontend && npm run build                    # vue-tsc 타입체크 포함
   ```
3. 배포가 필요하면 이미지 재빌드 → containerd import → rollout.
   **빌드 직후 `docker builder prune -af`를 반드시 실행한다** — 캐시가 쌓여 dev01이
   DiskPressure에 걸리고 포털 pod이 evict된 사고가 있었다.
4. [docs/progress.md](docs/progress.md)에 결과와 실측을 남긴다. 특히 **겪은 함정**을 적는다.

## 하지 말 것

- 요청 범위를 넘는 인접 코드 개선·리팩터·dead code 삭제(발견 시 보고만).
- 검증 없이 "동작한다" 보고. 실측 결과를 함께 남긴다.
- 사용자 데이터·실 클러스터에 영향을 주는 작업을 사전 고지 없이 실행.
