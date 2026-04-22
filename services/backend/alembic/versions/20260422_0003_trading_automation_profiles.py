"""add trading automation profiles

Revision ID: 20260422_0003
Revises: 20260408_0002
Create Date: 2026-04-22 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260422_0003"
down_revision = "20260408_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trading_automation_profiles",
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("automation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_mode", sa.String(length=30), nullable=False, server_default="semi_automatic"),
        sa.Column("allowed_strategy_slugs", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("tradable_actions", sa.JSON(), nullable=False, server_default=sa.text("'[\"buy\"]'::json")),
        sa.Column("allowed_provider_types", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.58"),
        sa.Column("default_order_notional", sa.Float(), nullable=False, server_default="100"),
        sa.Column("stop_loss_pct", sa.Float(), nullable=True),
        sa.Column("take_profit_pct", sa.Float(), nullable=True),
        sa.Column("trailing_stop_pct", sa.Float(), nullable=True),
        sa.Column("max_orders_per_run", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("risk_profile", sa.String(length=30), nullable=False, server_default="balanced"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(length=30), nullable=True),
        sa.Column("last_run_message", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trading_automation_profiles_mode"), "trading_automation_profiles", ["mode"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_trading_automation_profiles_mode"), table_name="trading_automation_profiles")
    op.drop_table("trading_automation_profiles")
