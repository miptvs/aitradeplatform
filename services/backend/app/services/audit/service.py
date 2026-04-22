from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.utils.time import utcnow


class AuditService:
    def log(
        self,
        db: Session,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_id: str | None = None,
        status: str = "success",
        mode: str | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            mode=mode,
            details_json=details or {},
            occurred_at=utcnow(),
        )
        db.add(entry)
        db.flush()
        return entry


audit_service = AuditService()
