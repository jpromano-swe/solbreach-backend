from __future__ import annotations

from app.modules.waitlist.domain.entities.waitlist_entry import WaitlistInterest
from app.modules.waitlist.domain.repositories.waitlist_repository import WaitlistRepository


class ListWaitlistEntriesUseCase:
    def __init__(self, repository: WaitlistRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        limit: int,
        offset: int,
        is_solana_dev: bool | None = None,
        interest: str | None = None,
    ) -> list:
        if interest is not None:
            WaitlistInterest(interest)
        return await self._repository.list(
            limit=limit,
            offset=offset,
            is_solana_dev=is_solana_dev,
            interest=interest,
        )
