from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BrokerAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "broker_accounts"

    name: Mapped[str] = mapped_column(String(100))
    broker_type: Mapped[str] = mapped_column(String(50), index=True)
    mode: Mapped[str] = mapped_column(String(50), default="live")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    live_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="disconnected")
    external_account_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[dict[str, Any]] = mapped_column(default=dict)


class BrokerSyncEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "broker_sync_events"

    broker_account_id: Mapped[str | None] = mapped_column(ForeignKey("broker_accounts.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    details_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
