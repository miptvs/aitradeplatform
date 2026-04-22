from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.news import NewsArticle
from app.models.risk import RiskRule
from app.services.mcp.context_tools import build_architecture_payload, build_signal_context_payload
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_build_signal_context_payload_returns_asset_market_news_and_rules() -> None:
    db = build_session()

    asset = Asset(symbol="QQQ", name="Invesco QQQ Trust", asset_type="etf", exchange="NASDAQ", currency="USD")
    db.add(asset)
    db.flush()

    for day in range(4, -1, -1):
        db.add(
            MarketSnapshot(
                asset_id=asset.id,
                timestamp=utcnow() - timedelta(days=day),
                open_price=400 + day,
                high_price=403 + day,
                low_price=398 + day,
                close_price=401 + day,
                volume=1_000_000 + (day * 1000),
                source="yahoo-chart",
            )
        )

    db.add(
        NewsArticle(
            title="QQQ sees renewed inflows",
            source="Example Wire",
            url="https://example.com/qqq",
            published_at=utcnow(),
            summary="ETF inflows accelerated into the close.",
            sentiment="positive",
            impact_score=0.7,
            affected_symbols=["QQQ"],
            provider_type="rss",
            model_name="rss-heuristic",
            dedupe_key="qqq-news",
        )
    )
    db.add(
        RiskRule(
            name="Daily Max Loss",
            rule_type="daily_max_loss",
            enabled=True,
            auto_close=False,
            description="Pause after large daily losses.",
            config_json={"max_daily_loss_pct": 0.025},
        )
    )
    db.commit()

    payload = build_signal_context_payload(db, "QQQ", mode="simulation")

    assert payload["asset"]["symbol"] == "QQQ"
    assert payload["recent_market_snapshots"]
    assert payload["recent_news"][0]["title"] == "QQQ sees renewed inflows"
    assert payload["active_risk_rules"][0]["rule_type"] == "daily_max_loss"


def test_build_architecture_payload_exposes_mcp_topology() -> None:
    db = build_session()
    payload = build_architecture_payload(db)
    assert payload["mcp"]["enabled"] is True
    assert payload["mcp"]["transport"] == "streamable-http"
    assert payload["backend"]["mounted_mcp_endpoint"].endswith("/mcp/")
