from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.modules.labs.domain.entities.lab import LabStatus


class LabResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    status: LabStatus
    sandbox_config: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
