from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.audit import Alert
from app.models.base import Base
from app.models.broker import BrokerAccount
from app.models.health import SystemHealthEvent
from app.models.portfolio import Order, Position, Trade
from app.models.provider import ProviderConfig
from app.models.risk import RiskRule
from app.models.signal import Signal, SignalEvaluation
from app.models.simulation import SimulationAccount
from app.models.trading import TradingAutomationProfile
from app.schemas.portfolio import PositionCreate
from app.schemas.trading import TradingAutomationProfileUpsert
from app.services.portfolio.service import portfolio_service
from app.services.signals.service import signal_service
from app.services.trading.service import trading_workspace_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_simulation_automation_can_submit_order_from_candidate_signal() -> None:
    db = build_session()
    asset = Asset(symbol="AUTO", name="Automation Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
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
    account = SimulationAccount(name="Auto Sim", starting_cash=1000, cash_balance=1000, fees_bps=0, slippage_bps=0, latency_ms=0, is_active=True)
    db.add(account)
    db.flush()
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.91,
            status="candidate",
            occurred_at=utcnow(),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="High conviction automation candidate.",
            suggested_entry=100,
            suggested_stop_loss=97,
            suggested_take_profit=106,
            estimated_risk_reward=2.0,
            provider_type="openai_simulation",
            model_name="gpt-5-mini",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "trend-following"},
        )
    )
    db.flush()

    trading_workspace_service.upsert_profile(
        db,
        "simulation",
        TradingAutomationProfileUpsert(
            automation_enabled=True,
            approval_mode="fully_automatic",
            confidence_threshold=0.5,
            default_order_notional=100,
            stop_loss_pct=0.03,
            take_profit_pct=0.06,
            trailing_stop_pct=0.02,
        ),
    )

    result = trading_workspace_service.run_automation(db, "simulation", simulation_account_id=account.id)
    db.commit()

    updated_signal = db.scalar(select(Signal).where(Signal.asset_id == asset.id))
    evaluation = db.scalar(select(SignalEvaluation).where(SignalEvaluation.signal_id == updated_signal.id).order_by(SignalEvaluation.created_at.desc()))
    assert result["submitted_orders"] == 1
    assert result["status"] == "success"
    assert updated_signal is not None
    assert updated_signal.status == "candidate"
    assert evaluation is not None
    assert evaluation.outcome == "simulated"

    order = db.scalar(select(Order).where(Order.signal_id == updated_signal.id))
    assert order is not None
    trade = db.scalar(select(Trade).where(Trade.order_id == order.id))
    assert trade is not None
    position = db.get(Position, order.position_id)
    assert position is not None

    order_trace = signal_service.get_order_trace(db, order.id)
    trade_trace = signal_service.get_trade_trace(db, trade.id)
    position_trace = signal_service.get_position_trace(db, position.id)

    assert order_trace["entrypoint"]["type"] == "order"
    assert trade_trace["entrypoint"]["type"] == "trade"
    assert position_trace["entrypoint"]["type"] == "position"
    assert order_trace["signal"]["id"] == updated_signal.id
    assert trade_trace["signal"]["id"] == updated_signal.id
    assert position_trace["signal"]["id"] == updated_signal.id
    assert order_trace["orders"][0]["id"] == order.id
    assert trade.id in {item["id"] for item in position_trace["trades"]}
    assert order_trace["risk_checks"] is not None
    assert position_trace["stop_history"]
    assert "simulation_fill" in {item["source"] for item in position_trace["stop_history"]}


