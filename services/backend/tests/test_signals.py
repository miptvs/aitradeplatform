from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.asset import Asset, MarketSnapshot
from app.models.base import Base
from app.models.news import NewsArticle
from app.models.portfolio import Position
from app.models.provider import ProviderConfig
from app.models.signal import Signal
from app.models.strategy import Strategy
from app.services.providers.base import ProviderRunResult
from app.services.signals.strategies import StrategyDecision
from app.services.signals.service import signal_service
from app.utils.time import utcnow


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_generate_signals_uses_explicit_provider_and_hides_template_rows(monkeypatch) -> None:
    db = build_session()

    asset = Asset(symbol="NVDA", name="NVIDIA Corp.", asset_type="stock", exchange="NASDAQ", currency="USD")
    db.add(asset)
    db.flush()

    for day in range(35, -1, -1):
        close = 800 + (35 - day) * 3
        db.add(
            MarketSnapshot(
                asset_id=asset.id,
                timestamp=utcnow() - timedelta(days=day),
                open_price=close - 5,
                high_price=close + 8,
                low_price=close - 8,
                close_price=close,
                volume=2_000_000 + day * 1000,
                source="stooq-daily",
            )
        )

    db.add(
        NewsArticle(
            title="NVIDIA demand remains strong across AI infrastructure buyers",
            source="Example Markets",
            url="https://example.com/nvda",
            published_at=utcnow(),
            summary="Fresh article supports continued demand and strong revenue momentum.",
            sentiment="positive",
            impact_score=0.78,
            affected_symbols=["NVDA"],
            provider_type="rss",
            model_name="rss-heuristic",
            dedupe_key="nvda-news",
        )
    )
    db.add(
        ProviderConfig(
            provider_type="local_qwen3_simulation",
            name="Qwen 3 / Simulation",
            enabled=True,
            base_url="http://ollama:11434",
            default_model="qwen3:8b",
            temperature=0.2,
            max_tokens=512,
            context_window=8192,
            tool_calling_enabled=False,
            reasoning_mode="standard",
            task_defaults={},
            settings_json={},
        )
    )

    for name, slug in [
        ("Trend Following", "trend-following"),
        ("Mean Reversion", "mean-reversion"),
        ("Breakout", "breakout"),
        ("News Momentum", "news-momentum"),
        ("Event Driven", "event-driven"),
        ("Blended", "blended"),
    ]:
        db.add(Strategy(name=name, slug=slug, category="test", description=f"{name} strategy", enabled=True, config_json={}))

    db.add(
        Signal(
            asset_id=asset.id,
            action="buy",
            confidence=0.9,
            status="candidate",
            occurred_at=utcnow() - timedelta(hours=2),
            indicators_json={},
            related_news_ids=[],
            related_event_ids=[],
            ai_rationale="Old template signal",
            provider_type="system",
            model_name="template",
            mode="simulation",
            source_kind="auto",
            metadata_json={},
        )
    )
    db.commit()

    def fake_run_task(*args, **kwargs):
        assert kwargs["provider_type"] == "local_qwen3_simulation"
        assert '"asset"' in kwargs["prompt"]
        assert "MCP signal context" in kwargs["prompt"]
        return ProviderRunResult(
            text='{"action":"buy","confidence":0.81,"strategy":"blended","rationale":"Real provider-backed signal with technical and news confirmation.","suggested_entry":905.5,"suggested_stop_loss":878.0,"suggested_take_profit":962.0,"estimated_risk_reward":2.05,"suggested_position_size_type":"percentage","suggested_position_size_value":5}',
            provider_type="local",
            model_name="qwen3:8b",
        )

    monkeypatch.setattr(
        "app.services.signals.service.mcp_client_service.get_signal_context",
        lambda **kwargs: {"asset": {"symbol": "NVDA"}, "open_positions": [], "provider_health": []},
    )
    monkeypatch.setattr("app.services.signals.service.provider_service.run_task", fake_run_task)

    created = signal_service.generate_signals(db, provider_type="local_qwen3_simulation")
    db.commit()

    assert len(created) == 1
    assert created[0].provider_type == "local_qwen3_simulation"
    assert created[0].model_name == "qwen3:8b"
    assert created[0].source_kind == "agent"

    listed = signal_service.list_signals(db, provider_type="local_qwen3_simulation")
    assert len(listed) == 1
    assert listed[0]["provider_type"] == "local_qwen3_simulation"
    assert listed[0]["ai_rationale"].startswith("Real provider-backed signal")
    assert listed[0]["suggested_position_size_type"] == "percentage"
    assert listed[0]["suggested_position_size_value"] == 5


