from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class WaitlistContactType(StrEnum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    X = "x"
    UNKNOWN = "unknown"


class WaitlistInterest(StrEnum):
    LEARN_SOLANA_SECURITY = "learn_solana_security"
    RUST_DEVELOPER = "rust_developer"
    COMMUNITY_OR_COHORT = "community_or_cohort"
    FIRST_FLIGHT_AUDITS = "first_flight_audits"
    LIKES_THE_PRODUCT = "likes_the_product"
    PARTNER_INTEREST = "partner_interest"


@dataclass(slots=True)
class WaitlistEntry:
    id: str
    name_or_handle: str
    contact: str
    normalized_contact: str
    contact_type: WaitlistContactType
    is_solana_dev: bool
    community_or_org: str | None
    interests: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None
