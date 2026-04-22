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
