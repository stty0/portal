"""등록된 클러스터의 slurmrestd API 버전을 v0.0.43으로 올린다

**예약 생성 때문이다.** `POST /slurm/vX/reservation`은 **0.0.43에만 있다** — 0.0.40~0.0.42는
조회·삭제만 연다(실 클러스터 openapi 스펙 실측). 노드 제어(`POST /node/{name}`)는 모든
버전에 있고, 파티션은 **모든 버전에서 조회만** 가능하다.

포털은 한 버전만 쓴다. 호출마다 버전을 섞으면 "이 응답은 어느 스키마인가"가 코드에서
흐려지고, 응답 파싱이 버전에 묶여 있어(예: `time_limit`은 분 단위 정수) 그 혼동이 곧
버그가 된다.

**대가**: 0.0.43을 서비스하지 않는 구버전 Slurm 클러스터는 이 포털로 등록할 수 없다.
등록 폼의 선택지도 `SUPPORTED_API_VERSIONS` 하나로 좁혀져 있다.

Revision ID: 0010
Revises: 0009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "v0.0.41"
_NEW = "v0.0.43"


def upgrade() -> None:
    _retarget(_OLD, _NEW)


def downgrade() -> None:
    _retarget(_NEW, _OLD)


def _retarget(old: str, new: str) -> None:
    """이 포털이 걸어 둔 버전만 옮긴다.

    다른 값이 손으로 들어가 있다면 그건 관리자의 의도이므로 건드리지 않는다.
    """
    op.get_bind().execute(
        sa.text("UPDATE cluster SET api_version = :new WHERE api_version = :old"),
        {"new": new, "old": old},
    )
