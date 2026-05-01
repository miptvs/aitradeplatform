from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.portfolio import Order, Position, Trade
from app.models.provider import ProviderConfig
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


def test_short_simulation_can_profit_when_price_falls() -> None:
    db = build_session()
    asset = Asset(symbol="DOWN", name="Shortable Simulation Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=2),
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
            volume=1000,
            source="test",
        )
    )
    account = SimulationAccount(name="Short Sim", starting_cash=1000, cash_balance=1000, fees_bps=0, slippage_bps=0, latency_ms=0, short_enabled=True)
    db.add(account)
    db.flush()

    short_order = Order(asset_id=asset.id, mode="simulation", side="short", order_type="market", quantity=1, requested_price=100, status="accepted", manual=False)
    db.add(short_order)
    db.flush()
    simulation_service.execute_order_from_order(db, order=short_order, simulation_account_id=account.id)
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow(),
            open_price=80,
            high_price=82,
            low_price=79,
            close_price=80,
            volume=1200,
            source="test",
        )
    )
    cover_order = Order(asset_id=asset.id, mode="simulation", side="cover_short", order_type="market", quantity=1, requested_price=80, status="accepted", manual=False)
    db.add(cover_order)
    db.flush()

    _, sim_trade, position = simulation_service.execute_order_from_order(db, order=cover_order, simulation_account_id=account.id)
    db.commit()

    assert sim_trade.realized_pnl == 20
    assert account.cash_balance == 1020
    assert position.status == "closed"


def test_slippage_affects_simulated_fill_price() -> None:
    db = build_session()
    asset = Asset(symbol="SLIP", name="Slippage Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    account = SimulationAccount(name="Slip Sim", starting_cash=1000, cash_balance=1000, fees_bps=0, slippage_bps=100, latency_ms=0)
    db.add(account)
    db.flush()
    order = Order(asset_id=asset.id, mode="simulation", side="buy", order_type="market", quantity=1, requested_price=100, status="accepted", manual=False)
    db.add(order)
    db.flush()

    sim_order, _, _ = simulation_service.execute_order_from_order(db, order=order, simulation_account_id=account.id)

    assert sim_order.executed_price == 101


def test_short_borrow_fee_affects_cover_short_pnl() -> None:
    db = build_session()
    asset = Asset(symbol="BRRW", name="Borrow Fee Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    account = SimulationAccount(
        name="Borrow Sim",
        starting_cash=1000,
        cash_balance=1000,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        short_enabled=True,
        short_borrow_fee_bps=100,
    )
    db.add(account)
    db.flush()
    short_order = Order(asset_id=asset.id, mode="simulation", side="short", order_type="market", quantity=1, requested_price=100, status="accepted", manual=False)
    db.add(short_order)
    db.flush()
    simulation_service.execute_order_from_order(db, order=short_order, simulation_account_id=account.id)
    cover_order = Order(asset_id=asset.id, mode="simulation", side="cover_short", order_type="market", quantity=1, requested_price=90, status="accepted", manual=False)
    db.add(cover_order)
    db.flush()

    _, sim_trade, _ = simulation_service.execute_order_from_order(db, order=cover_order, simulation_account_id=account.id)

    assert sim_trade.realized_pnl == 9


def test_short_margin_rule_blocks_excessive_short_exposure() -> None:
    from app.schemas.risk import RiskValidationRequest
    from app.services.risk.service import risk_service

    db = build_session()
    asset = Asset(symbol="MARG", name="Margin Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    account = SimulationAccount(
        name="Margin Sim",
        starting_cash=100,
        cash_balance=100,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        short_enabled=True,
        short_margin_requirement=1.5,
    )
    db.add(account)
    db.commit()

    result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="short",
            quantity=1,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )

    assert result.approved is False
    assert any("margin requirement" in reason for reason in result.rejection_reasons)


def test_margin_call_forces_simulated_short_close_when_equity_breaches_requirement() -> None:
    db = build_session()
    asset = Asset(symbol="MCALL", name="Margin Call Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=2),
            open_price=100,
            high_price=100,
            low_price=100,
            close_price=100,
            volume=1000,
            source="test",
        )
    )
    account = SimulationAccount(
        name="Margin Call Sim",
        starting_cash=1000,
        cash_balance=1000,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        short_enabled=True,
        short_margin_requirement=1.5,
    )
    db.add(account)
    db.flush()
    short_order = Order(asset_id=asset.id, mode="simulation", side="short", order_type="market", quantity=1, requested_price=100, status="accepted", manual=False)
    db.add(short_order)
    db.flush()
    _, _, position = simulation_service.execute_order_from_order(db, order=short_order, simulation_account_id=account.id)
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow(),
            open_price=1000,
            high_price=1000,
            low_price=1000,
            close_price=1000,
            volume=1000,
            source="test",
        )
    )
    db.flush()

    result = simulation_service.enforce_margin_requirements(db, account.id)

    assert result["status"] == "forced_closed"
    assert result["forced_closes"][0]["position_id"] == position.id
    assert position.status == "closed"
    assert position.quantity == 0
    assert account.cash_balance == 100


