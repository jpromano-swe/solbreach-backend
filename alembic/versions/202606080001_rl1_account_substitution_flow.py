"""rl1 account substitution flow

Revision ID: 202606080001
Revises: 202605280002
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "202606080001"
down_revision = "202605280002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_lab_sessions",
        sa.Column("impact_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column(
            "verified_evidence_refs_json", sa.JSON(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column(
            "finding_review_passed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column("finding_review_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column("finding_review_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column("finding_review_answers_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column("failed_question_ids_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column(
            "critical_questions_passed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column("finding_review_feedback", sa.Text(), nullable=True),
    )
    op.add_column(
        "research_lab_sessions",
        sa.Column(
            "audit_report_builder_passed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "research_lab_transactions",
        sa.Column("account_deltas_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "research_lab_transactions",
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("research_lab_transactions", "evidence_refs_json")
    op.drop_column("research_lab_transactions", "account_deltas_json")
    op.drop_column("research_lab_sessions", "audit_report_builder_passed")
    op.drop_column("research_lab_sessions", "finding_review_feedback")
    op.drop_column("research_lab_sessions", "critical_questions_passed")
    op.drop_column("research_lab_sessions", "failed_question_ids_json")
    op.drop_column("research_lab_sessions", "finding_review_answers_json")
    op.drop_column("research_lab_sessions", "finding_review_score")
    op.drop_column("research_lab_sessions", "finding_review_attempts")
    op.drop_column("research_lab_sessions", "finding_review_passed")
    op.drop_column("research_lab_sessions", "verified_evidence_refs_json")
    op.drop_column("research_lab_sessions", "impact_verified")
