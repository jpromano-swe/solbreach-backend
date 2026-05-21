from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin


class CertificationModel(UUIDTimestampMixin, Base):
    __tablename__ = "certifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    unlock_status: Mapped[str] = mapped_column(
        String(30), default="unlocked", index=True, nullable=False
    )
    mint_status: Mapped[str] = mapped_column(
        String(30), default="not_minted", index=True, nullable=False
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
