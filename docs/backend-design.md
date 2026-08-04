# Backend 설계 문서 — Slurm HPC Portal

FastAPI 기반 백엔드의 아키텍처·외부 연동·권한·인프라 설계를 정리한다.
프론트/기능 SoT는 [정의서.md](../정의서.md), 연동 경계는 정의서 §4.1(C-03) 참조. 본 문서는 그 백엔드 대응 설계다.

> 상태: 설계(구현 전). 값·수치는 결정 사항이며, 미확정 항목은 §9에 명시.

---

## 1. 아키텍처 개요

### 1.1 스택 · 스타일
- **런타임**: FastAPI (JSON API 전용, View 계층 없음 → MVC 아님)
- **아키텍처**: **Layered Architecture** — `router → service → repository/client`
- **규모 판단**: **모듈러 모놀리스(Modular Monolith)**. MSA 아님(독립 배포·DB 소유권 분리·네트워크 경계 기준 미충족). 단일 배포 단위 안에서 도메인 모듈로 분리.
- **프론트**: Vue + Nginx 정적 서빙(별도 컨테이너). 백엔드는 순수 API.

### 1.2 계층 책임
| 계층 | 역할 | 비고 |
|---|---|---|
| `router` | HTTP 엔드포인트(Controller). 요청 검증(schema)·인가(Depends)·응답 직렬화 | 비즈니스 로직 금지 |
| `service` | 비즈니스 로직. 여러 repository/client 조합(Composition) | 트랜잭션 경계 |
| `repository` | 테이블별 CRUD (ORM 모델) | DB 접근 캡슐화 |
| `client` | 외부 REST/LDAP 클라이언트 (AD, Slurmrestd) | 외부 연동 캡슐화 |

### 1.3 패키지/모듈 구조
```
app/
  routers/       # FastAPI endpoint (Controller)
  services/      # 비즈니스 로직 (Repository/Client 조합)
  repositories/  # 테이블별 CRUD (ORM)
  models/        # SQLAlchemy ORM 모델 (DB 테이블 매핑)
  schemas/       # Pydantic 모델 (요청/응답 검증, DTO)
  clients/       # 외부 API 클라이언트 (AD, Slurm, SCP Billing, FlexLM)
  db/            # DB 커넥션/세션 관리
  core/          # 설정, 인증/인가, 스케줄러
  jobs/          # 배치 작업 스크립트
```
- 패키지(폴더) = 상위, 모듈(.py) = 하위. 규모 확장 시 도메인별 서브패키지로 분화(`repositories/user/`, `services/billing/`).

### 1.4 모듈 간 관계 · DI
- **Service ↔ Repository/Client**: `has-a`(Composition/DI). 상속 아님.
- **BaseHttpClient ↔ REST client(SlurmrestdClient·ScpBillingClient)**: `is-a`(상속) — REST 공통(base URL·타임아웃·재시도·keep-alive 세션·상태코드→예외 매핑)을 slurmrestd·SCP Billing API 두 client가 공유. **AdClient(LDAP)·SshClient(SSH)는 프로토콜이 다르고 구현체가 각 1개라 베이스 없이 단독**(투기적 추상화 배제). 클래스 상세는 [Architecture.md](Architecture.md).
- FastAPI `Depends`로 의존성 주입. 조합 로직 명칭(참고): 병렬 조합=Aggregator, 순차 조율=Orchestrator, 단일 인터페이스 은닉=Facade, DDD=Application Service.

---

## 2. 외부 연동 (Slurmrestd · AD)

> 정의서 §4.1(C-03): **slurmrestd(REST) 주 경로 + SSH/SFTP 보조**. 본 절은 REST/LDAP 중심. 파일(U-FM)·터미널(U-SH)·인터랙티브(U-IA)의 SSH/SFTP는 별도 client로 분리.

