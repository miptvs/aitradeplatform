from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.services.market_data.service import market_data_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_search_assets_uses_trading212_verified_match(monkeypatch) -> None:
    db = build_session()

    def fake_search(_: Session, broker_type: str, query: str) -> dict:
        assert broker_type == "trading212"
        assert query == "XDND"
        return {
            "success": True,
            "message": "Trading212 verified 1 instrument match.",
            "data": {
                "matches": [
                    {
                        "symbol": "XDND.DE",
                        "display_symbol": "XDND.DE",
                        "name": "Xtrackers Nasdaq 100 UCITS ETF",
                        "asset_type": "etf",
                        "exchange": "DE",
                        "currency": "EUR",
                        "latest_price": None,
                        "source": "trading212",
                        "source_label": "Trading212 verified",
                        "verified": True,
                        "broker_ticker": "XDND_DE_ETF",
                    }
                ]
            },
        }

    monkeypatch.setattr("app.services.market_data.service.broker_service.search_instruments", fake_search)

    response = market_data_service.search_assets(db, "XDND")

    assert response["validation_status"] == "verified"
    assert response["results"][0]["symbol"] == "XDND.DE"
    assert response["results"][0]["source"] == "trading212"
    assert response["results"][0]["broker_ticker"] == "XDND_DE_ETF"


def test_refresh_market_data_updates_seed_rows_with_real_history(monkeypatch) -> None:
    db = build_session()
    asset = Asset(symbol="SPY", name="SPDR S&P 500 ETF Trust", asset_type="etf", exchange="NYSEARCA", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(days=1),
            open_price=500,
            high_price=505,
            low_price=495,
            close_price=502,
            volume=10,
            source="seed",
        )
    )
    db.commit()

    monkeypatch.setattr(
        market_data_service,
        "_fetch_remote_history",
        lambda _: [
            {
                "date": (utcnow() - timedelta(days=1)).date(),
                "open_price": 599.0,
                "high_price": 605.0,
                "low_price": 595.0,
                "close_price": 603.0,
                "volume": 1234567.0,
                "source": "yahoo-chart",
            }
        ],
    )

    report = market_data_service.refresh_market_data(db)
    db.commit()

    refreshed = db.query(MarketSnapshot).filter(MarketSnapshot.asset_id == asset.id).one()
    assert report["snapshots_updated"] == 1
    assert refreshed.close_price == 603.0
    assert refreshed.source == "yahoo-chart"
