from urllib.parse import urlparse

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset, MarketSnapshot
from app.models.broker import BrokerAccount
from app.models.news import ExtractedEvent, NewsArticle
from app.models.portfolio import PortfolioSnapshot, Position
from app.models.risk import RiskRule
from app.models.simulation import SimulationAccount
from app.services.market_data.service import market_data_service
from app.services.providers.service import provider_service
from app.utils.serialization import to_plain_dict
from app.utils.time import utcnow


settings = get_settings()


def build_signal_context_payload(db: Session, symbol: str, mode: str = "simulation") -> dict:
    normalized_symbol = symbol.strip().upper()
    asset = db.scalar(select(Asset).where(Asset.symbol == normalized_symbol))
    if asset is None:
        raise ValueError(f"Asset not found for symbol {normalized_symbol}")

    history = list(
        db.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.asset_id == asset.id)
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(8)
        )
    )
    news_rows = list(
        db.scalars(
            select(NewsArticle)
            .where(NewsArticle.provider_type != "system", ~NewsArticle.url.like("https://local.demo/%"))
            .order_by(desc(NewsArticle.published_at))
            .limit(80)
        )
    )
    related_news = [article for article in news_rows if normalized_symbol in (article.affected_symbols or [])][:5]
    related_events = list(
        db.scalars(
            select(ExtractedEvent)
            .where(ExtractedEvent.symbol == normalized_symbol)
            .order_by(desc(ExtractedEvent.created_at))
            .limit(5)
        )
    )
    positions = list(
        db.scalars(
            select(Position)
            .where(Position.asset_id == asset.id, Position.status == "open")
            .order_by(desc(Position.updated_at))
            .limit(10)
        )
    )
    mode_snapshot = db.scalar(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.mode == mode)
        .order_by(desc(PortfolioSnapshot.timestamp))
        .limit(1)
    )
    risk_rules = list(db.scalars(select(RiskRule).where(RiskRule.enabled.is_(True)).order_by(RiskRule.name)))
    latest_price = market_data_service.get_latest_price(db, asset.id)

    return {
        "generated_at": utcnow().isoformat(),
        "requested_mode": mode,
        "asset": {
            "id": asset.id,
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "sector": asset.sector,
            "exchange": asset.exchange,
            "currency": asset.currency,
            "latest_price": latest_price,
        },
        "recent_market_snapshots": [to_plain_dict(snapshot) for snapshot in reversed(history)],
        "recent_news": [
            {
                "title": article.title,
                "source": article.source,
                "published_at": article.published_at.isoformat(),
                "summary": article.summary,
                "sentiment": article.sentiment,
                "impact_score": article.impact_score,
                "url": article.url,
            }
            for article in related_news
        ],
        "recent_events": [to_plain_dict(event) for event in related_events],
        "open_positions": [
            {
                **to_plain_dict(position),
                "symbol": asset.symbol,
                "asset_name": asset.name,
            }
            for position in positions
        ],
        "portfolio_snapshot": to_plain_dict(mode_snapshot) if mode_snapshot else None,
        "active_risk_rules": [
            {
                "name": rule.name,
                "rule_type": rule.rule_type,
                "scope": rule.scope,
                "description": rule.description,
                "config_json": rule.config_json,
            }
            for rule in risk_rules
        ],
        "provider_health": provider_service.get_health(db),
    }


def build_architecture_payload(db: Session) -> dict:
    provider_configs = [provider_service.serialize_config(config) for config in provider_service.list_configs(db)]
    broker_accounts = [
        {
            "name": account.name,
            "broker_type": account.broker_type,
            "mode": account.mode,
            "enabled": account.enabled,
            "status": account.status,
            "live_trading_enabled": account.live_trading_enabled,
        }
        for account in db.scalars(select(BrokerAccount).order_by(BrokerAccount.name))
    ]
    simulation_accounts = [
        {
            "name": account.name,
            "starting_cash": account.starting_cash,
            "cash_balance": account.cash_balance,
            "reset_count": account.reset_count,
            "is_active": account.is_active,
        }
        for account in db.scalars(select(SimulationAccount).order_by(SimulationAccount.name))
    ]
    return {
        "generated_at": utcnow().isoformat(),
        "app_name": settings.app_name,
        "mcp": {
            "enabled": settings.mcp_enabled,
            "server_url": settings.mcp_server_url,
            "transport": "streamable-http",
            "mounted_path": "/mcp/",
        },
        "backend": {
            "api_base": "http://localhost:8000/api/v1",
            "mounted_mcp_endpoint": "http://localhost:8000/mcp/",
        },
        "datastores": {
            "postgres": _mask_connection_target(settings.database_url),
            "redis": _mask_connection_target(settings.redis_url),
        },
        "providers": provider_configs,
        "brokers": broker_accounts,
        "simulation_accounts": simulation_accounts,
    }


def _mask_connection_target(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.hostname or "unknown"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.lstrip("/")
    suffix = f"/{path}" if path else ""
    return f"{parsed.scheme}://{host}{port}{suffix}"
