"""앱별 허용 Slurm 계정

인터랙티브 앱·Batch 앱을 **그 앱에 배정된 계정에 속한 사용자만** 쓰게 한다
(U-IA-01 · U-JB-13, A-US-02의 배정 부분).

**허용 목록이고, 행이 없으면 전원 허용이다.** 그래서 이 마이그레이션은 동작을
바꾸지 않는다 — 표가 비어 있는 동안 모든 앱은 지금까지처럼 열려 있다.

Revision ID: 0014
Revises: 0013
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        # 두 카탈로그의 앱 id가 겹칠 수 있어 kind가 함께 키가 된다.
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("app_id", sa.String(length=32), nullable=False),
        # 계정은 slurmdbd 소유다 — FK가 아니라 이름 참조다(경계: models/__init__).
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["cluster.id"], name=op.f("fk_app_access_cluster_id_cluster")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_access")),
        sa.UniqueConstraint("cluster_id", "kind", "app_id", "account", name="uq_app_access"),
    )


def downgrade() -> None:
    # 인덱스·제약을 따로 지우지 않는다 — 표를 지우면 함께 사라지고, FK가 걸린 컬럼의
    # 인덱스는 MySQL이 개별 삭제를 거부한다(0013에서 겪은 1553).
    op.drop_table("app_access")
