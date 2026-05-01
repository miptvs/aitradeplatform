from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import AlertRead
from app.services.alerts.service import alert_service

router = APIRouter()


@router.get("/", response_model=list[AlertRead])
def list_alerts(db: Session = Depends(get_db)) -> list[AlertRead]:
    return [AlertRead.model_validate(item) for item in alert_service.list_alerts(db)]


@router.delete("/")
def clear_alerts(
    mode: str | None = Query(default=None),
    category: str | None = Query(default=None),
    include_system: bool = Query(default=False),
    warning_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    resolved = alert_service.resolve_alerts(
        db,
        mode=mode,
        category=category,
        include_system=include_system,
        warning_only=warning_only,
    )
    db.commit()
    return {"resolved": resolved}
