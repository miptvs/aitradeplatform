from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.portfolio.service import portfolio_service

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
