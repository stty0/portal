"""앱 이미지의 **출처**(OCI 참조)를 DB에 남긴다

`image_file`은 *무엇을 실행하는지*(`openfoam-2512.sif`)만 말하고 **어디서 왔는지는
말하지 않는다.** 지금 그 출처는 `docs/progress.md` 본문에만 있어서, 버전을 올리거나
다른 클러스터에 같은 이미지를 만들려면 문서를 뒤져야 한다.

`image_ref`가 그 자리다 — `docker://opencfd/openfoam-default:2512`. T-08(변환을 Slurm
잡으로)이 이 값을 그대로 `apptainer build`에 넘긴다. 레지스트리 호스트를 따로 두지 않는
이유는 **여러 레지스트리를 섞어 쓰기 때문**이다(Docker Hub · nvcr.io).

Revision ID: 0018
Revises: 0017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_catalog", sa.Column("image_ref", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("app_catalog", "image_ref")
