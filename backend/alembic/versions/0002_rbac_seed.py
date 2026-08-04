"""RBAC 초기 seed

db-erd.md §2·backend-design §3.4: role 2행(USER/ADMIN), permission 1행(admin:access),
매핑 1행(ADMIN→admin:access). 향후 role 추가(예: PI)·`resource:action` 세분화는
스키마 변경 없이 **행 삽입만**으로 수용한다.

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = [
    ("USER", "일반 사용자", "Job 제출/조회, 본인 파일·세션 관리, 본인 사용량 조회"),
    ("ADMIN", "관리자", "클러스터·노드·정책 관리, 전체 Job 제어, 통계/감사"),
]
PERMISSIONS = [("admin:access", "ADMIN 페이지/기능 접근")]
MAPPINGS = [("ADMIN", "admin:access")]


def upgrade() -> None:
    role = sa.table(
        "role",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    perm = sa.table(
        "permission",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
    )
    rp = sa.table(
        "role_permission",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    op.bulk_insert(role, [{"code": c, "name": n, "description": d} for c, n, d in ROLES])
    op.bulk_insert(perm, [{"code": c, "description": d} for c, d in PERMISSIONS])

    conn = op.get_bind()
    role_ids = dict(conn.execute(sa.text("SELECT code, id FROM role")).all())
    perm_ids = dict(conn.execute(sa.text("SELECT code, id FROM permission")).all())
    op.bulk_insert(
        rp,
        [
            {"role_id": role_ids[rc], "permission_id": perm_ids[pc]}
            for rc, pc in MAPPINGS
            if rc in role_ids and pc in perm_ids
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE role_id IN "
            "(SELECT id FROM role WHERE code IN ('USER','ADMIN'))"
        )
    )
    conn.execute(sa.text("DELETE FROM permission WHERE code = 'admin:access'"))
    conn.execute(sa.text("DELETE FROM role WHERE code IN ('USER','ADMIN')"))
