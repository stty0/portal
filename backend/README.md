# Backend — Slurm HPC Portal

FastAPI 기반 포털 백엔드. 설계 근거: [../docs/backend-design.md](../docs/backend-design.md), 기능 SoT: [../정의서.md](../정의서.md).

> **현재 상태**: 실 클러스터(slurm01·slurm02)에 연동되어 동작 중. 인증/사용자·AD·클러스터·
> Job·노드·QOS·계정·파일·터미널·인터랙티브 세션·사용량·리포트·Billing·운영 설정까지 구현했다.
> **미구현은 License(A-LM 전부)와 헬프데스크 티켓(A-OP-05·U-AC-04)뿐이다.**
> 엔드포인트 단위 구현 여부는 [../docs/api.md](../docs/api.md)의 취소선 표기를 본다.

## 아키텍처
- **스타일**: Layered — `router → service → repository/client` (backend-design §1.2)
- **규모**: 모듈러 모놀리스(단일 배포 단위, 도메인 모듈 분리) (§1.1)
- **API 전용**: View 계층 없음, 순수 JSON API

계층 방향은 문서가 아니라 [tests/test_layering.py](tests/test_layering.py)가 강제한다(라우터→repository/client 직접 호출 금지 등).

## 실행

MySQL·Redis는 k3s에 배포돼 있다 — [../deploy/k8s/](../deploy/k8s/) 참조(네임스페이스 `hpc-portal`, NodePort 30306/30379).

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"

set -a && . ./.env.dev && set +a        # DB/Redis/JWT/setup 토큰 (자격증명 포함, gitignore됨)

.venv/bin/alembic upgrade head          # 20개 테이블(+alembic_version) + RBAC seed
.venv/bin/python scripts/seed_dev.py    # 개발용 예시 데이터 (멱등, --reset 지원)
.venv/bin/uvicorn app.main:app --reload # http://localhost:8000/docs
```

`.env.dev`가 없다면 [../deploy/k8s/README.md](../deploy/k8s/README.md)의 "접속 정보 확인"으로 다시 만든다.
Secret 저장소(`EnvSecretStore`)가 읽는 값은 별도 환경변수다 — `seed_dev.py` 실행 시 필요한 이름이 출력된다.

테스트는 외부 환경이 필요 없다(SQLite in-memory + fake Redis/AD/slurmrestd):

```bash
.venv/bin/pytest        # 261 tests
```

## 최초 기동 절차 (C-02)
1. `GET /api/v1/auth/setup-status` → `bootstrap_required: true`
2. `POST /api/v1/auth/setup` — AD 연결 정보 + `setup_token` + seed ADMIN으로 지정할 AD 사용자명.
   AD에서 해당 사용자를 실제로 조회해 검증한 뒤 ADMIN 1명을 seed한다.
3. 이후 `POST /auth/setup`은 서버가 하드 거부한다(1회용 잠금). 정상 AD 로그인으로 전환.

## 패키지 구조 (`app/`)
| 패키지 | 역할 | 근거 |
|---|---|---|
| `routers/` | HTTP 엔드포인트(Controller). 요청 검증·인가(Depends)·응답 직렬화. 비즈니스 로직 금지 | §1.2 |
| `services/` | 비즈니스 로직. repository/client 조합(Composition). 트랜잭션 경계 | §1.2 |
| `repositories/` | 테이블별 CRUD(ORM). DB 접근 캡슐화 | §1.2 |
| `models/` | SQLAlchemy ORM 모델 — db-erd.md의 포털 소유 **20개 엔티티와 1:1** | §1.3, ERD |
| `schemas/` | Pydantic 요청/응답 검증(DTO) | §1.3 |
| `clients/` | 외부 연동 — `base_http`(REST 공통) → `slurm`, `ad`(LDAP), `factory`(클러스터별 풀링), `token_provider` | §1.3, §7 |
| `db/` | DB 커넥션/세션 관리 (요청별 open/close) | §1.3, §2.1 |
| `core/` | 설정·오류·인증/인가(`require_permission`)·Redis·Secret | §3.5, §4 |
| `jobs/` | 배치 작업 (AD 동기화, APScheduler + Redis 분산락) | §3.3, §5.5 |

## 설계상 지켜지는 것들
- **신원**: `user` PK = `ad_object_guid`(불변). 개명은 role 유지, sAMAccountName 재사용은 별인으로 판별(§3.2·§3.3).
- **인가**: 라우터는 항상 `require_permission("admin:access")` 문법. permission 세분화 시 라우터 무수정(§3.4).
- **세션**: JWT 서명 + Redis 세션 존재 + 토큰 `guid`↔사용자 대조. 강제 로그아웃이 즉시 반영된다(§4.1).
- **Impersonation**: `X-SLURM-USER-NAME`은 서버가 인증된 본인으로만 채운다. 제출 API 스키마에 사용자명 필드가 **없다**(§2.3).
- **Job 스코프**: USER는 본인 Job만. 남의 Job은 403이 아니라 404로 응답해 존재 여부를 숨긴다.
- **Secret**: JWT·SSH 키·AD bind 암호는 `SecretStore`에만. DB엔 `secret_ref`, 응답·감사 로그엔 값이 없다(§6).
- **감사**: 제어성 액션만 `audit_log`에 기록(C-05). 조회는 기록하지 않는다.

## 데이터 소유권 경계
Portal DB(MySQL)는 **포털 고유 데이터**(RBAC·클러스터 등록/시크릿 참조·AD 설정·공지/티켓/감사·Billing)만 소유.
Slurm 기능 데이터(account·QOS·association·Job)는 **클러스터별 slurmdbd**에 있으며 `clients/slurm`(slurmrestd)로 접근 — Portal DB 스키마 아님. (ERD [../docs/db-erd.md](../docs/db-erd.md))

## 알려진 제약
- `EnvSecretStore.put()`은 프로세스 내 오버레이라 **멀티 replica 간 공유되지 않는다**. Secret 저장소 구체는 backend-design §9 미확정 — 확정 시 `SecretStore` 구현체 하나만 교체하면 된다.
- slurmrestd v0.0.41 응답은 **실물로 검증했다**. 어댑터(`_as_job_list` 등)가 방어적으로 파싱하는 것은 유지한다 — 버전별 형태 차이를 흡수한다. 실측으로 확인한 특성: `#SBATCH`는 REST 제출에서 무시되고, `environment`는 통째로 교체되며(HOME 누락 주의), 한도는 `{set, infinite, number}` 삼중항으로 온다.
- 파일 브라우저·조작(U-FM-01·02·04), 웹 터미널(U-SH-01), 인터랙티브 세션(U-IA-01·02·04)은 **SSH/SFTP 경로로 구현됐다**. 미구현은 파일 편집(U-FM-03)·로그 tail(U-JB-06)·컴퓨트 노드 터미널(U-SH-02).
- **로그인 노드 → 워커 구간이 평문**이다(세션 RFB). 지금은 두 노드가 같은 기계라 loopback이지만 분리 전에 재검토해야 한다 → [../docs/session-transport-security.md](../docs/session-transport-security.md).
