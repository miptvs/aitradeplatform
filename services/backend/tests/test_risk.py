from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.portfolio import PortfolioSnapshot, Position, Trade
from app.models.risk import RiskRule
from app.models.simulation import SimulationAccount
from app.schemas.risk import RiskValidationRequest
from app.services.risk.service import risk_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_risk_rejects_insufficient_simulation_cash() -> None:
    db = build_session()
    asset = Asset(symbol="TEST", name="Test Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=1),
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
            volume=1000,
            source="test",
        )
    )
    db.add(SimulationAccount(name="Test Sim", starting_cash=100, cash_balance=100, fees_bps=0, slippage_bps=0, latency_ms=0))
    db.flush()
    account = db.query(SimulationAccount).first()
    db.add(RiskRule(name="Kill Switch", scope="global", rule_type="kill_switch", enabled=True, config_json={"active": False}))
    db.commit()

    result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=5,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )

    assert result.approved is False
    assert any("Insufficient simulation cash" in reason for reason in result.rejection_reasons)


def test_daily_max_loss_uses_pct_of_account_value() -> None:
    db = build_session()
    asset = Asset(symbol="TEST", name="Test Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=1),
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
            volume=1000,
            source="test",
        )
    )
    db.add(SimulationAccount(name="Test Sim", starting_cash=100000, cash_balance=100000, fees_bps=0, slippage_bps=0, latency_ms=0))
    db.flush()
    account = db.query(SimulationAccount).first()
    db.add(
        PortfolioSnapshot(
            mode="simulation",
            simulation_account_id=account.id,
            timestamp=utcnow(),
            total_value=100000,
            cash=100000,
            equity=0,
            realized_pnl=-2600,
            unrealized_pnl=0,
            daily_return=-0.026,
            weekly_return=0,
            monthly_return=0,
            exposure_json={},
        )
    )
    db.add(
        Trade(
            asset_id=asset.id,
            mode="simulation",
            side="sell",
            quantity=1,
            price=100,
            realized_pnl=-2600,
            executed_at=utcnow(),
        )
    )
    db.add(RiskRule(name="Kill Switch", scope="global", rule_type="kill_switch", enabled=True, config_json={"active": False}))
    db.add(
        RiskRule(
            name="Daily Max Loss",
            scope="global",
            rule_type="daily_max_loss",
            enabled=True,
            config_json={"max_daily_loss_pct": 0.025},
        )
    )
    db.commit()

    result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=1,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )

    assert result.approved is False
    assert any("Daily max loss threshold reached" in reason for reason in result.rejection_reasons)
    daily_loss_check = next(check for check in result.checks if check.rule == "daily_max_loss")
    assert daily_loss_check.details["limit_pct"] == 0.025
    assert daily_loss_check.details["limit_amount"] == -2500


def test_cash_reserve_blocks_order_that_would_spend_reserved_cash() -> None:
    db = build_session()
    asset = Asset(symbol="CASH", name="Cash Reserve Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=utcnow() - timedelta(minutes=1),
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
            volume=1000,
            source="test",
        )
    )
    account = SimulationAccount(name="Reserve Sim", starting_cash=10000, cash_balance=10000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add(account)
    db.add(RiskRule(name="Kill Switch", scope="global", rule_type="kill_switch", enabled=True, config_json={"active": False}))
    db.add(
        RiskRule(
            name="Cash Reserve",
            scope="global",
            rule_type="cash_reserve",
            enabled=True,
            config_json={"min_cash_reserve_pct": 0.2},
        )
    )
    db.commit()

    result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=90,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )

    assert result.approved is False
    assert any("cash reserve" in reason.lower() for reason in result.rejection_reasons)
    reserve_check = next(check for check in result.checks if check.rule == "cash_reserve")
    assert reserve_check.details["reserve_pct"] == 0.2
    assert reserve_check.details["available_to_trade"] == 8000
    assert reserve_check.details["required"] == 9000


def test_cash_reserve_allows_buy_above_reserved_cash_and_does_not_block_close() -> None:
    db = build_session()
    asset = Asset(symbol="ALLOW", name="Allowed Reserve Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    account = SimulationAccount(name="Reserve Sim", starting_cash=10000, cash_balance=10000, fees_bps=0, slippage_bps=0, latency_ms=0)
    db.add(account)
    db.flush()
    db.add(
        Position(
            asset_id=asset.id,
            simulation_account_id=account.id,
            mode="simulation",
            quantity=5,
            avg_entry_price=100,
            current_price=100,
            status="open",
        )
    )
    db.add(
        RiskRule(
            name="Cash Reserve",
            scope="global",
            rule_type="cash_reserve",
            enabled=True,
            config_json={"min_cash_reserve_pct": 0.2},
        )
    )
    db.commit()

    buy_result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=50,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )
    close_result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="close_long",
            quantity=5,
            requested_price=100,
            simulation_account_id=account.id,
        ),
    )

    assert buy_result.approved is True
    assert close_result.approved is True
    close_reserve_check = next(check for check in close_result.checks if check.rule == "cash_reserve")
    assert "reductions or closes" in close_reserve_check.reason


def test_cash_reserve_override_applies_per_simulation_model_account() -> None:
    db = build_session()
    asset = Asset(symbol="MODEL", name="Model Reserve Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    model_a = SimulationAccount(
        name="Model A",
        provider_type="model_a",
        starting_cash=10000,
        cash_balance=10000,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        min_cash_reserve_percent=0.5,
    )
    model_b = SimulationAccount(
        name="Model B",
        provider_type="model_b",
        starting_cash=10000,
        cash_balance=10000,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        min_cash_reserve_percent=0.1,
    )
    db.add_all([model_a, model_b])
    db.add(
        RiskRule(
            name="Cash Reserve",
            scope="global",
            rule_type="cash_reserve",
            enabled=True,
            config_json={"min_cash_reserve_pct": 0.2},
        )
    )
    db.commit()

    model_a_result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=60,
            requested_price=100,
            simulation_account_id=model_a.id,
        ),
    )
    model_b_result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=60,
            requested_price=100,
            simulation_account_id=model_b.id,
        ),
    )

    assert model_a_result.approved is False
    assert model_b_result.approved is True


def test_live_short_is_rejected_when_broker_does_not_support_shorting() -> None:
    db = build_session()
    asset = Asset(symbol="LIVE", name="Live Short Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.commit()

    result = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="live",
            side="short",
            quantity=1,
            requested_price=100,
            broker_account_id="broker-1",
        ),
    )

    assert result.approved is False
    assert any("Live short execution is not supported" in reason for reason in result.rejection_reasons)


def test_simulation_account_market_hours_blocks_and_allows_by_exchange_session() -> None:
    db = build_session()
    asset = Asset(symbol="HOURS", name="Hours Asset", asset_type="stock", sector="Technology", exchange="NASDAQ", currency="USD")
    db.add(asset)
    db.flush()
    account = SimulationAccount(
        name="Hours Sim",
        starting_cash=1000,
        cash_balance=1000,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        enforce_market_hours=True,
    )
    db.add(account)
    db.commit()

    blocked = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=1,
            requested_price=100,
            simulation_account_id=account.id,
            observed_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        ),
    )
    allowed = risk_service.validate_order(
        db,
        RiskValidationRequest(
            asset_id=asset.id,
            mode="simulation",
            side="buy",
            quantity=1,
            requested_price=100,
            simulation_account_id=account.id,
            observed_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        ),
    )

    assert blocked.approved is False
    assert any("market-hours" in reason for reason in blocked.rejection_reasons)
    assert allowed.approved is True
