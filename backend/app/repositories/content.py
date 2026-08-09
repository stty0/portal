"""공지·포털 설정·앱 카탈로그 repository (A-OP-01·02·04, U-CL-03)."""

from datetime import datetime

from sqlalchemy import or_, select

from app.models import AppCatalog, Notice, PortalSetting
from app.repositories.base import BaseRepository


class NoticeRepository(BaseRepository[Notice]):
    model = Notice

    def search(
        self,
        *,
        banner_only: bool = False,
        now: datetime | None = None,
    ) -> list[Notice]:
        """공지 목록. **포털 전체 대상이라 클러스터로 거르지 않는다.**"""
        stmt = select(Notice)
        if banner_only:
            stmt = stmt.where(Notice.banner_enabled.is_(True))
            if now is not None:
                # 기간이 비어 있으면 상시 노출로 본다.
                stmt = stmt.where(
                    or_(Notice.start_at.is_(None), Notice.start_at <= now),
                    or_(Notice.end_at.is_(None), Notice.end_at >= now),
                )
        return list(self.session.scalars(stmt.order_by(Notice.id.desc())))


class PortalSettingRepository(BaseRepository[PortalSetting]):
    model = PortalSetting

    def get_or_create(self) -> PortalSetting:
        """설정은 **단일 행**이다. 없으면 모델 기본값으로 만든다.

        "설정이 없음"과 "기본값"을 구분할 이유가 없어서, 조회 시점에 만들어 둔다.
        """
        row = self.session.scalar(select(PortalSetting).order_by(PortalSetting.id).limit(1))
        if row is None:
            row = PortalSetting()
            self.session.add(row)
            self.session.flush()
        return row


class AppCatalogRepository(BaseRepository[AppCatalog]):
    """A-OP-02. `(kind, app_id)`가 업무 키다 — id는 화면 조작용."""

    model = AppCatalog

    def list_all(self) -> list[AppCatalog]:
        return list(
            self.session.scalars(
                select(AppCatalog).order_by(AppCatalog.kind, AppCatalog.app_id)
            )
        )

    def get_by_app(self, kind: str, app_id: str) -> AppCatalog | None:
        return self.session.scalar(
            select(AppCatalog).where(AppCatalog.kind == kind, AppCatalog.app_id == app_id)
        )
