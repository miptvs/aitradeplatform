from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.broker import BrokerAccount, BrokerSyncEvent
from app.services.brokers.base import BrokerResult
from app.services.brokers.service import broker_service


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_trading212_sync_maps_account_balance_correctly(monkeypatch) -> None:
    db = build_session()
    account = BrokerAccount(
        name="Trading212 Live",
        broker_type="trading212",
        mode="live",
        enabled=True,
        live_trading_enabled=False,
        status="connected",
        settings_json={},
    )
    db.add(account)
    db.commit()

    adapter = broker_service.get_adapter("trading212")
    monkeypatch.setattr(
        adapter,
        "sync_account",
        lambda _account: BrokerResult(
            True,
            "ok",
            {
                "id": "acct-123",
                "currencyCode": "EUR",
                "cash": {"availableToTrade": 1234.5, "reservedForOrders": 50},
                "investments": {"currentValue": 2000, "unrealizedProfitLoss": 75, "realizedProfitLoss": 12},
                "totalValue": 3309.5,
            },
        ),
    )
    monkeypatch.setattr(adapter, "sync_positions", lambda _account: BrokerResult(True, "positions ok", {"positions": []}))
    monkeypatch.setattr(adapter, "sync_orders", lambda _account: BrokerResult(True, "orders ok", {}))
    monkeypatch.setattr(adapter, "sync_pies", lambda _account: BrokerResult(True, "pies ok", {"pies": []}))

    result = broker_service.sync_account(db, account.id)
    db.commit()

    synced = db.get(BrokerAccount, account.id)
    assert result["status"] == "ok"
    assert synced.settings_json["available_cash"] == 1234.5
    assert synced.settings_json["blocked_cash"] == 50
    assert synced.settings_json["invested_value"] == 2000
    assert synced.settings_json["total_value"] == 3309.5
    assert synced.settings_json["currency"] == "EUR"
    assert "raw_account_summary" in synced.settings_json


def test_trading212_sync_failure_exposes_actionable_error(monkeypatch) -> None:
    db = build_session()
    account = BrokerAccount(
        name="Trading212 Live",
        broker_type="trading212",
        mode="live",
        enabled=True,
        live_trading_enabled=False,
        status="connected",
        settings_json={"available_cash": 100, "total_value": 100, "last_synced_at": "previous"},
    )
    db.add(account)
    db.commit()

    adapter = broker_service.get_adapter("trading212")
    monkeypatch.setattr(adapter, "sync_account", lambda _account: BrokerResult(False, "Trading212 rejected the credentials with 401 Unauthorized.", {}))
    monkeypatch.setattr(adapter, "sync_positions", lambda _account: BrokerResult(False, "positions unavailable", {"positions": []}))
    monkeypatch.setattr(adapter, "sync_orders", lambda _account: BrokerResult(False, "orders unavailable", {}))
    monkeypatch.setattr(adapter, "sync_pies", lambda _account: BrokerResult(False, "pies unavailable", {"pies": []}))

    result = broker_service.sync_account(db, account.id)
    db.commit()
    event = db.scalar(select(BrokerSyncEvent).where(BrokerSyncEvent.broker_account_id == account.id))
    synced = db.get(BrokerAccount, account.id)

    assert result["status"] == "error"
    assert "401 Unauthorized" in result["account_message"]
    assert event.status == "error"
    assert "401 Unauthorized" in event.details_json["account_message"]
    assert synced.settings_json["available_cash"] == 100
