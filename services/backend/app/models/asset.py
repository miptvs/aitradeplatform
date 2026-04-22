from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlists"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    asset_type: Mapped[str] = mapped_column(String(50), default="stock")
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(80), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WatchlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_asset"),)

    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id"))
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))


class MarketSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "market_snapshots"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open_price: Mapped[float] = mapped_column(Float)
    high_price: Mapped[float] = mapped_column(Float)
    low_price: Mapped[float] = mapped_column(Float)
    close_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(80), default="local-bootstrap")
