from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.portfolio import PositionCreate, PositionRead, PositionUpdate
from app.services.portfolio.service import portfolio_service

router = APIRouter()


@router.get("/")
def list_positions(
    mode: str | None = Query(default=None),
    simulation_account_id: str | None = Query(default=None),
    broker_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return portfolio_service.list_positions(
        db,
        mode=mode,
        simulation_account_id=simulation_account_id,
        broker_account_id=broker_account_id,
    )


@router.post("/", response_model=PositionRead)
def create_position(payload: PositionCreate, db: Session = Depends(get_db)) -> PositionRead:
    try:
        position = portfolio_service.create_manual_position(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(position)
    return PositionRead.model_validate(position)


@router.patch("/{position_id}", response_model=PositionRead)
def update_position(position_id: str, payload: PositionUpdate, db: Session = Depends(get_db)) -> PositionRead:
    try:
        position = portfolio_service.update_position(db, position_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(position)
    return PositionRead.model_validate(position)


@router.post("/{position_id}/close", response_model=PositionRead)
def close_position(
    position_id: str,
    quantity: float | None = Query(default=None),
    close_percent: float | None = Query(default=None),
    exit_price: float | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PositionRead:
    try:
        position = portfolio_service.close_position(db, position_id, quantity=quantity, close_percent=close_percent, exit_price=exit_price)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(position)
    return PositionRead.model_validate(position)
