from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.asset import Asset, MarketSnapshot, Watchlist, WatchlistItem
from app.models.audit import Alert
from app.models.broker import BrokerAccount
from app.models.health import SystemHealthEvent
from app.models.simulation import SimulationAccount
from app.models.strategy import Strategy
from app.models.user import User
from app.schemas.broker import BrokerAccountCreate
from app.schemas.provider import ProviderConfigUpsert, TaskMappingUpsert
from app.schemas.risk import RiskRuleUpsert
from app.schemas.simulation import SimulationAccountCreate
from app.services.alerts.service import alert_service
from app.services.audit.service import audit_service
from app.services.brokers.service import broker_service
from app.services.market_data.service import market_data_service
from app.services.news.service import news_service
from app.services.providers.service import provider_service
from app.services.risk.service import risk_service
from app.services.simulation.service import simulation_service
from app.services.trading.service import trading_workspace_service
from app.utils.time import utcnow


def seed_demo() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        assets_already_seeded = db.scalar(select(Asset).limit(1)) is not None

        admin = db.scalar(select(User).where(User.username == settings.default_admin_username))
        if admin is None:
            admin = User(
                username=settings.default_admin_username,
                hashed_password=hash_password(settings.default_admin_password),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.flush()

        for provider_type, profile in provider_service.catalog.items():
            if provider_service.get_config(db, provider_type) is None:
                payload = ProviderConfigUpsert(
                    enabled=profile.enabled_by_default,
                    base_url=profile.default_base_url,
                    default_model=profile.default_model,
                    temperature=profile.temperature,
                    max_tokens=profile.max_tokens,
                    context_window=profile.context_window,
                    tool_calling_enabled=profile.tool_calling_default,
                    reasoning_mode=profile.reasoning_modes[0] if profile.reasoning_modes else None,
                    task_defaults={
                        "signal_explanation": profile.default_model,
                        "portfolio_commentary": profile.default_model,
                        "simulation_commentary": profile.default_model,
                    }
                    if profile.default_model
                    else {},
                    settings_json={
                        **profile.settings_defaults,
                        "vendor_key": profile.vendor_key,
                        "deployment_scope": profile.deployment_scope,
                        "trading_mode": profile.trading_mode,
                    },
                )
                provider_service.upsert_config(db, provider_type, payload)

        task_mappings = [
            TaskMappingUpsert(task_name="news_summarization", provider_type="local_qwen3_simulation", model_name="qwen3:8b"),
            TaskMappingUpsert(task_name="sentiment_analysis", provider_type="local_qwen25_simulation", model_name="qwen2.5:7b-instruct"),
            TaskMappingUpsert(task_name="event_extraction", provider_type="local_qwen25_simulation", model_name="qwen2.5:7b-instruct"),
            TaskMappingUpsert(task_name="signal_explanation", provider_type="local_llama3_simulation", model_name="llama3.2:3b"),
            TaskMappingUpsert(
                task_name="trade_rationale_generation",
                provider_type="local_llama3_live",
                model_name="llama3.1:8b",
                fallback_chain=[{"provider_type": "local_qwen3_simulation", "model_name": "qwen3:8b"}],
            ),
            TaskMappingUpsert(task_name="candidate_ranking", provider_type="local_gpt_oss_simulation", model_name="gpt-oss:20b"),
            TaskMappingUpsert(
                task_name="portfolio_commentary",
                provider_type="openai_live",
                model_name="gpt-5.2",
                fallback_chain=[
                    {"provider_type": "anthropic_live", "model_name": "claude-opus-4-6"},
                    {"provider_type": "local_llama3_live", "model_name": "llama3.1:8b"},
                ],
            ),
            TaskMappingUpsert(
                task_name="simulation_commentary",
                provider_type="deepseek_simulation",
                model_name="deepseek-chat",
                fallback_chain=[
                    {"provider_type": "openai_simulation", "model_name": "gpt-5-mini"},
                    {"provider_type": "local_deepseek_r1_simulation", "model_name": "deepseek-r1:8b"},
                    {"provider_type": "local_qwen3_simulation", "model_name": "qwen3:8b"},
                ],
            ),
        ]
        for mapping in task_mappings:
            provider_service.upsert_task_mapping(db, mapping)

        risk_rules = [
            RiskRuleUpsert(name="Kill Switch", rule_type="kill_switch", config_json={"active": False}, description="Global hard stop for order flow."),
            RiskRuleUpsert(name="Max Position Size", rule_type="max_position_size", config_json={"max_notional": 25000, "max_quantity": 250}, description="Limit single position notional and quantity."),
            RiskRuleUpsert(name="Max Capital Per Asset", rule_type="max_capital_per_asset", config_json={"max_pct": 0.3}, description="Limit concentration per asset."),
            RiskRuleUpsert(name="Max Open Positions", rule_type="max_open_positions", config_json={"max_open_positions": 8}, description="Limit open book size."),
            RiskRuleUpsert(name="Max Sector Exposure", rule_type="max_sector_exposure", config_json={"max_sector_pct": 0.45}, description="Limit total sector concentration."),
            RiskRuleUpsert(
                name="Cash Reserve",
                rule_type="cash_reserve",
                config_json={"min_cash_reserve_pct": 0.2, "simulation_override_pct": None, "live_override_pct": None},
                description="Always keep this percentage of account value uninvested as cash.",
            ),
            RiskRuleUpsert(
                name="Daily Max Loss",
                rule_type="daily_max_loss",
                config_json={"max_daily_loss_pct": 0.025},
                description="Pause new orders after daily losses reach 2.5% of total account value.",
            ),
            RiskRuleUpsert(name="Max Drawdown Halt", rule_type="max_drawdown_halt", config_json={"max_drawdown_pct": 0.14}, description="Stop new orders under deep drawdown."),
            RiskRuleUpsert(name="Loss Streak Cooldown", rule_type="loss_streak_cooldown", config_json={"loss_streak": 3, "cooldown_minutes": 240}, description="Cooldown after consecutive losses."),
            RiskRuleUpsert(name="Per Trade Risk", rule_type="per_trade_risk", config_json={"max_risk_pct": 0.015, "reference_account_value": 1000, "require_stop_loss": False}, description="Cap loss from entry to stop."),
            RiskRuleUpsert(name="Market Hours Guard", rule_type="market_hours", config_json={"enforce_market_hours": False}, description="Optional market-hours restriction."),
        ]
        for rule in risk_rules:
            risk_service.upsert_rule(db, rule)

        paper_account = broker_service.upsert_account(
            db,
            BrokerAccountCreate(
                name="Paper Mirror",
                broker_type="paper",
                mode="paper",
                enabled=False,
                live_trading_enabled=False,
                base_url=None,
                settings_json={"notes": "Local scaffold only; never used as live cash."},
            ),
        )
        trading212_account = db.scalar(select(BrokerAccount).where(BrokerAccount.broker_type == "trading212", BrokerAccount.mode == "live"))
        if trading212_account is None:
            broker_service.upsert_account(
                db,
                BrokerAccountCreate(
                    name="Trading212 Scaffold",
                    broker_type="trading212",
                    mode="live",
                    enabled=False,
                    live_trading_enabled=False,
                    base_url="https://live.trading212.com/api/v0",
                    settings_json={"sync_mode": "manual-mirror", "supported_actions": ["sync_account", "sync_positions", "sync_orders"]},
                ),
            )

        simulation_account = db.scalar(select(SimulationAccount).where(SimulationAccount.name == "Primary Simulation"))
        if simulation_account is None:
            simulation_account = simulation_service.create_account(
                db,
                SimulationAccountCreate(name="Primary Simulation", starting_cash=1000, fees_bps=5, slippage_bps=2, latency_ms=50, decimal_precision=6),
            )
        simulation_service.ensure_model_accounts(db)
        trading_workspace_service.get_or_create_profile(db, "live")
        trading_workspace_service.get_or_create_profile(db, "simulation")

        if assets_already_seeded:
            print("Core provider/risk settings ensured; existing market seed already present.")
            db.commit()
            return

        assets_data = [
            ("AAPL", "Apple Inc.", "stock", "Technology", "NASDAQ", 190.5),
            ("MSFT", "Microsoft Corp.", "stock", "Technology", "NASDAQ", 425.2),
            ("NVDA", "NVIDIA Corp.", "stock", "Technology", "NASDAQ", 915.4),
            ("SPY", "SPDR S&P 500 ETF Trust", "etf", "Index", "NYSEARCA", 522.8),
            ("QQQ", "Invesco QQQ Trust", "etf", "Index", "NASDAQ", 446.1),
            ("XLF", "Financial Select Sector SPDR", "etf", "Financials", "NYSEARCA", 43.9),
        ]
        assets: dict[str, Asset] = {}
        for symbol, name, asset_type, sector, exchange, base_price in assets_data:
            asset = Asset(symbol=symbol, name=name, asset_type=asset_type, sector=sector, exchange=exchange, currency="USD")
            db.add(asset)
            db.flush()
            assets[symbol] = asset

        refresh_report = market_data_service.refresh_market_data(db)
        assets_without_real_history = {
            symbol: asset
            for symbol, asset in assets.items()
            if not db.scalar(select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id).limit(1))
        }
        for symbol, asset in assets_without_real_history.items():
            base_price = next(item[5] for item in assets_data if item[0] == symbol)
            for day in range(45, -1, -1):
                drift = 1 + ((45 - day) * 0.0025) + (((day % 5) - 2) * 0.003)
                close = round(base_price * drift, 2)
                snapshot = MarketSnapshot(
                    asset_id=asset.id,
                    timestamp=utcnow() - timedelta(days=day),
                    open_price=round(close * 0.992, 2),
                    high_price=round(close * 1.012, 2),
                    low_price=round(close * 0.987, 2),
                    close_price=close,
                    volume=1_500_000 + (day * 12_500),
                    source="local-bootstrap",
                )
                db.add(snapshot)

        watchlist = Watchlist(name="Core US Equities", description="Large-cap stocks and broad ETFs", is_default=True)
        db.add(watchlist)
        db.flush()
        for symbol in ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"]:
            db.add(WatchlistItem(watchlist_id=watchlist.id, asset_id=assets[symbol].id))

        strategies = [
            ("Trend Following", "trend-following", "technical", "Uses moving averages, MACD, and momentum filters."),
            ("Mean Reversion", "mean-reversion", "technical", "Looks for RSI and Bollinger mean-reversion setups."),
            ("Breakout", "breakout", "technical", "Monitors support, resistance, and volume expansion."),
            ("News Momentum", "news-momentum", "news", "Scores sentiment and momentum from recent articles."),
            ("Event Driven", "event-driven", "events", "React to earnings, analyst, macro, and company events."),
            ("Blended", "blended", "hybrid", "Combines technical and news/event inputs into a single candidate."),
        ]
        for name, slug, category, description in strategies:
            db.add(Strategy(name=name, slug=slug, category=category, description=description, enabled=True, config_json={}))

        try:
            news_service.refresh_latest_news(db)
        except Exception:
            pass

        alert_service.create_alert(
            db,
            category="provider",
            severity="info",
            title="OpenAI provider disabled",
            message="OpenAI-compatible provider is configured but disabled until a key is saved.",
            mode="system",
            source_ref="provider:openai",
        )
        alert_service.create_alert(
            db,
            category="broker",
            severity="warning",
            title="Trading212 execution unavailable",
            message="Trading212 remains scaffold-only; execution is intentionally disabled.",
            mode="live",
            source_ref="broker:trading212",
        )

        health_events = [
            SystemHealthEvent(component="backend", status="ok", message="API online", metadata_json={}, observed_at=utcnow()),
            SystemHealthEvent(component="worker", status="ok", message="Celery worker ready", metadata_json={}, observed_at=utcnow()),
            SystemHealthEvent(component="scheduler", status="ok", message="Beat scheduler ready", metadata_json={}, observed_at=utcnow()),
            SystemHealthEvent(component="provider:local-models", status="warn", message="Local model families are configured; connectivity depends on Ollama availability.", metadata_json={}, observed_at=utcnow()),
            SystemHealthEvent(
                component="market-data.seed",
                status="ok" if refresh_report["assets_failed"] == 0 else "warn",
                message=(
                    f"Initial market data refresh created {refresh_report['snapshots_created']} snapshots and updated "
                    f"{refresh_report['snapshots_updated']}."
                ),
                metadata_json=refresh_report,
                observed_at=utcnow(),
            ),
        ]
        for event in health_events:
            db.add(event)

        audit_service.log(
            db,
            actor="system",
            action="provider.settings.seed",
            target_type="provider_config",
            status="success",
            details={"providers": list(provider_service.catalog.keys())},
        )
        audit_service.log(
            db,
            actor="system",
            action="risk.rules.seed",
            target_type="risk_rule",
            status="success",
            details={"count": len(risk_rules)},
        )
        audit_service.log(
            db,
            actor="system",
            action="live_trading.guard",
            target_type="system",
            status="success",
            mode="live",
            details={"enabled": settings.enable_live_trading},
        )
        audit_service.log(
            db,
            actor="system",
            action="broker.sync.scaffold",
            target_type="broker_account",
            target_id=paper_account.id,
            status="success",
            mode="live",
            details={"trading212_execution": "disabled"},
        )

        db.commit()
        print("Demo seed completed.")


def main() -> None:
    seed_demo()


if __name__ == "__main__":
    main()