### 2.1 연결(세션) 유지 전략 — 호출 빈도 기준
| 대상 | 호출 빈도 | 전략 |
|---|---|---|
| **Slurmrestd** | 반복적, 대다수 기능 의존 | **keep-alive 커넥션 유지** — 앱 lifespan 동안 재사용 (Singleton-scoped Client + Connection Pooling) |
| **AD 사용자 조회** | 시간당 1회·관리자 수동 | **매 요청 open/close** — 재사용 이점 적고 미관리 자원 배려 |
| **AD 로그인 bind** | 사용자수 × 로그인빈도 | **재사용 불가** — 사용자별 자격증명이 다르므로 매번 새 bind |
| **DB Session** | 매 요청 | **매 요청 open/close**(트랜잭션 격리, 원칙 불변) |

- HTTP client는 트랜잭션 개념이 없어 커넥션 재사용이 성능상 유리. "커넥션 재사용"과 "인증(JWT)"은 별개 문제.

### 2.2 Slurmrestd 인증 (JWT)
- **전송**: `X-SLURM-USER-TOKEN` 헤더에 JWT.
- **발급**: `scontrol token username=$USER lifespan=<초>` (기본 1800s). `lifespan=infinite` 가능하나 관리자 정책상 제한될 수 있음. slurmrestd에 **자동 갱신 API 없음**(재발급만).
- **외부 소유 클러스터**(scontrol/서명키 접근 불가): **관리자가 발급한 JWT를 포털에 등록받아 사용**. → 클러스터 등록 폼의 JWT 서명 키/토큰 입력과 연결(프론트 clusters.html).
- **만료 대응**(자동 갱신 불가):
  - JWT `exp` 클레임을 `verify_signature=False`로 디코드해 만료 시각 파악.
  - 만료 임박 시 스케줄러가 **다단계 임계값 사전 알림**(Slack/이메일).
  - 만료 후 **401 감지 → 재등록 안내**(반자동 플로우).
- **무중단 교체**: JWT는 stateless → 복수 토큰 동시 유효. 기존 만료 전 새 토큰 미리 등록으로 공백 없이 교체.
- **클러스터별 독립 slurmdbd**(정의서 확정): 토큰·엔드포인트·association을 **클러스터마다 독립 관리**. client는 클러스터 단위로 구성.

### 2.3 사용자 위임 (Impersonation)
- 관리자(SlurmUser/root) JWT + `X-SLURM-USER-NAME` 헤더로 실제 AD 사용자를 대리 실행.
- sacct 등 Slurm 기록은 `X-SLURM-USER-NAME`의 실제 사용자 기준.
- **보안(중요)**: 관리자 토큰 = "누구로든 위장 가능한 마스터키". **포털이 서버 사이드에서 AD 인증된 본인 username만 채워 넣도록 강제** — 클라이언트가 임의 사용자명 지정 불가. (정의서 §4.1 "제한적 sudo impersonation"과 동일 원칙)

### 2.4 AD ↔ Slurm 사용자명 매핑
- 클러스터가 SSSD로 AD 연동 시 AD username과 Slurm 노드 인식 username이 동일 소스.
- **SSSD 기본값 `sAMAccountName`**(UPN은 커스텀·접미사 분리 이슈). 포털도 인증 시 `sAMAccountName` 기준 통일 → **별도 매핑 테이블 불필요**.
- 확인 필요(§9): 대소문자 정규화(소문자 통일), UID/GID 매핑(RFC2307 vs SID 자동매핑) 일관성.

---

## 3. 사용자 / 권한 관리

> 정의서 C-01(인증)·C-02(권한). 이번 세션 확정: **인증=AD, 역할=포털 authZ 테이블**(AD 그룹/스키마 미변경).

### 3.1 역할 분담
| 영역 | 담당 |
|---|---|
| 인증(비밀번호 확인) | AD |
| ID/기본정보(sAMAccountName, displayName) | AD |
| 권한/역할(role, permission) | **포털 자체 DB** |

