from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_configs"

    provider_type: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    base_url: Mapped[str] = mapped_column(String(255))
    default_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=512)
    context_window: Mapped[int] = mapped_column(Integer, default=8192)
    tool_calling_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reasoning_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    task_defaults: Mapped[dict[str, Any]] = mapped_column(default=dict)
    settings_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_health_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_health_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelTaskMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_task_mappings"

    task_name: Mapped[str] = mapped_column(String(120), unique=True)
    provider_type: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(120))
    fallback_chain: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)


class ModelRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_runs"

    task_name: Mapped[str] = mapped_column(String(120), index=True)
    provider_type: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(50))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
