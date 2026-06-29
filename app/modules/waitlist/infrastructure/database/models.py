from __future__ import annotations

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin


class WaitlistEntryModel(UUIDTimestampMixin, Base):
    __tablename__ = "waitlist_entries"

    name_or_handle: Mapped[str] = mapped_column(String(120), nullable=False)
    contact: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_contact: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    contact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_solana_dev: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False)
    community_or_org: Mapped[str | None] = mapped_column(String(160), nullable=True)
    interests_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
