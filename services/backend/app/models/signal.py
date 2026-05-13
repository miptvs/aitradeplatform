from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Signal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "signals"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    strategy_id: Mapped[str | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    indicators_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    related_news_ids: Mapped[list[str]] = mapped_column(default=list)
    related_event_ids: Mapped[list[str]] = mapped_column(default=list)
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_risk_reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_position_size_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    suggested_position_size_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    fallback_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), default="both")
    source_kind: Mapped[str] = mapped_column(String(30), default="auto")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)


class SignalEvaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "signal_evaluations"

    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), index=True)
    approved: Mapped[bool] = mapped_column(default=False)
    evaluator: Mapped[str] = mapped_column(String(120), default="risk-engine")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
