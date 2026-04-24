from pydantic import BaseModel

from app.schemas.provider import ProviderConfigRead, TaskMappingRead
from app.schemas.risk import RiskRuleRead

from app.schemas.trading import TradingAutomationProfileRead


class SettingsOverview(BaseModel):
    providers: list[ProviderConfigRead]
    task_mappings: list[TaskMappingRead]
    risk_rules: list[RiskRuleRead]
    live_automation: TradingAutomationProfileRead
    simulation_automation: TradingAutomationProfileRead
    live_trading_enabled: bool
