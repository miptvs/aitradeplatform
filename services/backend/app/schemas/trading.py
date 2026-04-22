from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import AlertRead, ORMModel
from app.schemas.market import AssetRead, StrategyRead


class TradingAutomationProfileUpsert(BaseModel):
    enabled: bool = True
    automation_enabled: bool = False
    approval_mode: Literal["manual_only", "semi_automatic", "fully_automatic"] = "semi_automatic"
    allowed_strategy_slugs: list[str] = Field(default_factory=list)
    tradable_actions: list[str] = Field(default_factory=lambda: ["buy"])
    allowed_provider_types: list[str] = Field(default_factory=list)
    confidence_threshold: float = 0.58
    default_order_notional: float = 100.0
    stop_loss_pct: float | None = 0.03
    take_profit_pct: float | None = 0.06
    trailing_stop_pct: float | None = None
    max_orders_per_run: int = 1
    risk_profile: str = "balanced"
    notes: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class TradingAutomationProfileRead(ORMModel):
    id: str
    mode: str
    name: str
    enabled: bool
    automation_enabled: bool
    approval_mode: str
    allowed_strategy_slugs: list[str]
    tradable_actions: list[str]
    allowed_provider_types: list[str]
    confidence_threshold: float
    default_order_notional: float
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    max_orders_per_run: int
    risk_profile: str
    notes: str | None = None
    last_run_status: str | None = None
    last_run_message: str | None = None
    config_json: dict[str, Any]


class TradingAccountSummary(BaseModel):
    mode: str
    account_id: str | None = None
    account_label: str
    broker_type: str | None = None
    status: str
    base_currency: str
    total_value: float
    cash_available: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions_count: int
    active_orders_count: int
    total_trades_count: int
    safety_message: str
    live_execution_enabled: bool
    manual_position_supported: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradingWorkspaceRead(BaseModel):
    mode: str
    account: TradingAccountSummary
    automation: TradingAutomationProfileRead
    positions: list[dict]
    orders: list[dict]
    trades: list[dict]
    signals: list[dict]
    recommendations: list["TradingRecommendationRead"] = Field(default_factory=list)
    alerts: list[AlertRead]
    assets: list[AssetRead]
    strategies: list[StrategyRead]
    controls: dict[str, Any] = Field(default_factory=dict)


class AutomationDecisionRead(BaseModel):
    signal_id: str
    symbol: str
    action: str
    confidence: float
    strategy_slug: str | None = None
    provider_type: str | None = None
    outcome: str
    reason: str
    order_id: str | None = None


class TradingRecommendationRead(BaseModel):
    signal_id: str
    asset_id: str
    symbol: str
    asset_name: str
    action: str
    confidence: float
    strategy_slug: str | None = None
    provider_type: str | None = None
    model_name: str | None = None
    status: str
    mode: str
    occurred_at: Any
    queued_at: Any
    reason: str
    suggested_entry: float | None = None
    suggested_stop_loss: float | None = None
    suggested_take_profit: float | None = None
    estimated_risk_reward: float | None = None


class RecommendationRejectRequest(BaseModel):
    reason: str | None = None


class AutomationRunResult(BaseModel):
    mode: str
    status: str
    message: str
    processed_signals: int
    submitted_orders: int
    approved_recommendations: int
    rejected_signals: int
    decisions: list[AutomationDecisionRead] = Field(default_factory=list)
