from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.levels.domain.entities.level_session import LevelSession, LevelState
from app.modules.levels.domain.repositories.level_session_repository import LevelSessionRepository
from app.modules.levels.infrastructure.database.models import LevelSessionModel


class SQLAlchemyLevelSessionRepository(LevelSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session: LevelSession) -> LevelSession:
        model = LevelSessionModel(
            id=session.id,
            user_id=session.user_id,
            level_id=session.level_id,
            state=session.state.value,
            attempt_count=session.attempt_count,
            started_at=session.started_at,
            completed_at=session.completed_at,
            last_submitted_at=session.last_submitted_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_active(self, user_id: str, level_id: str) -> LevelSession | None:
        result = await self._session.execute(
            select(LevelSessionModel)
            .where(
                LevelSessionModel.user_id == user_id,
                LevelSessionModel.level_id == level_id,
                LevelSessionModel.state == LevelState.IN_PROGRESS.value,
            )
            .order_by(LevelSessionModel.started_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_latest(self, user_id: str, level_id: str) -> LevelSession | None:
        result = await self._session.execute(
            select(LevelSessionModel)
            .where(LevelSessionModel.user_id == user_id, LevelSessionModel.level_id == level_id)
            .order_by(LevelSessionModel.started_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, session: LevelSession) -> LevelSession:
        model = await self._session.get(LevelSessionModel, session.id)
        if model is None:
            raise ValueError("Level session not found")
        model.state = session.state.value
        model.attempt_count = session.attempt_count
        model.completed_at = session.completed_at
        model.last_submitted_at = session.last_submitted_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: LevelSessionModel) -> LevelSession:
        return LevelSession(
            id=model.id,
            user_id=model.user_id,
            level_id=model.level_id,
            state=LevelState(model.state),
            attempt_count=model.attempt_count,
            started_at=model.started_at,
            completed_at=model.completed_at,
            last_submitted_at=model.last_submitted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
