"""클러스터별 인터랙티브 세션 컨테이너 이미지 참조

U-IA-02: Apptainer는 SIF 경로·`oras://`·`docker://`를 **같은 인자 자리**에서 받는다.
그래서 이 값 하나만 바꾸면 개발용 공유 NFS 배포에서 컨테이너 레지스트리로
전환된다(docs/plan.md §3.5) — 코드도 Job 스크립트도 바뀌지 않는다.

Revision ID: 0004
Revises: 0003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cluster", sa.Column("desktop_image_ref", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("cluster", "desktop_image_ref")
