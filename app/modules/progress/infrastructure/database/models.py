from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin, utc_now


class ProgressModel(UUIDTimestampMixin, Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "level_id", name="uq_progress_user_level"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    level_id: Mapped[str] = mapped_column(ForeignKey("levels.id"), index=True, nullable=False)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
