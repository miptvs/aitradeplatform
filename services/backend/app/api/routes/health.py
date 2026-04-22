from fastapi import APIRouter, Depends
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis import get_redis
from app.models.health import SystemHealthEvent
from app.schemas.common import HealthStatusSchema
from app.services.providers.service import provider_service

router = APIRouter()


@router.get("/live", response_model=HealthStatusSchema)
def live() -> HealthStatusSchema:
    return HealthStatusSchema(status="ok", details={"service": "backend"})


@router.get("/ready", response_model=HealthStatusSchema)
def ready(db: Session = Depends(get_db)) -> HealthStatusSchema:
    details = {"database": "ok", "redis": "ok"}
    db.execute(text("SELECT 1"))
    try:
        redis = get_redis()
        redis.ping()
        redis.close()
    except RedisError as exc:
        details["redis"] = str(exc)
        return HealthStatusSchema(status="error", details=details)
    return HealthStatusSchema(status="ok", details=details)


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    health_events = [
        {
            "component": event.component,
            "status": event.status,
            "message": event.message,
            "observed_at": event.observed_at.isoformat(),
        }
        for event in db.query(SystemHealthEvent).order_by(SystemHealthEvent.observed_at.desc()).limit(20)
    ]
    return {"status": "ok", "providers": provider_service.get_health(db), "events": health_events}
