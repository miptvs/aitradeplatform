from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.portfolio import Order
from app.models.simulation import SimulationAccount
from app.services.simulation.service import simulation_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_simulation_executes_buy_order_and_creates_position() -> None:
    db = build_session()
    asset = Asset(symbol="SIM", name="Simulation Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=1),
            open_price=50,
            high_price=51,
            low_price=49,
            close_price=50,
            volume=1000,
            source="test",
        )
    )
    account = SimulationAccount(name="Test Sim", starting_cash=10000, cash_balance=10000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add(account)
    db.flush()

    order = Order(
        asset_id=asset.id,
        mode="simulation",
        side="buy",
        order_type="market",
        quantity=10,
        requested_price=50,
        status="accepted",
        manual=True,
    )
    db.add(order)
    db.flush()

    sim_order, sim_trade, position = simulation_service.execute_order_from_order(db, order=order, simulation_account_id=account.id)
    db.commit()

    assert sim_order.status == "filled"
    assert sim_trade.quantity == 10
    assert position.quantity == 10
    assert account.cash_balance == 9500
