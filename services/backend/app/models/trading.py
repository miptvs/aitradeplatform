from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.time import utcnow


class TradingAutomationProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trading_automation_profiles"

    mode: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_mode: Mapped[str] = mapped_column(String(30), default="semi_automatic")
    allowed_strategy_slugs: Mapped[list[str]] = mapped_column(default=list)
    tradable_actions: Mapped[list[str]] = mapped_column(default=lambda: ["buy"])
    allowed_provider_types: Mapped[list[str]] = mapped_column(default=list)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.58)
    default_order_notional: Mapped[float] = mapped_column(Float, default=100.0)
    stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_stop_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_orders_per_run: Mapped[int] = mapped_column(Integer, default=1)
    risk_profile: Mapped[str] = mapped_column(String(30), default="balanced")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_run_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
