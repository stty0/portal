"""클러스터 마지막 헬스체크 결과

A-CL-01: 목록의 상태 컬럼이 "언제 확인했고 정상이었나"를 스스로 보여주게 한다.
연결 상태 **이력**(A-CL-03)은 별도 테이블이 필요하므로 여기 포함하지 않는다 —
여기는 "마지막 1건"만 클러스터 행에 캐시한다.

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cluster", sa.Column("last_health_at", sa.DateTime(), nullable=True))
    op.add_column("cluster", sa.Column("last_health_ok", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("cluster", "last_health_ok")
    op.drop_column("cluster", "last_health_at")
