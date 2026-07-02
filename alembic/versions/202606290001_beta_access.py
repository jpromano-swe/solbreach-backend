"""add beta access tables

Revision ID: 202606290001
Revises: 202606230001
Create Date: 2026-06-29 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202606290001"
down_revision: str | None = "202606230001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beta_access_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), server_default="1", nullable=False),
        sa.Column("redemption_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_beta_access_codes_code_hash"),
        "beta_access_codes",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_beta_access_codes_status"),
        "beta_access_codes",
        ["status"],
        unique=False,
    )

    op.create_table(
        "beta_access_grants",
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("access_code_id", sa.String(length=36), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["access_code_id"], ["beta_access_codes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_beta_access_grants_wallet_address"),
        "beta_access_grants",
        ["wallet_address"],
        unique=True,
    )
    op.create_index(
        op.f("ix_beta_access_grants_user_id"),
        "beta_access_grants",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_beta_access_grants_status"),
        "beta_access_grants",
        ["status"],
        unique=False,
    )

    op.create_table(
        "beta_access_requests",
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("normalized_contact", sa.String(length=255), nullable=True),
        sa.Column("name_or_handle", sa.String(length=120), nullable=True),
        sa.Column("interest", sa.String(length=80), nullable=True),
        sa.Column("community_or_org", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_beta_access_requests_wallet_address"),
        "beta_access_requests",
        ["wallet_address"],
        unique=True,
    )
    op.create_index(
        op.f("ix_beta_access_requests_normalized_contact"),
        "beta_access_requests",
        ["normalized_contact"],
        unique=True,
    )
    op.create_index(
        op.f("ix_beta_access_requests_status"),
        "beta_access_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "beta_access_code_redemptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code_id", sa.String(length=36), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["code_id"], ["beta_access_codes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_id", "wallet_address", name="uq_beta_access_code_wallet"),
    )
    op.create_index(
        op.f("ix_beta_access_code_redemptions_code_id"),
        "beta_access_code_redemptions",
        ["code_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_beta_access_code_redemptions_wallet_address"),
        "beta_access_code_redemptions",
        ["wallet_address"],
        unique=False,
    )
    op.create_index(
        op.f("ix_beta_access_code_redemptions_user_id"),
        "beta_access_code_redemptions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_beta_access_code_redemptions_user_id"),
        table_name="beta_access_code_redemptions",
    )
    op.drop_index(
        op.f("ix_beta_access_code_redemptions_wallet_address"),
        table_name="beta_access_code_redemptions",
    )
    op.drop_index(
        op.f("ix_beta_access_code_redemptions_code_id"),
        table_name="beta_access_code_redemptions",
    )
    op.drop_table("beta_access_code_redemptions")
    op.drop_index(op.f("ix_beta_access_requests_status"), table_name="beta_access_requests")
    op.drop_index(
        op.f("ix_beta_access_requests_normalized_contact"), table_name="beta_access_requests"
    )
    op.drop_index(
        op.f("ix_beta_access_requests_wallet_address"), table_name="beta_access_requests"
    )
    op.drop_table("beta_access_requests")
    op.drop_index(op.f("ix_beta_access_grants_status"), table_name="beta_access_grants")
    op.drop_index(op.f("ix_beta_access_grants_user_id"), table_name="beta_access_grants")
    op.drop_index(
        op.f("ix_beta_access_grants_wallet_address"), table_name="beta_access_grants"
    )
    op.drop_table("beta_access_grants")
    op.drop_index(op.f("ix_beta_access_codes_status"), table_name="beta_access_codes")
    op.drop_index(op.f("ix_beta_access_codes_code_hash"), table_name="beta_access_codes")
    op.drop_table("beta_access_codes")
