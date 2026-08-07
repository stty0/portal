"""클러스터 홈 상위 경로 설정

홈을 NSS(`getent passwd`)로만 인식하던 것을 **설정으로도 받을 수 있게** 한다.
값은 홈의 **상위** 경로 하나다(예: `/home`). 사용자 홈은 그 아래 사용자명이며,
사용자명은 서버가 인증 정보에서 채우므로 `{user}` 같은 자리표시자를 두지 않는다
(클라이언트가 대상 사용자를 고를 수 없다는 원칙과 같다).

비워 두면 지금까지처럼 NSS로 자동 인식한다 — 기존 클러스터는 값이 NULL이므로
동작이 바뀌지 않는다.

Revision ID: 0008
Revises: 0007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cluster", sa.Column("home_base", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("cluster", "home_base")
