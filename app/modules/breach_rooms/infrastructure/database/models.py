from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin


class BreachRoomSubmissionModel(UUIDTimestampMixin, Base):
    __tablename__ = "breach_room_submissions"

    room_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    wallet_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    likelihood: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="submitted", nullable=False, index=True)
    review_state: Mapped[str] = mapped_column(
        String(40), default="reviewing", nullable=False, index=True
    )
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(nullable=True)
    pr_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pr_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pr_creation_status: Mapped[str] = mapped_column(
        String(40), default="pending", nullable=False, index=True
    )
    pr_creation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_findings_json: Mapped[list] = mapped_column("matched_findings", JSON, default=list, nullable=False)
    missed_findings_json: Mapped[list] = mapped_column("missed_findings", JSON, default=list, nullable=False)
    xp_earned: Mapped[int] = mapped_column(default=0, nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