### 3.2 사용자 식별자 — PK 설계 (핵심)
- **문제**: `sAMAccountName`은 도메인 내 유일하나 **변경 가능·삭제 후 재사용 가능**. 재사용 시 이름만으로 매칭하면 신규 입사자가 전임자 role을 물려받는 **보안 사고** 위험.
- **해결**: **`objectGUID`를 PK**로 사용 — AD가 객체 생성 시 부여하는 전역 고유·불변 식별자(128비트). 이름 변경/이동에도 불변, 삭제 후 재생성 객체는 **새 GUID** → 자동으로 "다른 사람" 판별.

```python
class User(Base):
    ad_object_guid = Column(String(36), primary_key=True)   # 불변 정체성 (PK)
    username       = Column(String, unique=True, index=True) # sAMAccountName (로그인/Slurm 연동용)
    display_name   = Column(String)
    role           = Column(String, default="viewer")
    is_active      = Column(Boolean, default=True)
    deleted_at     = Column(DateTime, nullable=True)          # soft delete
```

- **로그인 로직**: `objectGUID`로 조회 → 없으면 신규 생성. username만 다르면 **개명 처리(role 유지)**, GUID가 다르면 **재사용 계정으로 판단해 신규 프로비저닝**.
- 외부 연동(Slurm `X-SLURM-USER-NAME`, JWT `sub`)은 계속 `username`(sAMAccountName) 사용.
- 정의서 C-02의 "`ad_id → role` authZ 테이블"에서 `ad_id` = `objectGUID`.

### 3.3 계정 동기화
- **트리거 1 — 최초 로그인(JIT Provisioning)**: 포털 DB에 없으면 기본 role(viewer)로 자동 생성. (정의서 A-US-01 "AD 자동 프로비저닝, 승인 없음"과 정합)
- **트리거 2 — 주기적 배치 동기화**: 삭제/비활성 감지·정보 최신화.
  - AD 조회 결과 없음 → **soft delete**(`is_active=False`, `deleted_at`). 이력/FK 무결성 보존, 오탐 복구 위해 hard delete 지양.
  - **AD 조회 실패(네트워크 장애) ≠ "진짜 삭제"** 구분 필수 — 실패 시 삭제 처리하지 않고 스킵.
  - objectGUID 불일치 → 재사용 판단, 재프로비저닝.
- 화이트리스트(사전 승인) vs JIT는 포털 민감도에 따라 선택 → 현재 정의서는 **허용 그룹(HPC-Users) 필터 + JIT**.

### 3.4 권한 체계 (RBAC → Permission 확장 대비)
- **1단계(현재)**: 단순 Role 기반 — **Role은 `USER`·`ADMIN` 2종, Permission은 `admin:access`(ADMIN 페이지/기능 접근 가능 여부) 1개**(ADMIN에만 부여, USER는 미보유). role-permission 매핑을 **코드 상수(dict)** 로.
- **2단계(확장)**: Role 추가(예: 그룹장 PI — 정의서 §1.2 v2 검토) 및 Permission을 `resource:action`(`job:read`, `job:cancel`)으로 세분화, DB 테이블(`Role`, `Permission`, `RolePermission` N:M)에 **행 추가만으로** 수용.
- **핵심 원칙**: 라우터는 **처음부터 permission 기반 문법**으로 작성 → 내부 구현만 dict→DB로 교체 시 라우터 무수정.

```python
@router.delete("/slurm/jobs/{job_id}")
async def cancel_job(job_id: str, user=Depends(require_permission("job:cancel"))):
    ...
```
- **FastAPI OAuth2 Scopes 미사용 권장** — 서드파티 세분화 인가용이라 내부 포털엔 오버스펙. 커스텀 `Depends` 기반 role/permission 체크가 실무적.

