"""research labs runtime state

Revision ID: 202605260001
Revises: 202605210002
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605260001"
down_revision: str | None = "202605210002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_lab_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lab_id", sa.String(length=100), nullable=False),
        sa.Column("lab_slug", sa.String(length=100), nullable=False),
        sa.Column("template_ref", sa.String(length=255), nullable=False),
        sa.Column("runtime_type", sa.String(length=50), nullable=False),
        sa.Column("runtime_instance_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("objective_progress", sa.Integer(), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_lab_sessions_lab_id", "research_lab_sessions", ["lab_id"])
    op.create_index("ix_research_lab_sessions_lab_slug", "research_lab_sessions", ["lab_slug"])
    op.create_index("ix_research_lab_sessions_status", "research_lab_sessions", ["status"])
    op.create_index("ix_research_lab_sessions_user_id", "research_lab_sessions", ["user_id"])

    op.create_table(
        "research_lab_files",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("writable", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["research_lab_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "path", name="uq_research_lab_file_session_path"),
    )
    op.create_index("ix_research_lab_files_session_id", "research_lab_files", ["session_id"])

    op.create_table(
        "research_lab_test_runs",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["research_lab_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_lab_test_runs_session_id", "research_lab_test_runs", ["session_id"]
    )
    op.create_index("ix_research_lab_test_runs_status", "research_lab_test_runs", ["status"])

    op.create_table(
        "research_lab_terminal_events",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("test_run_id", sa.String(length=36), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stream", sa.String(length=20), nullable=False),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["research_lab_sessions.id"]),
        sa.ForeignKeyConstraint(["test_run_id"], ["research_lab_test_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_research_lab_terminal_sequence"),
    )
    op.create_index(
        "ix_research_lab_terminal_events_session_id",
        "research_lab_terminal_events",
        ["session_id"],
    )
    op.create_index(
        "ix_research_lab_terminal_events_test_run_id",
        "research_lab_terminal_events",
        ["test_run_id"],
    )

    op.create_table(
        "research_lab_completions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lab_id", sa.String(length=100), nullable=False),
        sa.Column("lab_slug", sa.String(length=100), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["research_lab_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lab_id", name="uq_research_lab_completion_user_lab"),
    )
    op.create_index(
        "ix_research_lab_completions_lab_id", "research_lab_completions", ["lab_id"]
    )
    op.create_index(
        "ix_research_lab_completions_user_id", "research_lab_completions", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_research_lab_completions_user_id", table_name="research_lab_completions")
    op.drop_index("ix_research_lab_completions_lab_id", table_name="research_lab_completions")
    op.drop_table("research_lab_completions")
    op.drop_index(
        "ix_research_lab_terminal_events_test_run_id",
        table_name="research_lab_terminal_events",
    )
    op.drop_index(
        "ix_research_lab_terminal_events_session_id",
        table_name="research_lab_terminal_events",
    )
    op.drop_table("research_lab_terminal_events")
    op.drop_index("ix_research_lab_test_runs_status", table_name="research_lab_test_runs")
    op.drop_index("ix_research_lab_test_runs_session_id", table_name="research_lab_test_runs")
    op.drop_table("research_lab_test_runs")
    op.drop_index("ix_research_lab_files_session_id", table_name="research_lab_files")
    op.drop_table("research_lab_files")
    op.drop_index("ix_research_lab_sessions_user_id", table_name="research_lab_sessions")
    op.drop_index("ix_research_lab_sessions_status", table_name="research_lab_sessions")
    op.drop_index("ix_research_lab_sessions_lab_slug", table_name="research_lab_sessions")
    op.drop_index("ix_research_lab_sessions_lab_id", table_name="research_lab_sessions")
    op.drop_table("research_lab_sessions")
