from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "AI Trader Platform"
    app_env: str = "development"
    app_debug: bool = True

    database_url: str = "postgresql+psycopg://ai_trader:ai_trader@postgres:5432/ai_trader"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "change-me"
    app_encryption_key: str = "txvIg1N1P7A_Bn_iQ7Kg2__nrkSZ7Oly94enZeBmN_U="
    access_token_expire_minutes: int = 720

    enable_live_trading: bool = False
    auto_seed_demo: bool = True

    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://frontend:3000"]
    )
    news_rss_feeds: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "https://news.google.com/rss/search?q=stock+market+OR+ETF+when:1d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=Federal+Reserve+OR+inflation+markets+when:1d&hl=en-US&gl=US&ceid=US:en",
        ]
    )
    news_backup_rss_feeds: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "https://www.investing.com/rss/news_25.rss",
            "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        ]
    )

    provider_local_base_url: str = "http://ollama:11434"
    provider_openai_base_url: str = "https://api.openai.com/v1"
    provider_deepseek_base_url: str = "https://api.deepseek.com/v1"
    mcp_enabled: bool = True
    mcp_server_url: str = "http://backend:8000/mcp/"
    mcp_request_timeout_seconds: int = 8
    mcp_connect_timeout_seconds: int = 3
    trading212_live_base_url: str = "https://live.trading212.com/api/v0"
    trading212_demo_base_url: str = "https://demo.trading212.com/api/v0"
    trading212_api_key: str | None = None
    trading212_api_secret: str | None = None
    trading212_instrument_cache_seconds: int = 600

    market_refresh_seconds: int = 300
    news_refresh_seconds: int = 600
    news_feed_items_limit: int = 12
    news_initial_lookback_hours: int = 72
    news_refresh_overlap_minutes: int = 720
    news_incremental_backfill_hours: int = 48
    news_force_backfill_hours: int = 48
    news_symbol_feed_limit: int = 6
    signal_refresh_seconds: int = 300
    automation_scan_seconds: int = 60
    provider_health_seconds: int = 900
    portfolio_snapshot_seconds: int = 300

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("news_rss_feeds", "news_backup_rss_feeds", mode="before")
    @classmethod
    def split_news_rss_feeds(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
