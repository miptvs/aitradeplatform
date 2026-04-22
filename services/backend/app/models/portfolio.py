from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.time import utcnow


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "positions"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    broker_account_id: Mapped[str | None] = mapped_column(ForeignKey("broker_accounts.id"), nullable=True)
    simulation_account_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_accounts.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), index=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    strategy_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    avg_entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    broker_account_id: Mapped[str | None] = mapped_column(ForeignKey("broker_accounts.id"), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    position_id: Mapped[str | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), index=True)
    broker_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=True)
    strategy_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    side: Mapped[str] = mapped_column(String(20))
    order_type: Mapped[str] = mapped_column(String(30), default="market")
    quantity: Mapped[float] = mapped_column(Float)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    requested_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    entry_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_context: Mapped[dict[str, Any]] = mapped_column(default=dict)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Trade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trades"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    position_id: Mapped[str | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    entry_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Fill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fills"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "portfolio_snapshots"

    mode: Mapped[str] = mapped_column(String(30), index=True)
    broker_account_id: Mapped[str | None] = mapped_column(ForeignKey("broker_accounts.id"), nullable=True)
    simulation_account_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_accounts.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_value: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    daily_return: Mapped[float] = mapped_column(Float, default=0)
    weekly_return: Mapped[float] = mapped_column(Float, default=0)
    monthly_return: Mapped[float] = mapped_column(Float, default=0)
    exposure_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
