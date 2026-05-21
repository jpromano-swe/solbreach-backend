from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, SoftDeleteMixin, UUIDTimestampMixin, utc_now


class LevelModel(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "levels"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    vulnerability_id: Mapped[str | None] = mapped_column(
        ForeignKey("vulnerabilities.id"), index=True
    )
    vulnerability_category: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    difficulty: Mapped[str] = mapped_column(String(40), default="easy", index=True, nullable=False)
    objectives: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verification_requirements: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    repository_url: Mapped[str | None] = mapped_column(String(500))
    resources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    verification_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    deployment_info: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class LevelSessionModel(UUIDTimestampMixin, Base):
    __tablename__ = "level_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    level_id: Mapped[str] = mapped_column(ForeignKey("levels.id"), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