### 3.5 인가 메커니즘 — Depends
- 라우터 실행 **전** 훅. 실패 시 라우터 미호출·즉시 응답.
- 중첩 가능(의존성 체인). 공통 인증(로그인 여부)은 **라우터 그룹 레벨**(`APIRouter(dependencies=[...])`)로 묶고, 세부 permission은 API별 지정.
- **Middleware 대신 Depends**: API별 상이한 권한을 Middleware로 다루면 URL-permission 매핑을 별도 관리 → 라우터와 분리되어 동기화 깨짐. Middleware는 CORS·로깅 등 전역 공통에 한정.

### 3.6 최초 관리자 부트스트랩
- 정의서 C-02: **최초 실행 setup(최초 AD 연결 설정 화면, 1회용 토큰·로컬 접근 보호)에서 AD 연결·검증 후 첫 ADMIN 1명 seed**. 로컬 비밀번호 미저장. seed 후 정상 RBAC.
- **프론트 분기용 상태 확인**: `AuthService.is_bootstrapped()`(`ad_connection.seed_admin_guid` 존재 여부) → `GET /auth/setup-status`(공개)로 노출. Vue 라우터가 이 값으로 최초 설정 화면/로그인 화면을 분기. `bootstrap_required=false` 이후 `POST /auth/setup`은 서버측에서 하드 거부(재실행 불가, 1회용 잠금).

---

## 4. 인증 / 세션 / 캐싱 (Redis)

### 4.1 Redis 용도
| 대상 | 목적 |
|---|---|
| Role-Permission 매핑 | DB 조회 최소화(거의 불변, TTL 캐싱 + 변경 시 명시적 무효화) |
| 세션/JWT 상태 | JWT "발급 후 무효화 불가" 한계 보완 — 강제 로그아웃/비활성 즉시 반영 |

**세션 키 = 난수 세션 ID(sid)** — username을 키로 쓰지 않는다.

`sAMAccountName`은 변경·재사용될 수 있어(§3.2) `session:{username}`을 키로 삼으면, 이름이 재사용됐을 때 **옛 소유자의 유효한 JWT가 동명이인의 세션에 올라탄다**(서명도 유효하고 세션도 존재하므로 통과한다). 신원을 JWT 클레임이 아니라 **세션 레코드**에서 읽으면 이 경로가 구조적으로 사라진다. 부수 효과로 기기별 개별 로그아웃도 가능해진다.

```python
# 로그인: 세션을 먼저 만들고 그 sid를 토큰에 담는다
sid = secrets.token_urlsafe(32)
r.setex(f"session:{sid}", ttl, json.dumps({"guid": user.ad_object_guid, "username": user.username}))
r.sadd(f"user_sessions:{user.ad_object_guid}", sid)   # 강제 로그아웃용 역인덱스
r.expire(f"user_sessions:{user.ad_object_guid}", ttl)
token = jwt.encode({"sid": sid, "sub": username, "guid": guid, "role": role, ...})

# 요청마다: JWT 서명 검증 → sid로 세션 조회 → **세션의 guid로** 사용자 로드
session = r.get(f"session:{payload['sid']}")
if session is None:
    raise HTTPException(401, "세션이 만료되었거나 로그아웃되었습니다")
user = users.get_by_guid(json.loads(session)["guid"])   # sub(username)로 조회하지 않는다

# 로그아웃(해당 기기만) / 강제 로그아웃(전 세션)
r.delete(f"session:{sid}")
for s in r.smembers(f"user_sessions:{guid}"): r.delete(f"session:{s}")
```

- JWT의 `sub`·`guid`·`role`은 **로그·디버깅용 부가 정보**이며 인가 판단에 쓰지 않는다. 권한은 항상 DB/`PermissionCache` 조회로 결정한다.
- 비활성화(`is_active=False`) 시 `revoke_all(guid)`로 기존 세션을 즉시 끊는다.

### 4.2 K8s 멀티 replica 고려
- Pod 로컬 메모리 캐시/세션 **금지**(Pod별 상태 불일치). Redis 등 공유 스토어 사실상 필수.

---

## 5. 배포 / 인프라

