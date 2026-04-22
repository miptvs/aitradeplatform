from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class SimulationAccountCreate(BaseModel):
    name: str = "Primary Simulation"
    starting_cash: float = 1000
    fees_bps: float = 5
    slippage_bps: float = 2
    latency_ms: int = 50


class SimulationAccountUpdate(BaseModel):
    name: str | None = None
    starting_cash: float | None = None
    fees_bps: float | None = None
    slippage_bps: float | None = None
    latency_ms: int | None = None
    is_active: bool | None = None


class SimulationAccountRead(ORMModel):
    id: str
    name: str
    starting_cash: float
    cash_balance: float
    fees_bps: float
    slippage_bps: float
    latency_ms: int
    is_active: bool
    reset_count: int


class SimulationOrderCreate(BaseModel):
    simulation_account_id: str
    asset_id: str
    side: str
    quantity: float | None = None
    amount: float | None = None
    requested_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    signal_id: str | None = None
    manual: bool = True
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    reason: str | None = None


class SimulationOrderRead(ORMModel):
    id: str
    simulation_account_id: str
    asset_id: str
    signal_id: str | None = None
    side: str
    quantity: float
    requested_price: float
    executed_price: float | None = None
    fees: float
    status: str
    reason: str | None = None
    rejection_reason: str | None = None
    manual: bool
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    executed_at: datetime | None = None


class SimulationTradeRead(ORMModel):
    id: str
    simulation_account_id: str
    simulation_order_id: str | None = None
    asset_id: str
    side: str
    quantity: float
    price: float
    fees: float
    realized_pnl: float
    rationale: str | None = None
    executed_at: datetime


class SimulationSummary(BaseModel):
    account: SimulationAccountRead
    equity_curve: list[dict]
    open_positions: int
    total_trades: int
    hypothetical_pnl: float
    latest_orders: list[dict]
