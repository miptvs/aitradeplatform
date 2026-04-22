from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.broker import BrokerSyncResult
from app.schemas.portfolio import OrderCreate, OrderRead, PositionRead, PositionUpdate
from app.schemas.trading import AutomationDecisionRead, AutomationRunResult, RecommendationRejectRequest, TradingAccountSummary, TradingAutomationProfileRead, TradingAutomationProfileUpsert, TradingWorkspaceRead
from app.services.brokers.service import broker_service
from app.services.portfolio.service import portfolio_service
from app.services.trading.service import trading_workspace_service

router = APIRouter()


@router.get("/workspace", response_model=TradingWorkspaceRead)
def workspace(db: Session = Depends(get_db)) -> TradingWorkspaceRead:
    return TradingWorkspaceRead.model_validate(trading_workspace_service.get_workspace(db, "live"))


@router.get("/account", response_model=TradingAccountSummary)
def account(db: Session = Depends(get_db)) -> TradingAccountSummary:
    return TradingAccountSummary.model_validate(trading_workspace_service.get_workspace(db, "live")["account"])


@router.get("/positions")
def positions(db: Session = Depends(get_db)) -> list[dict]:
    return portfolio_service.list_positions(db, mode="live")


@router.get("/orders")
def orders(db: Session = Depends(get_db)) -> list[dict]:
    return portfolio_service.list_orders(db, mode="live")


@router.get("/trades")
def trades(db: Session = Depends(get_db)) -> list[dict]:
    return portfolio_service.list_trades(db, mode="live")


@router.post("/orders", response_model=OrderRead)
def create_live_order(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderRead:
    try:
        order = portfolio_service.create_order(db, payload.model_copy(update={"mode": "live"}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(portfolio_service._order_view(db, order))


@router.patch("/positions/{position_id}/stops", response_model=PositionRead)
def update_live_stops(position_id: str, payload: PositionUpdate, db: Session = Depends(get_db)) -> PositionRead:
    try:
        position = portfolio_service.update_position(db, position_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(position)
    return PositionRead.model_validate(position)


@router.post("/positions/{position_id}/close", response_model=PositionRead)
def close_live_position(
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


@router.get("/automation", response_model=TradingAutomationProfileRead)
def get_automation(db: Session = Depends(get_db)) -> TradingAutomationProfileRead:
    return TradingAutomationProfileRead.model_validate(trading_workspace_service.serialize_profile(trading_workspace_service.get_or_create_profile(db, "live")))


@router.put("/automation", response_model=TradingAutomationProfileRead)
def save_automation(payload: TradingAutomationProfileUpsert, db: Session = Depends(get_db)) -> TradingAutomationProfileRead:
    profile = trading_workspace_service.upsert_profile(db, "live", payload)
    db.commit()
    db.refresh(profile)
    return TradingAutomationProfileRead.model_validate(trading_workspace_service.serialize_profile(profile))


@router.post("/automation/run", response_model=AutomationRunResult)
def run_automation(db: Session = Depends(get_db)) -> AutomationRunResult:
    result = trading_workspace_service.run_automation(db, "live")
    db.commit()
    return AutomationRunResult.model_validate(result)


@router.post("/recommendations/{signal_id}/reject", response_model=AutomationDecisionRead)
def reject_recommendation(signal_id: str, payload: RecommendationRejectRequest | None = None, db: Session = Depends(get_db)) -> AutomationDecisionRead:
    try:
        result = trading_workspace_service.reject_recommendation(db, "live", signal_id, payload.reason if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return AutomationDecisionRead.model_validate(result)


@router.post("/broker-sync", response_model=BrokerSyncResult)
def sync_broker(broker_account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> BrokerSyncResult:
    account_id = broker_account_id or trading_workspace_service.get_workspace(db, "live")["controls"].get("active_broker_account_id")
    if not account_id:
        raise HTTPException(status_code=400, detail="No active live broker account is configured.")
    try:
        result = broker_service.sync_account(db, account_id, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return BrokerSyncResult.model_validate(result)
