# CLAUDE.md — Slurm HPC Portal

Claude가 이 프로젝트에서 세션마다 읽는 기본 컨텍스트 파일이다.

## 프로젝트 개요
- **대상**: Slurm 기반 HPC 클러스터 웹 포털 (백엔드 + 프론트엔드)
- **현재 상태**: 실 클러스터에 연동되어 동작 중. 미구현은 **License 관리(SCR-17)**,
  헬프데스크 티켓(A-OP-05·U-AC-04), **정기 리포트 발송(A-RP-04)·과금 연계(A-RP-05)**,
  비용 수집 이력(A-BL-03·04의 `billing_snapshot`)이다 — 전부 표만 있고 코드가 없다
  (근거·목록은 [backend/app/models/ops.py](backend/app/models/ops.py) 머리말,
  `test_tables_without_code_are_the_documented_ones`가 목록의 표류를 막는다).
- **기능 정의서**: [정의서.md](정의서.md) — 화면(SCR)·기능(U-/A-) ID의 단일 출처(SoT)
- **진행 기록**: [docs/progress.md](docs/progress.md) — 구현 경위·실측 결과·미해결 이슈
- **개발 노트**: [notes.md](notes.md) — 정적 프로토타입 시기의 히스토리
- **GPU 도입 검토**: [docs/gpu-simulation.md](docs/gpu-simulation.md) — Isaac Sim/Omniverse
  아키텍처 결정, GPU 선택(RT 코어), 미구현 4건

### 스택
| 영역 | 구성 |
|---|---|
| 백엔드 | FastAPI + SQLAlchemy + Alembic, MySQL 8.4, Redis. `router → service → repository/client` |
| 프론트엔드 | Vue 3 + TypeScript + Tailwind CSS v4 + Vite (SPA) |
| 외부 연동 | slurmrestd **v0.0.41**(REST), AD(LDAP), 로그인 노드 SSH/SFTP(paramiko), SCP Billing |
| 배포 | k3s(네임스페이스 `hpc-portal`) + Traefik. `https://www.dt-hpc.net:9443` |
| 클러스터 | dev01 192.168.1.100 / slurm01 .201 / slurm02 .202 (현재 로그인=워커 동일 기계) |

`design/`는 최초 정적 프로토타입이다. **제품이 아니라 디자인 원본**이며, Vue 이관 후에는
동기화 의무가 없다(톱바 검색창 제거 시 의도적으로 Vue만 수정한 전례가 있다).

## 구조 규칙 (수정 시 반드시 유지)
- **계층 방향은 문서가 아니라 테스트가 강제한다** — [backend/tests/test_layering.py](backend/tests/test_layering.py).
  라우터에서 repository/client 직접 호출 금지.
- **대상 사용자는 언제나 요청자 본인이다.** 클라이언트가 사용자명을 넘길 수 없고,
  Slurm impersonation(`X-SLURM-USER-NAME`)은 서버가 인증된 본인으로만 채운다.
- **파일 조작은 조회와 같은 경계를 쓴다** — 허용 루트(**홈뿐이다**)를 벗어나는
  생성·삭제·이동·다운로드는 경로 정규화 **뒤에** 차단한다. 스크래치·그룹 공유
  디렉터리는 포털 범위 밖이다(정의서 §4.1, 마이그레이션 `0006`).
- 디자인 토큰은 [frontend/src/assets/main.css](frontend/src/assets/main.css)의 `@theme`
  블록에만 정의한다(Tailwind v4 방식). 색상·간격을 컴포넌트에서 하드코딩하지 말 것.
  브랜드 블루 `--color-brand-700: #1428a0`, 배경 `--color-bg: #f4f6fa`,
  사이드바 네이비 `--color-side-bg: #131a3a`.
- 각 UI 요소는 기능 정의서 ID를 `<Fid id="U-XX-00" />` 컴포넌트로 매핑 (리뷰/추적용).
- 한국어 하드코딩. i18n(C-06)은 미도입.

---

# Claude 개발 워크플로

