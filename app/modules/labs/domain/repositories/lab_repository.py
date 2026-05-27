from __future__ import annotations

from typing import Protocol

from app.modules.labs.domain.entities.lab import Lab


class LabRepository(Protocol):
    async def list(self, limit: int, offset: int) -> list[Lab]: ...
