from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.badges.domain.badge_definitions import BadgeDefinition
from app.modules.badges.infrastructure.database.models import UserBadgeModel
from app.modules.labs.infrastructure.database.models import ResearchLabCompletionModel
from app.modules.levels.infrastructure.database.models import LevelModel
from app.modules.progress.infrastructure.database.models import ProgressModel


class SQLAlchemyBadgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: str) -> list[UserBadgeModel]:
        result = await self._session.execute(
            select(UserBadgeModel)
            .where(UserBadgeModel.user_id == user_id)
            .order_by(UserBadgeModel.level_order.asc().nulls_last(), UserBadgeModel.slug.asc())
        )
        return list(result.scalars().all())

    async def get_for_user_slug(self, user_id: str, slug: str) -> UserBadgeModel | None:
        result = await self._session.execute(
            select(UserBadgeModel).where(
                UserBadgeModel.user_id == user_id,
                UserBadgeModel.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def create_badge(
        self,
        *,
        user_id: str,
        wallet_address: str | None,
        definition: BadgeDefinition,
        metadata: dict,
        earned_at: datetime,
    ) -> UserBadgeModel:
        model = UserBadgeModel(
            user_id=user_id,
            wallet_address=wallet_address,
            slug=definition.slug,
            title=definition.title,
            description=definition.description,
            kind=definition.kind,
            level_order=definition.level_order,
            image=definition.image,
            metadata_json=metadata,
            earned=True,
            earned_at=earned_at,
            seen_at=None,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def update_seen_at(self, badge: UserBadgeModel, seen_at: datetime) -> UserBadgeModel:
        badge.seen_at = seen_at
        await self._session.flush()
        await self._session.refresh(badge)
        return badge

    async def completed_level_orders(self, user_id: str) -> set[int]:
        result = await self._session.execute(
            select(LevelModel.order)
            .join(ProgressModel, ProgressModel.level_id == LevelModel.id)
            .where(ProgressModel.user_id == user_id)
        )
        return {int(order) for order in result.scalars().all()}

    async def has_completed_research_lab(self, user_id: str, lab_id: str) -> bool:
        result = await self._session.execute(
            select(ResearchLabCompletionModel.id)
            .where(
                ResearchLabCompletionModel.user_id == user_id,
                ResearchLabCompletionModel.lab_id == lab_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
