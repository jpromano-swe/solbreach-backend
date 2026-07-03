from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions.domain import ConflictError, DomainError
from app.modules.beta_access.domain.entities.beta_access import (
    BetaAccessCodeStatus,
    BetaAccessCodeRedemption,
    BetaAccessGrant,
    BetaAccessRequest,
    BetaAccessSource,
    BetaAccessStatus,
)
from app.modules.beta_access.domain.repositories.beta_access_repository import (
    BetaAccessRepository,
)

_CODE_PATTERN = re.compile(r"[^A-Z0-9]")


class InvalidAccessCodeError(DomainError):
    code = "INVALID_ACCESS_CODE"
    status_code = 400


class ExpiredAccessCodeError(DomainError):
    code = "EXPIRED_ACCESS_CODE"
    status_code = 400


class ExhaustedAccessCodeError(DomainError):
    code = "EXHAUSTED_ACCESS_CODE"
    status_code = 409


class WalletRequiredForAccessCodeError(DomainError):
    code = "WALLET_REQUIRED"
    status_code = 422


def normalize_wallet(wallet_address: str | None) -> str | None:
    if wallet_address is None:
        return None
    normalized = wallet_address.strip()
    if not normalized:
        return None
    if len(normalized) < 32 or len(normalized) > 64:
        raise ConflictError("Wallet address must be between 32 and 64 characters")
    return normalized


def normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized[:max_length] if normalized else None


def normalize_contact(contact: str | None) -> tuple[str | None, str | None]:
    normalized = normalize_optional_text(contact, max_length=255)
    if normalized is None:
        return None, None
    return normalized, normalized.lower().replace(" ", "")


def normalize_access_code(code: str) -> str:
    normalized = _CODE_PATTERN.sub("", code.upper())
    if len(normalized) < 4 or len(normalized) > 64:
        raise InvalidAccessCodeError("Access code is invalid.")
    return normalized


def hash_access_code(code: str) -> str:
    return hashlib.sha256(normalize_access_code(code).encode("utf-8")).hexdigest()


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class GetBetaAccessStatusUseCase:
    def __init__(self, repository: BetaAccessRepository) -> None:
        self._repository = repository

    async def execute(self, wallet_address: str) -> dict:
        wallet = normalize_wallet(wallet_address)
        if wallet is None:
            raise ConflictError("Wallet address is required")
        grant = await self._repository.get_grant_by_wallet(wallet)
        if grant is None or grant.status is not BetaAccessStatus.APPROVED:
            return {
                "walletAddress": wallet,
                "hasAccess": False,
                "accessSource": grant.source.value if grant else None,
                "status": grant.status.value if grant else BetaAccessStatus.NONE.value,
            }
        return {
            "walletAddress": wallet,
            "hasAccess": True,
            "accessSource": grant.source.value,
            "status": grant.status.value,
        }


class RequestBetaAccessUseCase:
    def __init__(self, repository: BetaAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        wallet_address: str | None,
        contact: str | None,
        name_or_handle: str | None,
        interest: str | None,
        community_or_org: str | None,
    ) -> tuple[BetaAccessRequest, bool]:
        wallet = normalize_wallet(wallet_address)
        persisted_contact, normalized_contact = normalize_contact(contact)
        if wallet is None and normalized_contact is None:
            raise ConflictError("Wallet address or contact is required")

        existing = None
        if wallet is not None:
            existing = await self._repository.get_request_by_wallet(wallet)
        if existing is None and normalized_contact is not None:
            existing = await self._repository.get_request_by_normalized_contact(normalized_contact)

        normalized_name = normalize_optional_text(name_or_handle, max_length=120)
        normalized_interest = normalize_optional_text(interest, max_length=80)
        normalized_community = normalize_optional_text(community_or_org, max_length=160)

        if existing is None:
            request = BetaAccessRequest(
                id=str(uuid4()),
                wallet_address=wallet,
                contact=persisted_contact,
                normalized_contact=normalized_contact,
                name_or_handle=normalized_name,
                interest=normalized_interest,
                community_or_org=normalized_community,
                status=BetaAccessStatus.PENDING,
            )
            return await self._repository.create_request(request), False

        if wallet is not None:
            existing.wallet_address = wallet
        if persisted_contact is not None:
            existing.contact = persisted_contact
            existing.normalized_contact = normalized_contact
        if normalized_name is not None:
            existing.name_or_handle = normalized_name
        if normalized_interest is not None:
            existing.interest = normalized_interest
        if normalized_community is not None:
            existing.community_or_org = normalized_community
        return await self._repository.update_request(existing), True


class RedeemBetaAccessCodeUseCase:
    def __init__(self, repository: BetaAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, code: str, wallet_address: str | None, user_id: str | None = None
    ) -> dict:
        wallet = normalize_wallet(wallet_address)
        if wallet is None:
            raise WalletRequiredForAccessCodeError("Wallet address is required to redeem access.")

        access_code = await self._repository.get_code_by_hash_for_update(hash_access_code(code))
        if access_code is None or access_code.status is not BetaAccessCodeStatus.ACTIVE:
            raise InvalidAccessCodeError("Access code is invalid.")
        if access_code.expires_at is not None and utc_datetime(access_code.expires_at) <= datetime.now(UTC):
            raise ExpiredAccessCodeError("Access code has expired.")
        if access_code.redemption_count >= access_code.max_redemptions:
            raise ExhaustedAccessCodeError("Access code has already been fully redeemed.")

        existing_redemption = await self._repository.get_redemption(
            code_id=access_code.id, wallet_address=wallet
        )
        if existing_redemption is None:
            await self._repository.create_redemption(
                BetaAccessCodeRedemption(
                    id=str(uuid4()),
                    code_id=access_code.id,
                    wallet_address=wallet,
                    user_id=user_id,
                    redeemed_at=datetime.now(UTC),
                )
            )
            access_code.redemption_count += 1
            await self._repository.update_code(access_code)

        grant = await self._repository.get_grant_by_wallet(wallet)
        if grant is None:
            grant = await self._repository.create_grant(
                BetaAccessGrant(
                    id=str(uuid4()),
                    wallet_address=wallet,
                    user_id=user_id,
                    status=BetaAccessStatus.APPROVED,
                    source=BetaAccessSource.ACCESS_CODE,
                    access_code_id=access_code.id,
                )
            )
        elif grant.status is not BetaAccessStatus.APPROVED:
            grant.status = BetaAccessStatus.APPROVED
            grant.source = BetaAccessSource.ACCESS_CODE
            grant.access_code_id = access_code.id
            grant.user_id = user_id or grant.user_id
            grant.revoked_at = None
            grant = await self._repository.update_grant(grant)

        return {
            "walletAddress": wallet,
            "hasAccess": grant.status is BetaAccessStatus.APPROVED,
            "accessSource": grant.source.value,
            "status": grant.status.value,
        }