def test_per_model_simulation_accounts_are_isolated() -> None:
    db = build_session()
    asset = Asset(symbol="ISO", name="Isolation Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
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
    db.add(
        ProviderConfig(
            provider_type="openai_simulation",
            name="ChatGPT / OpenAI / Simulation",
            enabled=True,
            base_url="https://api.openai.com/v1",
            default_model="gpt-5-mini",
            temperature=0.2,
            max_tokens=512,
            context_window=128000,
            tool_calling_enabled=True,
            reasoning_mode="minimal",
            task_defaults={},
            settings_json={},
        )
    )
    db.add(
        ProviderConfig(
            provider_type="deepseek_simulation",
            name="DeepSeek API / Simulation",
            enabled=True,
            base_url="https://api.deepseek.com",
            default_model="deepseek-chat",
            temperature=0.2,
            max_tokens=512,
            context_window=64000,
            tool_calling_enabled=False,
            reasoning_mode="chat",
            task_defaults={},
            settings_json={},
        )
    )
    db.commit()

    accounts = simulation_service.list_accounts(db)
    openai_account = next(account for account in accounts if account.provider_type == "openai_simulation")
    deepseek_account = next(account for account in accounts if account.provider_type == "deepseek_simulation")

    order = Order(
        asset_id=asset.id,
        mode="simulation",
        side="buy",
        order_type="market",
        quantity=2,
        requested_price=50,
        status="accepted",
        manual=False,
        provider_type="openai_simulation",
        model_name="gpt-5-mini",
    )
    db.add(order)
    db.flush()
    simulation_service.execute_order_from_order(db, order=order, simulation_account_id=openai_account.id)
    db.commit()

    assert openai_account.cash_balance < openai_account.starting_cash
    assert round(openai_account.cash_balance, 2) == 899.93
    assert deepseek_account.cash_balance == deepseek_account.starting_cash


def test_reset_account_clears_only_selected_model_ledger() -> None:
    db = build_session()
    asset = Asset(symbol="RST", name="Reset Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=1),
            open_price=25,
            high_price=26,
            low_price=24,
            close_price=25,
            volume=1000,
            source="test",
        )
    )
    first = SimulationAccount(name="Model A", provider_type="model_a", starting_cash=1000, cash_balance=1000, fees_bps=0, slippage_bps=0, latency_ms=0)
    second = SimulationAccount(name="Model B", provider_type="model_b", starting_cash=1000, cash_balance=1000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add_all([first, second])
    db.flush()

    first_order = Order(
        asset_id=asset.id,
        mode="simulation",
        side="buy",
        order_type="market",
        quantity=2,
        requested_price=25,
        status="accepted",
        manual=False,
        audit_context={"simulation_account_id": first.id},
    )
    second_order = Order(
        asset_id=asset.id,
        mode="simulation",
        side="buy",
        order_type="market",
        quantity=1,
        requested_price=25,
        status="accepted",
        manual=False,
        audit_context={"simulation_account_id": second.id},
    )
    db.add_all([first_order, second_order])
    db.flush()
    simulation_service.execute_order_from_order(db, order=first_order, simulation_account_id=first.id)
    simulation_service.execute_order_from_order(db, order=second_order, simulation_account_id=second.id)
    legacy_position = Position(
        asset_id=asset.id,
        mode="simulation",
        manual=True,
        quantity=3,
        avg_entry_price=25,
        current_price=25,
        status="open",
        notes="Legacy unscoped simulation row from older builds",
    )
    provider_matched_legacy_position = Position(
        asset_id=asset.id,
        mode="simulation",
        manual=False,
        provider_type="model_a",
        quantity=4,
        avg_entry_price=25,
        current_price=25,
        status="open",
        notes="Legacy provider-scoped row without an account id",
    )
    db.add_all([legacy_position, provider_matched_legacy_position])
    db.commit()

    simulation_service.reset_account(db, first.id)
    db.commit()

    assert first.cash_balance == first.starting_cash
    assert db.scalar(select(Position).where(Position.simulation_account_id == first.id)) is None
    assert db.scalar(select(Order).where(Order.id == first_order.id)) is None
    assert db.scalar(select(Trade).where(Trade.order_id == first_order.id)) is None
    assert db.scalar(select(Position).where(Position.id == legacy_position.id)) is None
    assert db.scalar(select(Position).where(Position.id == provider_matched_legacy_position.id)) is None
    assert db.scalar(select(Position).where(Position.simulation_account_id == second.id)) is not None
    assert db.scalar(select(Order).where(Order.id == second_order.id)) is not None
