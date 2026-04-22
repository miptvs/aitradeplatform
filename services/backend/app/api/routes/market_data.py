from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import MarketSnapshotRead
from app.services.events.service import publish_event
from app.services.market_data.service import market_data_service

router = APIRouter()


@router.get("/latest", response_model=list[MarketSnapshotRead])
def latest(db: Session = Depends(get_db)) -> list[MarketSnapshotRead]:
    return [MarketSnapshotRead.model_validate(snapshot) for snapshot in market_data_service.list_latest_snapshots(db)]


@router.get("/{asset_id}/history", response_model=list[MarketSnapshotRead])
def history(asset_id: str, limit: int = Query(default=60, le=500), db: Session = Depends(get_db)) -> list[MarketSnapshotRead]:
    return [MarketSnapshotRead.model_validate(snapshot) for snapshot in market_data_service.get_history(db, asset_id, limit=limit)]


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)) -> dict:
    report = market_data_service.refresh_market_data(db)
    db.commit()
    if report["snapshots_created"] or report["snapshots_updated"]:
        publish_event("market.refreshed", report)
    return report
