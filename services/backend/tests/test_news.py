from datetime import timedelta
from email.utils import format_datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset
from app.models.audit import Alert
from app.models.base import Base
from app.models.health import SystemHealthEvent
from app.models.news import NewsArticle
from app.services.news.service import news_service
from app.tasks import periodic
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_refresh_latest_news_imports_rss_items(monkeypatch) -> None:
    db = build_session()
    db.add(Asset(symbol="NVDA", name="NVIDIA Corp.", asset_type="stock", sector="Technology", exchange="NASDAQ", currency="USD"))
    db.commit()

    published_at = utcnow()
    feed_xml = f"""
    <rss version="2.0">
      <channel>
        <item>
          <title>NVIDIA beats expectations as AI demand stays strong</title>
          <link>https://example.com/nvda-1</link>
          <guid>nvda-1</guid>
          <description>Analyst commentary points to stronger demand across data-center buyers.</description>
          <source>Example Markets</source>
          <pubDate>{format_datetime(published_at)}</pubDate>
        </item>
      </channel>
    </rss>
    """.strip()

    monkeypatch.setattr(news_service, "_build_feed_urls", lambda _: ["https://example.com/rss"])
    monkeypatch.setattr(news_service, "_fetch_feed", lambda _: feed_xml)

    result = news_service.refresh_latest_news(db)
    db.commit()

    article = db.query(NewsArticle).one()
    assert result["articles_added"] == 1
    assert article.source == "Example Markets"
    assert article.sentiment == "positive"
    assert article.affected_symbols == ["NVDA"]


def test_refresh_latest_news_only_imports_items_after_last_refresh(monkeypatch) -> None:
    db = build_session()
    db.add(Asset(symbol="SPY", name="SPDR S&P 500 ETF Trust", asset_type="etf", sector="Index", exchange="NYSEARCA", currency="USD"))
    last_refresh = utcnow()
    db.add(
        NewsArticle(
            title="Older market headline",
            source="Example Markets",
            url="https://example.com/old",
            published_at=last_refresh,
            summary="Already stored from the last overlap window.",
            sentiment="neutral",
            impact_score=0.4,
            affected_symbols=["SPY"],
            provider_type="rss",
            model_name="rss-heuristic",
            dedupe_key="old",
            analysis_metadata={},
        )
    )
    db.add(
        SystemHealthEvent(
            component="news.rss_refresh",
            status="ok",
            message="Previous refresh",
            metadata_json={"latest_seen_published_at": last_refresh.isoformat()},
            observed_at=last_refresh,
        )
    )
    db.commit()

    older_item = format_datetime(last_refresh)
    newer_item = format_datetime(last_refresh + timedelta(seconds=1))
    feed_xml = f"""
    <rss version="2.0">
      <channel>
        <item>
          <title>Older market headline</title>
          <link>https://example.com/old</link>
          <guid>old</guid>
          <description>Already covered before the latest refresh.</description>
          <source>Example Markets</source>
          <pubDate>{older_item}</pubDate>
        </item>
        <item>
          <title>SPY rises after fresh macro data</title>
          <link>https://example.com/new</link>
          <guid>new</guid>
          <description>ETF flows remain constructive after the latest inflation print.</description>
          <source>Example Markets</source>
          <pubDate>{newer_item}</pubDate>
        </item>
      </channel>
    </rss>
    """.strip()

    monkeypatch.setattr(news_service, "_build_feed_urls", lambda _: ["https://example.com/rss"])
    monkeypatch.setattr(news_service, "_fetch_feed", lambda _: feed_xml)

    result = news_service.refresh_latest_news(db)
    db.commit()

    articles = db.query(NewsArticle).all()
    assert result["articles_added"] == 1
    assert result["duplicates_skipped"] >= 1
    assert len(articles) == 2
    assert any(article.url == "https://example.com/new" for article in articles)


