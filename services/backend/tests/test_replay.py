from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.replay import ReplayModelResult, ReplayRun
from app.models.provider import ModelRun
from app.models.signal import Signal
from app.models.simulation import SimulationAccount, SimulationTrade
from app.schemas.replay import ReplayRunCreate
from app.services.analytics.service import analytics_service
from app.services.replay.service import replay_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_replay_creates_isolated_run_for_two_models_on_same_inputs() -> None:
    db = build_session()
    start = utcnow() - timedelta(days=3)
    end = utcnow()
    asset = Asset(symbol="RPLY", name="Replay Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    for index, price in enumerate([100, 104, 108]):
        db.add(
            MarketSnapshot(
                asset_id=asset.id,
                timestamp=start + timedelta(days=index),
                open_price=price,
                high_price=price + 1,
                low_price=price - 1,
                close_price=price,
                volume=1000,
                source="test",
            )
        )
    db.add(
        SimulationAccount(
            name="Normal Sim",
            provider_type="model_a",
            starting_cash=5000,
            cash_balance=5000,
            fees_bps=0,
            slippage_bps=0,
            latency_ms=0,
        )
    )
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.9,
            status="candidate",
            occurred_at=start + timedelta(hours=2),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Replay model A buy.",
            suggested_entry=100,
            provider_type="model_a",
            model_name="alpha",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "trend-following"},
        )
    )
    db.add(
        Signal(
            asset_id=asset.id,
            action="hold",
            confidence=0.8,
            status="candidate",
            occurred_at=start + timedelta(hours=2),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Replay model B holds.",
            suggested_entry=100,
            provider_type="model_b",
            model_name="beta",
            mode="both",
            source_kind="agent",
            metadata_json={"preferred_strategy": "trend-following"},
        )
    )
    db.commit()

    before_cash = db.scalar(select(SimulationAccount)).cash_balance
    view = replay_service.create_run(
        db,
        ReplayRunCreate(
            date_start=start,
            date_end=end,
            starting_cash=10_000,
            selected_models=["model_a", "model_b"],
            symbols=["RPLY"],
            fees_bps=0,
            slippage_bps=0,
            cash_reserve_percent=0.2,
            short_enabled=True,
        ),
    )
    db.commit()

    run = db.scalar(select(ReplayRun))
    results = list(db.scalars(select(ReplayModelResult).order_by(ReplayModelResult.provider_type)))
    after_cash = db.scalar(select(SimulationAccount)).cash_balance

    assert view["status"] == "completed"
    assert run is not None
    assert len(results) == 2
    assert {result.provider_type for result in results} == {"model_a", "model_b"}
    assert results[0].metrics_json["input_hash"] == results[1].metrics_json["input_hash"]
    assert before_cash == after_cash
    assert db.scalar(select(SimulationTrade)) is None


def test_replay_results_are_available_in_model_comparison_metrics() -> None:
    db = build_session()
    start = utcnow() - timedelta(days=1)
    asset = Asset(symbol="METR", name="Metric Asset", asset_type="stock", sector="Technology", exchange="TEST", currency="USD")
    db.add(asset)
    db.flush()
    db.add(
        MarketSnapshot(
            asset_id=asset.id,
            timestamp=start,
            open_price=50,
            high_price=51,
            low_price=49,
            close_price=50,
            volume=1000,
            source="test",
        )
    )
    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.9,
            status="candidate",
            occurred_at=start + timedelta(minutes=1),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Replay model buy.",
            suggested_entry=50,
            provider_type="model_metrics",
            model_name="metric",
            mode="both",
            source_kind="agent",
            metadata_json={},
        )
    )
    db.add(
        ModelRun(
            task_name="signal_generation",
            provider_type="model_metrics",
            model_name="metric",
            status="success",
            latency_ms=250,
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            estimated_cost=0.0123,
            created_at=start + timedelta(minutes=2),
        )
    )
    db.commit()

    run = replay_service.create_run(
        db,
        ReplayRunCreate(
            date_start=start,
            date_end=utcnow(),
            starting_cash=1000,
            selected_models=["model_metrics"],
            symbols=["METR"],
        ),
    )
    db.commit()

    rows = analytics_service.model_comparison(db, scope="replay", replay_run_id=run["id"])
    csv_payload = analytics_service.model_comparison_csv(db, scope="replay", replay_run_id=run["id"])

    assert len(rows) == 1
    assert rows[0]["scope"] == "replay"
    assert rows[0]["provider_type"] == "model_metrics"
    assert rows[0]["model_cost"] == 0.0123
    assert "provider_type" in csv_payload
    assert "model_metrics" in csv_payload
