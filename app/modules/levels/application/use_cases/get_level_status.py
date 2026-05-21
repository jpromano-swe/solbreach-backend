from app.modules.levels.application.dto.level_gameplay import LevelStatusView
from app.modules.levels.application.use_cases.get_level import LevelNotFoundError
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.levels.domain.repositories.level_session_repository import LevelSessionRepository
from app.modules.levels.domain.services.level_access import LevelAccessService
from app.modules.submissions.domain.repositories.submission_repository import SubmissionRepository


class GetLevelStatusUseCase:
    def __init__(
        self,
        levels: LevelRepository,
        sessions: LevelSessionRepository,
        submissions: SubmissionRepository,
        access: LevelAccessService,
    ) -> None:
        self._levels = levels
        self._sessions = sessions
        self._submissions = submissions
        self._access = access

    async def execute(self, user_id: str, level_id: str) -> LevelStatusView:
        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")
        latest_session = await self._sessions.get_latest(user_id, level_id)
        state, progress = await self._access.state_for(user_id, level, latest_session)
        next_level = await self._levels.get_by_order(level.order + 1)
        submissions = await self._submissions.list_for_user_level(user_id, level_id)
        return LevelStatusView(
            level=level,
            state=state,
            session=latest_session,
            progress=progress,
            submissions=submissions,
            next_level_id=next_level.id if next_level else None,
        )
