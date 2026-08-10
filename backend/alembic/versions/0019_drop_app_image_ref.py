"""`app_catalog.image_ref` 제거 — 포털이 레지스트리에서 이미지를 받지 않는다

`0018`이 만든 컬럼과 그것을 쓰던 변환 기능(빌드→배치)을 함께 걷어낸다.

**관리자가 포털 밖에서** 이미지를 받아 SIF로 바꾼 뒤 클러스터의 `{home_base}/.portal/images`에
올려 놓는 방식으로 정해졌다(사용자 결정). 그러면 OCI 참조를 읽는 코드가 하나도 남지 않는다 —
이 프로젝트는 그런 표를 남기지 않는다(`job_template` 제거 근거와 같다).

출처를 적어 두고 싶으면 `description`에 쓴다. 이미 있는 칸이고 관리자가 채우는 값이라
새 컬럼 없이 같은 정보가 남는다.

Revision ID: 0019
Revises: 0018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("app_catalog", "image_ref")


def downgrade() -> None:
    op.add_column("app_catalog", sa.Column("image_ref", sa.String(length=255), nullable=True))
