from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, SoftDeleteMixin, UUIDTimestampMixin, utc_now


class LabModel(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "labs"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True, nullable=False)
    sandbox_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ResearchLabSessionModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_sessions"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    lab_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    lab_slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    template_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    runtime_instance_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    objective_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchLabFileModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_files"
    __table_args__ = (
        UniqueConstraint("session_id", "path", name="uq_research_lab_file_session_path"),
    )

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    writable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ResearchLabTestRunModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_test_runs"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    results_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchLabTerminalEventModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_terminal_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_research_lab_terminal_sequence"),
    )

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), index=True
    )
    test_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_lab_test_runs.id"), nullable=True, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stream: Mapped[str] = mapped_column(String(20), nullable=False)
    line: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchLabCompletionModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_completions"
    __table_args__ = (
        UniqueConstraint("user_id", "lab_id", name="uq_research_lab_completion_user_lab"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    lab_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    lab_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), nullable=False
    )
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchLabReportModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_reports"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_research_lab_report_session"),
    )

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    lab_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    fields_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchLabTransactionModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_transactions"
    __table_args__ = (
        UniqueConstraint("session_id", "transaction_ref", name="uq_research_lab_tx_ref"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_research_lab_tx_idem"),
        UniqueConstraint("session_id", "sequence_number", name="uq_research_lab_tx_seq"),
    )

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), index=True
    )
    transaction_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, server_default="legacy")
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    instruction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    logs_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchLabExploitVerificationModel(UUIDTimestampMixin, Base):
    __tablename__ = "research_lab_exploit_verifications"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_lab_sessions.id"), index=True
    )
    objective_ref: Mapped[str] = mapped_column(String(150), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
