from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SignalRead(ORMModel):
    id: str
    asset_id: str
    strategy_id: str | None = None
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
    provider_type: str | None = None
    model_name: str | None = None
    mode: str
    source_kind: str
    metadata_json: dict


class SignalGenerationResponse(BaseModel):
    provider_type: str
    status: str = "success"
    created_signal_ids: list[str] = Field(default_factory=list)
    created_count: int = 0
    message: str
    detail: str | None = None
    market_report: dict = Field(default_factory=dict)
    news_report: dict = Field(default_factory=dict)