Claude가 계획·구현·검증을 모두 담당한다. 전체 흐름과 상세 규칙은 [docs/workflow.md](docs/workflow.md) 참조.

## Claude의 책임 (이 세션)
1. **요구사항 분석** — 정의서 기준으로 핵심 기능·제약 파악
2. **계획 수립** — `plan.md`(무엇을/왜) + `exec-plan.md`(Task 단위 실행 계획) 작성
3. **구현** — 승인된 Task 구현, 테스트 작성/실행, 버그 수정, `progress.md` 갱신
4. **검증** — diff·품질·보안·회귀 검증
5. **최종 승인** — 변경 종합 검토 후 승인, commit/branch/PR 작업

## 코딩 가이드라인 (Karpathy) — 상시 적용
구현·수정·리뷰·리팩터링 작업을 시작할 때 **`andrej-karpathy-skills:karpathy-guidelines` 스킬을 먼저 invoke**한다. 핵심 4원칙:
1. **Think Before Coding** — 가정을 명시하고, 해석이 여럿이면 제시하고, 불명확하면 멈추고 질문한다.
2. **Simplicity First** — 요청된 것만, 최소 코드로. 투기적 추상화·설정·불가능 시나리오 예외처리 금지.
3. **Surgical Changes** — 요청과 직결되는 라인만 수정. 인접 코드 임의 개선·리팩터·기존 dead code 삭제 금지(발견 시 보고만).
4. **Goal-Driven Execution** — 검증 가능한 성공 기준 정의 후 통과까지 반복. 다단계는 `단계 → 검증` 계획 명시.

## 작업 문서 (docs/ 하위 working 파일)
| 파일 | 작성 | 내용 |
|---|---|---|
| `docs/plan.md` | Claude | 요구사항·설계·범위·수용 기준 |
| `docs/exec-plan.md` | Claude | 승인된 Task 목록(구현 단위, 의존성, 검증 방법) |
| `docs/progress.md` | Claude | Task별 구현 진행·결과·미해결 이슈 |

템플릿: [docs/templates/](docs/templates/)

## 권장 모델 구성
| 단계 | 담당 | 기본 모델 |
|---|---|---|
| 계획 | Claude | claude-opus-5 |
| 구현 | Claude | claude-sonnet-5 |
| 검증 | Claude | claude-sonnet-5 |
| 고위험 검증(보안·권한·DB·인프라·대규모) | Claude | claude-opus-5 |
| Git 작업 | Claude | claude-haiku-4.5 |
| 코드 리뷰 | Claude | claude-opus-5 |

## 검증 방법
```bash
cd backend  && .venv/bin/python -m pytest -q   # 444개. 외부 환경 불필요(SQLite+fake)
cd frontend && npm run build                    # vue-tsc 타입체크 + 빌드
```
- 배포 확인: `curl -sk -H 'Host: www.dt-hpc.net' https://127.0.0.1:9443/` → 200,
  `/api/v1/clusters` → 401(미인증 정상). **공인 IP로는 hairpin NAT 때문에 안 닿는다.**
- **이미지 빌드 뒤에는 반드시 `docker builder prune -af`.** 캐시와 apptainer 캐시가 쌓여
  dev01이 DiskPressure에 걸리고 포털 pod이 evict된 사고가 있었다(progress.md 참조).
  SIF 변환 시 `APPTAINER_TMPDIR`·`APPTAINER_CACHEDIR`을 둘 다 `/home` 아래로 돌린다.
- 정적 프로토타입(`design/`) 검증 패턴은 notes.md 참조 — 지금은 쓰지 않는다.

## 프로젝트 전용 서브에이전트 (.claude/agents/)
Claude의 검토·검증을 돕는 에이전트. Agent 툴로 호출한다.
| 에이전트 | 용도 |
|---|---|
| `portal-verifier` | 기계적 검증(pytest·타입체크·계층 규칙·코드↔문서 정합성) 실행·보고 |
| `portal-reviewer` | 변경을 정의서·구조 규칙 대비 검토, 계획 이탈·고위험 신호 지적 |
