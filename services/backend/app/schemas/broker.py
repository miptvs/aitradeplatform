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
    supports_execution: bool
    supports_sync: bool
    started_at: str | None = None
    completed_at: str | None = None
