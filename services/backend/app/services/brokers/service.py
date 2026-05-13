from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.models.asset import Asset, MarketSnapshot
from app.models.broker import BrokerAccount, BrokerSyncEvent
from app.models.portfolio import PortfolioSnapshot, Position
from app.schemas.broker import BrokerAccountCreate
from app.services.audit.service import audit_service
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
        return list(
            db.scalars(
                select(BrokerAccount).order_by(
                    BrokerAccount.enabled.desc(),
                    BrokerAccount.updated_at.desc(),
                    BrokerAccount.name,
                )
            )
        )

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
            "supports_execution": self.adapters[account.broker_type].capability.supports_execution,
            "supports_sync": self.adapters[account.broker_type].capability.supports_sync,
            "capability_message": self.adapters[account.broker_type].capability.message,
        }

    def latest_sync_event(self, db: Session, account_id: str) -> BrokerSyncEvent | None:
        return db.scalar(
            select(BrokerSyncEvent)
            .where(BrokerSyncEvent.broker_account_id == account_id)
            .order_by(desc(BrokerSyncEvent.completed_at), desc(BrokerSyncEvent.started_at), desc(BrokerSyncEvent.created_at))
            .limit(1)
        )

    def latest_successful_sync_event(self, db: Session, account_id: str) -> BrokerSyncEvent | None:
        return db.scalar(
            select(BrokerSyncEvent)
            .where(BrokerSyncEvent.broker_account_id == account_id, BrokerSyncEvent.status.in_(["ok", "warn"]))
            .order_by(desc(BrokerSyncEvent.completed_at), desc(BrokerSyncEvent.started_at), desc(BrokerSyncEvent.created_at))
            .limit(1)
        )

    def serialize_runtime_account(self, db: Session, account: BrokerAccount) -> dict:
        payload = self.serialize_account(account)
        adapter = self.adapters[account.broker_type]
        latest_sync = self.latest_sync_event(db, account.id)
        latest_successful_sync = self.latest_successful_sync_event(db, account.id)
        payload.update(
            {
                "supports_execution": adapter.capability.supports_execution,
                "supports_sync": adapter.capability.supports_sync,
                "capability_message": adapter.capability.message,
                "last_sync_status": latest_sync.status if latest_sync else None,
                "last_sync_started_at": latest_sync.started_at.isoformat() if latest_sync and latest_sync.started_at else None,
                "last_sync_completed_at": latest_sync.completed_at.isoformat() if latest_sync and latest_sync.completed_at else None,
                "last_sync_message": (latest_sync.details_json or {}).get("message") if latest_sync else None,
                "last_successful_sync_completed_at": latest_successful_sync.completed_at.isoformat() if latest_successful_sync and latest_successful_sync.completed_at else None,
                "cash_balance": account.settings_json.get("cash_balance"),
                "available_cash": account.settings_json.get("available_cash"),
                "invested_value": account.settings_json.get("invested_value"),
                "total_value": account.settings_json.get("total_value"),
                "currency": account.settings_json.get("currency"),
                "short_supported": bool(account.settings_json.get("short_supported", False)),
                "synced_positions": account.settings_json.get("synced_positions", []),
                "synced_pies": account.settings_json.get("synced_pies", []),
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
        matching_accounts = list(
            db.scalars(
                select(BrokerAccount)
                .where(
                    BrokerAccount.broker_type == payload.broker_type,
                    BrokerAccount.mode == payload.mode,
                )
                .order_by(BrokerAccount.enabled.desc(), BrokerAccount.updated_at.desc(), BrokerAccount.created_at.asc())
            )
        )
        account = matching_accounts[0] if matching_accounts else None
        if account is None:
            account = BrokerAccount(
                name=payload.name,
                broker_type=payload.broker_type,
            )
            db.add(account)
        for duplicate in matching_accounts[1:]:
            duplicate.enabled = False
            duplicate.status = "disabled"
        account.name = payload.name
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
        pies_result = (
            adapter.sync_pies(account)
            if hasattr(adapter, "sync_pies") and adapter.capability.supports_sync
            else BrokerResult(True, "Pies sync is not supported by this adapter.", {"pies": []})
        )

        successes = [account_result.success, positions_result.success, orders_result.success, pies_result.success]
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
            "pies_message": pies_result.message,
            "supports_execution": adapter.capability.supports_execution,
            "supports_sync": adapter.capability.supports_sync,
        }
        if account_result.success:
            account.status = "connected"
            normalized_summary = self._normalize_account_summary(account_result.data or {})
            synced_positions = positions_result.data.get("positions", []) if positions_result.success else []
            synced_pies = pies_result.data.get("pies", []) if pies_result.success else []
            if positions_result.success:
                self._upsert_live_positions(db, account, synced_positions)
            account.settings_json = {
                **(account.settings_json or {}),
                **normalized_summary,
                "synced_positions": synced_positions,
                "synced_pies": synced_pies,
                "last_synced_at": sync_event.completed_at.isoformat() if sync_event.completed_at else None,
                "sync_source": account.broker_type,
            }
            if normalized_summary.get("external_account_id") is not None:
                account.external_account_id = str(normalized_summary["external_account_id"])
            if normalized_summary.get("total_value") is not None:
                db.add(
                    PortfolioSnapshot(
                        mode="live",
                        broker_account_id=account.id,
                        timestamp=sync_event.completed_at or utcnow(),
                        total_value=float(normalized_summary.get("total_value") or 0),
                        cash=float(normalized_summary.get("available_cash") or 0),
                        equity=float(normalized_summary.get("invested_value") or 0),
                        realized_pnl=float(normalized_summary.get("realized_pnl") or 0),
                        unrealized_pnl=float(normalized_summary.get("unrealized_pnl") or 0),
                        daily_return=0,
                        weekly_return=0,
                        monthly_return=0,
                        exposure_json={"source": account.broker_type},
                    )
                )
        elif status == "error":
            account.status = "scaffolded"
        db.flush()
        audit_service.log(
            db,
            actor="system",
            action="broker.sync",
            target_type="broker_account",
            target_id=account.id,
            status=status,
            mode=account.mode,
            details=sync_event.details_json,
        )

        return {
            "broker_account_id": account.id,
            "broker_type": account.broker_type,
            "status": status,
            "message": message,
            "account_message": account_result.message,
            "positions_message": positions_result.message,
            "orders_message": orders_result.message,
            "pies_message": pies_result.message,
            "positions_count": len(positions_result.data.get("positions", [])) if positions_result.success else 0,
            "pies_count": len(pies_result.data.get("pies", [])) if pies_result.success else 0,
            "supports_execution": adapter.capability.supports_execution,
            "supports_sync": adapter.capability.supports_sync,
            "started_at": sync_event.started_at.isoformat() if sync_event.started_at else None,
            "completed_at": sync_event.completed_at.isoformat() if sync_event.completed_at else None,
        }

    def get_account(self, db: Session, account_id: str) -> BrokerAccount | None:
        return db.scalar(select(BrokerAccount).where(BrokerAccount.id == account_id))

    def get_adapter(self, broker_type: str):
        return self.adapters[broker_type]

    def _normalize_account_summary(self, payload: dict) -> dict:
        cash_payload = payload.get("cash") if isinstance(payload.get("cash"), dict) else payload
        investments_payload = payload.get("investments") if isinstance(payload.get("investments"), dict) else {}
        free_cash = self._safe_float(
            cash_payload.get("availableToTrade")
            or cash_payload.get("free")
            or cash_payload.get("available")
            or cash_payload.get("availableCash")
            or cash_payload.get("cash")
        )
        blocked_cash = self._safe_float(
            cash_payload.get("reservedForOrders")
            or cash_payload.get("blocked")
            or cash_payload.get("blockedCash")
        )
        invested = self._safe_float(
            investments_payload.get("currentValue")
            or investments_payload.get("totalCost")
            or cash_payload.get("invested")
            or cash_payload.get("investedValue")
        )
        unrealized = self._safe_float(
            investments_payload.get("unrealizedProfitLoss")
            or cash_payload.get("ppl")
            or cash_payload.get("unrealizedPnl")
        )
        realized = self._safe_float(
            investments_payload.get("realizedProfitLoss")
            or cash_payload.get("result")
            or cash_payload.get("realizedPnl")
        )
        total = self._safe_float(cash_payload.get("total") or cash_payload.get("totalValue"))
        if total is None:
            total = self._safe_float(payload.get("totalValue"))
        if total is None and free_cash is not None:
            total = free_cash + (blocked_cash or 0) + (invested or 0) + (unrealized or 0)
        return {
            "external_account_id": payload.get("id"),
            "currency": payload.get("currencyCode") or payload.get("currency"),
            "cash_balance": free_cash,
            "available_cash": free_cash,
            "blocked_cash": blocked_cash,
            "invested_value": invested,
            "unrealized_pnl": unrealized,
            "realized_pnl": realized,
            "total_value": total,
            "short_supported": False,
            "raw_account_summary": payload,
        }

    def _upsert_live_positions(self, db: Session, account: BrokerAccount, positions: list[dict]) -> None:
        seen_asset_ids: set[str] = set()
        for item in positions:
            symbol = str(item.get("symbol") or item.get("broker_ticker") or "").strip().upper()
            if not symbol:
                continue
            asset = self._get_or_create_synced_asset(db, item)
            seen_asset_ids.add(asset.id)
            quantity = self._safe_float(item.get("quantity")) or 0.0
            if quantity <= 0:
                continue
            current_price = self._safe_float(item.get("current_price")) or self._safe_float(item.get("avg_entry_price")) or 0.0
            avg_entry_price = self._safe_float(item.get("avg_entry_price")) or current_price
            unrealized = self._safe_float(item.get("unrealized_pnl"))
            position = db.scalar(
                select(Position).where(
                    Position.mode == "live",
                    Position.broker_account_id == account.id,
                    Position.asset_id == asset.id,
                    Position.status == "open",
                )
            )
            if position is None:
                position = Position(
                    asset_id=asset.id,
                    broker_account_id=account.id,
                    mode="live",
                    manual=True,
                    strategy_name="broker-sync",
                    provider_type=account.broker_type,
                    quantity=quantity,
                    avg_entry_price=avg_entry_price,
                    current_price=current_price,
                    unrealized_pnl=unrealized if unrealized is not None else (current_price - avg_entry_price) * quantity,
                    notes="Synced from Trading212 portfolio.",
                    tags=["broker-sync", account.broker_type],
                )
                db.add(position)
            else:
                position.quantity = quantity
                position.avg_entry_price = avg_entry_price
                position.current_price = current_price
                position.unrealized_pnl = unrealized if unrealized is not None else (current_price - avg_entry_price) * quantity
                position.notes = self._synced_position_note(item)
                position.status = "open"
            self._record_synced_price(db, asset.id, current_price)

        for stale in db.scalars(
            select(Position).where(
                Position.mode == "live",
                Position.broker_account_id == account.id,
                Position.provider_type == account.broker_type,
                Position.strategy_name == "broker-sync",
                Position.status == "open",
            )
        ):
            if stale.asset_id not in seen_asset_ids:
                stale.status = "closed"
                stale.quantity = 0
                stale.closed_at = utcnow()
                stale.notes = self._append_note(stale.notes, "Marked closed because Trading212 sync no longer reports this holding.")

    def _get_or_create_synced_asset(self, db: Session, item: dict) -> Asset:
        symbol = str(item.get("symbol") or item.get("broker_ticker") or "").strip().upper()
        asset = db.scalar(select(Asset).where(Asset.symbol == symbol))
        if asset is not None:
            return asset
        asset = Asset(
            symbol=symbol,
            name=str(item.get("name") or symbol),
            asset_type=str(item.get("asset_type") or "stock").lower(),
            exchange=item.get("exchange") or "TRADING212",
            currency=str(item.get("currency") or "USD"),
        )
        db.add(asset)
        db.flush()
        return asset

    def _record_synced_price(self, db: Session, asset_id: str, price: float) -> None:
        if price <= 0:
            return
        db.add(
            MarketSnapshot(
                asset_id=asset_id,
                timestamp=utcnow(),
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=0,
                source="trading212-sync",
            )
        )

    def _synced_position_note(self, item: dict) -> str:
        available = item.get("quantity_available")
        in_pies = item.get("quantity_in_pies")
        return f"Synced from Trading212 portfolio. Available for trading: {available}; in pies: {in_pies}."

    def _append_note(self, existing: str | None, note: str) -> str:
        if not existing:
            return note
        if note in existing:
            return existing
        return f"{existing}\n{note}"

    def _safe_float(self, value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
