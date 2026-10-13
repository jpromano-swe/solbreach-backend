from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.waitlist.domain.entities.waitlist_entry import WaitlistInterest


class WaitlistCreateRequest(BaseModel):
    name_or_handle: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=1, max_length=255)
    is_solana_dev: bool
    interests: list[WaitlistInterest] = Field(min_length=1)
    community_or_org: str | None = Field(default=None, max_length=160)

    @field_validator("name_or_handle", "contact", mode="before")
    @classmethod
    def trim_required(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("must not be blank")
            return stripped
        return value

    @field_validator("community_or_org", mode="before")
    @classmethod
    def trim_optional(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = " ".join(value.strip().split())
            return stripped or None
        return value


class WaitlistEntryResponse(BaseModel):
    id: str
    already_joined: bool
    name_or_handle: str
    contact: str
    contact_type: str
    is_solana_dev: bool
    interests: list[str]
    community_or_org: str | None
    created_at: datetime
    updated_at: datetime


class WaitlistAPIResponse(BaseModel):
    success: bool = True
    data: Any
    error: Any = None
