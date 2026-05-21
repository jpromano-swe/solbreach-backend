from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LabStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(slots=True)
class Lab:
    id: str
    slug: str
    title: str
    description: str
    status: LabStatus = LabStatus.DRAFT
    sandbox_config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
