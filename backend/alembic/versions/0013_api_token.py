"""사용자별 API 토큰

액세스 토큰이 30분이라 자동화를 감당할 수 없고, AD 비밀번호를 스크립트에 박으면
반복 실패로 **AD 계정이 잠긴다.** 사람 로그인과 분리된 기계용 자격증명을 둔다.

원문은 저장하지 않는다(sha256만) — DB가 새어도 토큰을 되살릴 수 없다.

Revision ID: 0013
Revises: 0012
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_guid", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        # 조회는 해시로만 한다 — unique라 충돌도 여기서 걸린다.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_guid"], ["user.ad_object_guid"], name=op.f("fk_api_token_user_guid_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_token")),
    )
    op.create_index(op.f("ix_api_token_user_guid"), "api_token", ["user_guid"])
    op.create_index(op.f("ix_api_token_token_hash"), "api_token", ["token_hash"], unique=True)


def downgrade() -> None:
    # 인덱스를 따로 지우지 않는다. `user_guid`는 FK가 걸려 있어 MySQL이 인덱스 삭제를
    # 거부하고(1553), 어차피 표를 지우면 인덱스도 함께 사라진다.
    #
    # 실측으로 걸린 문제다. MySQL은 DDL이 트랜잭션이 아니라 **중간에 실패하면 앞 단계가
    # 되돌아가지 않는다** — 첫 시도가 token_hash 인덱스만 지우고 멈춰서, 두 번째 시도는
    # "그런 인덱스 없다"(1091)로 다르게 실패했다.
    op.drop_table("api_token")