def test_simulation_automation_repairs_legacy_filters_for_blended_signals() -> None:
    db = build_session()
    asset = Asset(symbol="BLND", name="Blended Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
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
    account = SimulationAccount(
        name="Legacy Filter Sim",
        provider_type="openai_simulation",
        starting_cash=1000,
        cash_balance=1000,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        is_active=True,
        short_enabled=True,
    )
    db.add(account)
    db.add(
        TradingAutomationProfile(
            mode="simulation",
            name="Simulation Automation",
            enabled=True,
            automation_enabled=True,
            scheduled_execution_enabled=True,
            approval_mode="fully_automatic",
            allowed_strategy_slugs=["event-driven", "mean-reversion"],
            tradable_actions=["buy", "sell"],
            allowed_provider_types=["openai_simulation"],
            confidence_threshold=0.5,
            default_order_notional=100,
            stop_loss_pct=0.03,
            take_profit_pct=0.06,
            trailing_stop_pct=0.02,
            max_orders_per_run=1,
            risk_profile="balanced",
            config_json={},
        )
    )
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.82,
            status="candidate",
            occurred_at=utcnow(),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Blended buy candidate.",
            suggested_entry=50,
            provider_type="openai_simulation",
            model_name="gpt-5-mini",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "blended"},
        )
    )
    db.flush()

    result = trading_workspace_service.run_automation(db, "simulation", simulation_account_id=account.id)
    db.commit()

    repaired_profile = db.scalar(select(TradingAutomationProfile).where(TradingAutomationProfile.mode == "simulation"))
    assert result["status"] == "success"
    assert result["submitted_orders"] == 1
    assert repaired_profile is not None
    assert "blended" in repaired_profile.allowed_strategy_slugs
    assert "cover_short" in set(repaired_profile.tradable_actions)
    assert "short" not in set(repaired_profile.tradable_actions)
    assert repaired_profile.config_json["short_automation_opt_in"] is False


def test_simulation_workspace_reports_closed_realized_pnl_and_short_exposure() -> None:
    db = build_session()
    asset = Asset(symbol="PNL", name="PnL Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    account = SimulationAccount(
        name="PnL Sim",
        starting_cash=1000,
        cash_balance=1290.57,
        fees_bps=0,
        slippage_bps=0,
        latency_ms=0,
        is_active=True,
        short_enabled=True,
    )
    db.add(account)
    db.flush()
    db.add_all(
        [
            Position(
                asset_id=asset.id,
                mode="simulation",
                simulation_account_id=account.id,
                quantity=-1.393722,
                avg_entry_price=214.2072,
                current_price=213.81,
                unrealized_pnl=0.5536,
                realized_pnl=0,
                status="open",
            ),
            Position(
                asset_id=asset.id,
                mode="simulation",
                simulation_account_id=account.id,
                quantity=0,
                avg_entry_price=100,
                current_price=96,
                unrealized_pnl=-4,
                realized_pnl=-7.42,
                status="closed",
                closed_at=utcnow(),
            ),
        ]
    )
    db.commit()

    workspace = trading_workspace_service.get_workspace(db, "simulation", simulation_account_id=account.id)
    closed_view = next(position for position in workspace["positions"] if position["status"] == "closed")

    assert workspace["account"]["realized_pnl"] == -7.42
    assert workspace["account"]["unrealized_pnl"] == 0.55
    assert workspace["account"]["metadata"]["short_liability"] == 297.99
    assert workspace["account"]["metadata"]["net_position_value"] == -297.99
    assert closed_view["unrealized_pnl"] == 0


def test_automation_skips_buy_when_cash_reserve_leaves_no_trade_budget() -> None:
    db = build_session()
    asset = Asset(symbol="RESV", name="Reserve Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
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
    account = SimulationAccount(name="Reserve Sim", starting_cash=100, cash_balance=100, fees_bps=0, slippage_bps=0, latency_ms=0, is_active=True)
    db.add(account)
    db.add(
        RiskRule(
            name="Cash Reserve",
            scope="global",
            rule_type="cash_reserve",
            enabled=True,
            config_json={"min_cash_reserve_pct": 1.0},
        )
    )
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.95,
            status="candidate",
            occurred_at=utcnow(),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Would normally qualify, but cash is reserved.",
            suggested_entry=100,
            provider_type="openai_simulation",
            model_name="gpt-5-mini",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "trend-following"},
        )
    )
    db.flush()
    trading_workspace_service.upsert_profile(
        db,
        "simulation",
        TradingAutomationProfileUpsert(
            automation_enabled=True,
            approval_mode="fully_automatic",
            confidence_threshold=0.5,
            default_order_notional=100,
            max_orders_per_run=1,
        ),
    )
    db.commit()

    result = trading_workspace_service.run_automation(db, "simulation", simulation_account_id=account.id)
    db.commit()

    assert result["submitted_orders"] == 0
    assert result["rejected_signals"] == 1
    assert "cash reserve" in result["decisions"][0]["reason"].lower()
    assert db.scalar(select(Order).where(Order.asset_id == asset.id)) is None


