from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ORMModel


class SimulationAccountCreate(BaseModel):
    name: str = "Primary Simulation"
    provider_type: str | None = None
    model_name: str | None = None
    starting_cash: float = 1000
    fees_bps: float = 5
    slippage_bps: float = 2
    latency_ms: int = 50
    min_cash_reserve_percent: float | None = None
    short_enabled: bool = False
    short_borrow_fee_bps: float = 0
    short_margin_requirement: float = 1.5
    partial_fill_ratio: float = 1.0
    decimal_precision: int = 6
    enforce_market_hours: bool = False


class SimulationAccountUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    starting_cash: float | None = None
    fees_bps: float | None = None
    slippage_bps: float | None = None
    latency_ms: int | None = None
    min_cash_reserve_percent: float | None = None
    short_enabled: bool | None = None
    short_borrow_fee_bps: float | None = None
    short_margin_requirement: float | None = None
    partial_fill_ratio: float | None = None
    decimal_precision: int | None = None
    enforce_market_hours: bool | None = None
    is_active: bool | None = None


class SimulationAccountRead(ORMModel):
    id: str
    name: str
    provider_type: str | None = None
    model_name: str | None = None
    starting_cash: float
    cash_balance: float
    fees_bps: float
    slippage_bps: float
    latency_ms: int
    min_cash_reserve_percent: float | None = None
    short_enabled: bool
    short_borrow_fee_bps: float
    short_margin_requirement: float
    partial_fill_ratio: float
    decimal_precision: int
    enforce_market_hours: bool
    is_active: bool
    reset_count: int


class SimulationOrderCreate(BaseModel):
    simulation_account_id: str
    asset_id: str
    side: str
    sizing_mode: Literal["percentage", "amount", "quantity"] | None = None
    sizing_value: float | None = None
    quantity: float | None = None
    amount: float | None = None
    allow_fractional_resize: bool = True
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
    provider_type: str | None = None
    model_name: str | None = None
    executed_at: datetime


class SimulationSummary(BaseModel):
    account: SimulationAccountRead
    equity_curve: list[dict]
    open_positions: int
    total_trades: int
    hypothetical_pnl: float
    latest_orders: list[dict]
