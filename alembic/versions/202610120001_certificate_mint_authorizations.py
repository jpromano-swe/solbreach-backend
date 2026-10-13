"""Persist certificate mint replay protection and per-wallet rate limits."""

import sqlalchemy as sa

from alembic import op

revision = "202610120001"
down_revision = "202607240002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificate_mint_authorizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("wallet_address", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_certificate_mint_authorizations_wallet_address",
        "certificate_mint_authorizations",
        ["wallet_address"],
    )


def downgrade() -> None:
    op.drop_table("certificate_mint_authorizations")
