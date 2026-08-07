"""공지에서 클러스터 스코프 제거

공지는 **이 포털을 쓰는 사용자 전체**를 대상으로 한다. 클러스터별로 나눌 이유가 없다.

실제로도 그렇게 쓰이고 있었다 — 관리자 공지 등록 폼(`SettingsView.vue`)은 대상 클러스터를
받지 않아 등록되는 공지는 전부 `NULL`(전체)이었다. 컬럼과 조회 필터만 남아 "클러스터별
공지"라는 없는 개념을 코드가 계속 말하고 있던 셈이다.

점검 공지(A-ND-05)도 이제 전체 대상으로 뜬다. 특정 클러스터 점검이라면 **제목·본문에
클러스터를 적어야** 한다 — 배너에는 대상이 드러나지 않는다.

Revision ID: 0011
Revises: 0010
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK가 먼저 걸려 있으면 컬럼을 못 지운다. 이름은 명명 규칙(fk_<표>_<열>_<참조표>)을 따른다.
    with op.batch_alter_table("notice") as batch:
        batch.drop_constraint("fk_notice_target_cluster_id_cluster", type_="foreignkey")
        batch.drop_column("target_cluster_id")


def downgrade() -> None:
    with op.batch_alter_table("notice") as batch:
        batch.add_column(sa.Column("target_cluster_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_notice_target_cluster_id_cluster", "cluster", ["target_cluster_id"], ["id"]
        )
