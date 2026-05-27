"""research lab reports

Revision ID: 202605260003
Revises: 202605260002
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605260003"
down_revision: str | None = "202605260002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_lab_reports",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lab_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("validation_result_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["research_lab_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_research_lab_report_session"),
    )
    op.create_index("ix_research_lab_reports_lab_id", "research_lab_reports", ["lab_id"])
    op.create_index(
        "ix_research_lab_reports_session_id", "research_lab_reports", ["session_id"]
    )
    op.create_index("ix_research_lab_reports_status", "research_lab_reports", ["status"])
    op.create_index("ix_research_lab_reports_user_id", "research_lab_reports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_research_lab_reports_user_id", table_name="research_lab_reports")
    op.drop_index("ix_research_lab_reports_status", table_name="research_lab_reports")
    op.drop_index("ix_research_lab_reports_session_id", table_name="research_lab_reports")
    op.drop_index("ix_research_lab_reports_lab_id", table_name="research_lab_reports")
    op.drop_table("research_lab_reports")
