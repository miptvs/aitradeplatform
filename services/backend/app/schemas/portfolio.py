from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class PositionCreate(BaseModel):
    asset_id: str | None = None
    asset_symbol: str | None = None
    asset_name: str | None = None
    asset_type: str = "stock"
    currency: str = "USD"
    exchange: str | None = None
    mode: str = "simulation"
    quantity: float
    avg_entry_price: float
    current_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    manual: bool = True
    manual_override: bool = False
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    simulation_account_id: str | None = None
    broker_account_id: str | None = None

    @model_validator(mode="after")
    def validate_asset_reference(self) -> "PositionCreate":
        if not self.asset_id and not self.asset_symbol:
            raise ValueError("Either asset_id or asset_symbol is required.")
        return self


class PositionUpdate(BaseModel):
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    notes: str | None = None
    tags: list[str] | None = None
    manual_override: bool | None = None


class PositionRead(ORMModel):
    id: str
    asset_id: str
    symbol: str | None = None
    asset_name: str | None = None
    asset_currency: str | None = None
    signal_id: str | None = None
    broker_account_id: str | None = None
    simulation_account_id: str | None = None
    mode: str
    manual: bool
    manual_override: bool
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    quantity: float
    avg_entry_price: float
    current_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    unrealized_pnl: float
    realized_pnl: float
    notes: str | None = None
    tags: list[str]
    status: str
    opened_at: datetime
    closed_at: datetime | None = None


class OrderCreate(BaseModel):
    asset_id: str
    mode: str = "simulation"
    side: str
    sizing_mode: Literal["percentage", "amount", "quantity"] | None = None
    sizing_value: float | None = None
    quantity: float | None = None
    amount: float | None = None
    allow_fractional_resize: bool = True
    order_type: str = "market"
    requested_price: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    signal_id: str | None = None
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    manual: bool = True
    entry_reason: str | None = None
    exit_reason: str | None = None
    broker_account_id: str | None = None
    simulation_account_id: str | None = None

    @model_validator(mode="after")
    def validate_sizing(self) -> "OrderCreate":
        if self.sizing_mode == "percentage" and self.sizing_value is None:
            raise ValueError("Percentage sizing requires sizing_value.")
        if self.sizing_mode == "amount" and self.sizing_value is None and self.amount is None:
            raise ValueError("Amount sizing requires sizing_value or amount.")
        if self.sizing_mode == "quantity" and self.sizing_value is None and self.quantity is None:
            raise ValueError("Quantity sizing requires sizing_value or quantity.")
        if self.sizing_mode is None and self.quantity is None and self.amount is None and self.sizing_value is None:
            raise ValueError("Either percentage, amount, or quantity sizing is required.")
        return self


class OrderRead(ORMModel):
    id: str
    asset_id: str
    symbol: str | None = None
    asset_name: str | None = None
    broker_account_id: str | None = None
    signal_id: str | None = None
    position_id: str | None = None
    mode: str
    broker_type: str | None = None
    manual: bool
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    side: str
    order_type: str
    quantity: float
    sizing_mode: str | None = None
    sizing_value: float | None = None
    order_notional: float | None = None
    portfolio_percent: float | None = None
    rounding_warning: str | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    requested_price: float | None = None
    filled_price: float | None = None
    fees: float
    status: str
    entry_reason: str | None = None
    exit_reason: str | None = None
    rejection_reason: str | None = None
    audit_context: dict
    submitted_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime


class TradeRead(ORMModel):
    id: str
    asset_id: str
    symbol: str | None = None
    asset_name: str | None = None
    order_id: str | None = None
    position_id: str | None = None
    signal_id: str | None = None
    mode: str
    manual: bool = True
    side: str
    quantity: float
    price: float
    fees: float
    realized_pnl: float
    entry_reason: str | None = None
    exit_reason: str | None = None
    strategy_name: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    executed_at: datetime


class PortfolioSnapshotRead(ORMModel):
    id: str
    mode: str
    broker_account_id: str | None = None
    simulation_account_id: str | None = None
    timestamp: datetime
    total_value: float
    cash: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    daily_return: float
    weekly_return: float
    monthly_return: float
    exposure_json: dict


class PortfolioSummary(BaseModel):
    total_portfolio_value: float
    cash_available: float
    realized_pnl: float
    unrealized_pnl: float
    daily_return: float
    weekly_return: float
    monthly_return: float
    win_rate: float
    open_positions_count: int
    closed_trades_count: int
    best_performer: dict
    worst_performer: dict
    risk_exposure_summary: dict
    broker_connection_status: dict
    provider_status: dict
    automation_status: dict
