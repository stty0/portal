"""클러스터 이름은 slurmrestd가 정하고, 사람은 별칭을 붙인다

등록 폼이 `name`을 **필수로** 받고 있었는데, 그 값은 REST 연결 테스트가 slurm.conf의
`ClusterName`으로 덮어쓴다. 관리자에게 "곧 사라질 값"을 반드시 입력하게 만드는 구성이었다.

- `name`을 nullable로 바꾼다. 등록 시점에는 비어 있고, REST 연결 테스트가 채운다.
  채워진 뒤에는 포털에서 수정할 수 없다(기존 규칙 유지).
- `description` → `alias`. 화면은 이미 이 값을 클러스터 표시명으로 쓰고 있었다
  (`c.description || c.name`). 이름이 확인되기 전까지 클러스터를 가리키는 유일한 값이므로
  실제 역할에 맞는 이름을 준다.

Revision ID: 0009
Revises: 0008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "cluster", "name", existing_type=sa.String(length=64), nullable=True
    )
    op.alter_column(
        "cluster",
        "description",
        new_column_name="alias",
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "cluster",
        "alias",
        new_column_name="description",
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )
    # 이름이 비어 있는 행은 NOT NULL로 되돌릴 수 없다 — 자리표시자를 채운 뒤 좁힌다.
    op.execute(
        "UPDATE cluster SET name = CONCAT('unnamed-', id) WHERE name IS NULL OR name = ''"
    )
    op.alter_column(
        "cluster", "name", existing_type=sa.String(length=64), nullable=False
    )
