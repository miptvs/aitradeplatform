from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class BrokerAccountCreate(BaseModel):
    name: str
    broker_type: str
    mode: str = "live"
    enabled: bool = False
    live_trading_enabled: bool = False
    base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    settings_json: dict[str, Any] = Field(default_factory=dict)


class BrokerAccountRead(ORMModel):
    id: str
    name: str
    broker_type: str
    mode: str
    enabled: bool
    live_trading_enabled: bool
    status: str
    base_url: str | None = None
    settings_json: dict[str, Any]
    has_secret: bool
    supports_execution: bool | None = None
    supports_sync: bool | None = None
    capability_message: str | None = None
    last_sync_status: str | None = None
    last_sync_started_at: str | None = None
    last_sync_completed_at: str | None = None
    last_sync_message: str | None = None
    cash_balance: float | None = None
    available_cash: float | None = None
    invested_value: float | None = None
    total_value: float | None = None
    currency: str | None = None
    short_supported: bool | None = None


class BrokerAdapterStatus(BaseModel):
    broker_type: str
    supports_execution: bool
    supports_sync: bool
    message: str


class BrokerSyncResult(BaseModel):
    broker_account_id: str
    broker_type: str
    status: str
    message: str
    account_message: str
    positions_message: str
    orders_message: str
    pies_message: str | None = None
    positions_count: int = 0
    pies_count: int = 0
    supports_execution: bool
    supports_sync: bool
    started_at: str | None = None
    completed_at: str | None = None