def test_workspaces_share_the_same_signal_pool() -> None:
    db = build_session()
    asset = Asset(symbol="POOL", name="Shared Pool Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    signal = Signal(
        asset_id=asset.id,
        action="buy",
        confidence=0.82,
        status="candidate",
        occurred_at=utcnow(),
        indicators_json={},
        related_news_ids=[],
        related_event_ids=[],
        ai_rationale="Shared candidate visible in both workspaces.",
        suggested_entry=50,
        suggested_stop_loss=48,
        suggested_take_profit=55,
        estimated_risk_reward=2.5,
        provider_type="openai_simulation",
        model_name="gpt-5-mini",
        mode="both",
        source_kind="agent",
        metadata_json={"preferred_strategy": "trend-following"},
    )
    db.add(signal)
    db.commit()

    live_workspace = trading_workspace_service.get_workspace(db, "live")
    simulation_workspace = trading_workspace_service.get_workspace(db, "simulation")
    live_signal_ids = {item["id"] for item in live_workspace["signals"]}
    simulation_signal_ids = {item["id"] for item in simulation_workspace["signals"]}

    assert signal.id in live_signal_ids
    assert signal.id in simulation_signal_ids
    assert next(item for item in live_workspace["signals"] if item["id"] == signal.id)["mode"] == "shared"
    assert next(item for item in simulation_workspace["signals"] if item["id"] == signal.id)["mode"] == "shared"


