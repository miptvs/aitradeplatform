from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.audit import Alert


class AlertService:
    def list_alerts(self, db: Session) -> list[Alert]:
        return list(db.scalars(select(Alert).where(Alert.status == "open").order_by(desc(Alert.created_at)).limit(50)))

    def has_open_alert(self, db: Session, *, source_ref: str | None = None, title: str | None = None) -> bool:
        stmt = select(Alert).where(Alert.status == "open")
        if source_ref is not None:
            stmt = stmt.where(Alert.source_ref == source_ref)
        if title is not None:
            stmt = stmt.where(Alert.title == title)
        return db.scalar(stmt.limit(1)) is not None

    def resolve_alerts(self, db: Session, *, source_ref: str | None = None, title: str | None = None) -> int:
        stmt = select(Alert).where(Alert.status == "open")
        if source_ref is not None:
            stmt = stmt.where(Alert.source_ref == source_ref)
        if title is not None:
            stmt = stmt.where(Alert.title == title)

        updated = 0
        for alert in db.scalars(stmt):
            alert.status = "resolved"
            updated += 1
        return updated

    def create_alert(
        self,
        db: Session,
        *,
        category: str,
        severity: str,
        title: str,
        message: str,
        mode: str | None = None,
        source_ref: str | None = None,
        metadata: dict | None = None,
        dedupe: bool = False,
    ) -> Alert:
        if dedupe and self.has_open_alert(db, source_ref=source_ref, title=title):
            existing_stmt = select(Alert).where(Alert.status == "open", Alert.title == title)
            if source_ref is not None:
                existing_stmt = existing_stmt.where(Alert.source_ref == source_ref)
            existing = db.scalar(existing_stmt.limit(1))
            if existing is not None:
                return existing

        alert = Alert(
            category=category,
            severity=severity,
            title=title,
            message=message,
            mode=mode,
            source_ref=source_ref,
            metadata_json=metadata or {},
        )
        db.add(alert)
        db.flush()
        return alert


alert_service = AlertService()
