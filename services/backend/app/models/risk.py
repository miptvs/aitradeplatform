from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RiskRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_rules"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    scope: Mapped[str] = mapped_column(String(50), default="global")
    rule_type: Mapped[str] = mapped_column(String(80), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_close: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
