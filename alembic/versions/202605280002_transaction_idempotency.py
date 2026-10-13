"""Add idempotency_key to transactions

Revision ID: 202605280002
Revises: 202605280001
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "202605280002"
down_revision = "202605280001"

def upgrade():
    op.add_column(
        "research_lab_transactions",
        sa.Column("idempotency_key", sa.String(100), nullable=False, server_default="legacy"),
    )
    op.create_unique_constraint(
        "uq_research_lab_tx_idem",
        "research_lab_transactions",
        ["session_id", "idempotency_key"],
    )

def downgrade():
    op.drop_constraint("uq_research_lab_tx_idem", "research_lab_transactions")
    op.drop_column("research_lab_transactions", "idempotency_key")
