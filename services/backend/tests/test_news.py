from datetime import timedelta
from email.utils import format_datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset
from app.models.base import Base
from app.models.health import SystemHealthEvent
from app.models.news import NewsArticle
from app.services.news.service import news_service
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
