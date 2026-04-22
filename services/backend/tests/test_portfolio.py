from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.portfolio import Position
from app.schemas.portfolio import PositionCreate
from app.services.portfolio.service import portfolio_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_create_manual_position_creates_custom_asset_and_price_snapshot() -> None:
    db = build_session()

    position = portfolio_service.create_manual_position(
        db,
        PositionCreate(
            asset_symbol="VUSA",
            asset_name="Vanguard S&P 500 UCITS ETF",
            currency="EUR",
            mode="simulation",
            quantity=0.84,
            avg_entry_price=118.9,
            current_price=119.4,
            manual=True,
        ),
    )
    db.commit()

    asset = db.scalar(select(Asset).where(Asset.symbol == "VUSA"))
    snapshot = db.scalar(select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id))

    assert asset is not None
    assert asset.currency == "EUR"
    assert position.asset_id == asset.id
    assert snapshot is not None
    assert snapshot.close_price == 119.4


def test_close_position_by_percent_supports_fractional_quantity() -> None:
    db = build_session()
    asset = Asset(symbol="TEST", name="Test Asset", asset_type="stock", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow(),
            open_price=100,
            high_price=100,
            low_price=100,
            close_price=100,
            volume=0,
            source="test",
        )
    )
    position = Position(
        asset_id=asset.id,
        mode="simulation",
        quantity=0.8,
        avg_entry_price=100,
        current_price=110,
        unrealized_pnl=8,
        realized_pnl=0,
        manual=True,
    )
    db.add(position)
    db.commit()

    updated = portfolio_service.close_position(db, position.id, close_percent=25, exit_price=120)
    db.commit()

    assert round(updated.quantity, 6) == 0.6
    assert round(updated.realized_pnl, 6) == 4.0
