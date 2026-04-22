from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.portfolio import OrderCreate, OrderRead
from app.services.portfolio.service import portfolio_service

router = APIRouter()


@router.get("/")
def list_orders(
    mode: str | None = Query(default=None),
    simulation_account_id: str | None = Query(default=None),
    broker_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return portfolio_service.list_orders(
        db,
        mode=mode,
        simulation_account_id=simulation_account_id,
        broker_account_id=broker_account_id,
    )


@router.post("/", response_model=OrderRead)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderRead:
    try:
        order = portfolio_service.create_order(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(portfolio_service._order_view(db, order))
