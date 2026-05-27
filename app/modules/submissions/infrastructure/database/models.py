from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin


class SubmissionModel(UUIDTimestampMixin, Base):
    __tablename__ = "submissions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    level_id: Mapped[str] = mapped_column(ForeignKey("levels.id"), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("level_sessions.id"), index=True, nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(default=1, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tx_signature: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    wallet_address: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True, nullable=False)
    verification_message: Mapped[str | None] = mapped_column(Text)
    verification_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
