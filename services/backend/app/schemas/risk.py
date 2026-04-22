from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RiskRuleUpsert(BaseModel):
    name: str
    scope: str = "global"
    rule_type: str
    enabled: bool = True
    auto_close: bool = False
    description: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class RiskRuleRead(ORMModel):
    id: str
    name: str
    scope: str
    rule_type: str
    enabled: bool
    auto_close: bool
    description: str | None = None
    config_json: dict[str, Any]


class RiskCheck(BaseModel):
    rule: str
    passed: bool
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class RiskValidationRequest(BaseModel):
    asset_id: str
    mode: str
    side: str
    quantity: float
    requested_price: float
    stop_loss: float | None = None
    simulation_account_id: str | None = None
    broker_account_id: str | None = None
    strategy_name: str | None = None


class RiskValidationResponse(BaseModel):
    approved: bool
    checks: list[RiskCheck]
    rejection_reasons: list[str]
