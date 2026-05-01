"""add operational realism scaffolds

Revision ID: 20260501_0007
Revises: 20260430_0006
Create Date: 2026-05-01 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260501_0007"
down_revision = "20260430_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "position_stop_events",
        sa.Column("position_id", sa.String(length=36), nullable=True),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("signal_id", sa.String(length=36), nullable=True),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("trailing_stop", sa.Float(), nullable=True),
        sa.Column("triggered_price", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_position_stop_events_position_id", "position_stop_events", ["position_id"])
    op.create_index("ix_position_stop_events_order_id", "position_stop_events", ["order_id"])
    op.create_index("ix_position_stop_events_signal_id", "position_stop_events", ["signal_id"])
    op.create_index("ix_position_stop_events_mode", "position_stop_events", ["mode"])
    op.create_index("ix_position_stop_events_observed_at", "position_stop_events", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_position_stop_events_observed_at", table_name="position_stop_events")
    op.drop_index("ix_position_stop_events_mode", table_name="position_stop_events")
    op.drop_index("ix_position_stop_events_signal_id", table_name="position_stop_events")
    op.drop_index("ix_position_stop_events_order_id", table_name="position_stop_events")
    op.drop_index("ix_position_stop_events_position_id", table_name="position_stop_events")
    op.drop_table("position_stop_events")
