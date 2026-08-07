"""개발용 시드 데이터 (멱등).

`alembic upgrade head` 이후 실행한다. 마이그레이션 0002가 넣는 RBAC seed
(role 2 / permission 1 / 매핑 1)는 **운영에도 필요한 초기 데이터**이고,
이 스크립트는 **개발·데모용 예시 데이터**다 — 운영 DB에 실행하지 않는다.

**사용자를 만들지 않는다.** 사용자의 단일 출처는 AD이며, 포털 사용자는 로그인
시 JIT 프로비저닝 또는 `POST /ad/sync`로만 생긴다(A-US-01). 여기서 가짜 사용자를
넣으면 다음 AD 동기화가 "AD에 없는 사용자"로 판단해 즉시 soft delete 하므로
서로 싸운다. 대신 콘텐츠의 소유자(created_by 등)는 **이미 존재하는 실제 사용자**를
찾아 연결하고, 사용자가 없으면 해당 콘텐츠를 건너뛴다.

**부트스트랩도 완료 처리하지 않는다.** `ad_connection.seed_admin_guid`는 비워 두어
운영자가 실제 `POST /auth/setup` 경로를 타도록 한다(C-02).

사용:
    set -a && . ./.env.dev && set +a
    .venv/bin/python scripts/seed_dev.py [--reset]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory, init_engine
from app.models import (
    AdConnection,
    AuditLog,
    BillingConfig,
    BillingRule,
    BillingSnapshot,
    ChargebackRate,
    Cluster,
    ClusterCredential,
    InteractiveSession,
    LicenseFeatureSnapshot,
    LicenseServer,
    Notice,
    PortalSetting,
    ReportSchedule,
    Role,
    Ticket,
    User,
)

NOW = datetime.now(timezone.utc)

# 개발 AD (dt-hpc.net). bind 암호는 여기 없다 — Secret 저장소(PORTAL_SECRET_AD_BIND).
AD_DEFAULTS = {
    "ldaps_url": "ldap://192.168.1.10:389",
    "base_dn": "DC=dt-hpc,DC=net",
    "bind_account": "sysadmin@dt-hpc.net",
    "bind_secret_ref": "ad/bind",
    "allowed_group": None,  # HPC 전용 그룹 생성 후 지정 (A-US-01)
    "id_attribute": "sAMAccountName",
    "sync_interval": "1h",
}

CLUSTERS = [
    {
        "name": "seoul-hpc",
        "alias": "본원 데이터센터",
        "slurmrestd_url": "http://slurmrestd.seoul.internal:6820",
        "api_version": "v0.0.43",
        "auth_method": "jwt",
        "login_node": "login01.seoul.internal",
        "ssh_port": 22,
        "ssh_account": "svc-portal",
        "is_default": True,
    },
    {
        "name": "pangyo-gpu",
        "alias": "GPU 특화",
        "slurmrestd_url": "http://slurmrestd.pangyo.internal:6820",
        "api_version": "v0.0.43",
        "auth_method": "jwt",
        "login_node": "login01.pangyo.internal",
        "ssh_port": 22,
        "ssh_account": "svc-portal",
        "is_default": False,
    },
]

# --reset이 지우는 대상. **User·AdConnection은 제외** — 사용자는 AD가 소유하고,
# AD 연결 설정은 실제 접속 정보라 여기서 날리면 안 된다.
DEV_TABLES = [
    AuditLog,
    InteractiveSession,
    Ticket,
    Notice,
    LicenseFeatureSnapshot,
    LicenseServer,
    BillingSnapshot,
    BillingRule,
    BillingConfig,
    ChargebackRate,
    ReportSchedule,
    PortalSetting,
    ClusterCredential,
    Cluster,
]


def get_or_create(session, model, defaults=None, **filters):
    row = session.scalars(select(model).filter_by(**filters)).first()
    if row is not None:
        return row, False
    row = model(**filters, **(defaults or {}))
    session.add(row)
    session.flush()
    return row, True


def resolve_users(session) -> tuple[User | None, list[User]]:
    """콘텐츠 소유자로 쓸 실제 사용자를 찾는다 (AD에서 프로비저닝된 것)."""
    users = list(
        session.scalars(select(User).where(User.deleted_at.is_(None), User.is_active.is_(True)))
    )
    if not users:
        return None, []
    admin = next((u for u in users if u.role and u.role.code == "ADMIN"), users[0])
    return admin, users


def seed(session) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    notes: list[str] = []
    if not session.scalars(select(Role)).first():
        raise SystemExit("role 테이블이 비어 있습니다. `alembic upgrade head`를 먼저 실행하세요.")

    owner, users = resolve_users(session)
    if owner is None:
        notes.append(
            "포털 사용자가 없어 사용자 연관 콘텐츠(공지·템플릿·티켓·세션·감사로그)를 건너뜁니다. "
            "AD 로그인 또는 POST /ad/sync 이후 다시 실행하세요."
        )

    # --- AD 연결 (단일 행) ---
    # seed_admin_guid는 채우지 않는다 — 부트스트랩은 POST /auth/setup으로 수행한다.
    _, is_new = get_or_create(session, AdConnection, id=1, defaults=dict(AD_DEFAULTS))
    counts["ad_connection"] = int(is_new)

    # --- 클러스터 + 자격증명 참조 ---
    clusters: dict[str, Cluster] = {}
    created = 0
    for spec in CLUSTERS:
        cluster, is_new = get_or_create(
            session, Cluster, name=spec["name"], defaults={k: v for k, v in spec.items() if k != "name"}
        )
        clusters[cluster.name] = cluster
        created += is_new
    counts["cluster"] = created

    created = 0
    for cluster in clusters.values():
        for kind, ttl in (("SLURM_JWT", timedelta(days=30)), ("SSH_KEY", None)):
            # DB에는 참조와 만료만. 실값은 Secret 저장소(backend-design §6).
            _, is_new = get_or_create(
                session,
                ClusterCredential,
                cluster_id=cluster.id,
                kind=kind,
                defaults={
                    "secret_ref": f"cluster/{cluster.id}/{kind}",
                    "expires_at": (NOW + ttl) if ttl else None,
                },
            )
            created += is_new
    counts["cluster_credential"] = created

    seoul = clusters["seoul-hpc"]

    # --- 운영 설정 (사용자 무관) ---
    _, is_new = get_or_create(
        session,
        PortalSetting,
        id=1,
        defaults={
            "poll_interval_sec": 30,  # C-04 ≤30초
            "session_timeout_min": 480,
            "smtp_host": "smtp.dt-hpc.net",
            "smtp_port": 25,
            "smtp_sender": "hpc-portal@dt-hpc.net",
        },
    )
    counts["portal_setting"] = int(is_new)

    _, is_new = get_or_create(
        session,
        ReportSchedule,
        id=1,
        defaults={
            "recipients": "hpc-ops@dt-hpc.net",
            "cycle": "monthly",
            "format": "pdf",
            "scope": "전체 요약",
            "is_active": True,
        },
    )
    counts["report_schedule"] = int(is_new)

    created = 0
    for resource, rate, unit in [("cpu", 12, "core·h"), ("gpu", 950, "gpu·h")]:
        _, is_new = get_or_create(
            session, ChargebackRate, resource=resource, defaults={"rate_krw": rate, "unit": unit}
        )
        created += is_new
    counts["chargeback_rate"] = created

    # --- License (A-LM) ---
    server, is_new = get_or_create(
        session,
        LicenseServer,
        name="ansys-flexlm",
        defaults={
            "host": "lic01.dt-hpc.net",
            "port": 1055,
            "vendor_daemon": "ansyslmd",
            "collect_interval": "5m",
            "is_active": True,
        },
    )
    counts["license_server"] = int(is_new)

    created = 0
    for feature, total, in_use in [("ansys_cfd", 50, 37), ("ansys_mech", 30, 12), ("hpc_pack", 256, 192)]:
        _, is_new = get_or_create(
            session,
            LicenseFeatureSnapshot,
            server_id=server.id,
            feature=feature,
            defaults={"total": total, "in_use": in_use},
        )
        created += is_new
    counts["license_feature_snapshot"] = created

    # --- Billing (A-BL). 실제 SCP 자격증명 아님 — 연동 전 교체 필요 ---
    _, is_new = get_or_create(
        session,
        BillingConfig,
        id=1,
        defaults={
            "api_endpoint": "https://scp.samsungsdscloud.com",
            "scp_account_id": "REPLACE_WITH_REAL_ACCOUNT",
            "secret_ref": "billing/scp",
            "collect_interval": "1d",
            "monthly_alert_krw": 50_000_000,
        },
    )
    counts["billing_config"] = int(is_new)

    created = 0
    for order, (kind, condition, label) in enumerate(
        [
            ("billing_item", "billing_item_id = OBJECT_STORAGE", "archive"),
            ("resource_name", "resource_name LIKE hpc-*", "hpc-compute"),
            ("service_category", "service_category = COMPUTING", "compute"),
        ],
        start=1,
    ):
        _, is_new = get_or_create(
            session,
            BillingRule,
            condition=condition,
            defaults={"kind": kind, "mapping_label": label, "is_active": True, "sort_order": order},
        )
        created += is_new
    counts["billing_rule"] = created

    created = 0
    for period, dimension, cost in [
        ("2026-06", "compute", 41_200_000),
        ("2026-06", "archive", 3_800_000),
        ("2026-07", "compute", 44_900_000),
        ("2026-07", "archive", 4_050_000),
    ]:
        _, is_new = get_or_create(
            session, BillingSnapshot, period=period, dimension=dimension, defaults={"cost_krw": cost}
        )
        created += is_new
    counts["billing_snapshot"] = created

    if owner is None:
        return counts, notes

    # --- 이하 사용자 연관 콘텐츠 (실제 AD 사용자에 연결) ---
    created = 0
    for title, body, banner, target in [
        (
            "[점검] seoul-hpc 정기 점검 안내",
            "8월 10일 02:00~06:00 gpu 파티션 점검이 예정되어 있습니다. 해당 시간 제출 Job은 대기 상태로 유지됩니다.",
            True,
            seoul.id,
        ),
        ("GROMACS 2025.2 모듈 추가", "module load gromacs/2025.2 로 사용 가능합니다.", False, None),
        ("포털 사용 가이드 공개", "Job 제출·파일 관리·인터랙티브 앱 사용법 문서를 게시했습니다.", False, None),
    ]:
        _, is_new = get_or_create(
            session,
            Notice,
            title=title,
            defaults={
                "body": body,
                "banner_enabled": banner,
                "target_cluster_id": target,
                "start_at": NOW - timedelta(days=1),
                "end_at": NOW + timedelta(days=14),
                "created_by": owner.ad_object_guid,
            },
        )
        created += is_new
    counts["notice"] = created

    created = 0
    for idx, (title, status, job_id) in enumerate(
        [
            ("Job 45771 OOM 원인 문의", "open", "45771"),
            ("GROMACS 2025.2 설치 요청", "in_progress", None),
            ("scratch quota 증설 신청", "open", None),
        ]
    ):
        requester = users[idx % len(users)]
        _, is_new = get_or_create(
            session,
            Ticket,
            title=title,
            defaults={
                "body": "상세 내용은 담당자와 확인 예정입니다.",
                "requester_guid": requester.ad_object_guid,
                "assignee_guid": owner.ad_object_guid if status != "open" else None,
                "status": status,
                "job_id": job_id,
            },
        )
        created += is_new
    counts["ticket"] = created

    _, is_new = get_or_create(
        session,
        InteractiveSession,
        user_guid=owner.ad_object_guid,
        slurm_job_id="45820",
        defaults={
            "cluster_id": seoul.id,
            "app_type": "jupyter",
            "status": "running",
            "node_host": "gpu007.seoul.internal",
            "node_port": 18888,
            "connect_url": "/sessions/45820/",
        },
    )
    counts["interactive_session"] = int(is_new)

    created = 0
    for action, target, detail in [
        ("CLUSTER_CREATE", "seoul-hpc", None),
        ("CLUSTER_CREDENTIAL_PUT", "seoul-hpc", "kind=SLURM_JWT"),
        ("JOB_SUBMIT", "45812", "partition=gpu nodes=1 gpus=4"),
    ]:
        _, is_new = get_or_create(
            session,
            AuditLog,
            action=action,
            target=target,
            defaults={
                "actor_guid": owner.ad_object_guid,
                "actor_role": owner.role.code if owner.role else None,
                "target_cluster_id": seoul.id,
                "detail": detail,
                "at": NOW - timedelta(hours=2),
            },
        )
        created += is_new
    counts["audit_log"] = created

    notes.append(f"콘텐츠 소유자: {owner.username} (실제 AD 사용자 {len(users)}명 중)")
    return counts, notes


def reset(session) -> None:
    """개발 데이터만 지운다. user·ad_connection·role/permission·alembic_version은 보존."""
    for model in DEV_TABLES:
        session.query(model).delete()
    session.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="개발용 시드 데이터 투입 (멱등)")
    parser.add_argument("--reset", action="store_true", help="개발 데이터를 지우고 다시 넣는다")
    args = parser.parse_args()

    settings = get_settings()
    init_engine(settings.database_url)
    session = get_session_factory()()
    try:
        if args.reset:
            reset(session)
            print("기존 개발 데이터 삭제 (user·ad_connection·RBAC 보존)")
        counts, notes = seed(session)
        session.commit()
    finally:
        session.close()

    print(f"대상 DB: {settings.database_url.split('@')[-1]}")
    for table, n in counts.items():
        print(f"  {table:<26} +{n}")
    for note in notes:
        print(f"\n※ {note}")
    print("\n필요한 Secret 환경변수 (EnvSecretStore):")
    print("  PORTAL_SECRET_AD_BIND                  AD bind 계정 암호")
    print("  PORTAL_SECRET_CLUSTER_1_SLURM_JWT      seoul-hpc slurmrestd JWT")
    print("  PORTAL_SECRET_CLUSTER_1_SSH_KEY        seoul-hpc 로그인 노드 SSH 개인키")
    print("  PORTAL_SECRET_CLUSTER_2_SLURM_JWT      pangyo-gpu slurmrestd JWT")
    print("  PORTAL_SECRET_CLUSTER_2_SSH_KEY        pangyo-gpu 로그인 노드 SSH 개인키")


if __name__ == "__main__":
    main()
