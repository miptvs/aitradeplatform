from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SystemHealthEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_health_events"

    component: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
