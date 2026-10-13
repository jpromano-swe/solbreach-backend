"""extend analytics events for beta and rl1 funnel

Revision ID: 202606300001
Revises: 202606290001
Create Date: 2026-06-30 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606300001"
down_revision: str | None = "202606290001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analytics_events", sa.Column("session_id", sa.String(length=36), nullable=True))
    op.add_column("analytics_events", sa.Column("lab_id", sa.String(length=120), nullable=True))
    op.add_column("analytics_events", sa.Column("level_id", sa.String(length=120), nullable=True))
    op.add_column(
        "analytics_events",
        sa.Column("source", sa.String(length=40), server_default="backend", nullable=False),
    )
    op.add_column("analytics_events", sa.Column("request_id", sa.String(length=80), nullable=True))
    op.add_column("analytics_events", sa.Column("user_agent", sa.String(length=255), nullable=True))
    op.add_column("analytics_events", sa.Column("ip_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_analytics_events_session_id"), "analytics_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_analytics_events_lab_id"), "analytics_events", ["lab_id"], unique=False)
    op.create_index(op.f("ix_analytics_events_level_id"), "analytics_events", ["level_id"], unique=False)
    op.create_index(op.f("ix_analytics_events_request_id"), "analytics_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_analytics_events_request_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_level_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_lab_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_session_id"), table_name="analytics_events")
    op.drop_column("analytics_events", "ip_hash")
    op.drop_column("analytics_events", "user_agent")
    op.drop_column("analytics_events", "request_id")
    op.drop_column("analytics_events", "source")
    op.drop_column("analytics_events", "level_id")
    op.drop_column("analytics_events", "lab_id")
    op.drop_column("analytics_events", "session_id")
