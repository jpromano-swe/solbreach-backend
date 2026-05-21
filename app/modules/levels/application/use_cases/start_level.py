import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions.domain import ForbiddenError
from app.modules.levels.application.dto.level_gameplay import LevelStartResult
from app.modules.levels.application.use_cases.get_level import LevelNotFoundError
from app.modules.levels.domain.entities.level_session import LevelSession, LevelState
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.levels.domain.repositories.level_session_repository import LevelSessionRepository
from app.modules.levels.domain.services.level_access import LevelAccessService
from app.shared.events.event_bus import DomainEvent, EventPublisher

logger = logging.getLogger(__name__)


class LevelLockedError(ForbiddenError):
    code = "LEVEL_LOCKED"


class StartLevelUseCase:
    def __init__(
        self,
        levels: LevelRepository,
        sessions: LevelSessionRepository,
        access: LevelAccessService,
        events: EventPublisher,
    ) -> None:
        self._levels = levels
        self._sessions = sessions
        self._access = access
        self._events = events

    async def execute(self, user_id: str, level_id: str) -> LevelStartResult:
        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")

        active_session = await self._sessions.get_active(user_id, level_id)
        latest_session = active_session or await self._sessions.get_latest(user_id, level_id)
        state, _ = await self._access.state_for(user_id, level, latest_session)
        if state == LevelState.LOCKED:
            raise LevelLockedError("Complete the previous level before starting this one")
        if active_session is not None:
            logger.info(
                "level_start_resumed",
                extra={"user_id": user_id, "level_id": level_id, "session_id": active_session.id},
            )
            return LevelStartResult(
                level=level, state=LevelState.IN_PROGRESS, session=active_session
            )

        session = await self._sessions.create(
            LevelSession(
                id=str(uuid4()),
                user_id=user_id,
                level_id=level_id,
                state=LevelState.IN_PROGRESS,
                attempt_count=0,
                started_at=datetime.now(UTC),
            )
        )
        await self._events.publish(
            DomainEvent(name="level_started", payload={"user_id": user_id, "level_id": level_id})
        )
        logger.info(
            "level_started",
            extra={"user_id": user_id, "level_id": level_id, "session_id": session.id},
        )
        return LevelStartResult(level=level, state=LevelState.IN_PROGRESS, session=session)
