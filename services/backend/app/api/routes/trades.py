from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.signal import SignalTraceRead
from app.services.portfolio.service import portfolio_service
from app.services.signals.service import signal_service

router = APIRouter()


@router.get("/")
def list_trades(
    mode: str | None = Query(default=None),
    simulation_account_id: str | None = Query(default=None),
    broker_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return portfolio_service.list_trades(
        db,
        mode=mode,
        simulation_account_id=simulation_account_id,
        broker_account_id=broker_account_id,
    )


@router.get("/{trade_id}/trace", response_model=SignalTraceRead)
def trade_trace(trade_id: str, db: Session = Depends(get_db)) -> SignalTraceRead:
    try:
        return SignalTraceRead.model_validate(signal_service.get_trade_trace(db, trade_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
