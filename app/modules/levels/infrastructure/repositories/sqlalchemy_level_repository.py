from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.levels.domain.entities.level import Level, LevelStage
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.levels.infrastructure.database.models import LevelModel


class SQLAlchemyLevelRepository(LevelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, level: Level) -> Level:
        model = LevelModel(
            id=level.id,
            slug=level.slug,
            title=level.title,
            description=level.description,
            order=level.order,
            stage=level.stage.value,
            vulnerability_id=level.vulnerability_id,
            vulnerability_category=level.vulnerability_category,
            difficulty=level.difficulty,
            objectives=level.objectives,
            instructions=level.instructions,
            verification_requirements=level.verification_requirements,
            repository_url=level.repository_url,
            resources=level.resources,
            verification_config=level.verification_config,
            deployment_info=level.deployment_info,
            xp_reward=level.xp_reward,
            is_active=level.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, level_id: str) -> Level | None:
        model = await self._session.get(LevelModel, level_id)
        if model is None or model.deleted_at is not None:
            return None
        return self._to_entity(model)

    async def get_by_slug(self, slug: str) -> Level | None:
        result = await self._session.execute(
            select(LevelModel).where(LevelModel.slug == slug, LevelModel.deleted_at.is_(None))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_order(self, order: int) -> Level | None:
        result = await self._session.execute(
            select(LevelModel).where(
                LevelModel.order == order,
                LevelModel.stage == LevelStage.VULNERABILITIES.value,
                LevelModel.deleted_at.is_(None),
                LevelModel.is_active.is_(True),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(self, limit: int, offset: int) -> list[Level]:
        result = await self._session.execute(
            select(LevelModel)
            .where(LevelModel.deleted_at.is_(None), LevelModel.is_active.is_(True))
            .order_by(LevelModel.stage, LevelModel.order)
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_active_vulnerability_levels(self) -> list[Level]:
        result = await self._session.execute(
            select(LevelModel)
            .where(
                LevelModel.deleted_at.is_(None),
                LevelModel.is_active.is_(True),
                LevelModel.stage == LevelStage.VULNERABILITIES.value,
            )
            .order_by(LevelModel.order)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    @staticmethod
    def _to_entity(model: LevelModel) -> Level:
        return Level(
            id=model.id,
            slug=model.slug,
            title=model.title,
            description=model.description,
            order=model.order,
            stage=LevelStage(model.stage),
            vulnerability_id=model.vulnerability_id,
            vulnerability_category=model.vulnerability_category,
            difficulty=model.difficulty,
            objectives=model.objectives,
            instructions=model.instructions,
            verification_requirements=model.verification_requirements,
            repository_url=model.repository_url,
            resources=model.resources,
            verification_config=model.verification_config,
            deployment_info=model.deployment_info,
            xp_reward=model.xp_reward,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
