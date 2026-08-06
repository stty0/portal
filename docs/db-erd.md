# DB 모델 ERD — Slurm HPC Portal (Portal DB)

포털 백엔드가 소유하는 **Portal DB(MySQL)** 의 엔티티 관계도. 설계 근거는 [backend-design.md](backend-design.md), 기능 SoT는 [정의서.md](../정의서.md).

> **경계(중요)**: Slurm의 **account·QOS·association·slurm user 는 각 클러스터의 `slurmdbd`(외부)에 존재**하며 `slurmrestd`로 접근한다 — **Portal DB 테이블이 아니다**(클러스터별 독립 slurmdbd). **session·role-permission 캐시·동기화 분산락은 Redis** 관리로 DB 밖이다. 아래 ERD는 포털이 직접 소유하는 테이블만 포함한다.

---

## 1. ERD (PlantUML)

```plantuml
@startuml portal-db-erd
hide circle
skinparam linetype ortho
skinparam shadowing false
skinparam roundcorner 6
title Slurm HPC Portal — Portal DB (MySQL)

' ===== 신원 & 인가 (C-01 / C-02) =====
entity "user" as user {
  *ad_object_guid : CHAR(36) <<PK>>
  --
  *username : VARCHAR(64) <<UNIQUE>>   ' sAMAccountName
  display_name : VARCHAR(128)
  email : VARCHAR(256)
  role_id : INT <<FK>>
  default_cluster_id : INT <<FK,NULL>>
  is_active : BOOL
  notify_prefs : JSON                  ' 알림 수신 설정(이메일/푸시/SMS, U-AC-03)
  last_login_at : DATETIME
  deleted_at : DATETIME <<NULL>>       ' soft delete
  created_at : DATETIME
  updated_at : DATETIME
}

entity "role" as role {
  *id : INT <<PK>>
  --
  *code : VARCHAR(32) <<UNIQUE>>       ' 초기 USER·ADMIN 2행(향후 추가 가능, 예: PI)
  name : VARCHAR(64)
  description : VARCHAR(255)
}

entity "permission" as perm {
  *id : INT <<PK>>
  --
  *code : VARCHAR(64) <<UNIQUE>>       ' 초기 admin:access 1행 → resource:action 세분화(job:cancel 등)
  description : VARCHAR(255)
}

entity "role_permission" as rp {
  *role_id : INT <<PK,FK>>
  *permission_id : INT <<PK,FK>>       ' 초기 ADMIN→admin:access 1행
}

' ===== 클러스터 & 시크릿 (C-03 / A-CL) =====
entity "cluster" as cluster {
  *id : INT <<PK>>
  --
  *name : VARCHAR(64) <<UNIQUE>>       ' slurm.conf ClusterName
  description : VARCHAR(255)
  slurmrestd_url : VARCHAR(255)
  api_version : VARCHAR(16)            ' v0.0.41
  auth_method : VARCHAR(16)            ' jwt / munge
  login_node : VARCHAR(128)           ' SSH (웹터미널·SFTP 공용)
  ssh_port : INT                      ' 기본 22
  ssh_account : VARCHAR(64)           ' 서비스 계정 (제한 sudo)
  group_path_tpl : VARCHAR(255)       ' /group/{group}
  scratch_path_tpl : VARCHAR(255)     ' /scratch/{user}
  is_default : BOOL
  is_active : BOOL
  last_health_at : DATETIME           ' A-CL-01 마지막 헬스체크 (NULL=미확인)
  last_health_ok : BOOL               ' 마지막 REST 연결 결과
  created_at : DATETIME
  updated_at : DATETIME
}

entity "cluster_credential" as ccred {
  *id : INT <<PK>>
  --
  *cluster_id : INT <<FK>>
  kind : VARCHAR(16)                   ' SLURM_JWT / SSH_KEY
  secret_ref : VARCHAR(255)            ' Secret 저장소 참조(값 평문 저장 금지)
  expires_at : DATETIME <<NULL>>       ' JWT exp (만료 알림용)
  created_at : DATETIME
}

' ===== AD 연결 (A-US-01, 단일) =====
entity "ad_connection" as ad {
  *id : INT <<PK>>                     ' 단일 행
  --
  ldaps_url : VARCHAR(255)
  base_dn : VARCHAR(255)
  bind_account : VARCHAR(128)
  bind_secret_ref : VARCHAR(255)       ' Secret 저장소 참조
  allowed_group : VARCHAR(255)         ' memberOf 필터
  id_attribute : VARCHAR(32)           ' sAMAccountName / uid
  sync_interval : VARCHAR(16)
  last_sync_at : DATETIME
  last_sync_result : VARCHAR(255)
  seed_admin_guid : CHAR(36) <<NULL>>  ' 최초 setup seed
  created_at : DATETIME
  updated_at : DATETIME
}

' ===== 포털 콘텐츠 =====
entity "notice" as notice {
  *id : INT <<PK>>
  --
  title : VARCHAR(255)
  body : TEXT
  target_cluster_id : INT <<FK,NULL>>  ' NULL=전체
  banner_enabled : BOOL
  start_at : DATETIME
  end_at : DATETIME
  created_by : CHAR(36) <<FK>>
  created_at : DATETIME
}

entity "job_template" as tpl {
  *id : INT <<PK>>
  --
  name : VARCHAR(128)
  type : VARCHAR(16)                   ' interactive / batch
  version : VARCHAR(16)
  params : JSON
  is_public : BOOL
  created_by : CHAR(36) <<FK>>
  created_at : DATETIME
  updated_at : DATETIME
}

entity "ticket" as ticket {
  *id : INT <<PK>>
  --
  title : VARCHAR(255)
  body : TEXT
  requester_guid : CHAR(36) <<FK>>
  assignee_guid : CHAR(36) <<FK,NULL>>
  status : VARCHAR(16)                 ' open / in_progress / resolved
  job_id : VARCHAR(32) <<NULL>>
  created_at : DATETIME
  resolved_at : DATETIME <<NULL>>
}

entity "audit_log" as audit {
  *id : BIGINT <<PK>>
  --
  at : DATETIME
  actor_guid : CHAR(36) <<FK>>
  actor_role : VARCHAR(32)
  action : VARCHAR(64)                 ' JOB_SUBMIT / NODE_DOWN ...
  target_cluster_id : INT <<FK,NULL>>
  target : VARCHAR(128)
  detail : VARCHAR(512)
  ip : VARCHAR(45)
}

' ===== Billing (A-BL) =====
entity "billing_config" as bcfg {
  *id : INT <<PK>>                     ' 단일 행
  --
  api_endpoint : VARCHAR(255)          ' https://scp.samsungsdscloud.com
  scp_account_id : CHAR(32)            ' 조회 대상 계정(bills·usages 필터)
  access_key : VARCHAR(128)            ' Scp-Accesskey
  secret_ref : VARCHAR(255)            ' Secret Key 참조 — Scp-Signature 서명용
  collect_interval : VARCHAR(16)
  monthly_alert_krw : BIGINT
  last_verified_at : DATETIME
}

entity "billing_rule" as brule {
  *id : INT <<PK>>
  --
  kind : VARCHAR(16)                   ' billing_item / category / resource_name / region / account
  condition : VARCHAR(255)             ' billing_item_id = OBJECT_STORAGE, resource_name LIKE hpc-*
  mapping_label : VARCHAR(128)         ' archive / staging ...
  is_active : BOOL
  sort_order : INT
}

entity "billing_snapshot" as bsnap {
  *id : BIGINT <<PK>>
  --
  period : CHAR(7)                     ' YYYY-MM
  dimension : VARCHAR(64)              ' tag/type/일자
  cost_krw : BIGINT
  collected_at : DATETIME
}

' ===== 인터랙티브 세션 (U-IA-04, 정의서 §4.1③) =====
entity "interactive_session" as isession {
  *id : INT <<PK>>
  --
  *user_guid : CHAR(36) <<FK>>
  *cluster_id : INT <<FK>>
  app_type : VARCHAR(16)               ' jupyter / vnc / code-server
  slurm_job_id : VARCHAR(32)           ' 백엔드 Job (종료=scancel via REST)
  status : VARCHAR(16)                 ' starting / running / terminated
  node_host : VARCHAR(128)             ' Job 콜백 보고(POST /internal/sessions/{id}/ready)
  node_port : INT
  connect_url : VARCHAR(255)           ' Traefik 동적 라우트 접속 경로
  created_at : DATETIME
  terminated_at : DATETIME <<NULL>>
}

' ===== 포털 운영 설정 (A-OP-04, 단일) =====
entity "portal_setting" as psetting {
  *id : INT <<PK>>                     ' 단일 행
  --
  poll_interval_sec : INT              ' 상태 폴링 주기(C-04 ≤30초)
  session_timeout_min : INT
  smtp_host : VARCHAR(128)
  smtp_port : INT
  smtp_sender : VARCHAR(128)
  webhook_url : VARCHAR(255)
  updated_at : DATETIME
}

' ===== License (A-LM) =====
entity "license_server" as lserver {
  *id : INT <<PK>>
  --
  *name : VARCHAR(64) <<UNIQUE>>
  host : VARCHAR(128)                  ' port@host 의 host
  port : INT
  vendor_daemon : VARCHAR(64)
  collect_interval : VARCHAR(16)       ' lmstat 수집 주기
  is_active : BOOL
  last_check_at : DATETIME
  last_check_result : VARCHAR(255)
  created_at : DATETIME
  updated_at : DATETIME
}

entity "license_feature_snapshot" as lfsnap {
  *id : BIGINT <<PK>>
  --
  *server_id : INT <<FK>>
  feature : VARCHAR(128)
  total : INT
  in_use : INT
  collected_at : DATETIME
}

' ===== 리포트 (A-RP-04·05) =====
entity "report_schedule" as rsched {
  *id : INT <<PK>>                     ' 단일 행
  --
  recipients : VARCHAR(512)            ' 수신자(콤마 구분)
  cycle : VARCHAR(16)                  ' weekly / monthly / quarterly
  format : VARCHAR(8)                  ' pdf / excel / csv
  scope : VARCHAR(32)                  ' 전체 요약 / 계정별 / 사용자별
  is_active : BOOL
  updated_at : DATETIME
}

entity "chargeback_rate" as crate {
  *id : INT <<PK>>
  --
  *resource : VARCHAR(16) <<UNIQUE>>   ' cpu / gpu
  rate_krw : INT                       ' 예: CPU 12원/core·h, GPU 950원/gpu·h
  unit : VARCHAR(16)                   ' core·h / gpu·h
  updated_at : DATETIME
}

' ===== 관계 =====
role ||--o{ user : role_id
role ||--o{ rp
perm ||--o{ rp
cluster |o--o{ user : default_cluster_id
cluster ||--o{ ccred : cluster_id
cluster |o--o{ notice : target_cluster_id
cluster |o--o{ audit : target_cluster_id
user ||--o{ notice : created_by
user ||--o{ tpl : created_by
user ||--o{ ticket : requester_guid
user |o--o{ ticket : assignee_guid
user ||--o{ audit : actor_guid
user ||--o{ isession : user_guid
cluster ||--o{ isession : cluster_id
lserver ||--o{ lfsnap : server_id

' ===== 외부 경계 (Portal DB 아님) =====
package "«external» slurmdbd (클러스터별)" <<Cloud>> {
  entity "slurm account" as sacct #eeeeee
  entity "slurm qos" as sqos #eeeeee
  entity "association\n(cluster,account,user,partition)" as sassoc #eeeeee
}
cluster ..> sacct : slurmrestd (JWT)
note bottom of sassoc
  account·QOS·association·slurm user 는
  slurmdbd 소유 → slurmrestd 로 CRUD.
  사용자↔계정 N:M, 허용/기본 QOS 배정도 여기.
  포털 DB에 미러링하지 않음(필요 시 캐시만).
end note

note as N_redis
  <b>Redis (DB 밖)</b>
  • session:{sid} → {guid, username}  (신원의 정본)
  • user_sessions:{guid} → {sid...}  (강제 로그아웃 역인덱스)
  • rolePerm 캐시 (TTL + 명시적 무효화)
  • sync:lock  (배치 중복 실행 방지)
end note

@enduml
```

