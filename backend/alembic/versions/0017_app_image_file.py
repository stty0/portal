"""앱 이미지를 클러스터 저장소가 아니라 앱 카탈로그가 갖는다

전:  cluster.image_repository (있는 곳, 클러스터마다) + 코드 카탈로그의 파일명
후:  settings.app_image_dir  (있는 곳, 포털 하나)   + app_catalog.image_file

운영 중인 두 클러스터가 같은 경로(`/home/portal/images`)를 쓰고 있었고, **이미지를
바꾸려면 클러스터를 고쳐야 하는데 정작 바뀌는 것은 앱**이라 자리가 어긋나 있었다.
아이콘(`icon_file`)과 같은 모양으로 맞춘다.

`image_location`(0015, 레지스트리 참조까지 받던 자유 문자열)은 파일명만 받는
`image_file`이 된다. 값은 아직 비어 있어 이관이 없다 — 등록이 없으면 코드 카탈로그의
기본 파일명으로 떨어지므로 실행은 그대로 된다.

Revision ID: 0017
Revises: 0016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("app_catalog", "image_location")
    op.add_column("app_catalog", sa.Column("image_file", sa.String(length=128), nullable=True))
    op.drop_column("cluster", "image_repository")


def downgrade() -> None:
    op.add_column("cluster", sa.Column("image_repository", sa.String(length=255), nullable=True))
    op.drop_column("app_catalog", "image_file")
    op.add_column("app_catalog", sa.Column("image_location", sa.String(length=255), nullable=True))
