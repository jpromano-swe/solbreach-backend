"""add waitlist entries

Revision ID: 202606230001
Revises: 202606160001
Create Date: 2026-06-23 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202606230001"
down_revision: str | None = "202606160001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("name_or_handle", sa.String(length=120), nullable=False),
        sa.Column("contact", sa.String(length=255), nullable=False),
        sa.Column("normalized_contact", sa.String(length=255), nullable=False),
        sa.Column("contact_type", sa.String(length=30), nullable=False),
        sa.Column("is_solana_dev", sa.Boolean(), nullable=False),
        sa.Column("community_or_org", sa.String(length=160), nullable=True),
        sa.Column("interests_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_waitlist_entries_normalized_contact"),
        "waitlist_entries",
        ["normalized_contact"],
        unique=True,
    )
    op.create_index(
        op.f("ix_waitlist_entries_is_solana_dev"),
        "waitlist_entries",
        ["is_solana_dev"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_waitlist_entries_is_solana_dev"), table_name="waitlist_entries")
    op.drop_index(op.f("ix_waitlist_entries_normalized_contact"), table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
