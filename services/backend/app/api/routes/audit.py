from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog
from app.schemas.common import AuditLogRead

router = APIRouter()


@router.get("/", response_model=list[AuditLogRead])
def list_audit_logs(db: Session = Depends(get_db)) -> list[AuditLogRead]:
    return [AuditLogRead.model_validate(item) for item in db.scalars(select(AuditLog).order_by(desc(AuditLog.occurred_at)).limit(200))]
