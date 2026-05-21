from app.modules.progress.domain.entities.progress import Progress
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository


class ListUserProgressUseCase:
    def __init__(self, progress: ProgressRepository) -> None:
        self._progress = progress

    async def execute(self, user_id: str, limit: int, offset: int) -> list[Progress]:
        return await self._progress.list_for_user(user_id, limit, offset)
