from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class ReplayRunCreate(BaseModel):
    name: str | None = None
    date_start: datetime
    date_end: datetime
    starting_cash: float = 10_000
    selected_models: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    fees_bps: float = 5
    slippage_bps: float = 2
    cash_reserve_percent: float = 0.2
    short_enabled: bool = False
    config_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @field_validator("cash_reserve_percent")
    @classmethod
    def clamp_reserve(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @field_validator("selected_models", "symbols")
    @classmethod
    def strip_empty_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value and value.strip()]


class ReplayModelResultRead(ORMModel):
    id: str
    replay_run_id: str
    provider_type: str
    model_name: str | None = None
    status: str
    cash: float
    portfolio_value: float
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    max_drawdown: float
    sharpe: float
    sortino: float
    win_rate: float
    profit_factor: float
    average_holding_time_minutes: float
    turnover: float
    trades: int
    rejected_trades: int
    invalid_signals: int
    useful_signal_rate: float
    latency_ms: int | None = None
    model_cost: float | None = None
    metrics_json: dict[str, Any]


class ReplayRunRead(ORMModel):
    id: str
    name: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    date_start: datetime
    date_end: datetime
    starting_cash: float
    fees_bps: float
    slippage_bps: float
    cash_reserve_percent: float
    short_enabled: bool
    selected_models: list[str]
    symbols: list[str]
    config_json: dict[str, Any]
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    results: list[ReplayModelResultRead] = Field(default_factory=list)
