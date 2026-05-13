from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AssetRead(ORMModel):
    id: str
    symbol: str
    name: str
    asset_type: str
    sector: str | None = None
    exchange: str | None = None
    currency: str
    is_active: bool
    latest_price: float | None = None


class AssetSearchResultRead(BaseModel):
    key: str
    asset_id: str | None = None
    symbol: str
    display_symbol: str
    name: str
    asset_type: str
    exchange: str | None = None
    currency: str
    latest_price: float | None = None
    source: str
    source_label: str
    verified: bool = True
    broker_ticker: str | None = None


class AssetSearchResponse(BaseModel):
    query: str
    validation_source: str | None = None
    validation_status: str
    message: str | None = None
    results: list[AssetSearchResultRead]


class MarketSnapshotRead(ORMModel):
    id: str
    asset_id: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    source: str


class WatchlistRead(ORMModel):
    id: str
    name: str
    description: str | None = None
    is_default: bool


class NewsArticleRead(ORMModel):
    id: str
    title: str
    source: str
    url: str
    published_at: datetime
    summary: str | None = None
    sentiment: str | None = None
    impact_score: float | None = None
    affected_symbols: list[str]
    provider_type: str | None = None
    model_name: str | None = None
    analysis_metadata: dict = Field(default_factory=dict)


class ExtractedEventRead(ORMModel):
    id: str
    news_article_id: str | None = None
    event_type: str
    symbol: str | None = None
    confidence: float
    impact_score: float
    summary: str


class StrategyRead(ORMModel):
    id: str
    name: str
    slug: str
    category: str
    description: str
    enabled: bool
    config_json: dict


class NewsRefreshRequest(BaseModel):
    force_refresh: bool = False
    backfill_hours: int | None = None


class NewsFeedDiagnostic(BaseModel):
    feed_url: str
    feed_label: str
    feed_group: str = "primary"
    status: str
    fetched_count: int
    added_count: int
    duplicate_count: int
    date_skipped_count: int
    parse_error_count: int
    sample_titles: list[str] = Field(default_factory=list)
    latest_seen_published_at: datetime | None = None
    error: str | None = None


class NewsRefreshResponse(BaseModel):
    message: str
    run_type: str = "manual"
    observed_at: str | None = None
    articles_added: int
    feeds_checked: int
    feeds_failed: int
    duplicates_skipped: int
    date_skipped: int
    latest_article_id: str | None = None
    cutoff: str
    latest_seen_published_at: str | None = None
    force_refresh: bool = False
    fallback_feeds_used: bool = False
    last_successful_fetch_time: str | None = None
    errors: list[str] = Field(default_factory=list)
    feed_reports: list[NewsFeedDiagnostic] = Field(default_factory=list)
