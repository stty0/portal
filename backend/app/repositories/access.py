"""앱별 허용 계정 repository (`app_access`)."""

from sqlalchemy import select

from app.models import AppAccess
from app.repositories.base import BaseRepository


class AppAccessRepository(BaseRepository[AppAccess]):
    model = AppAccess

    def by_app(self, cluster_id: int) -> dict[tuple[str, str], list[str]]:
        """`(kind, app_id) → 허용 계정`. **배정이 없는 앱은 키 자체가 없다.**

        빈 목록과 "키 없음"을 구분할 필요가 없다 — 둘 다 전원 허용이다. 한 번에 읽어
        두면 목록 화면이 앱 수만큼 질의하지 않는다.
        """
        rows = self.session.scalars(
            select(AppAccess)
            .where(AppAccess.cluster_id == cluster_id)
            .order_by(AppAccess.account)
        )
        out: dict[tuple[str, str], list[str]] = {}
        for row in rows:
            out.setdefault((row.kind, row.app_id), []).append(row.account)
        return out

    def accounts_for(self, cluster_id: int, kind: str, app_id: str) -> list[str]:
        return list(
            self.session.scalars(
                select(AppAccess.account)
                .where(
                    AppAccess.cluster_id == cluster_id,
                    AppAccess.kind == kind,
                    AppAccess.app_id == app_id,
                )
                .order_by(AppAccess.account)
            )
        )

    def replace(self, cluster_id: int, kind: str, app_id: str, accounts: list[str]) -> None:
        """이 앱의 배정을 통째로 갈아 끼운다(QOS 배정과 같은 규칙 — 화면이 전체를 보낸다).

        commit은 service가 잡는다.
        """
        for row in self.session.scalars(
            select(AppAccess).where(
                AppAccess.cluster_id == cluster_id,
                AppAccess.kind == kind,
                AppAccess.app_id == app_id,
            )
        ):
            self.session.delete(row)
        # 삭제를 먼저 흘려보내지 않으면 같은 계정을 다시 넣을 때 UNIQUE에 걸린다.
        self.session.flush()
        for account in dict.fromkeys(accounts):  # 중복 제거 + 입력 순서 유지
            self.session.add(
                AppAccess(cluster_id=cluster_id, kind=kind, app_id=app_id, account=account)
            )
        self.session.flush()
