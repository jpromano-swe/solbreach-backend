"""Add certificate mint metadata fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607130002"
down_revision: str | None = "202607130001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("certifications", sa.Column("wallet_address", sa.String(length=64), nullable=True))
    op.add_column("certifications", sa.Column("asset_id", sa.String(length=128), nullable=True))
    op.add_column("certifications", sa.Column("certificate_pda", sa.String(length=128), nullable=True))
    op.add_column("certifications", sa.Column("metadata_uri", sa.String(length=500), nullable=True))
    op.add_column("certifications", sa.Column("minted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_certifications_wallet_address"), "certifications", ["wallet_address"], unique=False)
    op.create_index(op.f("ix_certifications_asset_id"), "certifications", ["asset_id"], unique=False)
    op.create_index(
        op.f("ix_certifications_certificate_pda"),
        "certifications",
        ["certificate_pda"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_certifications_certificate_pda"), table_name="certifications")
    op.drop_index(op.f("ix_certifications_asset_id"), table_name="certifications")
    op.drop_index(op.f("ix_certifications_wallet_address"), table_name="certifications")
    op.drop_column("certifications", "minted_at")
    op.drop_column("certifications", "metadata_uri")
    op.drop_column("certifications", "certificate_pda")
    op.drop_column("certifications", "asset_id")
    op.drop_column("certifications", "wallet_address")
