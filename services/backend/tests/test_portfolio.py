from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.broker import BrokerAccount
from app.models.portfolio import Position
from app.models.risk import RiskRule
from app.models.simulation import SimulationAccount
from app.schemas.portfolio import OrderCreate, PositionCreate
from app.services.portfolio.service import portfolio_service
from app.services.risk import service as risk_module
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


def test_create_simulation_order_supports_fractional_quantity_from_fixed_amount() -> None:
    db = build_session()
    asset = Asset(symbol="FRAC", name="Fractional Asset", asset_type="stock", currency="USD")
    account = SimulationAccount(name="Fractional Sim", starting_cash=1000, cash_balance=1000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add_all([asset, account])
    db.flush()

    order = portfolio_service.create_order(
        db,
        OrderCreate(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            sizing_mode="amount",
            sizing_value=25,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )
    db.commit()

    assert order.status == "filled"
    assert order.quantity == 0.25
    assert round(account.cash_balance, 6) == 975


def test_create_simulation_order_supports_percentage_sizing() -> None:
    db = build_session()
    asset = Asset(symbol="PCT", name="Percentage Asset", asset_type="stock", currency="USD")
    account = SimulationAccount(name="Percent Sim", starting_cash=10000, cash_balance=10000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add_all([asset, account])
    db.flush()

    order = portfolio_service.create_order(
        db,
        OrderCreate(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            sizing_mode="percentage",
            sizing_value=5,
            requested_price=200,
            simulation_account_id=account.id,
        ),
    )
    db.commit()

    assert order.status == "filled"
    assert order.quantity == 2.5
    assert order.audit_context["sizing"]["portfolio_percent"] == 0.05
    assert round(account.cash_balance, 6) == 9500


def test_order_is_resized_to_fractional_max_allowed_by_cash_reserve() -> None:
    db = build_session()
    asset = Asset(symbol="RSZ", name="Resize Asset", asset_type="stock", currency="USD")
    account = SimulationAccount(name="Resize Sim", starting_cash=10000, cash_balance=10000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add_all(
        [
            asset,
            account,
            RiskRule(name="Cash Reserve", rule_type="cash_reserve", enabled=True, config_json={"min_cash_reserve_pct": 0.2}),
        ]
    )
    db.flush()

    order = portfolio_service.create_order(
        db,
        OrderCreate(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            sizing_mode="amount",
            sizing_value=9000,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )
    db.commit()

    assert order.status == "filled"
    assert order.quantity == 80
    assert order.audit_context["resize_note"]
    assert round(account.cash_balance, 6) == 2000


def test_simulation_decimal_precision_rounds_down_with_visible_warning() -> None:
    db = build_session()
    asset = Asset(symbol="ROUND", name="Rounding Asset", asset_type="stock", currency="USD")
    account = SimulationAccount(
        name="Rounding Sim",
        starting_cash=100,
        cash_balance=100,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        decimal_precision=2,
    )
    db.add_all([asset, account])
    db.flush()

    order = portfolio_service.create_order(
        db,
        OrderCreate(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            sizing_mode="amount",
            sizing_value=10,
            requested_price=3,
            simulation_account_id=account.id,
        ),
    )
    db.commit()

    assert order.quantity == 3.33
    assert "rounded down" in order.audit_context["sizing"]["rounding_warning"]
    assert round(account.cash_balance, 2) == 90.01


def test_live_order_resolves_fractional_quantity_before_trading212_rejection(monkeypatch) -> None:
    monkeypatch.setattr(risk_module.settings, "enable_live_trading", True)
    db = build_session()
    asset = Asset(symbol="LIVEF", name="Live Fractional Asset", asset_type="stock", currency="USD")
    broker = BrokerAccount(
        name="Trading212 Test",
        broker_type="trading212",
        mode="live",
        enabled=True,
        live_trading_enabled=False,
        status="connected",
        settings_json={"available_cash": 100, "cash_balance": 100, "total_value": 100, "currency": "USD"},
    )
    db.add_all([asset, broker])
    db.flush()

    order = portfolio_service.create_order(
        db,
        OrderCreate(
            asset_id=asset.id,
            mode="live",
            side="buy",
            sizing_mode="amount",
            sizing_value=50,
            requested_price=100,
            broker_account_id=broker.id,
        ),
    )
    db.commit()

    assert order.status == "rejected"
    assert order.quantity == 0.5
    assert "Resolved fractional order was 0.5 shares" in (order.rejection_reason or "")
    assert order.audit_context["fractional_trading"]["broker_type"] == "trading212"
