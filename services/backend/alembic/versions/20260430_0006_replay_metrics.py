"""add replay backtest scaffold tables

Revision ID: 20260430_0006
Revises: 20260424_0005
Create Date: 2026-04-30 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260430_0006"
down_revision = "20260424_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_accounts", sa.Column("short_borrow_fee_bps", sa.Float(), nullable=False, server_default="0"))
    op.add_column("simulation_accounts", sa.Column("short_margin_requirement", sa.Float(), nullable=False, server_default="1.5"))
    op.add_column("simulation_accounts", sa.Column("partial_fill_ratio", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("simulation_accounts", sa.Column("enforce_market_hours", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    op.create_table(
        "replay_runs",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("starting_cash", sa.Float(), nullable=False),
        sa.Column("fees_bps", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Float(), nullable=False),
        sa.Column("cash_reserve_percent", sa.Float(), nullable=False),
        sa.Column("short_enabled", sa.Boolean(), nullable=False),
        sa.Column("selected_models", sa.JSON(), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_replay_runs_status", "replay_runs", ["status"])
    op.create_index("ix_replay_runs_date_start", "replay_runs", ["date_start"])
    op.create_index("ix_replay_runs_date_end", "replay_runs", ["date_end"])

    op.create_table(
        "replay_model_results",
        sa.Column("replay_run_id", sa.String(length=36), nullable=False),
        sa.Column("provider_type", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("portfolio_value", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("total_return", sa.Float(), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=False),
        sa.Column("sharpe", sa.Float(), nullable=False),
        sa.Column("sortino", sa.Float(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False),
        sa.Column("profit_factor", sa.Float(), nullable=False),
        sa.Column("average_holding_time_minutes", sa.Float(), nullable=False),
        sa.Column("turnover", sa.Float(), nullable=False),
        sa.Column("trades", sa.Integer(), nullable=False),
        sa.Column("rejected_trades", sa.Integer(), nullable=False),
        sa.Column("invalid_signals", sa.Integer(), nullable=False),
        sa.Column("useful_signal_rate", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("model_cost", sa.Float(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["replay_run_id"], ["replay_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_replay_model_results_replay_run_id", "replay_model_results", ["replay_run_id"])
    op.create_index("ix_replay_model_results_provider_type", "replay_model_results", ["provider_type"])
    op.create_index("ix_replay_model_results_status", "replay_model_results", ["status"])


def downgrade() -> None:
    op.drop_index("ix_replay_model_results_status", table_name="replay_model_results")
    op.drop_index("ix_replay_model_results_provider_type", table_name="replay_model_results")
    op.drop_index("ix_replay_model_results_replay_run_id", table_name="replay_model_results")
    op.drop_table("replay_model_results")
    op.drop_index("ix_replay_runs_date_end", table_name="replay_runs")
    op.drop_index("ix_replay_runs_date_start", table_name="replay_runs")
    op.drop_index("ix_replay_runs_status", table_name="replay_runs")
    op.drop_table("replay_runs")
    op.drop_column("simulation_accounts", "enforce_market_hours")
    op.drop_column("simulation_accounts", "partial_fill_ratio")
    op.drop_column("simulation_accounts", "short_margin_requirement")
    op.drop_column("simulation_accounts", "short_borrow_fee_bps")
