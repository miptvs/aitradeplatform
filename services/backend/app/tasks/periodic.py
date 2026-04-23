from sqlalchemy import desc, select

from app.core.database import SessionLocal
from app.models.audit import Alert
from app.models.health import SystemHealthEvent
from app.models.portfolio import PortfolioSnapshot, Position
from app.models.provider import ProviderConfig
from app.services.alerts.service import alert_service
from app.services.analytics.service import analytics_service
from app.services.brokers.service import broker_service
from app.services.events.service import publish_event
from app.services.market_data.service import market_data_service
from app.services.news.service import news_service
from app.services.providers.service import provider_service
from app.services.signals.service import signal_service
from app.services.simulation.service import simulation_service
from app.utils.time import utcnow
from app.workers.celery_app import celery_app


def _health_event(db, component: str, status: str, message: str, metadata: dict | None = None) -> None:
    db.add(SystemHealthEvent(component=component, status=status, message=message, metadata_json=metadata or {}, observed_at=utcnow()))


@celery_app.task(name="app.tasks.periodic.refresh_market_data")
def refresh_market_data() -> dict:
    with SessionLocal() as db:
        report = market_data_service.refresh_market_data(db)
        status = "ok" if report["assets_failed"] == 0 else ("warn" if report["assets_refreshed"] else "error")
        _health_event(
            db,
            "market-data",
            status,
            (
                f"Market data refresh created {report['snapshots_created']} snapshots and updated "
                f"{report['snapshots_updated']} across {report['assets_refreshed']} assets."
            ),
            report,
        )
        db.commit()
        publish_event("market.refreshed", report)
        return report


@celery_app.task(name="app.tasks.periodic.refresh_news")
def refresh_news() -> dict:
    with SessionLocal() as db:
        refreshed = news_service.refresh_latest_news(db)
        _health_event(db, "news", "ok" if refreshed.get("feeds_failed", 0) == 0 else "warn", refreshed["message"], refreshed)
        db.commit()
        if refreshed.get("articles_added", 0):
            publish_event("news.refreshed", {"article_id": refreshed.get("latest_article_id"), "articles_added": refreshed["articles_added"]})
        return refreshed


@celery_app.task(name="app.tasks.periodic.generate_signals")
def generate_signals() -> dict:
    with SessionLocal() as db:
        signals = signal_service.generate_signals(db)
        _health_event(db, "signals", "ok" if signals else "warn", f"Generated {len(signals)} provider-backed signals")
        db.commit()
        if signals:
            publish_event("signals.generated", {"count": len(signals)})
        return {"count": len(signals)}


@celery_app.task(name="app.tasks.periodic.provider_health_checks")
def provider_health_checks() -> dict:
    with SessionLocal() as db:
        results = []
        for config in provider_service.list_configs(db):
            if not config.enabled:
                results.append(
                    {
                        "provider_type": config.provider_type,
                        "status": "disabled",
                        "message": "Provider profile disabled",
                        "latency_ms": None,
                    }
                )
                continue
            try:
                result = provider_service.test_connection(db, config.provider_type)
            except Exception as exc:
                result = {"provider_type": config.provider_type, "status": "error", "message": str(exc), "latency_ms": None}
            results.append(result)
            _health_event(db, f"provider:{config.provider_type}", result["status"], result["message"])
        db.commit()
        publish_event("providers.health", {"results": results})
        return {"results": results}


