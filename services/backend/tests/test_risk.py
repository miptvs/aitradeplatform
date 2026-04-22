from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.portfolio import PortfolioSnapshot, Trade
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
