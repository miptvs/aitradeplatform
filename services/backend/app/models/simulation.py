from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SimulationAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "simulation_accounts"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    provider_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    starting_cash: Mapped[float] = mapped_column(Float)
    cash_balance: Mapped[float] = mapped_column(Float)
    fees_bps: Mapped[float] = mapped_column(Float, default=5)
    slippage_bps: Mapped[float] = mapped_column(Float, default=2)
    latency_ms: Mapped[int] = mapped_column(Integer, default=50)
    min_cash_reserve_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    short_borrow_fee_bps: Mapped[float] = mapped_column(Float, default=0)
    short_margin_requirement: Mapped[float] = mapped_column(Float, default=1.5)
    partial_fill_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    decimal_precision: Mapped[int] = mapped_column(Integer, default=6)
    enforce_market_hours: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reset_count: Mapped[int] = mapped_column(Integer, default=0)


class SimulationOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "simulation_orders"

    simulation_account_id: Mapped[str] = mapped_column(ForeignKey("simulation_accounts.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    side: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(Float)
    requested_price: Mapped[float] = mapped_column(Float)
    executed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=True)
    strategy_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SimulationTrade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "simulation_trades"

    simulation_account_id: Mapped[str] = mapped_column(ForeignKey("simulation_accounts.id"), index=True)
    simulation_order_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_orders.id"), nullable=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    side: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
