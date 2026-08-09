"""앱 아이콘을 URL이 아니라 파일명으로 저장

아이콘은 `/home/portal/app-icons`(설정 `app_icon_dir`)에 파일로 두고, DB에는 **파일명만**
남긴다. URL은 서버가 만든다(`/api/v1/app-icons/{name}`) — 배포 위치가 바뀌어도 DB는 그대로다.
임의 외부 URL·`data:` URI를 받던 이전 형태는 출처를 통제할 수 없어 접었다.

`app_catalog`는 0015에서 만들어졌고 아직 운영 데이터가 없어 값 이관은 없다.

Revision ID: 0016
Revises: 0015
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("app_catalog", "icon_url")
    op.add_column("app_catalog", sa.Column("icon_file", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("app_catalog", "icon_file")
    op.add_column("app_catalog", sa.Column("icon_url", sa.Text(), nullable=True))
