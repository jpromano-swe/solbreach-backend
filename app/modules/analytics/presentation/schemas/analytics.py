from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsEventCreateRequest(BaseModel):
    event_name: str = Field(alias="eventName", min_length=1, max_length=80)
    wallet_address: str | None = Field(default=None, alias="walletAddress", max_length=64)
    session_id: str | None = Field(default=None, alias="sessionId", max_length=36)
    lab_id: str | None = Field(default=None, alias="labId", max_length=120)
    level_id: str | None = Field(default=None, alias="levelId", max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
