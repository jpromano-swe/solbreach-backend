from app.modules.levels.domain.entities.level import Level
from app.modules.levels.domain.entities.level_session import LevelSession, LevelState
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.progress.domain.entities.progress import Progress
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository


class LevelAccessService:
    def __init__(self, levels: LevelRepository, progress: ProgressRepository) -> None:
        self._levels = levels
        self._progress = progress

    async def state_for(
        self,
        user_id: str,
        level: Level,
        latest_session: LevelSession | None,
    ) -> tuple[LevelState, Progress | None]:
        if not await self.is_unlocked(user_id, level):
            return LevelState.LOCKED, None

        if latest_session and latest_session.state == LevelState.IN_PROGRESS:
            progress = await self._progress.get_for_user_level(user_id, level.id)
            return LevelState.IN_PROGRESS, progress
        progress = await self._progress.get_for_user_level(user_id, level.id)
        if progress is not None:
            return LevelState.COMPLETED, progress
        if latest_session and latest_session.state == LevelState.FAILED:
            return LevelState.FAILED, None
        return LevelState.AVAILABLE, None

    async def is_unlocked(self, user_id: str, level: Level) -> bool:
        levels = await self._levels.list_active_vulnerability_levels()
        first_order = min((candidate.order for candidate in levels), default=level.order)
        if level.order == first_order:
            return True
        previous_level = await self._levels.get_by_order(level.order - 1)
        if previous_level is None:
            return True
        return await self._progress.get_for_user_level(user_id, previous_level.id) is not None
