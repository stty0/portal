"""앱 카탈로그 (A-OP-02 앱 관리)

앱의 **정보**만 담는다 — 벤더·버전·아이콘·이미지 위치·설명. 실행 방식(기동 스크립트·
transport·파라미터 스키마)은 `services/session_apps.py`·`batch_apps.py`의 코드 카탈로그가
계속 정본이다. 2026-08-07에 `job_template`을 지운 이유("이미지 + 실행 커맨드 + 파라미터
스키마는 한 몸이라 DB에 넣으면 코드 배포와 어긋난다")는 그대로 유효하고, 여기 있는 값은
그 셋에 속하지 않는다.

`(kind, app_id)`가 코드 카탈로그로 가는 연결 키다 — `app_access`와 같은 형태.

Revision ID: 0015
Revises: 0014
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("app_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("vendor", sa.String(length=128), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=True),
        sa.Column("image_location", sa.String(length=255), nullable=True),
        sa.Column("icon_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "app_id", name="uq_app_catalog_kind_app"),
    )


def downgrade() -> None:
    op.drop_table("app_catalog")
