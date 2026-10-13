from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin, utc_now


class BetaAccessGrantModel(UUIDTimestampMixin, Base):
    __tablename__ = "beta_access_grants"

    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    access_code_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("beta_access_codes.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BetaAccessRequestModel(UUIDTimestampMixin, Base):
    __tablename__ = "beta_access_requests"

    wallet_address: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_contact: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    name_or_handle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    community_or_org: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)


class BetaAccessCodeModel(UUIDTimestampMixin, Base):
    __tablename__ = "beta_access_codes"

    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    max_redemptions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    redemption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BetaAccessCodeRedemptionModel(Base):
    __tablename__ = "beta_access_code_redemptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("beta_access_codes.id"), index=True, nullable=False
    )
    wallet_address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
