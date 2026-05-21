from app.modules.levels.domain.entities.level import Level
from app.modules.levels.domain.repositories.level_repository import LevelRepository


class ListLevelsUseCase:
    def __init__(self, levels: LevelRepository) -> None:
        self._levels = levels

    async def execute(self, limit: int, offset: int) -> list[Level]:
        return await self._levels.list(limit, offset)
