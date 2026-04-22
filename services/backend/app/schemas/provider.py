from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProviderConfigUpsert(BaseModel):
    enabled: bool = False
    base_url: str
    default_model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 512
    context_window: int = 8192
    tool_calling_enabled: bool = False
    reasoning_mode: str | None = None
    task_defaults: dict[str, str] = Field(default_factory=dict)
    settings_json: dict[str, Any] = Field(default_factory=dict)
    api_key: str | None = None


class ProviderConfigRead(ORMModel):
    id: str
    provider_type: str
    adapter_type: str
    vendor_key: str
    vendor_name: str
    deployment_scope: str
    trading_mode: str
    mode_label: str
    name: str
    description: str
    enabled: bool
    base_url: str
    default_model: str | None = None
    temperature: float
    max_tokens: int
    context_window: int
    tool_calling_enabled: bool
    reasoning_mode: str | None = None
    reasoning_modes: list[str] = Field(default_factory=list)
    task_defaults: dict[str, Any]
    settings_json: dict[str, Any]
    suggested_models: list[str] = Field(default_factory=list)
    supports_api_key: bool = True
    has_secret: bool
    last_health_status: str | None = None
    last_health_message: str | None = None
    last_checked_at: datetime | None = None


class ProviderHealthRead(BaseModel):
    provider_type: str
    status: str
    message: str
    latency_ms: int | None = None


class ProviderModelsRead(BaseModel):
    provider_type: str
    models: list[str]


class TaskMappingUpsert(BaseModel):
    task_name: str
    provider_type: str
    model_name: str
    fallback_chain: list[dict[str, Any]] = Field(default_factory=list)
    timeout_seconds: int = 30


class TaskMappingRead(ORMModel):
    id: str
    task_name: str
    provider_type: str
    model_name: str
    fallback_chain: list[dict[str, Any]]
    timeout_seconds: int


class ProviderRunRequest(BaseModel):
    task_name: str
    prompt: str
    metadata: dict[str, Any] = Field(default_factory=dict)
