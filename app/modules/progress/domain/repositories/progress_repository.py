from typing import Protocol

from app.modules.progress.domain.entities.progress import Progress


class ProgressRepository(Protocol):
    async def create(self, progress: Progress) -> Progress: ...

    async def get_for_user_level(self, user_id: str, level_id: str) -> Progress | None: ...

    async def list_for_user(self, user_id: str, limit: int, offset: int) -> list[Progress]: ...
