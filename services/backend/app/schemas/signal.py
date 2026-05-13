from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import AuditLogRead, ORMModel
from app.schemas.market import ExtractedEventRead, NewsArticleRead
from app.schemas.portfolio import OrderRead, PositionRead, TradeRead


class SignalRead(ORMModel):
    id: str
    asset_id: str
    symbol: str
    asset_name: str
    strategy_id: str | None = None
    strategy_slug: str | None = None
    strategy_name: str | None = None
    action: str
    confidence: float
    status: str
    occurred_at: datetime
    indicators_json: dict
    related_news_ids: list[str]
    related_event_ids: list[str]
    ai_rationale: str | None = None
    suggested_entry: float | None = None
    suggested_stop_loss: float | None = None
    suggested_take_profit: float | None = None
    estimated_risk_reward: float | None = None
    suggested_position_size_type: str | None = None
    suggested_position_size_value: float | None = None
    fallback_quantity: float | None = None
    provider_type: str | None = None
    model_name: str | None = None
    mode: str
    source_kind: str
    metadata_json: dict
    signal_flavor: str = "technical-only"
    fresh_news_used: bool = False
    lane_statuses: dict[str, str] = Field(default_factory=dict)


class SignalEvaluationRead(ORMModel):
    id: str
    signal_id: str
    approved: bool
    evaluator: str
    reason: str | None = None
    risk_score: float | None = None
    expected_return: float | None = None
    realized_return: float | None = None
    outcome: str | None = None
    created_at: datetime


class SignalDetailRead(SignalRead):
    related_news: list[NewsArticleRead] = Field(default_factory=list)
    related_events: list[ExtractedEventRead] = Field(default_factory=list)


class SignalTraceRead(BaseModel):
    signal: SignalDetailRead | None = None
    entrypoint: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    risk_checks: list[dict] = Field(default_factory=list)
    stop_history: list[dict] = Field(default_factory=list)
    evaluations: list[SignalEvaluationRead] = Field(default_factory=list)
    orders: list[OrderRead] = Field(default_factory=list)
    positions: list[PositionRead] = Field(default_factory=list)
    trades: list[TradeRead] = Field(default_factory=list)
    audit_logs: list[AuditLogRead] = Field(default_factory=list)


class SignalGenerationResponse(BaseModel):
    provider_type: str
    status: str = "success"
    run_type: str = "manual"
    observed_at: str | None = None
    created_signal_ids: list[str] = Field(default_factory=list)
    created_count: int = 0
    message: str
    detail: str | None = None
    market_report: dict = Field(default_factory=dict)
    news_report: dict = Field(default_factory=dict)
