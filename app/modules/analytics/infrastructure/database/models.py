from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin, utc_now


class AnalyticsEventModel(UUIDTimestampMixin, Base):
    __tablename__ = "analytics_events"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    wallet_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subject_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    subject_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    lab_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    level_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="backend")
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