---

## 2. 엔티티 설명

### 신원 · 인가
| 테이블 | 목적 | 근거 |
|---|---|---|
| `user` | AD 사용자의 포털 표현. **PK=objectGUID(불변)**, `username`=sAMAccountName(변경/재사용 가능). soft delete. | backend §3.2, C-02 |
| `role` / `permission` / `role_permission` | RBAC. **초기 seed: role 2행(`USER`/`ADMIN`) · permission 1행(`admin:access`=ADMIN 페이지 접근 여부) · 매핑 1행(ADMIN→admin:access)**. 향후 role 추가(예: PI, 정의서 §1.2)·`resource:action` 세분화(`job:cancel` 등)를 **스키마 변경 없이 행 추가**로 수용. 1단계 구현은 코드 dict 가능. | backend §3.4, 정의서 §1.2 |

### 클러스터 · 연동
| 테이블 | 목적 | 근거 |
|---|---|---|
| `cluster` | 등록 클러스터(엔드포인트·API버전·SSH 접속·경로 템플릿·기본 여부). 클러스터별 독립 slurmdbd. | C-03, A-CL, §4.1 |
| `cluster_credential` | 클러스터 JWT/SSH 키의 **Secret 참조 + 만료(exp)**. 값은 Secret 저장소, DB엔 참조만. | backend §2.2, §6 |
| `ad_connection` | 단일 AD 연결 설정 + seed admin. Bind 암호는 Secret 참조. | A-US-01, C-02 |

