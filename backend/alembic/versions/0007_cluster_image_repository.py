"""클러스터 이미지 설정을 '파일 하나'에서 '저장소'로

인터랙티브 앱이 여러 개가 되면서 클러스터당 이미지 한 칸으로는 부족해졌다.
클러스터는 이제 이미지가 **있는 곳**만 갖고, 어떤 이미지를 쓸지는 앱이 정한다
(`app/services/session_apps.py` 카탈로그). `0004`에서 만든 컬럼의 후속이다.

  desktop_image_ref  /home/portal/images/rocky9-mate-1.5.sif   (이미지 파일 하나)
  image_repository   /home/portal/images                       (그 아래를 앱이 고른다)

**기존 값도 함께 옮긴다.** 컬럼 이름만 바꾸면 살아 있는 클러스터의 값이 파일 경로로
남아 `<파일>/<파일>` 같은 참조가 만들어져 세션이 워커에서 죽는다. 그래서 `.sif`로
끝나는 값은 마지막 조각을 떼어 디렉터리로 만든다. 레지스트리 참조(`docker://…`)는
그대로 둔다 — 이미 저장소 형태다.

Revision ID: 0007
Revises: 0006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "cluster",
        "desktop_image_ref",
        new_column_name="image_repository",
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )
    _strip_filenames()


def downgrade() -> None:
    op.alter_column(
        "cluster",
        "image_repository",
        new_column_name="desktop_image_ref",
        existing_type=sa.String(length=255),
        existing_nullable=True,
    )
    # 되돌릴 때 파일명은 복원하지 않는다 — 어떤 앱의 이미지였는지 알 수 없다.
    # 관리자가 다시 채워야 한다.


def _strip_filenames() -> None:
    """SIF 파일 경로 → 그것을 담고 있는 디렉터리.

    SQL 방언에 의존하지 않도록 Python에서 처리한다(MySQL 운영 / SQLite 개발).
    """
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, image_repository FROM cluster WHERE image_repository IS NOT NULL")
    ).fetchall()
    for row_id, value in rows:
        if value.endswith(".sif") and "/" in value:
            conn.execute(
                sa.text("UPDATE cluster SET image_repository = :v WHERE id = :i"),
                {"v": value.rsplit("/", 1)[0], "i": row_id},
            )
