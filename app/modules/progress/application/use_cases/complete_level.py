import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.levels.application.use_cases.get_level import LevelNotFoundError
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.progress.domain.entities.progress import Progress
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository
from app.modules.users.application.use_cases.get_user import UserNotFoundError
from app.modules.users.domain.repositories.user_repository import UserRepository
from app.shared.events.event_bus import DomainEvent, EventPublisher

logger = logging.getLogger(__name__)


class CompleteLevelUseCase:
    def __init__(
        self,
        progress: ProgressRepository,
        levels: LevelRepository,
        users: UserRepository,
        events: EventPublisher,
    ) -> None:
        self._progress = progress
        self._levels = levels
        self._users = users
        self._events = events

    async def execute(self, user_id: str, level_id: str) -> Progress:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")
        existing_progress = await self._progress.get_for_user_level(user_id, level_id)
        if existing_progress is not None:
            return existing_progress

        progress = await self._progress.create(
            Progress(
                id=str(uuid4()),
                user_id=user_id,
                level_id=level_id,
                xp_awarded=level.xp_reward,
                completed_at=datetime.now(UTC),
            )
        )
        user.xp += level.xp_reward
        user.completed_levels += 1
        await self._users.update(user)
        logger.info(
            "xp_awarded",
            extra={
                "user_id": user_id,
                "level_id": level_id,
                "xp_awarded": level.xp_reward,
                "total_xp": user.xp,
            },
        )
        await self._events.publish(
            DomainEvent(
                name="level_completed",
                payload={"user_id": user_id, "level_id": level_id, "xp_awarded": level.xp_reward},
            )
        )
        return progress
