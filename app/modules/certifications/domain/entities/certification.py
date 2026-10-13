from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class CertificationMintStatus(StrEnum):
    NOT_MINTED = "not_minted"
    PENDING = "pending"
    MINTED = "minted"
    FAILED = "failed"


class CertificationUnlockStatus(StrEnum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"


@dataclass(slots=True)
class Certification:
    id: str
    user_id: str
    slug: str
    title: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)
    unlock_status: CertificationUnlockStatus = CertificationUnlockStatus.UNLOCKED
    mint_status: CertificationMintStatus = CertificationMintStatus.NOT_MINTED
    wallet_address: str | None = None
    asset_id: str | None = None
    certificate_pda: str | None = None
    metadata_uri: str | None = None
    minted_at: datetime | None = None
    unlocked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