### 5.1 CI/CD
- **GitHub Actions**만으로 build-test → deploy 충분(Jenkins 불필요).
- AWS 배포 시 **OIDC 기반 인증** 권장(장기 키 지양).
- Helm 배포는 ArgoCD 없이 `helm upgrade --install`로 가능(소규모/단일 클러스터). GitOps(ArgoCD)는 멀티 클러스터·drift 감지·자동 sync 필요 시 도입.

### 5.2 컨테이너 / 오케스트레이션
- Backend(FastAPI) + Frontend(Vue+Nginx) 모두 컨테이너 → K8s 배포.
- Docker(이미지 빌드)와 Helm(배포 정의)은 계층이 다른 개념, 함께 사용.
- Frontend Ingress: **Traefik**(K8s Ingress 또는 Traefik `IngressRoute` CRD).
- **인터랙티브 세션 동적 라우트(§7)**: Traefik이 백엔드의 `/internal/gateway/dynamic-config`를 HTTP provider로 폴링하도록 설정 — K8s Service/Endpoints/IngressRoute·RBAC 불필요(pull 방식). 폴링 엔드포인트는 공유 시크릿 또는 네트워크 정책으로 Traefik만 접근하도록 제한(§9).

### 5.3 데이터베이스 (MySQL)
- **소규모 권장**: RDS 단일 인스턴스 + 자동 백업(Multi-AZ는 비용 2배, 초기 불필요).
- K8s 내 이중화(Percona XtraDB / Oracle MySQL Operator)는 소규모엔 오버엔지니어링.
- **K8s 내 단일 Pod 운영 시 필수**:
  - StatefulSet + 네트워크 스토리지(PVC, 로컬 스토리지 지양)
  - Liveness probe로 데몬 재시작 자동화
  - 정기 백업(CronJob → S3) 별도 필수 구현
  - PVC `reclaimPolicy: Retain`

### 5.4 Redis (K8s 내 배포)
- 캐시/세션 용도면 데이터 유실 허용 가능 → 이중화 필요성 낮음.
- 소규모: 단일 Pod + Deployment(또는 StatefulSet), 필요 시 AOF 영속성.
- 관리형(ElastiCache) 전환 고려 가능(MySQL 대비 직접 운영 부담 낮음).

### 5.5 배치 작업 (AD 동기화)
- **K8s 외부 의존 회피**: 애플리케이션 내장 스케줄러(**APScheduler**).
- **멀티 replica 중복 실행 방지**: Redis 분산 락(`SET key value NX EX timeout`).

```python
@contextmanager
def redis_lock(key, timeout=300):
    acquired = r.set(key, "locked", nx=True, ex=timeout)
    try:
        yield acquired
    finally:
        if acquired:
            r.delete(key)
```
- (K8s CronJob이 더 표준적이나, 본 프로젝트는 **포털 내부 구현**으로 결정.)

---

## 6. 데이터 모델 (초안)

핵심 테이블(확장 대비 골격). 상세 스키마는 구현 시 마이그레이션으로 확정.

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `user` | `ad_object_guid`(PK), `username`(uniq), `display_name`, `role`, `is_active`, `deleted_at` | §3.2 |
| `role` / `permission` / `role_permission` | (2단계) `resource:action` 매핑 N:M | §3.4, 1단계는 dict |
| `cluster` | `id`, `name`(ClusterName), `slurmrestd_url`, `api_version`, `auth`, `login_node`, `ssh_port`, 경로 템플릿 | 클러스터별 독립 slurmdbd |
| `cluster_secret` | 클러스터 JWT/SSH 개인키 (Secret 저장소 참조) | 값은 DB에 평문 저장 금지 |
| `notice` / `job_template` / `ticket` / `audit_log` | Portal DB 고유 데이터 | 정의서 §4.1 ③ |

- **Secret 취급**: AD Bind 암호·Slurm JWT·SSH 개인키는 **Secret 저장소(암호화)** 에 보관, DB엔 참조만. 화면 재표시 안 함(정의서 반영과 동일).
- 모든 제어성 액션은 **감사 로그(C-05)** 기록.

