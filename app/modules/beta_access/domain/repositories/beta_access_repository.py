from __future__ import annotations

from typing import Protocol

from app.modules.beta_access.domain.entities.beta_access import (
    BetaAccessCode,
    BetaAccessCodeRedemption,
    BetaAccessGrant,
    BetaAccessRequest,
)


class BetaAccessRepository(Protocol):
    async def get_grant_by_wallet(self, wallet_address: str) -> BetaAccessGrant | None:
        ...

    async def create_grant(self, grant: BetaAccessGrant) -> BetaAccessGrant:
        ...

    async def update_grant(self, grant: BetaAccessGrant) -> BetaAccessGrant:
        ...

    async def get_request_by_wallet(self, wallet_address: str) -> BetaAccessRequest | None:
        ...

    async def get_request_by_normalized_contact(
        self, normalized_contact: str
    ) -> BetaAccessRequest | None:
        ...

    async def create_request(self, request: BetaAccessRequest) -> BetaAccessRequest:
        ...

    async def update_request(self, request: BetaAccessRequest) -> BetaAccessRequest:
        ...

    async def get_code_by_hash(self, code_hash: str) -> BetaAccessCode | None:
        ...

    async def get_code_by_hash_for_update(self, code_hash: str) -> BetaAccessCode | None:
        ...

    async def update_code(self, code: BetaAccessCode) -> BetaAccessCode:
        ...

    async def get_redemption(
        self, *, code_id: str, wallet_address: str
    ) -> BetaAccessCodeRedemption | None:
        ...

    async def create_redemption(
        self, redemption: BetaAccessCodeRedemption
    ) -> BetaAccessCodeRedemption:
        ...