def test_refresh_latest_news_imports_delayed_items_inside_rolling_window(monkeypatch) -> None:
    db = build_session()
    db.add(Asset(symbol="MSFT", name="Microsoft Corp.", asset_type="stock", sector="Technology", exchange="NASDAQ", currency="USD"))
    latest_seen = utcnow()
    db.add(
        SystemHealthEvent(
            component="news.rss_refresh",
            status="ok",
            message="Previous refresh saw a newer top-of-feed item",
            metadata_json={"latest_seen_published_at": latest_seen.isoformat()},
            observed_at=latest_seen,
        )
    )
    db.commit()

    delayed_item = latest_seen - timedelta(hours=24)
    feed_xml = f"""
    <rss version="2.0">
      <channel>
        <item>
          <title>Microsoft gains after cloud analyst upgrade</title>
          <link>https://example.com/msft-delayed</link>
          <guid>msft-delayed</guid>
          <description>A delayed RSS item is still inside the rolling overlap window.</description>
          <source>Example Markets</source>
          <pubDate>{format_datetime(delayed_item)}</pubDate>
        </item>
      </channel>
    </rss>
    """.strip()

    monkeypatch.setattr(news_service, "_build_feed_urls", lambda _: ["https://example.com/rss"])
    monkeypatch.setattr(news_service, "_fetch_feed", lambda _: feed_xml)

    result = news_service.refresh_latest_news(db)
    db.commit()

    assert result["articles_added"] == 1
    assert result["feed_reports"][0]["added_count"] == 1
    assert db.query(NewsArticle).filter(NewsArticle.url == "https://example.com/msft-delayed").one()


def test_refresh_latest_news_force_refresh_backfills_recent_items(monkeypatch) -> None:
    db = build_session()
    db.add(Asset(symbol="QQQ", name="Invesco QQQ Trust", asset_type="etf", sector="Index", exchange="NASDAQ", currency="USD"))
    db.commit()

    published_at = utcnow() - timedelta(hours=12)
    feed_xml = f"""
    <rss version="2.0">
      <channel>
        <item>
          <title>QQQ backfill headline</title>
          <link>https://example.com/backfill</link>
          <guid>backfill</guid>
          <description>Recent ETF article that should still import during a forced backfill.</description>
          <source>Example Markets</source>
          <pubDate>{format_datetime(published_at)}</pubDate>
        </item>
      </channel>
    </rss>
    """.strip()

    monkeypatch.setattr(news_service, "_build_feed_urls", lambda _: ["https://example.com/rss"])
    monkeypatch.setattr(news_service, "_fetch_feed", lambda _: feed_xml)

    result = news_service.refresh_latest_news(db, force_refresh=True, backfill_hours=24)
    db.commit()

    assert result["articles_added"] == 1
    assert result["force_refresh"] is True
    assert result["feed_reports"][0]["added_count"] == 1


def test_refresh_latest_news_partial_feed_failure_is_warn_not_error(monkeypatch) -> None:
    db = build_session()
    db.add(Asset(symbol="SPY", name="SPDR S&P 500 ETF Trust", asset_type="etf", sector="Index", exchange="NYSEARCA", currency="USD"))
    db.commit()

    empty_feed = """
    <rss version="2.0">
      <channel></channel>
    </rss>
    """.strip()

    monkeypatch.setattr(news_service, "_build_feed_urls", lambda _: ["https://example.com/ok", "https://example.com/fail"])

    def fake_fetch(url: str) -> str:
        if url.endswith("/fail"):
            raise RuntimeError("temporary upstream timeout")
        return empty_feed

    monkeypatch.setattr(news_service, "_fetch_feed", fake_fetch)

    result = news_service.refresh_latest_news(db)
    db.commit()

    latest_event = db.query(SystemHealthEvent).filter(SystemHealthEvent.component == "news.rss_refresh").order_by(SystemHealthEvent.observed_at.desc()).first()
    assert result["articles_added"] == 0
    assert result["feeds_failed"] == 1
    assert latest_event is not None
    assert latest_event.status == "warn"


def test_alert_generation_resolves_stale_news_error_alert(monkeypatch) -> None:
    db = build_session()
    db.add(
        Alert(
            category="health",
            severity="warning",
            title="news.rss_refresh reported an error",
            message="Old failure",
            status="open",
            mode="system",
            source_ref="news.rss_refresh",
            metadata_json={},
        )
    )
    db.add(
        SystemHealthEvent(
            component="news.rss_refresh",
            status="warn",
            message="Feeds were stale but reachable.",
            metadata_json={},
            observed_at=utcnow(),
        )
    )
    db.commit()

    class _SessionContext:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(periodic, "SessionLocal", lambda: _SessionContext())

    result = periodic.alert_generation()
    db.expire_all()

    alert = db.query(Alert).filter(Alert.title == "news.rss_refresh reported an error").first()
    assert result["cleaned"] >= 1
    assert alert is not None
    assert alert.status == "resolved"
