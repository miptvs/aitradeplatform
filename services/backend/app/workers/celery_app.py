from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_trader_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.periodic"],
)

celery_app.conf.update(
    timezone="UTC",
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_time_limit=180,
    task_soft_time_limit=150,
    task_annotations={
        "app.tasks.periodic.generate_signals": {"time_limit": 180, "soft_time_limit": 150},
        "app.tasks.periodic.refresh_market_data": {"time_limit": 90, "soft_time_limit": 75},
        "app.tasks.periodic.refresh_news": {"time_limit": 90, "soft_time_limit": 75},
        "app.tasks.periodic.run_scheduled_simulation_automation": {"time_limit": 45, "soft_time_limit": 30},
        "app.tasks.periodic.portfolio_snapshots": {"time_limit": 60, "soft_time_limit": 45},
        "app.tasks.periodic.provider_health_checks": {"time_limit": 90, "soft_time_limit": 75},
    },
    beat_schedule={
        "market-refresh": {
            "task": "app.tasks.periodic.refresh_market_data",
            "schedule": settings.market_refresh_seconds,
            "options": {"expires": settings.market_refresh_seconds},
        },
        "news-refresh": {
            "task": "app.tasks.periodic.refresh_news",
            "schedule": settings.news_refresh_seconds,
            "options": {"expires": settings.news_refresh_seconds},
        },
        "signal-generation": {
            "task": "app.tasks.periodic.generate_signals",
            "schedule": settings.signal_refresh_seconds,
            "options": {"expires": settings.signal_refresh_seconds},
        },
        "simulation-automation": {
            "task": "app.tasks.periodic.run_scheduled_simulation_automation",
            "schedule": settings.automation_scan_seconds,
            "options": {"expires": settings.automation_scan_seconds},
        },
        "provider-health": {
            "task": "app.tasks.periodic.provider_health_checks",
            "schedule": settings.provider_health_seconds,
            "options": {"expires": settings.provider_health_seconds},
        },
        "portfolio-snapshots": {
            "task": "app.tasks.periodic.portfolio_snapshots",
            "schedule": settings.portfolio_snapshot_seconds,
            "options": {"expires": settings.portfolio_snapshot_seconds},
        },
        "broker-sync": {"task": "app.tasks.periodic.broker_sync", "schedule": 900, "options": {"expires": 900}},
        "risk-checks": {"task": "app.tasks.periodic.risk_checks", "schedule": 300, "options": {"expires": 300}},
        "analytics-recalc": {"task": "app.tasks.periodic.analytics_recalc", "schedule": 600, "options": {"expires": 600}},
        "alert-generation": {"task": "app.tasks.periodic.alert_generation", "schedule": 600, "options": {"expires": 600}},
    },
)
