from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.models.broker import BrokerAccount, BrokerSyncEvent
from app.schemas.broker import BrokerAccountCreate
from app.services.brokers.base import BrokerResult
from app.services.brokers.paper import PaperBrokerAdapter
from app.services.brokers.trading212 import Trading212BrokerAdapter
from app.utils.time import utcnow


class BrokerService:
    def __init__(self) -> None:
        self.adapters = {
            "paper": PaperBrokerAdapter(),
            "trading212": Trading212BrokerAdapter(),
        }

    def list_accounts(self, db: Session) -> list[BrokerAccount]:
        return list(db.scalars(select(BrokerAccount).order_by(BrokerAccount.name)))

    def serialize_account(self, account: BrokerAccount) -> dict:
        return {
            "id": account.id,
            "name": account.name,
            "broker_type": account.broker_type,
            "mode": account.mode,
            "enabled": account.enabled,
            "live_trading_enabled": account.live_trading_enabled,
            "status": account.status,
            "base_url": account.base_url,
            "settings_json": account.settings_json,
            "has_secret": bool(account.encrypted_api_key or account.encrypted_api_secret),
        }

    def latest_sync_event(self, db: Session, account_id: str) -> BrokerSyncEvent | None:
        return db.scalar(
            select(BrokerSyncEvent)
            .where(BrokerSyncEvent.broker_account_id == account_id)
            .order_by(desc(BrokerSyncEvent.completed_at), desc(BrokerSyncEvent.started_at), desc(BrokerSyncEvent.created_at))
            .limit(1)
        )

    def serialize_runtime_account(self, db: Session, account: BrokerAccount) -> dict:
        payload = self.serialize_account(account)
        adapter = self.adapters[account.broker_type]
        latest_sync = self.latest_sync_event(db, account.id)
        payload.update(
            {
                "supports_execution": adapter.capability.supports_execution,
                "supports_sync": adapter.capability.supports_sync,
                "capability_message": adapter.capability.message,
                "last_sync_status": latest_sync.status if latest_sync else None,
                "last_sync_started_at": latest_sync.started_at.isoformat() if latest_sync and latest_sync.started_at else None,
                "last_sync_completed_at": latest_sync.completed_at.isoformat() if latest_sync and latest_sync.completed_at else None,
                "last_sync_message": (latest_sync.details_json or {}).get("message") if latest_sync else None,
            }
        )
        return payload

    def list_adapter_statuses(self) -> list[dict]:
        return [
            {
                "broker_type": adapter.capability.broker_type,
                "supports_execution": adapter.capability.supports_execution,
                "supports_sync": adapter.capability.supports_sync,
                "message": adapter.capability.message,
            }
            for adapter in self.adapters.values()
        ]

    def upsert_account(self, db: Session, payload: BrokerAccountCreate) -> BrokerAccount:
        account = db.scalar(
            select(BrokerAccount).where(
                BrokerAccount.name == payload.name,
                BrokerAccount.broker_type == payload.broker_type,
            )
        )
        if account is None:
            account = BrokerAccount(
                name=payload.name,
                broker_type=payload.broker_type,
            )
            db.add(account)
        account.mode = payload.mode
        account.enabled = payload.enabled
        account.live_trading_enabled = payload.live_trading_enabled
        account.base_url = payload.base_url
        account.settings_json = payload.settings_json
        if payload.api_key:
            account.encrypted_api_key = encrypt_secret(payload.api_key)
        if payload.api_secret:
            account.encrypted_api_secret = encrypt_secret(payload.api_secret)
        db.flush()
        return account

    def validate_connection(self, db: Session, account_id: str) -> dict:
        account = db.scalar(select(BrokerAccount).where(BrokerAccount.id == account_id))
        if account is None:
            raise ValueError("Broker account not found")
        adapter = self.adapters[account.broker_type]
        result = adapter.validate_connection(account)
        account.status = "connected" if result.success else "scaffolded"
        db.flush()
        return {
            "broker_type": account.broker_type,
            "supports_execution": adapter.capability.supports_execution,
            "supports_sync": adapter.capability.supports_sync,
            "message": result.message,
        }

    def sync_account(self, db: Session, account_id: str, *, trigger: str = "manual") -> dict:
        account = self.get_account(db, account_id)
        if account is None:
            raise ValueError("Broker account not found")

        adapter = self.adapters[account.broker_type]
        sync_event = BrokerSyncEvent(
            broker_account_id=account.id,
            event_type=f"{trigger}_sync",
            status="running",
            details_json={"trigger": trigger},
            started_at=utcnow(),
        )
        db.add(sync_event)
        db.flush()

        account_result = adapter.sync_account(account)
        positions_result = (
            adapter.sync_positions(account)
            if adapter.capability.supports_sync
            else BrokerResult(True, "Positions sync is not supported by this adapter.", {})
        )
        orders_result = (
            adapter.sync_orders(account)
            if adapter.capability.supports_sync
            else BrokerResult(True, "Orders sync is not supported by this adapter.", {})
        )

        successes = [account_result.success, positions_result.success, orders_result.success]
        if all(successes):
            status = "ok"
        elif any(successes):
            status = "warn"
        else:
            status = "error"

        message = "Broker sync completed."
        if status == "warn":
            message = "Broker sync completed with partial scaffold coverage."
        elif status == "error":
            message = "Broker sync failed."

        sync_event.status = status
        sync_event.completed_at = utcnow()
        sync_event.details_json = {
            "trigger": trigger,
            "message": message,
            "account_message": account_result.message,
            "positions_message": positions_result.message,
            "orders_message": orders_result.message,
            "supports_execution": adapter.capability.supports_execution,
            "supports_sync": adapter.capability.supports_sync,
        }
        if account_result.success:
            account.status = "connected"
        elif status == "error":
            account.status = "scaffolded"
        db.flush()

        return {
            "broker_account_id": account.id,
            "broker_type": account.broker_type,
            "status": status,
            "message": message,
            "account_message": account_result.message,
            "positions_message": positions_result.message,
            "orders_message": orders_result.message,
            "supports_execution": adapter.capability.supports_execution,
            "supports_sync": adapter.capability.supports_sync,
            "started_at": sync_event.started_at.isoformat() if sync_event.started_at else None,
            "completed_at": sync_event.completed_at.isoformat() if sync_event.completed_at else None,
        }

    def get_account(self, db: Session, account_id: str) -> BrokerAccount | None:
        return db.scalar(select(BrokerAccount).where(BrokerAccount.id == account_id))

    def get_adapter(self, broker_type: str):
        return self.adapters[broker_type]

    def search_instruments(self, db: Session, broker_type: str, query: str) -> dict:
        account = db.scalar(select(BrokerAccount).where(BrokerAccount.broker_type == broker_type).order_by(BrokerAccount.enabled.desc()))
        if account is None:
            account = BrokerAccount(
                name=f"{broker_type} lookup",
                broker_type=broker_type,
                mode="live",
                enabled=False,
                live_trading_enabled=False,
                settings_json={},
            )
        adapter = self.get_adapter(broker_type)
        result = adapter.search_instruments(account, query)
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
        }


broker_service = BrokerService()
