from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BetaAccessStatus(StrEnum):
    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"


class BetaAccessSource(StrEnum):
    WALLET_ALLOWLIST = "wallet_allowlist"
    ACCESS_CODE = "access_code"
    ADMIN = "admin"
    PARTNER = "partner"
    DEV_OVERRIDE = "dev_override"


class BetaAccessCodeStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(slots=True)
class BetaAccessGrant:
    id: str
    wallet_address: str
    status: BetaAccessStatus
    source: BetaAccessSource
    user_id: str | None = None
    access_code_id: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class BetaAccessRequest:
    id: str
    status: BetaAccessStatus
    wallet_address: str | None = None
    contact: str | None = None
    normalized_contact: str | None = None
    name_or_handle: str | None = None
    interest: str | None = None
    community_or_org: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class BetaAccessCode:
    id: str
    code_hash: str
    label: str | None
    status: BetaAccessCodeStatus
    max_redemptions: int
    redemption_count: int
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class BetaAccessCodeRedemption:
    id: str
    code_id: str
    wallet_address: str
    user_id: str | None = None
    redeemed_at: datetime | None = None
