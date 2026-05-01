"""add cash reserve and per-model simulation controls

Revision ID: 20260424_0005
Revises: 20260423_0004
Create Date: 2026-04-24 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260424_0005"
down_revision = "20260423_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_accounts", sa.Column("provider_type", sa.String(length=80), nullable=True))
    op.add_column("simulation_accounts", sa.Column("model_name", sa.String(length=120), nullable=True))
    op.add_column("simulation_accounts", sa.Column("min_cash_reserve_percent", sa.Float(), nullable=True))
    op.add_column(
        "simulation_accounts",
        sa.Column("short_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_simulation_accounts_provider_type", "simulation_accounts", ["provider_type"])

    op.add_column("simulation_trades", sa.Column("provider_type", sa.String(length=50), nullable=True))
    op.add_column("simulation_trades", sa.Column("model_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_trades", "model_name")
    op.drop_column("simulation_trades", "provider_type")
    op.drop_index("ix_simulation_accounts_provider_type", table_name="simulation_accounts")
    op.drop_column("simulation_accounts", "short_enabled")
    op.drop_column("simulation_accounts", "min_cash_reserve_percent")
    op.drop_column("simulation_accounts", "model_name")
    op.drop_column("simulation_accounts", "provider_type")
