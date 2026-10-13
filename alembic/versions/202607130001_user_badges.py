"""add backend user badges

Revision ID: 202607130001
Revises: 202606300001
Create Date: 2026-07-13 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607130001"
down_revision: str | None = "202606300001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_badges",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("level_order", sa.Integer(), nullable=True),
        sa.Column("image", sa.String(length=500), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("earned", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slug", name="uq_user_badge_user_slug"),
    )
    op.create_index(op.f("ix_user_badges_user_id"), "user_badges", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_user_badges_wallet_address"), "user_badges", ["wallet_address"], unique=False
    )
    op.create_index(op.f("ix_user_badges_slug"), "user_badges", ["slug"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_badges_slug"), table_name="user_badges")
    op.drop_index(op.f("ix_user_badges_wallet_address"), table_name="user_badges")
    op.drop_index(op.f("ix_user_badges_user_id"), table_name="user_badges")
    op.drop_table("user_badges")
