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
    unlocked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
