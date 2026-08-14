"""Add parameters to transactions

Revision ID: 202605280001
Revises: 202605270001
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "202605280001"
down_revision = "202605270001"

def upgrade():
    op.add_column("research_lab_transactions", sa.Column("parameters_json", sa.JSON(), nullable=False, server_default="{}"))

def downgrade():
    op.drop_column("research_lab_transactions", "parameters_json")
