"""add scheduled automation controls

Revision ID: 20260423_0004
Revises: 20260422_0003
Create Date: 2026-04-23 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260423_0004"
down_revision = "20260422_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trading_automation_profiles",
        sa.Column("scheduled_execution_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "trading_automation_profiles",
        sa.Column("execution_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
    )
    op.add_column(
        "trading_automation_profiles",
        sa.Column("last_scheduled_run_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trading_automation_profiles", "last_scheduled_run_at")
    op.drop_column("trading_automation_profiles", "execution_interval_seconds")
    op.drop_column("trading_automation_profiles", "scheduled_execution_enabled")
