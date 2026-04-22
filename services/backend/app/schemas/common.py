from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageSchema(BaseModel):
    message: str


class HealthStatusSchema(BaseModel):
    status: str
    details: dict[str, Any] = {}


class AuditLogRead(ORMModel):
    id: str
    actor: str
    action: str
    target_type: str
    target_id: str | None = None
    status: str
    mode: str | None = None
    details_json: dict[str, Any]
    occurred_at: datetime


class AlertRead(ORMModel):
    id: str
    category: str
    severity: str
    title: str
    message: str
    status: str
    mode: str | None = None
    source_ref: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
