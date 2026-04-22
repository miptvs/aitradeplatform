from fastapi import APIRouter

from app.api.routes import (
    alerts,
    analytics,
    assets,
    audit,
    auth,
    brokers,
    events,
    health,
    live,
    market_data,
    mcp,
    news,
    orders,
    portfolio,
    positions,
    providers,
    risk_rules,
    settings,
    signals,
    simulation,
    strategies,
    stream,
    trades,
    watchlists,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(live.router, prefix="/live", tags=["live"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(brokers.router, prefix="/brokers", tags=["brokers"])
api_router.include_router(watchlists.router, prefix="/watchlists", tags=["watchlists"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(market_data.router, prefix="/market-data", tags=["market-data"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(risk_rules.router, prefix="/risk-rules", tags=["risk-rules"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
