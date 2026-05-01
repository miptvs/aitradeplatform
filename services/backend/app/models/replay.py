from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReplayRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "replay_runs"

    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="created", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    date_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    starting_cash: Mapped[float] = mapped_column(Float)
    fees_bps: Mapped[float] = mapped_column(Float, default=5)
    slippage_bps: Mapped[float] = mapped_column(Float, default=2)
    cash_reserve_percent: Mapped[float] = mapped_column(Float, default=0)
    short_enabled: Mapped[bool] = mapped_column(default=False)
    selected_models: Mapped[list[str]] = mapped_column(default=list)
    symbols: Mapped[list[str]] = mapped_column(default=list)
    config_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReplayModelResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "replay_model_results"

    replay_run_id: Mapped[str] = mapped_column(ForeignKey("replay_runs.id"), index=True)
    provider_type: Mapped[str] = mapped_column(String(80), index=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    cash: Mapped[float] = mapped_column(Float, default=0)
    portfolio_value: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    total_return: Mapped[float] = mapped_column(Float, default=0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0)
    sharpe: Mapped[float] = mapped_column(Float, default=0)
    sortino: Mapped[float] = mapped_column(Float, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0)
    average_holding_time_minutes: Mapped[float] = mapped_column(Float, default=0)
    turnover: Mapped[float] = mapped_column(Float, default=0)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    rejected_trades: Mapped[int] = mapped_column(Integer, default=0)
    invalid_signals: Mapped[int] = mapped_column(Integer, default=0)
    useful_signal_rate: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
