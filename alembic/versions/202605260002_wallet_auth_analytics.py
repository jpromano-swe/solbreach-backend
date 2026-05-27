"""wallet auth and analytics

Revision ID: 202605260002
Revises: 202605260001
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605260002"
down_revision: str | None = "202605260001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_auth_nonces",
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wallet_auth_nonces_wallet_address", "wallet_auth_nonces", ["wallet_address"]
    )
    op.create_index("ix_wallet_auth_nonces_nonce", "wallet_auth_nonces", ["nonce"], unique=True)

    op.create_table(
        "analytics_events",
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=True),
        sa.Column("subject_id", sa.String(length=120), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index(
        "ix_analytics_events_wallet_address", "analytics_events", ["wallet_address"]
    )
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])
    op.create_index("ix_analytics_events_subject_type", "analytics_events", ["subject_type"])
    op.create_index("ix_analytics_events_subject_id", "analytics_events", ["subject_id"])

    with op.batch_alter_table("certifications") as batch_op:
        batch_op.create_unique_constraint(
            "uq_certifications_user_slug",
            ["user_id", "slug"],
        )


def downgrade() -> None:
    with op.batch_alter_table("certifications") as batch_op:
        batch_op.drop_constraint("uq_certifications_user_slug", type_="unique")
    op.drop_index("ix_analytics_events_subject_id", table_name="analytics_events")
    op.drop_index("ix_analytics_events_subject_type", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_type", table_name="analytics_events")
    op.drop_index("ix_analytics_events_wallet_address", table_name="analytics_events")
    op.drop_index("ix_analytics_events_user_id", table_name="analytics_events")
    op.drop_table("analytics_events")
    op.drop_index("ix_wallet_auth_nonces_nonce", table_name="wallet_auth_nonces")
    op.drop_index("ix_wallet_auth_nonces_wallet_address", table_name="wallet_auth_nonces")
    op.drop_table("wallet_auth_nonces")
