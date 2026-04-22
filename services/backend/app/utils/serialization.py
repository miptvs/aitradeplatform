from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_plain_dict(instance: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in instance.__table__.columns:
        value = getattr(instance, column.name)
        data[column.name] = _normalize_value(value)
    return data


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    return value
