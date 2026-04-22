from pydantic import BaseModel

from app.schemas.provider import ProviderConfigRead, TaskMappingRead
from app.schemas.risk import RiskRuleRead


class SettingsOverview(BaseModel):
    providers: list[ProviderConfigRead]
    task_mappings: list[TaskMappingRead]
    risk_rules: list[RiskRuleRead]
    live_trading_enabled: bool
