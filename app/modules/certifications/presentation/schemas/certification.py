from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.modules.certifications.domain.entities.certification import (
    CertificationMintStatus,
    CertificationUnlockStatus,
)


class CertificationResponse(BaseModel):
    id: str
    user_id: str
    slug: str
    title: str
    description: str
    metadata: dict[str, Any]
    unlock_status: CertificationUnlockStatus
    mint_status: CertificationMintStatus
    wallet_address: str | None = None
    asset_id: str | None = None
    certificate_pda: str | None = None
    metadata_uri: str | None = None
    minted_at: datetime | None = None
    unlocked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CertificateSlotResponse(BaseModel):
    certificateId: str
    certificateNumber: int
    level: int
    title: str
    status: str
    minted: bool
    mintedAt: str | None = None
    assetId: str | None = None
    certificatePda: str | None = None
    metadataUri: str
    imageUri: str


class CertificateSummaryResponse(BaseModel):
    minted: int
    total: int


class WalletCertificatesResponse(BaseModel):
    walletAddress: str | None
    certificates: list[CertificateSlotResponse]
    summary: CertificateSummaryResponse
