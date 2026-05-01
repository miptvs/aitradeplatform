from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.models.audit import Alert
from app.models.health import SystemHealthEvent


class AlertService:
    def list_alerts(self, db: Session, *, mode: str | None = None) -> list[Alert]:
        alerts = list(db.scalars(select(Alert).where(Alert.status == "open").order_by(desc(Alert.created_at)).limit(50)))
        results: list[Alert] = []
        for alert in alerts:
            if mode and alert.mode not in {None, "system", mode}:
                continue
            if not self._is_current_alert(db, alert):
                continue
            results.append(alert)
        return results

    def has_open_alert(self, db: Session, *, source_ref: str | None = None, title: str | None = None) -> bool:
        stmt = select(Alert).where(Alert.status == "open")
        if source_ref is not None:
            stmt = stmt.where(Alert.source_ref == source_ref)
        if title is not None:
            stmt = stmt.where(Alert.title == title)
        return db.scalar(stmt.limit(1)) is not None

    def resolve_alerts(
        self,
        db: Session,
        *,
        source_ref: str | None = None,
        title: str | None = None,
        mode: str | None = None,
        category: str | None = None,
        include_system: bool = False,
        warning_only: bool = False,
    ) -> int:
        stmt = select(Alert).where(Alert.status == "open")
        if source_ref is not None:
            stmt = stmt.where(Alert.source_ref == source_ref)
        if title is not None:
            stmt = stmt.where(Alert.title == title)
        if mode is not None:
            if include_system:
                stmt = stmt.where(or_(Alert.mode == mode, Alert.mode.is_(None), Alert.mode == "system"))
            else:
                stmt = stmt.where(Alert.mode == mode)
        if category is not None:
            stmt = stmt.where(Alert.category == category)
        if warning_only:
            stmt = stmt.where(or_(Alert.category == "risk", Alert.severity == "warning"))

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
                existing.message = message
                existing.mode = mode
                existing.metadata_json = metadata or {}
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

    def _is_current_alert(self, db: Session, alert: Alert) -> bool:
        if alert.category != "health":
            return True
        if not alert.title.endswith(" reported an error"):
            return True

        component = alert.source_ref if alert.source_ref else alert.title.removesuffix(" reported an error")
        latest_event = db.scalar(
            select(SystemHealthEvent)
            .where(SystemHealthEvent.component == component)
            .order_by(desc(SystemHealthEvent.observed_at))
            .limit(1)
        )
        if latest_event is None:
            return False
        return latest_event.status == "error"


alert_service = AlertService()