### 포털 콘텐츠 · 감사 · License · Billing
| 테이블 | 목적 | 근거 |
|---|---|---|
| `notice` | 공지(대상 클러스터 nullable=전체, 배너). | U-CL-03 / A-OP-01 |
| `job_template` | Job/인터랙티브 앱 템플릿(파라미터 JSON). | U-JB-03 / A-OP-02 |
| `interactive_session` | 인터랙티브 앱 세션 메타. `node_host/node_port`는 Job 콜백으로 채워짐 — Traefik이 이 값을 **HTTP provider로 주기 폴링**해 라우트를 직접 구성(K8s API 불필요), `connect_url`은 그 경로를 가리킴. 세션 트래픽은 FastAPI를 거치지 않고 Traefik→컴퓨트 노드 직결. 종료는 REST `scancel` + 상태 변경(다음 폴링에 라우트 자연 소멸). | U-IA-04, Architecture.md §1 |
| `ticket` | 헬프데스크 티켓(요청자/담당자). | U-AC-04 / A-OP-05 |
| `audit_log` | 제어성 액션 감사. | C-05 / A-OP-03 |
| `portal_setting` | 세션 정책(폴링 주기·타임아웃)·알림 채널(SMTP/웹훅). 단일 행. | A-OP-04 |
| `license_server` | FlexLM 서버 등록(host/port·벤더 데몬·수집 주기). `LicenseClient`가 백엔드 내장 lmutil로 **직접 TCP 접속**(SSH 아님, 클러스터 무관). | A-LM-01 |
| `license_feature_snapshot` | lmstat 수집 결과(Feature별 total/in_use). | A-LM-02·05 |
| `report_schedule` | 정기 리포트 발송 설정(수신자·주기·형식·범위). 단일 행. | A-RP-04 |
| `chargeback_rate` | 과금 요율(자원별 원/단위시간). | A-RP-05 |
| `billing_config` | SCP Financial Management API 연동(Python SDK, Access Key + Scp-Signature 서명 · 키는 Secret 참조). | A-BL-01 |
| `billing_rule` | 자원 식별 규칙(billing_item_id·service_category·resource_name·region). SCP 응답에 Tag 없음. | A-BL-02 |
| `billing_snapshot` | 수집 비용(ListUsages 일별·ListBills 월별·결제 상태). | A-BL-03·04 |

