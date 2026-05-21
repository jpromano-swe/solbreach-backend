"""initial schema

Revision ID: 202605210001
Revises:
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605210001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar", sa.String(length=500), nullable=True),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("reputation_score", sa.Integer(), nullable=False),
        sa.Column("completed_levels", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_wallet_address", "users", ["wallet_address"], unique=True)

    op.create_table(
        "vulnerabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vulnerabilities_category", "vulnerabilities", ["category"])
    op.create_index("ix_vulnerabilities_difficulty", "vulnerabilities", ["difficulty"])
    op.create_index("ix_vulnerabilities_slug", "vulnerabilities", ["slug"], unique=True)

    op.create_table(
        "labs",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("sandbox_config", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_labs_slug", "labs", ["slug"], unique=True)
    op.create_index("ix_labs_status", "labs", ["status"])

    op.create_table(
        "levels",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("vulnerability_id", sa.String(length=36), nullable=True),
        sa.Column("vulnerability_category", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=40), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("verification_requirements", sa.JSON(), nullable=False),
        sa.Column("repository_url", sa.String(length=500), nullable=True),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("verification_config", sa.JSON(), nullable=False),
        sa.Column("deployment_info", sa.JSON(), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_levels_is_active", "levels", ["is_active"])
    op.create_index("ix_levels_difficulty", "levels", ["difficulty"])
    op.create_index("ix_levels_order", "levels", ["order"])
    op.create_index("ix_levels_slug", "levels", ["slug"], unique=True)
    op.create_index("ix_levels_stage", "levels", ["stage"])
    op.create_index("ix_levels_vulnerability_id", "levels", ["vulnerability_id"])

    op.create_table(
        "level_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("level_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["level_id"], ["levels.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_level_sessions_level_id", "level_sessions", ["level_id"])
    op.create_index("ix_level_sessions_state", "level_sessions", ["state"])
    op.create_index("ix_level_sessions_user_id", "level_sessions", ["user_id"])

    op.create_table(
        "certifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("unlock_status", sa.String(length=30), nullable=False),
        sa.Column("mint_status", sa.String(length=30), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certifications_mint_status", "certifications", ["mint_status"])
    op.create_index("ix_certifications_slug", "certifications", ["slug"])
    op.create_index("ix_certifications_unlock_status", "certifications", ["unlock_status"])
    op.create_index("ix_certifications_user_id", "certifications", ["user_id"])

    op.create_table(
        "progress",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("level_id", sa.String(length=36), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["level_id"], ["levels.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "level_id", name="uq_progress_user_level"),
    )
    op.create_index("ix_progress_level_id", "progress", ["level_id"])
    op.create_index("ix_progress_user_id", "progress", ["user_id"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        *timestamps(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("level_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("verification_message", sa.Text(), nullable=True),
        sa.Column("verification_result", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["level_id"], ["levels.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["level_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submissions_level_id", "submissions", ["level_id"])
    op.create_index("ix_submissions_session_id", "submissions", ["session_id"])
    op.create_index("ix_submissions_status", "submissions", ["status"])
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])


def downgrade() -> None:
    op.drop_table("submissions")
    op.drop_table("progress")
    op.drop_table("certifications")
    op.drop_table("level_sessions")
    op.drop_table("levels")
    op.drop_table("labs")
    op.drop_table("vulnerabilities")
    op.drop_table("users")
