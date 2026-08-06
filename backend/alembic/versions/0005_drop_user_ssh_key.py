"""사용자 SSH 공개키 테이블 제거

U-AC-03의 SSH 공개키 등록을 범위에서 뺀다. 등록만 받고 **클러스터에 반영하는 경로가
없어서**, 사용자가 등록해 놓고 SSH가 안 되는 혼란만 만든다.

지금은 필요하지도 않다: 로그인 노드가 `PasswordAuthentication yes`라 AD 비밀번호로 이미
`ssh`·`scp`·`rsync`가 되고, 포털이 터미널·파일 관리자·데스크톱을 모두 덮는다.
나중에 `PasswordAuthentication no`로 가거나 외부 자동화가 생기면 그때 되살린다
(이 마이그레이션의 downgrade가 표를 그대로 복원한다).

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("user_ssh_key")


def downgrade() -> None:
    op.create_table(
        "user_ssh_key",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_guid", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_guid"], ["user.ad_object_guid"], name=op.f("fk_user_ssh_key_user_guid_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_ssh_key")),
    )
