from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.broker import BrokerAccount


@dataclass
class BrokerResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerCapability:
    broker_type: str
    supports_execution: bool
    supports_sync: bool
    message: str


@dataclass
class BrokerInstrumentMatch:
    symbol: str
    display_symbol: str
    name: str
    asset_type: str
    currency: str
    exchange: str | None = None
    broker_ticker: str | None = None
    source: str = "broker"
    source_label: str = "Broker lookup"
    verified: bool = True
    latest_price: float | None = None


class BaseBrokerAdapter(ABC):
    broker_type: str
    capability: BrokerCapability

    @abstractmethod
    def validate_connection(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def get_account(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def get_orders(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, account: BrokerAccount, order_payload: dict[str, Any]) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, account: BrokerAccount, order_id: str) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def sync_account(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def sync_positions(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def sync_orders(self, account: BrokerAccount) -> BrokerResult:
        raise NotImplementedError

    @abstractmethod
    def search_instruments(self, account: BrokerAccount, query: str) -> BrokerResult:
        raise NotImplementedError