def test_generate_signals_surfaces_provider_error_with_symbol_context(monkeypatch) -> None:
    db = build_session()

    asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", exchange="NASDAQ", currency="USD")
    db.add(asset)
    db.flush()

    for day in range(35, -1, -1):
        close = 180 + (35 - day) * 1.5
        db.add(
            MarketSnapshot(
                asset_id=asset.id,
                timestamp=utcnow() - timedelta(days=day),
                open_price=close - 1,
                high_price=close + 2,
                low_price=close - 2,
                close_price=close,
                volume=1_500_000 + day * 1000,
                source="yahoo-chart",
            )
        )

    db.add(
        ProviderConfig(
            provider_type="local_qwen3_simulation",
            name="Qwen 3 / Simulation",
            enabled=True,
            base_url="http://ollama:11434",
            default_model="qwen3:8b",
            temperature=0.2,
            max_tokens=256,
            context_window=8192,
            tool_calling_enabled=False,
            reasoning_mode="standard",
            task_defaults={},
            settings_json={},
        )
    )

    for name, slug in [
        ("Trend Following", "trend-following"),
        ("Mean Reversion", "mean-reversion"),
        ("Breakout", "breakout"),
        ("News Momentum", "news-momentum"),
        ("Event Driven", "event-driven"),
        ("Blended", "blended"),
    ]:
        db.add(Strategy(name=name, slug=slug, category="test", description=f"{name} strategy", enabled=True, config_json={}))

    db.commit()

    def fake_run_task(*args, **kwargs):
        raise ValueError("provider timeout")

    monkeypatch.setattr("app.services.signals.service.provider_service.run_task", fake_run_task)
    monkeypatch.setattr("app.services.signals.service.mcp_client_service.get_signal_context", lambda **kwargs: None)

    try:
        signal_service.generate_signals(db, provider_type="local_qwen3_simulation")
    except ValueError as exc:
        assert str(exc).startswith("AAPL: provider timeout")
    else:
        raise AssertionError("Expected provider error to be surfaced")


def test_position_exit_decision_creates_low_confidence_sell_watch() -> None:
    position = Position(
        asset_id="asset-1",
        quantity=1,
        avg_entry_price=205,
        current_price=199,
        status="open",
        mode="simulation",
    )
    indicators = {
        "close": 199,
        "sma_30": 202,
        "momentum_10": -0.03,
        "macd_histogram": -0.15,
    }
    decisions = {
        "breakout": StrategyDecision("sell", 0.63, "Testing support with downside pressure."),
        "mean-reversion": StrategyDecision("buy", 0.68, "Oversold bounce possible."),
        "blended": StrategyDecision("hold", 0.48, "Mixed thesis."),
    }

    decision = signal_service._position_exit_decision(position, "NVDA", indicators, decisions)

    assert decision is not None
    assert decision["trigger"] == "mixed_exit_watch"
    assert decision["confidence"] < 0.58


def test_signal_action_normalization_supports_sell_short_and_close_actions() -> None:
    assert signal_service._normalize_action("SHORT", "hold") == "short"
    assert signal_service._normalize_action("close position", "hold") == "close_long"
    assert signal_service._normalize_action("trim", "hold") == "reduce_long"
    assert signal_service._normalize_action("buy to cover", "hold") == "cover_short"