---

## 7. 연동 경로 매핑 (정의서 §4.1 대응)
- **REST(slurmrestd)**: Job 제출/조회/제어, 노드/파티션/예약, 계정/QOS/association, 사용량 → `clients/slurm`.
- **SSH/SFTP**: 파일 관리(U-FM)·웹 터미널(U-SH) → `clients/ssh`(서비스 계정 + 키, 제한 sudo impersonation). **인터랙티브 세션(U-IA)의 sbatch 제출은 REST**, 세션 접속 트래픽은 아래 K8s API 경로(SSH 아님, §1 참조).
- **LDAP**: 인증 bind·사용자 조회 → `clients/ad`.
- **FlexLM(lmutil, TCP 직접)**: 라이선스 서버 조회(A-LM-01·02·05) → `clients/license` — SSH 아님, 클러스터 무관 독립 client. A-LM-03(Slurm 반영)만 대상 클러스터의 `clients/slurm` 경유.
- **Traefik HTTP provider(폴링)**: 인터랙티브 세션 접속 게이트웨이(U-IA-01~05) — 별도 client 없이 `services/gateway`가 세션 상태(DB)만 관리, Traefik이 `/internal/gateway/dynamic-config`를 주기 폴링해 라우트를 직접 구성(pull 방식, K8s API·RBAC 불필요). 실제 세션 트래픽은 Traefik→컴퓨트 노드 직결, FastAPI 미경유(Open OnDemand Apache 프록시 모듈과 동일 패턴).
- **기타**: 메트릭(Prometheus)·알림(SMTP/Webhook)·Portal DB.

---

## 8. 결정 로그 (근거 요약)
- **objectGUID PK**: sAMAccountName 재사용에 의한 권한 상속 사고 방지(불변 식별자).
- **Slurm keep-alive / AD open-close**: 호출 빈도 기반. 트랜잭션 없는 HTTP는 재사용 유리, 저빈도 LDAP는 미관리 자원 배려.
- **JWT 등록 + 401 반자동 재등록**: 외부 소유 클러스터라 scontrol/서명키 접근 불가, 자동 갱신 API 부재.
- **Depends 기반 permission**: API별 권한을 라우터와 결합해 동기화 깨짐 방지. Scopes/Middleware 지양.
- **Redis 세션 보조**: stateless JWT의 강제 무효화 한계 보완 + 멀티 replica 일관성.
- **모듈러 모놀리스 / GHA / 단일 RDS**: 현재 규모에 MSA·ArgoCD·Multi-AZ는 오버엔지니어링.

---

## 9. 미확정 / 확인 필요
- SSSD username 대소문자 정규화 정책, UID/GID 매핑(RFC2307 vs SID) 일관성 (§2.4).
- JWT `lifespan` 정책(외부 클러스터 관리자와 합의), 만료 알림 임계값 단계.
- 화이트리스트 vs JIT 최종(현재 허용 그룹 + JIT).
- 파일/터미널/인터랙티브의 SSH 서비스 계정 sudoers 최소 권한 범위 (정의서 §4.1).
- Secret 저장소 구체(K8s Secret / Vault / SCP Secret Manager 등).
- Redis 영속성(AOF) 필요 여부, 세션 TTL 정책.
- **인터랙티브 세션 게이트웨이 폴링 보호**: `/internal/gateway/dynamic-config`를 Traefik만 호출하도록 공유 시크릿 헤더 vs 네트워크 정책 중 선택, Traefik 폴링 주기(지연-부하 트레이드오프)(§5.2, §7).
- **`sbatch --test-only` REST 동등 기능**: slurmrestd v0.0.41에 대기시간 예측(U-JB-12) 지원 여부 확인 필요 — 없으면 CLI(SSH) 폴백.
- **클러스터 간 비교 추천 기능**: "선택된 클러스터 스코프" 원칙과의 배치 여부 재검토(api.md §미결).
