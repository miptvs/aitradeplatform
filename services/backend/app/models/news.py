from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NewsArticle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "news_articles"

    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(500), unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    affected_symbols: Mapped[list[str]] = mapped_column(default=list)
    provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    analysis_metadata: Mapped[dict[str, Any]] = mapped_column(default=dict)


class ExtractedEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extracted_events"

    news_article_id: Mapped[str | None] = mapped_column(ForeignKey("news_articles.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    impact_score: Mapped[float] = mapped_column(Float, default=0.5)
    summary: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(default=dict)
