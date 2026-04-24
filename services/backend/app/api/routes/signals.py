from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.signal import SignalDetailRead, SignalGenerationResponse, SignalRead, SignalTraceRead
from app.services.events.service import publish_event
from app.services.market_data.service import market_data_service
from app.services.news.service import news_service
from app.services.providers.service import provider_service
from app.services.signals.service import signal_service

router = APIRouter()


@router.get("/", response_model=list[SignalRead])
def list_signals(provider_type: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[SignalRead]:
    return [SignalRead.model_validate(item) for item in signal_service.list_signals(db, provider_type=provider_type)]


@router.get("/{signal_id}", response_model=SignalDetailRead)
def get_signal(signal_id: str, db: Session = Depends(get_db)) -> SignalDetailRead:
    try:
        return SignalDetailRead.model_validate(signal_service.get_signal(db, signal_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{signal_id}/trace", response_model=SignalTraceRead)
def get_signal_trace(signal_id: str, db: Session = Depends(get_db)) -> SignalTraceRead:
    try:
        return SignalTraceRead.model_validate(signal_service.get_signal_trace(db, signal_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/refresh", response_model=SignalGenerationResponse)
def refresh_signals(
    provider_type: str = Query(...),
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> SignalGenerationResponse:
    market_report = {"snapshots_created": 0, "snapshots_updated": 0, "assets_refreshed": 0, "assets_failed": 0, "errors": []}
    news_report = {"articles_added": 0, "feeds_checked": 0, "feeds_failed": 0, "errors": []}
    refresh_notes: list[str] = []

    try:
        market_report = market_data_service.refresh_market_data(db)
    except Exception as exc:
        refresh_notes.append(f"Market data refresh failed: {exc}")
        market_report = {**market_report, "errors": [str(exc)]}

    try:
        news_report = news_service.refresh_latest_news(db, force_refresh=force_refresh)
    except Exception as exc:
        refresh_notes.append(f"News refresh failed: {exc}")
        news_report = {**news_report, "errors": [str(exc)]}

    try:
        signals = signal_service.generate_signals(db, provider_type=provider_type, force_refresh=force_refresh)
    except ValueError as exc:
        db.commit()
        return SignalGenerationResponse(
            provider_type=provider_type,
            status="blocked",
            created_signal_ids=[],
            created_count=0,
            message=_blocked_refresh_message(db, provider_type, str(exc), refresh_notes),
            detail=str(exc),
            market_report=market_report,
            news_report=news_report,
        )

    db.commit()
    for signal in signals[:5]:
        publish_event("signal.created", {"signal_id": signal.id, "asset_id": signal.asset_id, "action": signal.action})

    if signals:
        message = (
            f"Generated {len(signals)} real signals for {provider_type}. "
            f"Market data: +{market_report['snapshots_created']} new / {market_report['snapshots_updated']} updated. "
            f"News: +{news_report['articles_added']} RSS articles."
        )
        status = "success"
    else:
        notes_suffix = f" {' '.join(refresh_notes)}" if refresh_notes else ""
        message = (
            f"{'Manual refresh' if force_refresh else 'Refresh'} completed for {provider_type}, but no signals qualified yet. "
            f"Market data: +{market_report['snapshots_created']} new / {market_report['snapshots_updated']} updated. "
            f"News: +{news_report['articles_added']} RSS articles.{notes_suffix}"
        )
        status = "noop"

    return SignalGenerationResponse(
        provider_type=provider_type,
        status=status,
        created_signal_ids=[signal.id for signal in signals],
        created_count=len(signals),
        message=message,
        market_report=market_report,
        news_report=news_report,
    )


@router.post("/generate-demo", response_model=SignalGenerationResponse)
def generate_demo_signals_alias(provider_type: str = Query(...), db: Session = Depends(get_db)) -> SignalGenerationResponse:
    return refresh_signals(provider_type=provider_type, force_refresh=True, db=db)


def _blocked_refresh_message(db: Session, provider_type: str, detail: str, refresh_notes: list[str]) -> str:
    config = provider_service.get_config(db, provider_type)
    profile = provider_service.get_profile(provider_type)

    if config is None:
        message = f"Signal refresh could not start because {provider_type} is not configured."
    elif not config.enabled:
        message = f"Signal refresh is blocked because {profile.title} is disabled. Enable it in Settings first."
    elif profile.supports_api_key and not config.encrypted_api_key and "api key" in detail.lower():
        message = f"Signal refresh is blocked because {profile.title} has no saved API key yet."
    elif "No provider run succeeded" in detail:
        message = (
            f"Market data and news refreshed, but {profile.title} did not return a usable signal in time. "
            "Check provider connectivity, model speed, or switch to a faster profile."
        )
    else:
        message = f"Refresh completed, but signal generation for {profile.title} was blocked."

    if refresh_notes:
        message = f"{message} {' '.join(refresh_notes)}"
    return message