def test_manual_position_trace_remains_useful_without_signal() -> None:
    db = build_session()
    asset = Asset(symbol="MANL", name="Manual Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()

    position = portfolio_service.create_manual_position(
        db,
        PositionCreate(
            asset_id=asset.id,
            mode="simulation",
            quantity=2,
            avg_entry_price=25,
            current_price=26,
            stop_loss=24,
            take_profit=30,
            trailing_stop=1,
            strategy_name="manual-check",
            notes="Imported existing manual line.",
        ),
    )
    db.commit()

    trace = signal_service.get_position_trace(db, position.id)

    assert trace["signal"] is None
    assert trace["summary"]["signal_linked"] is False
    assert trace["summary"]["execution_mode"] == "manual"
    assert trace["entrypoint"]["type"] == "position"
    assert trace["positions"][0]["symbol"] == "MANL"
    assert trace["stop_history"][0]["source"] in {"manual_override", "current_position"}


def test_recommendations_stay_lane_specific_even_when_signals_are_shared() -> None:
    db = build_session()
    asset = Asset(symbol="QUEUE", name="Queue Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    signal = Signal(
        asset_id=asset.id,
        action="buy",
        confidence=0.82,
        status="candidate",
        occurred_at=utcnow(),
        indicators_json={},
        related_news_ids=[],
        related_event_ids=[],
        ai_rationale="Approved shared recommendation.",
        suggested_entry=50,
        suggested_stop_loss=48,
        suggested_take_profit=55,
        estimated_risk_reward=2.5,
        provider_type="openai_simulation",
        model_name="gpt-5-mini",
        mode="both",
        source_kind="agent",
        metadata_json={"preferred_strategy": "trend-following"},
    )
    db.add(signal)
    db.flush()
    db.add(
        SignalEvaluation(
            signal_id=signal.id,
            approved=True,
            evaluator="simulation-automation",
            reason="Prepared for manual review.",
            outcome="approved",
        )
    )
    db.commit()

    live_workspace = trading_workspace_service.get_workspace(db, "live")
    simulation_workspace = trading_workspace_service.get_workspace(db, "simulation")

    assert len(live_workspace["recommendations"]) == 0
    assert len(simulation_workspace["recommendations"]) == 1
    assert simulation_workspace["recommendations"][0]["signal_id"] == signal.id


def test_reject_recommendation_records_lane_rejection_without_changing_shared_signal() -> None:
    db = build_session()
    asset = Asset(symbol="RJCT", name="Reject Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    signal = Signal(
        asset_id=asset.id,
        action="sell",
        confidence=0.7,
        status="candidate",
        occurred_at=utcnow(),
        indicators_json={},
        related_news_ids=[],
        related_event_ids=[],
        ai_rationale="Rejected by operator.",
        suggested_entry=20,
        suggested_stop_loss=21,
        suggested_take_profit=18,
        estimated_risk_reward=1.5,
        provider_type="openai_simulation",
        model_name="gpt-5-mini",
        mode="both",
        source_kind="agent",
        metadata_json={"preferred_strategy": "mean-reversion"},
    )
    db.add(signal)
    db.flush()
    db.add(
        SignalEvaluation(
            signal_id=signal.id,
            approved=True,
            evaluator="simulation-automation",
            reason="Prepared for operator review.",
            outcome="approved",
        )
    )
    db.commit()

    result = trading_workspace_service.reject_recommendation(db, "simulation", signal.id, "Operator declined this setup.")
    db.commit()

    updated_signal = db.get(Signal, signal.id)
    evaluation = db.scalar(select(SignalEvaluation).where(SignalEvaluation.signal_id == signal.id).order_by(SignalEvaluation.created_at.desc()))

    assert result["outcome"] == "rejected"
    assert updated_signal is not None
    assert updated_signal.status == "candidate"
    assert evaluation is not None
    assert evaluation.reason == "Operator declined this setup."
    assert evaluation.outcome == "manual_rejected"


def test_workspace_hides_stale_news_error_alert_when_latest_health_is_warn() -> None:
    db = build_session()
    db.add(
        SystemHealthEvent(
            component="news.rss_refresh",
            status="error",
            message="Fetched 0 new RSS articles from 8 feeds since old-cutoff. 1 feed failed.",
            metadata_json={},
            observed_at=utcnow() - timedelta(minutes=15),
        )
    )
    db.flush()
    db.add(
        Alert(
            category="health",
            severity="warning",
            title="news.rss_refresh reported an error",
            message="Fetched 0 new RSS articles from 8 feeds since old-cutoff. 1 feed failed.",
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
            message="No fresh RSS articles were imported from 8 feeds. Older items were skipped.",
            metadata_json={},
            observed_at=utcnow(),
        )
    )
    db.commit()

    workspace = trading_workspace_service.get_workspace(db, "simulation")

    assert workspace["alerts"] == []


def test_simulation_workspace_can_inherit_live_automation_policy() -> None:
    db = build_session()

    trading_workspace_service.upsert_profile(
        db,
        "live",
        TradingAutomationProfileUpsert(
            automation_enabled=True,
            approval_mode="fully_automatic",
            confidence_threshold=0.73,
            default_order_notional=250,
            stop_loss_pct=0.025,
            take_profit_pct=0.07,
            trailing_stop_pct=0.015,
            allowed_strategy_slugs=["trend-following"],
            allowed_provider_types=["openai_simulation"],
            tradable_actions=["buy", "sell"],
        ),
    )
    trading_workspace_service.upsert_profile(
        db,
        "simulation",
        TradingAutomationProfileUpsert(
            enabled=True,
            automation_enabled=False,
            inherit_from_live=True,
            approval_mode="manual_only",
            confidence_threshold=0.4,
            default_order_notional=50,
        ),
    )
    db.commit()

    workspace = trading_workspace_service.get_workspace(db, "simulation")

    assert workspace["automation"]["inherit_from_live"] is True
    assert workspace["automation"]["effective_source_mode"] == "live"
    assert workspace["automation"]["automation_enabled"] is True
    assert workspace["automation"]["approval_mode"] == "fully_automatic"
    assert workspace["automation"]["confidence_threshold"] == 0.73
    assert workspace["automation"]["default_order_notional"] == 250


def test_live_workspace_does_not_show_fake_cash_without_trading212_sync() -> None:
    db = build_session()

    workspace = trading_workspace_service.get_workspace(db, "live")

    assert workspace["account"]["status"] == "disconnected"
    assert workspace["account"]["cash_available"] == 0
    assert workspace["account"]["available_to_trade_cash"] == 0
    assert "Trading212 not connected" in workspace["account"]["safety_message"]


def test_live_automation_blocks_when_no_live_model_is_configured() -> None:
    db = build_session()
    asset = Asset(symbol="LIVE", name="Live Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.add(
        BrokerAccount(
            name="Trading212 Live",
            broker_type="trading212",
            mode="live",
            enabled=True,
            live_trading_enabled=False,
            status="connected",
            settings_json={"available_cash": 1000, "total_value": 1000, "currency": "USD"},
        )
    )
    db.flush()
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.9,
            status="candidate",
            occurred_at=utcnow(),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Live candidate.",
            suggested_entry=100,
            provider_type="openai_live",
            model_name="gpt-5.2",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "trend-following"},
        )
    )
    trading_workspace_service.upsert_profile(
        db,
        "live",
        TradingAutomationProfileUpsert(
            automation_enabled=True,
            approval_mode="fully_automatic",
            confidence_threshold=0.5,
            default_order_notional=100,
        ),
    )
    db.commit()

    result = trading_workspace_service.run_automation(db, "live")

    assert result["status"] == "blocked"
    assert "exactly one configured Live trading model" in result["message"]


