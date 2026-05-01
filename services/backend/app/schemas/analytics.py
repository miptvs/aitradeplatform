from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    total_return: float
    realized_return: float
    unrealized_return: float
    annualized_return: float
    win_rate: float
    average_win: float
    average_loss: float
    payoff_ratio: float
    profit_factor: float
    max_drawdown: float
    sharpe: float
    sortino: float
    performance_by_symbol: list[dict]
    performance_by_strategy: list[dict]
    performance_by_provider: list[dict]
    confidence_correlation: float


class EquityCurvePoint(BaseModel):
    timestamp: str
    value: float


class SimulationVsLiveComparison(BaseModel):
    live_return: float
    simulation_return: float
    delta_return: float


class ModelMetricRead(BaseModel):
    scope: str
    replay_run_id: str | None = None
    simulation_account_id: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    cash: float
    reserved_cash: float
    available_cash: float
    portfolio_value: float
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    average_holding_time_minutes: float
    turnover: float
    trade_count: int
    rejected_trade_count: int
    invalid_signal_count: int
    latency_ms: int | None = None
    model_cost: float | None = None
    useful_signal_rate: float
