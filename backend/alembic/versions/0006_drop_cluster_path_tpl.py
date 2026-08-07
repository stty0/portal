"""클러스터 스크래치·그룹 경로 템플릿 컬럼 제거

스크래치(`/scratch/{user}`)·그룹 공유(`/groups/{account}`) 디렉터리 관리를 포털 범위에서
뺀다. 경로를 **인식**만 하고 **만들 수는 없어서** 반쪽이었다:

- 포털의 SSH는 언제나 `sudo -n -u <대상사용자>`로만 실행된다(정의서 §4.1 최소 권한).
  root 소유 `/scratch` 아래에 디렉터리를 만들 방법이 없다.
- 그룹 공유 디렉터리는 유닉스 gid가 있어야 하는데, 이 사이트 AD에는 `domain users`
  하나뿐이라 그걸 쓰면 전원이 모든 그룹 디렉터리에 쓰게 되어 경계가 사라진다.

그래서 화면에는 늘 '없음'만 떴다. 관리자가 클러스터마다 채워야 하는 설정 두 칸을
남겨 두면 "채웠는데 왜 안 되냐"는 혼란만 만든다(0005의 SSH 공개키와 같은 판단).

파일 브라우저·스토리지는 홈만 다룬다. 나중에 디렉터리 생성 경로(전용 root 헬퍼 등)가
생기면 이 마이그레이션의 downgrade가 컬럼을 그대로 복원한다.

Revision ID: 0006
Revises: 0005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("cluster", "group_path_tpl")
    op.drop_column("cluster", "scratch_path_tpl")


def downgrade() -> None:
    op.add_column("cluster", sa.Column("scratch_path_tpl", sa.String(length=255), nullable=True))
    op.add_column("cluster", sa.Column("group_path_tpl", sa.String(length=255), nullable=True))