def test_live_signal_approval_rejects_wrong_model_profile() -> None:
    db = build_session()
    asset = Asset(symbol="WRONG", name="Wrong Model Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.add(
        ProviderConfig(
            provider_type="openai_live",
            name="ChatGPT / OpenAI / Actual Trading",
            enabled=True,
            base_url="https://api.openai.com/v1",
            default_model="gpt-5.2",
            temperature=0.2,
            max_tokens=512,
            context_window=400000,
            tool_calling_enabled=True,
            reasoning_mode="minimal",
            task_defaults={},
            settings_json={},
        )
    )
    db.flush()
    signal = Signal(
        asset_id=asset.id,
        action="buy",
        confidence=0.9,
        status="candidate",
        occurred_at=utcnow(),
        indicators_json={},
        related_news_ids=[],
        related_event_ids=[],
        ai_rationale="Wrong live model.",
        suggested_entry=100,
        provider_type="deepseek_live",
        model_name="deepseek-reasoner",
        mode="both",
        source_kind="agent",
        metadata_json={"preferred_strategy": "trend-following"},
    )
    db.add(signal)
    trading_workspace_service.upsert_profile(
        db,
        "live",
        TradingAutomationProfileUpsert(
            allowed_provider_types=["openai_live"],
            config_json={"live_model_provider_type": "openai_live"},
        ),
    )
    db.commit()

    try:
        trading_workspace_service.approve_signal(db, "live", signal.id)
    except ValueError as exc:
        assert "locked to openai_live" in str(exc)
    else:
        raise AssertionError("Expected live approval to reject the wrong provider profile.")


def test_live_automation_allows_configured_healthy_model_for_review_queue() -> None:
    db = build_session()
    asset = Asset(symbol="OKLIVE", name="Healthy Live Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.add(
        ProviderConfig(
            provider_type="openai_live",
            name="ChatGPT / OpenAI / Actual Trading",
            enabled=True,
            base_url="https://api.openai.com/v1",
            default_model="gpt-5.2",
            temperature=0.2,
            max_tokens=512,
            context_window=400000,
            tool_calling_enabled=True,
            reasoning_mode="minimal",
            task_defaults={},
            settings_json={},
            last_health_status="ok",
            last_health_message="healthy",
        )
    )
    db.add(
        BrokerAccount(
            name="Trading212 Live",
            broker_type="trading212",
            mode="live",
            enabled=True,
            live_trading_enabled=False,
            status="connected",
            settings_json={"available_cash": 1000, "total_value": 1000, "currency": "USD", "last_synced_at": utcnow().isoformat()},
        )
    )
    db.flush()
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.9,
            status="candidate",
            occurred_at=utcnow(),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Healthy live candidate.",
            suggested_entry=100,
            provider_type="openai_live",
            model_name="gpt-5.2",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "trend-following"},
        )
    )
    trading_workspace_service.upsert_profile(
        db,
        "live",
        TradingAutomationProfileUpsert(
            automation_enabled=True,
            approval_mode="semi_automatic",
            confidence_threshold=0.5,
            default_order_notional=100,
            allowed_provider_types=["openai_live"],
            config_json={"live_model_provider_type": "openai_live"},
        ),
    )
    db.commit()

    result = trading_workspace_service.run_automation(db, "live")

    assert result["status"] == "success"
    assert result["approved_recommendations"] == 1
    assert result["submitted_orders"] == 0
