from app.core.exceptions.domain import NotFoundError
from app.modules.levels.domain.entities.level import Level
from app.modules.levels.domain.repositories.level_repository import LevelRepository


class LevelNotFoundError(NotFoundError):
    code = "LEVEL_NOT_FOUND"


class GetLevelUseCase:
    def __init__(self, levels: LevelRepository) -> None:
        self._levels = levels

    async def execute(self, level_id: str) -> Level:
        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")
        return level
