# Backend — Slurm HPC Portal

FastAPI 기반 포털 백엔드. 설계 근거: [../docs/backend-design.md](../docs/backend-design.md), 기능 SoT: [../정의서.md](../정의서.md).

> 현재는 **디렉토리 스켈레톤**만 존재한다(코드 미생성). 각 패키지 용도는 아래 참조.

## 아키텍처
- **스타일**: Layered — `router → service → repository/client` (backend-design §1.2)
- **규모**: 모듈러 모놀리스(단일 배포 단위, 도메인 모듈 분리) (§1.1)
- **API 전용**: View 계층 없음, 순수 JSON API

## 패키지 구조 (`app/`)
| 패키지 | 역할 | 근거 |
|---|---|---|
| `routers/` | HTTP 엔드포인트(Controller). 요청 검증·인가(Depends)·응답 직렬화. 비즈니스 로직 금지 | §1.2 |
| `services/` | 비즈니스 로직. repository/client 조합(Composition). 트랜잭션 경계 | §1.2 |
| `repositories/` | 테이블별 CRUD(ORM). DB 접근 캡슐화 | §1.2 |
| `models/` | SQLAlchemy ORM 모델 (Portal DB 테이블 매핑) | §1.3, ERD |
| `schemas/` | Pydantic 요청/응답 검증(DTO) | §1.3 |
| `clients/` | 외부 연동 클라이언트 (아래 3종) | §1.3, §7 |
| `clients/ad/` | LDAP — 인증 bind·사용자 조회 | §2, §7 |
| `clients/slurm/` | slurmrestd(REST) — Job·노드·QOS·association·사용량 | §2, §7 |
| `clients/ssh/` | SSH/SFTP — 파일(U-FM)·터미널(U-SH)·인터랙티브(U-IA) | §7 |
| `db/` | DB 커넥션/세션 관리 (요청별 open/close) | §1.3, §2.1 |
| `core/` | 설정·인증/인가(`require_permission`)·Redis·스케줄러 | §3.5, §4, §5.5 |
| `jobs/` | 배치 작업 스크립트 (AD 동기화 등, APScheduler) | §3.3, §5.5 |

> 규모 확장 시 도메인별 서브패키지로 분화(`repositories/user/`, `services/billing/`). 1단계는 flat 유지 (§1.3).

## 데이터 소유권 경계
Portal DB(MySQL)는 **포털 고유 데이터**(RBAC·클러스터 등록/시크릿 참조·AD 설정·공지/템플릿/티켓/감사·Billing)만 소유.
Slurm 기능 데이터(account·QOS·association·Job)는 **클러스터별 slurmdbd**에 있으며 `clients/slurm`(slurmrestd)로 접근 — Portal DB 스키마 아님. (ERD [../docs/db-erd.md](../docs/db-erd.md))
