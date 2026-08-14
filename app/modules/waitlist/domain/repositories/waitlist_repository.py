from __future__ import annotations

from typing import Protocol

from app.modules.waitlist.domain.entities.waitlist_entry import WaitlistEntry


class WaitlistRepository(Protocol):
    async def create(self, entry: WaitlistEntry) -> WaitlistEntry: ...

    async def update(self, entry: WaitlistEntry) -> WaitlistEntry: ...

    async def get_by_normalized_contact(self, normalized_contact: str) -> WaitlistEntry | None: ...

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        is_solana_dev: bool | None = None,
        interest: str | None = None,
    ) -> list[WaitlistEntry]: ...
