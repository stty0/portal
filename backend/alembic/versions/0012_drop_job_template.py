"""Job 템플릿 기능 제거

템플릿 제출 탭(U-JB-03)을 먼저 걷어냈고(2026-08-07), 그러자 관리자 등록 화면(A-OP-02)만
남아 **등록해도 쓰는 곳이 없는 상태**가 됐다. 반쪽 경로를 남겨 두면 관리자는 템플릿이
동작한다고 믿는다. 그래서 표까지 함께 지운다.

애초에 이 표는 요구된 기능을 담기에 모자랐다. 템플릿이 쓸모 있으려면 solver s/w가 설치된
컨테이너 이미지와 그 s/w에 값을 넣는 입력 인터페이스가 있어야 하는데, 여기 있는 것은
`params.script` 문자열과 `{{key}}` 치환뿐이었다. 되살릴 때는 이 스키마가 아니라 인터랙티브
앱 카탈로그(`session_apps.py` + 클러스터 `image_repository`)와 같은 모양이어야 한다.

`job_template`을 참조하는 표는 없다(나가는 FK만 있다) — 순서를 맞출 필요가 없다.

Revision ID: 0012
Revises: 0011
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("job_template")


def downgrade() -> None:
    # 0001의 정의 그대로 되돌린다 — 행 내용은 복구되지 않는다.
    op.create_table(
        "job_template",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=True),
        sa.Column("version", sa.String(length=16), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["user.ad_object_guid"], name=op.f("fk_job_template_created_by_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_template")),
    )
