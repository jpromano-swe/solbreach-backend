from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.progress.domain.entities.progress import Progress
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository
from app.modules.progress.infrastructure.database.models import ProgressModel


class SQLAlchemyProgressRepository(ProgressRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, progress: Progress) -> Progress:
        model = ProgressModel(
            id=progress.id,
            user_id=progress.user_id,
            level_id=progress.level_id,
            xp_awarded=progress.xp_awarded,
            completed_at=progress.completed_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_for_user_level(self, user_id: str, level_id: str) -> Progress | None:
        result = await self._session.execute(
            select(ProgressModel).where(
                ProgressModel.user_id == user_id, ProgressModel.level_id == level_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_for_user(self, user_id: str, limit: int, offset: int) -> list[Progress]:
        result = await self._session.execute(
            select(ProgressModel)
            .where(ProgressModel.user_id == user_id)
            .order_by(ProgressModel.completed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    @staticmethod
    def _to_entity(model: ProgressModel) -> Progress:
        return Progress(
            id=model.id,
            user_id=model.user_id,
            level_id=model.level_id,
            xp_awarded=model.xp_awarded,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
