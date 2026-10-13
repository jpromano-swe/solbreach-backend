"""rl1 transaction protocol state

Revision ID: 202606160001
Revises: 202606080001
Create Date: 2026-06-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "202606160001"
down_revision = "202606080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_lab_transactions",
        sa.Column("protocol_state_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "research_lab_transactions",
        sa.Column("user_facing_evidence_json", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("research_lab_transactions", "user_facing_evidence_json")
    op.drop_column("research_lab_transactions", "protocol_state_json")
