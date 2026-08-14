"""add breach room submissions"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608140001"
down_revision: str | None = "202607240002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "breach_room_submissions",
        sa.Column("room_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("likelihood", sa.String(length=20), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("report_markdown", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("review_state", sa.String(length=40), nullable=False),
        sa.Column("pr_url", sa.String(length=500), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("pr_branch", sa.String(length=255), nullable=True),
        sa.Column("pr_file_path", sa.String(length=500), nullable=True),
        sa.Column("pr_creation_status", sa.String(length=40), nullable=False),
        sa.Column("pr_creation_error", sa.Text(), nullable=True),
        sa.Column("matched_findings", sa.JSON(), nullable=False),
        sa.Column("missed_findings", sa.JSON(), nullable=False),
        sa.Column("xp_earned", sa.Integer(), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_breach_room_submissions_room_id"),
        "breach_room_submissions",
        ["room_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_user_id"),
        "breach_room_submissions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_wallet_address"),
        "breach_room_submissions",
        ["wallet_address"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_severity"),
        "breach_room_submissions",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_likelihood"),
        "breach_room_submissions",
        ["likelihood"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_status"),
        "breach_room_submissions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_review_state"),
        "breach_room_submissions",
        ["review_state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_breach_room_submissions_pr_creation_status"),
        "breach_room_submissions",
        ["pr_creation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_breach_room_submissions_pr_creation_status"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_review_state"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_status"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_likelihood"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_severity"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_wallet_address"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_user_id"),
        table_name="breach_room_submissions",
    )
    op.drop_index(
        op.f("ix_breach_room_submissions_room_id"),
        table_name="breach_room_submissions",
    )
    op.drop_table("breach_room_submissions")
