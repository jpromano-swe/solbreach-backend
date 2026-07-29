"""add onboarding v2 fields"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607240002"
down_revision: str | None = "202607240001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("profile", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("real_experience", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("blockchain_security_profile", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("preferred_formats", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("security_learning_attempt", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("study_techniques", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("difficult_areas", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("hardest_practice_step", sa.Text(), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("practice_signals", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("security_relevance", sa.Integer(), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("beta_intent", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("contact_name", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("preferred_contact_channel", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("contact", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("utm_source", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("utm_medium", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("utm_campaign", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "onboarding_response_submissions",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="submitted"),
    )
    op.create_index(
        op.f("ix_onboarding_response_submissions_profile"),
        "onboarding_response_submissions",
        ["profile"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_response_submissions_blockchain_security_profile"),
        "onboarding_response_submissions",
        ["blockchain_security_profile"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_response_submissions_security_learning_attempt"),
        "onboarding_response_submissions",
        ["security_learning_attempt"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_response_submissions_security_relevance"),
        "onboarding_response_submissions",
        ["security_relevance"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_response_submissions_beta_intent"),
        "onboarding_response_submissions",
        ["beta_intent"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_response_submissions_status"),
        "onboarding_response_submissions",
        ["status"],
        unique=False,
    )
    op.alter_column("onboarding_response_submissions", "schema_version", server_default=None)
    op.alter_column("onboarding_response_submissions", "real_experience", server_default=None)
    op.alter_column("onboarding_response_submissions", "preferred_formats", server_default=None)
    op.alter_column("onboarding_response_submissions", "study_techniques", server_default=None)
    op.alter_column("onboarding_response_submissions", "difficult_areas", server_default=None)
    op.alter_column("onboarding_response_submissions", "practice_signals", server_default=None)
    op.alter_column("onboarding_response_submissions", "status", server_default=None)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_onboarding_response_submissions_status"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_response_submissions_beta_intent"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_response_submissions_security_relevance"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_response_submissions_security_learning_attempt"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_response_submissions_blockchain_security_profile"),
        table_name="onboarding_response_submissions",
    )
    op.drop_index(
        op.f("ix_onboarding_response_submissions_profile"),
        table_name="onboarding_response_submissions",
    )
    op.drop_column("onboarding_response_submissions", "status")
    op.drop_column("onboarding_response_submissions", "utm_campaign")
    op.drop_column("onboarding_response_submissions", "utm_medium")
    op.drop_column("onboarding_response_submissions", "utm_source")
    op.drop_column("onboarding_response_submissions", "contact")
    op.drop_column("onboarding_response_submissions", "preferred_contact_channel")
    op.drop_column("onboarding_response_submissions", "contact_name")
    op.drop_column("onboarding_response_submissions", "beta_intent")
    op.drop_column("onboarding_response_submissions", "security_relevance")
    op.drop_column("onboarding_response_submissions", "practice_signals")
    op.drop_column("onboarding_response_submissions", "hardest_practice_step")
    op.drop_column("onboarding_response_submissions", "difficult_areas")
    op.drop_column("onboarding_response_submissions", "study_techniques")
    op.drop_column("onboarding_response_submissions", "security_learning_attempt")
    op.drop_column("onboarding_response_submissions", "preferred_formats")
    op.drop_column("onboarding_response_submissions", "blockchain_security_profile")
    op.drop_column("onboarding_response_submissions", "real_experience")
    op.drop_column("onboarding_response_submissions", "profile")
    op.drop_column("onboarding_response_submissions", "schema_version")