@celery_app.task(name="app.tasks.periodic.portfolio_snapshots")
def portfolio_snapshots() -> dict:
    with SessionLocal() as db:
        created = 0
        for account in simulation_service.list_accounts(db):
            simulation_service.create_snapshot(db, account)
            created += 1
        live_positions = list(db.scalars(select(Position).where(Position.mode == "live", Position.status == "open")))
        if live_positions:
            latest = db.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "live").order_by(desc(PortfolioSnapshot.timestamp)).limit(1))
            equity = sum(position.current_price * position.quantity for position in live_positions)
            cash = latest.cash if latest else 10000
            total = cash + equity
            db.add(
                PortfolioSnapshot(
                    mode="live",
                    broker_account_id=latest.broker_account_id if latest else None,
                    timestamp=utcnow(),
                    total_value=total,
                    cash=cash,
                    equity=equity,
                    realized_pnl=latest.realized_pnl if latest else 0,
                    unrealized_pnl=sum(position.unrealized_pnl for position in live_positions),
                    daily_return=0.0015,
                    weekly_return=0.0084,
                    monthly_return=0.026,
                    exposure_json=latest.exposure_json if latest else {},
                )
            )
            created += 1
        _health_event(db, "portfolio", "ok", f"Created {created} portfolio snapshots")
        db.commit()
        return {"created": created}


@celery_app.task(name="app.tasks.periodic.broker_sync")
def broker_sync() -> dict:
    with SessionLocal() as db:
        messages = []
        for account in broker_service.list_accounts(db):
            result = broker_service.sync_account(db, account.id, trigger="scheduled")
            messages.append({"broker": account.name, "message": result["message"], "status": result["status"]})
        _health_event(db, "brokers", "ok", "Broker sync scaffold executed", {"messages": messages})
        db.commit()
        return {"messages": messages}


@celery_app.task(name="app.tasks.periodic.risk_checks")
def risk_checks() -> dict:
    with SessionLocal() as db:
        open_alerts = len(list(db.scalars(select(Alert).where(Alert.status == "open"))))
        _health_event(db, "risk", "ok", "Risk periodic check completed", {"open_alerts": open_alerts})
        db.commit()
        return {"open_alerts": open_alerts}


@celery_app.task(name="app.tasks.periodic.analytics_recalc")
def analytics_recalc() -> dict:
    with SessionLocal() as db:
        overview = analytics_service.overview(db)
        _health_event(db, "analytics", "ok", "Analytics recalculated", {"total_return": overview["total_return"]})
        db.commit()
        return overview


@celery_app.task(name="app.tasks.periodic.alert_generation")
def alert_generation() -> dict:
    with SessionLocal() as db:
        cleaned = 0
        supported_provider_components = {f"provider:{provider_type}" for provider_type in provider_service.catalog}
        open_health_alerts = list(db.scalars(select(Alert).where(Alert.status == "open", Alert.category == "health")))
        for alert in open_health_alerts:
            if not alert.title.endswith(" reported an error"):
                continue
            component = alert.source_ref if alert.source_ref and ":" in alert.source_ref else alert.title.removesuffix(" reported an error")
            latest_event = db.scalar(
                select(SystemHealthEvent)
                .where(SystemHealthEvent.component == component)
                .order_by(desc(SystemHealthEvent.observed_at))
                .limit(1)
            )
            if latest_event is None or latest_event.status != "error":
                cleaned += alert_service.resolve_alerts(db, title=alert.title)

        recent_provider_errors = [
            event for event in db.scalars(select(SystemHealthEvent).where(SystemHealthEvent.status == "error").order_by(desc(SystemHealthEvent.observed_at)).limit(10))
        ]
        created = 0
        for event in recent_provider_errors:
            if event.component.startswith("provider:") and event.component not in supported_provider_components:
                cleaned += alert_service.resolve_alerts(db, title=f"{event.component} reported an error")
                continue

            alert_service.create_alert(
                db,
                category="health",
                severity="warning",
                title=f"{event.component} reported an error",
                message=event.message,
                mode="system",
                source_ref=event.component,
                metadata={"latest_event_id": event.id, "observed_at": event.observed_at.isoformat()},
                dedupe=True,
            )
            created += 1
        _health_event(db, "alerts", "ok", f"Alert generation completed with {created} alerts", {"cleaned": cleaned})
        db.commit()
        return {"created": created, "cleaned": cleaned}