---

## 3. 설계 노트
- **objectGUID PK**: sAMAccountName 재사용에 의한 권한 상속 사고 방지. 로그인 시 GUID로 매칭, username만 다르면 개명(role 유지), GUID 다르면 재프로비저닝.
- **Secret 비저장**: AD Bind 암호·Slurm JWT·SSH 개인키·SCP Secret Key는 **Secret 저장소**에 두고 DB엔 `*_ref` 참조만. 화면 재표시 안 함.
- **Slurm 엔티티 외부화**: account/QOS/association은 slurmdbd 소유 → 포털은 slurmrestd로 CRUD, 미러링 없음. 사용자↔계정 N:M, 허용/기본 QOS 배정도 slurmdbd에 반영.
- **단일 행 테이블**: `ad_connection`·`billing_config`·`portal_setting`·`report_schedule`은 현재 단일 행. 다중화 필요 시 FK 확장.
- **RBAC 초기 seed**: role=`USER`·`ADMIN` 2행, permission=`admin:access` 1행(ADMIN에만 매핑). 구조는 N:M 확장 대비이며, role/permission 추가는 스키마 변경 없이 **행 삽입만**으로 가능.
- **Redis 분리**: session/캐시/락은 MySQL 밖(멀티 replica 일관성).

---

## 4. 렌더링 방법
PlantUML 코드 블록을 렌더링해 이미지로 확인:
- VS Code: **PlantUML** 확장(Alt+D 미리보기) — Graphviz 또는 내장 서버 필요
- CLI: `plantuml docs/db-erd.md` (md 내 ```plantuml 블록 추출 지원 버전) 또는 코드만 `.puml`로 저장 후 `plantuml db-erd.puml`
- 온라인: PlantUML 서버(www.plantuml.com/plantuml)에 붙여넣기

> ERD는 설계 초안이다. 컬럼 타입/길이·인덱스·제약은 구현 시 마이그레이션(Alembic 등)에서 확정한다.
