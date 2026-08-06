"""공지·템플릿·포털 설정 repository (A-OP-01·02·04, U-CL-03, U-JB-03)."""

from datetime import datetime

from sqlalchemy import or_, select

from app.models import JobTemplate, Notice, PortalSetting
from app.repositories.base import BaseRepository


class NoticeRepository(BaseRepository[Notice]):
    model = Notice

    def search(
        self,
        *,
        cluster_id: int | None = None,
        banner_only: bool = False,
        now: datetime | None = None,
    ) -> list[Notice]:
        """공지 목록.

        `cluster_id`를 주면 **그 클러스터 대상 + 전체 대상(NULL)** 을 함께 준다 —
        전체 공지가 클러스터를 고른 사용자에게 안 보이면 공지의 의미가 없다.
        """
        stmt = select(Notice)
        if cluster_id is not None:
            stmt = stmt.where(
                or_(Notice.target_cluster_id == cluster_id, Notice.target_cluster_id.is_(None))
            )
        if banner_only:
            stmt = stmt.where(Notice.banner_enabled.is_(True))
            if now is not None:
                # 기간이 비어 있으면 상시 노출로 본다.
                stmt = stmt.where(
                    or_(Notice.start_at.is_(None), Notice.start_at <= now),
                    or_(Notice.end_at.is_(None), Notice.end_at >= now),
                )
        return list(self.session.scalars(stmt.order_by(Notice.id.desc())))


class JobTemplateRepository(BaseRepository[JobTemplate]):
    model = JobTemplate

    def visible_to(self, user_guid: str) -> list[JobTemplate]:
        """공개 템플릿 + 내가 만든 것 (api.md `/templates`)."""
        return list(
            self.session.scalars(
                select(JobTemplate)
                .where(or_(JobTemplate.is_public.is_(True), JobTemplate.created_by == user_guid))
                .order_by(JobTemplate.name)
            )
        )


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
