from fastapi import APIRouter, Depends
from redis.exceptions import RedisError
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis import get_redis
from app.models.asset import MarketSnapshot
from app.models.broker import BrokerAccount
from app.models.health import SystemHealthEvent
from app.models.news import NewsArticle
from app.models.signal import Signal
from app.models.trading import TradingAutomationProfile
from app.schemas.common import HealthStatusSchema
from app.services.brokers.service import broker_service
from app.services.news.service import news_service
from app.services.providers.service import provider_service
from app.utils.time import utcnow

router = APIRouter()


@router.get("/live", response_model=HealthStatusSchema)
def live() -> HealthStatusSchema:
    return HealthStatusSchema(status="ok", details={"service": "backend"})


@router.get("/ready", response_model=HealthStatusSchema)
def ready(db: Session = Depends(get_db)) -> HealthStatusSchema:
    details = {"database": "ok", "redis": "ok"}
    db.execute(text("SELECT 1"))
    try:
        redis = get_redis()
        redis.ping()
        redis.close()
    except RedisError as exc:
        details["redis"] = str(exc)
        return HealthStatusSchema(status="error", details=details)
    return HealthStatusSchema(status="ok", details=details)


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    latest_news = db.scalar(
        select(NewsArticle).where(NewsArticle.provider_type != "system").order_by(desc(NewsArticle.published_at)).limit(1)
    )
    latest_market = db.scalar(select(MarketSnapshot).order_by(desc(MarketSnapshot.timestamp)).limit(1))
    latest_signal = db.scalar(select(Signal).order_by(desc(Signal.occurred_at)).limit(1))
    latest_scheduler = db.scalar(
        select(SystemHealthEvent)
        .where(SystemHealthEvent.component.in_(["scheduler", "automation.scheduler"]))
        .order_by(desc(SystemHealthEvent.observed_at))
        .limit(1)
    )
    broker_accounts = list(db.scalars(select(BrokerAccount).where(BrokerAccount.mode == "live")))
    live_profile = db.scalar(select(TradingAutomationProfile).where(TradingAutomationProfile.mode == "live"))
    live_model_provider = (live_profile.config_json or {}).get("live_model_provider_type") if live_profile else None
    provider_health = provider_service.get_health(db)
    selected_live_model = next((item for item in provider_health if item["provider_type"] == live_model_provider), None) if live_model_provider else None
    health_events = [
        {
            "component": event.component,
            "status": event.status,
            "message": event.message,
            "observed_at": event.observed_at.isoformat(),
            "metadata": event.metadata_json,
        }
        for event in db.scalars(select(SystemHealthEvent).order_by(desc(SystemHealthEvent.observed_at)).limit(20))
    ]
    now = utcnow()
    news_diagnostics = news_service.latest_refresh_diagnostics(db)
    broker_sync = []
    for account in broker_accounts:
        latest_sync = broker_service.latest_sync_event(db, account.id)
        broker_sync.append(
            {
                "account_id": account.id,
                "name": account.name,
                "broker_type": account.broker_type,
                "status": account.status,
                "enabled": account.enabled,
                "last_sync_status": latest_sync.status if latest_sync else None,
                "last_sync_completed_at": latest_sync.completed_at.isoformat() if latest_sync and latest_sync.completed_at else None,
                "last_sync_error": (latest_sync.details_json or {}).get("account_message") if latest_sync and latest_sync.status in {"error", "warn"} else None,
            }
        )
    warnings = []
    if latest_news is None:
        warnings.append("No real news article has been ingested yet.")
    elif (now - latest_news.published_at).total_seconds() > 60 * 60 * 24:
        warnings.append("News data is stale.")
    if latest_market is None:
        warnings.append("No market snapshot has been recorded yet.")
    elif (now - latest_market.timestamp).total_seconds() > 60 * 60 * 24:
        warnings.append("Market data is stale.")
    if not broker_accounts or not any(account.enabled and account.status == "connected" for account in broker_accounts):
        warnings.append("Trading212 is not connected.")
    if not live_model_provider:
        warnings.append("No live trading model is configured.")
    elif selected_live_model and selected_live_model["status"] == "error":
        warnings.append("Selected live model is unhealthy.")
    if news_diagnostics.get("articles_added", 0) == 0 and news_diagnostics.get("run_type") != "none":
        warnings.append("Latest news refresh produced 0 new articles.")

    return {
        "status": "warn" if warnings else "ok",
        "providers": provider_health,
        "events": health_events,
        "freshness": {
            "news_latest_published_at": latest_news.published_at.isoformat() if latest_news else None,
            "market_latest_snapshot_at": latest_market.timestamp.isoformat() if latest_market else None,
            "last_signal_generation_at": latest_signal.occurred_at.isoformat() if latest_signal else None,
            "scheduler_status": latest_scheduler.status if latest_scheduler else "unknown",
            "scheduler_observed_at": latest_scheduler.observed_at.isoformat() if latest_scheduler else None,
        },
        "broker_sync": broker_sync,
        "model_health": {
            "live_model_provider_type": live_model_provider,
            "selected_live_model": selected_live_model,
        },
        "news": news_diagnostics,
        "warnings": warnings,
    }
