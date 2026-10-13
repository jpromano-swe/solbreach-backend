"""add onboarding responses"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607240001"
down_revision: str | None = "202607130002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "onboarding_response_submissions",
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
        sa.Column("step", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("responses", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_onboarding_responses_user_id"),
        "onboarding_response_submissions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_responses_wallet_address"),
        "onboarding_response_submissions",
        ["wallet_address"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_responses_step"),
        "onboarding_response_submissions",
        ["step"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_responses_request_id"),
        "onboarding_response_submissions",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_onboarding_responses_request_id"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_responses_step"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_responses_wallet_address"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_responses_user_id"),
        table_name="onboarding_response_submissions",
    )
    op.drop_table("onboarding_response_submissions")
