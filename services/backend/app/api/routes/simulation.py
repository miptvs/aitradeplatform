from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.portfolio import OrderCreate, OrderRead, PositionRead, PositionUpdate
from app.schemas.simulation import SimulationAccountCreate, SimulationAccountRead, SimulationAccountUpdate, SimulationOrderCreate, SimulationSummary
from app.schemas.trading import AutomationDecisionRead, AutomationRunResult, RecommendationRejectRequest, TradingAccountSummary, TradingAutomationProfileRead, TradingAutomationProfileUpsert, TradingWorkspaceRead
from app.services.portfolio.service import portfolio_service
from app.services.simulation.service import simulation_service
from app.services.trading.service import trading_workspace_service

router = APIRouter()


@router.get("/accounts", response_model=list[SimulationAccountRead])
def accounts(db: Session = Depends(get_db)) -> list[SimulationAccountRead]:
    return [SimulationAccountRead.model_validate(account) for account in simulation_service.list_accounts(db)]


@router.post("/accounts", response_model=SimulationAccountRead)
def create_account(payload: SimulationAccountCreate, db: Session = Depends(get_db)) -> SimulationAccountRead:
    account = simulation_service.create_account(db, payload)
    db.commit()
    db.refresh(account)
    return SimulationAccountRead.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=SimulationAccountRead)
def update_account(account_id: str, payload: SimulationAccountUpdate, db: Session = Depends(get_db)) -> SimulationAccountRead:
    try:
        account = simulation_service.update_account(db, account_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(account)
    return SimulationAccountRead.model_validate(account)


@router.post("/accounts/{account_id}/reset", response_model=SimulationAccountRead)
def reset_account(account_id: str, db: Session = Depends(get_db)) -> SimulationAccountRead:
    try:
        account = simulation_service.reset_account(db, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(account)
    return SimulationAccountRead.model_validate(account)


@router.get("/accounts/{account_id}/summary", response_model=SimulationSummary)
def account_summary(account_id: str, db: Session = Depends(get_db)) -> SimulationSummary:
    try:
        summary = simulation_service.summary(db, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SimulationSummary.model_validate(summary)


@router.get("/workspace", response_model=TradingWorkspaceRead)
def workspace(account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> TradingWorkspaceRead:
    return TradingWorkspaceRead.model_validate(trading_workspace_service.get_workspace(db, "simulation", simulation_account_id=account_id))


@router.get("/account", response_model=TradingAccountSummary)
def account_overview(account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> TradingAccountSummary:
    return TradingAccountSummary.model_validate(
        trading_workspace_service.get_workspace(db, "simulation", simulation_account_id=account_id)["account"]
    )


@router.get("/positions")
def positions(account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    return portfolio_service.list_positions(db, mode="simulation", simulation_account_id=account_id)


@router.get("/orders")
def orders(account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    return portfolio_service.list_orders(db, mode="simulation", simulation_account_id=account_id)


@router.get("/trades")
def trades(account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    return portfolio_service.list_trades(db, mode="simulation", simulation_account_id=account_id)


@router.post("/orders", response_model=OrderRead)
def create_simulation_order(payload: SimulationOrderCreate, db: Session = Depends(get_db)) -> OrderRead:
    try:
        order = portfolio_service.create_order(
            db,
            OrderCreate(
                asset_id=payload.asset_id,
                mode="simulation",
                side=payload.side,
                quantity=payload.quantity,
                amount=payload.amount,
                requested_price=payload.requested_price,
                signal_id=payload.signal_id,
                strategy_name=payload.strategy_name,
                provider_type=payload.provider_type,
                model_name=payload.model_name,
                manual=payload.manual,
                entry_reason=payload.reason,
                simulation_account_id=payload.simulation_account_id,
                stop_loss=payload.stop_loss,
                take_profit=payload.take_profit,
                trailing_stop=payload.trailing_stop,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(portfolio_service._order_view(db, order))


@router.patch("/positions/{position_id}/stops", response_model=PositionRead)
def update_simulation_stops(position_id: str, payload: PositionUpdate, db: Session = Depends(get_db)) -> PositionRead:
    try:
        position = portfolio_service.update_position(db, position_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(position)
    return PositionRead.model_validate(position)


@router.post("/positions/{position_id}/close", response_model=PositionRead)
def close_simulation_position(
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
    return TradingAutomationProfileRead.model_validate(
        trading_workspace_service.serialize_profile(trading_workspace_service.get_or_create_profile(db, "simulation"))
    )


@router.put("/automation", response_model=TradingAutomationProfileRead)
def save_automation(payload: TradingAutomationProfileUpsert, db: Session = Depends(get_db)) -> TradingAutomationProfileRead:
    profile = trading_workspace_service.upsert_profile(db, "simulation", payload)
    db.commit()
    db.refresh(profile)
    return TradingAutomationProfileRead.model_validate(trading_workspace_service.serialize_profile(profile))


@router.post("/automation/run", response_model=AutomationRunResult)
def run_automation(account_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> AutomationRunResult:
    result = trading_workspace_service.run_automation(db, "simulation", simulation_account_id=account_id)
    db.commit()
    return AutomationRunResult.model_validate(result)


@router.post("/recommendations/{signal_id}/reject", response_model=AutomationDecisionRead)
def reject_recommendation(signal_id: str, payload: RecommendationRejectRequest | None = None, db: Session = Depends(get_db)) -> AutomationDecisionRead:
    try:
        result = trading_workspace_service.reject_recommendation(db, "simulation", signal_id, payload.reason if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return AutomationDecisionRead.model_validate(result)
