from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, UUIDTimestampMixin


class OnboardingResponseModel(UUIDTimestampMixin, Base):
    __tablename__ = "onboarding_response_submissions"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    wallet_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    step: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), default="beta_onboarding", nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    real_experience_json: Mapped[list] = mapped_column("real_experience", JSON, default=list, nullable=False)
    blockchain_security_profile: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    preferred_formats_json: Mapped[list] = mapped_column("preferred_formats", JSON, default=list, nullable=False)
    security_learning_attempt: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    study_techniques_json: Mapped[list] = mapped_column("study_techniques", JSON, default=list, nullable=False)
    difficult_areas_json: Mapped[list] = mapped_column("difficult_areas", JSON, default=list, nullable=False)
    hardest_practice_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    practice_signals_json: Mapped[list] = mapped_column("practice_signals", JSON, default=list, nullable=False)
    security_relevance: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    beta_intent: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    preferred_contact_channel: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="submitted", nullable=False, index=True)
    responses_json: Mapped[dict | list] = mapped_column("responses", JSON, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
