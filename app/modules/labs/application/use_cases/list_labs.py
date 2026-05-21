from app.modules.labs.domain.entities.lab import Lab
from app.modules.labs.domain.repositories.lab_repository import LabRepository


class ListLabsUseCase:
    def __init__(self, labs: LabRepository) -> None:
        self._labs = labs

    async def execute(self, limit: int, offset: int) -> list[Lab]:
        return await self._labs.list(limit, offset)
