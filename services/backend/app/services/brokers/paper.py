from app.models.broker import BrokerAccount
from app.services.brokers.base import BaseBrokerAdapter, BrokerCapability, BrokerResult


class PaperBrokerAdapter(BaseBrokerAdapter):
    broker_type = "paper"
    capability = BrokerCapability(
        broker_type="paper",
        supports_execution=False,
        supports_sync=True,
        message="Paper broker adapter is a safe local scaffold and does not place live broker orders.",
    )

    def validate_connection(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker is locally available", {"status": "ready"})

    def get_account(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker account available", account.settings_json)

    def get_positions(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker sync scaffold returns local mirror data", {})

    def get_orders(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker sync scaffold returns local mirror data", {})

    def place_order(self, account: BrokerAccount, order_payload: dict) -> BrokerResult:
        return BrokerResult(
            False,
            "Paper broker adapter does not place live orders. Use simulation mode for executable local trading.",
        )

    def cancel_order(self, account: BrokerAccount, order_id: str) -> BrokerResult:
        return BrokerResult(False, "Paper broker cancel scaffold not implemented")

    def sync_account(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker sync scaffold completed", {"broker_type": "paper"})

    def sync_positions(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker positions sync scaffold completed", {})

    def sync_orders(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(True, "Paper broker orders sync scaffold completed", {})

    def search_instruments(self, account: BrokerAccount, query: str) -> BrokerResult:
        return BrokerResult(False, "Paper broker does not provide external ticker validation", {"matches": []})
