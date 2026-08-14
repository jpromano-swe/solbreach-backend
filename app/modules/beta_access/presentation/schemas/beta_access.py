from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BetaAccessStatusResponse(BaseModel):
    wallet_address: str = Field(alias="walletAddress")
    has_access: bool = Field(alias="hasAccess")
    access_source: str | None = Field(alias="accessSource")
    status: str

    model_config = ConfigDict(populate_by_name=True)


class BetaAccessRequestCreateRequest(BaseModel):
    wallet_address: str | None = Field(default=None, alias="walletAddress", max_length=64)
    contact: str | None = Field(default=None, max_length=255)
    name_or_handle: str | None = Field(default=None, alias="nameOrHandle", max_length=120)
    interest: str | None = Field(default=None, max_length=80)
    community_or_org: str | None = Field(default=None, alias="communityOrOrg", max_length=160)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator(
        "wallet_address",
        "contact",
        "name_or_handle",
        "interest",
        "community_or_org",
        mode="before",
    )
    @classmethod
    def trim_optional(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = " ".join(value.strip().split())
            return normalized or None
        return value


class BetaAccessRequestResponse(BaseModel):
    request_id: str = Field(alias="requestId")
    status: str
    message: str

    model_config = ConfigDict(populate_by_name=True)


class BetaAccessRedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=96)
    wallet_address: str = Field(alias="walletAddress", min_length=1, max_length=64)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("code", "wallet_address", mode="before")
    @classmethod
    def trim_required(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("must not be blank")
            return stripped
        return value
