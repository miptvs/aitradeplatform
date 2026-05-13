import base64
import time
from dataclasses import asdict
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.models.broker import BrokerAccount
from app.services.brokers.base import BaseBrokerAdapter, BrokerCapability, BrokerInstrumentMatch, BrokerResult

settings = get_settings()


class Trading212BrokerAdapter(BaseBrokerAdapter):
    broker_type = "trading212"
    capability = BrokerCapability(
        broker_type="trading212",
        supports_execution=False,
        supports_sync=True,
        message="Trading212 supports authenticated instrument validation and sync scaffolding. Direct execution remains intentionally disabled.",
    )

    def __init__(self) -> None:
        self._instrument_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def validate_connection(self, account: BrokerAccount) -> BrokerResult:
        credentials = self._resolve_credentials(account)
        if not credentials.success:
            return credentials
        try:
            summary_payload = self._account_summary(account)
        except Exception as exc:
            return BrokerResult(False, f"Trading212 validation failed: {exc}")
        return BrokerResult(
            True,
            "Trading212 credentials verified successfully.",
            {
                "account_id": summary_payload.get("id"),
                "currency": summary_payload.get("currency") or summary_payload.get("currencyCode"),
                "cash": (summary_payload.get("cash") or {}).get("availableToTrade")
                if isinstance(summary_payload.get("cash"), dict)
                else None,
                "total": summary_payload.get("totalValue"),
                "mode": account.mode,
            },
        )

    def get_account(self, account: BrokerAccount) -> BrokerResult:
        try:
            payload = self._account_summary(account)
        except Exception as exc:
            return BrokerResult(False, f"Trading212 account sync failed: {exc}")
        return BrokerResult(True, "Trading212 account balance retrieved.", payload)

    def get_positions(self, account: BrokerAccount) -> BrokerResult:
        try:
            payload = self._request_json(account, "/equity/positions")
        except Exception as exc:
            return BrokerResult(False, f"Trading212 positions sync failed: {exc}")
        if not isinstance(payload, list):
            return BrokerResult(False, "Trading212 positions response was not a list.", {"positions": []})
        positions = [self._normalize_position(item) for item in payload if isinstance(item, dict)]
        return BrokerResult(True, f"Trading212 returned {len(positions)} open position{'s' if len(positions) != 1 else ''}.", {"positions": positions})

    def get_orders(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(False, "Trading212 order sync TODO")

    def place_order(self, account: BrokerAccount, order_payload: dict) -> BrokerResult:
        quantity = order_payload.get("quantity")
        sizing_mode = order_payload.get("sizing_mode")
        order_notional = order_payload.get("order_notional") or order_payload.get("amount")
        return BrokerResult(
            False,
            (
                "Trading212 execution is intentionally unavailable in this scaffold. "
                f"Resolved fractional order was {quantity} shares"
                f" from {sizing_mode or 'unspecified'} sizing"
                f"{f' ({order_notional} notional)' if order_notional is not None else ''}; no rounding or broker submission occurred."
            ),
            {
                "fractional_quantity": quantity,
                "sizing_mode": sizing_mode,
                "order_notional": order_notional,
                "fractional_supported_assumption": True,
            },
        )

    def cancel_order(self, account: BrokerAccount, order_id: str) -> BrokerResult:
        return BrokerResult(False, "Trading212 cancel TODO")

    def sync_account(self, account: BrokerAccount) -> BrokerResult:
        return self.get_account(account)

    def sync_positions(self, account: BrokerAccount) -> BrokerResult:
        return self.get_positions(account)

    def sync_orders(self, account: BrokerAccount) -> BrokerResult:
        return BrokerResult(False, "Trading212 orders sync TODO")

    def get_pies(self, account: BrokerAccount) -> BrokerResult:
        try:
            payload = self._request_json(account, "/equity/pies")
        except Exception as exc:
            return BrokerResult(False, f"Trading212 pies sync failed: {exc}", {"pies": []})
        if not isinstance(payload, list):
            return BrokerResult(False, "Trading212 pies response was not a list.", {"pies": []})
        pies = [self._normalize_pie(item) for item in payload if isinstance(item, dict)]
        return BrokerResult(True, f"Trading212 returned {len(pies)} pie{'s' if len(pies) != 1 else ''}.", {"pies": pies})

    def sync_pies(self, account: BrokerAccount) -> BrokerResult:
        return self.get_pies(account)

    def search_instruments(self, account: BrokerAccount, query: str) -> BrokerResult:
        normalized = self._normalize_query(query)
        if not normalized:
            return BrokerResult(True, "Enter a ticker or instrument name to search.", {"matches": []})

        credentials = self._resolve_credentials(account)
        if not credentials.success:
            return BrokerResult(False, credentials.message, {"matches": [], "reason": "credentials_missing"})

        try:
            instruments = self._get_instruments(account)
        except Exception as exc:
            return BrokerResult(False, f"Trading212 lookup failed: {exc}", {"matches": [], "reason": "lookup_failed"})

        matches = self._match_instruments(instruments, normalized)
        if not matches:
            return BrokerResult(
                True,
                f"Trading212 did not confirm an accessible instrument for {normalized}.",
                {"matches": [], "reason": "no_match"},
            )
        return BrokerResult(
            True,
            f"Trading212 verified {len(matches)} instrument match{'es' if len(matches) != 1 else ''}.",
            {"matches": [asdict(match) for match in matches]},
        )

    def _get_instruments(self, account: BrokerAccount) -> list[dict[str, Any]]:
        cache_key = self._cache_key(account)
        cached = self._instrument_cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < settings.trading212_instrument_cache_seconds:
            return cached[1]

        payload = self._request_json(account, "/equity/metadata/instruments")
        if not isinstance(payload, list):
            raise ValueError("Unexpected Trading212 instruments response.")

        self._instrument_cache[cache_key] = (now, payload)
        return payload

    def _account_summary(self, account: BrokerAccount) -> dict[str, Any]:
        try:
            payload = self._request_json(account, "/equity/account/summary")
            if isinstance(payload, dict):
                return payload
        except Exception:
            # Older credentials/permissions may still allow the legacy info/cash pair.
            pass
        info_payload = self._request_json(account, "/equity/account/info")
        cash_payload = self._request_json(account, "/equity/account/cash")
        return {
            "id": info_payload.get("id"),
            "currency": info_payload.get("currencyCode"),
            "currencyCode": info_payload.get("currencyCode"),
            "cash": {
                "availableToTrade": cash_payload.get("free") or cash_payload.get("availableToTrade"),
                "reservedForOrders": cash_payload.get("blocked") or cash_payload.get("reservedForOrders"),
                "inPies": cash_payload.get("pieCash") or cash_payload.get("inPies"),
                **cash_payload,
            },
            "totalValue": cash_payload.get("total"),
            "raw_info": info_payload,
        }

    def _normalize_position(self, item: dict[str, Any]) -> dict[str, Any]:
        instrument = item.get("instrument") if isinstance(item.get("instrument"), dict) else {}
        broker_ticker = str(item.get("ticker") or instrument.get("ticker") or "").upper()
        parsed = self._parse_ticker(broker_ticker)
        wallet = item.get("walletImpact") if isinstance(item.get("walletImpact"), dict) else {}
        quantity = self._safe_float(item.get("quantity"))
        average_price = self._safe_float(item.get("averagePricePaid") or item.get("averagePrice"))
        current_price = self._safe_float(item.get("currentPrice"))
        current_value = self._safe_float(wallet.get("currentValue"))
        if current_price is None and current_value is not None and quantity:
            current_price = current_value / quantity
        return {
            "broker_ticker": broker_ticker,
            "symbol": parsed["display_symbol"] or parsed["symbol"] or broker_ticker,
            "name": instrument.get("name") or broker_ticker,
            "asset_type": str(instrument.get("type") or "stock").lower(),
            "currency": instrument.get("currency") or wallet.get("currency") or "USD",
            "exchange": parsed["exchange"],
            "quantity": quantity or 0,
            "quantity_available": self._safe_float(item.get("quantityAvailableForTrading")),
            "quantity_in_pies": self._safe_float(item.get("quantityInPies")),
            "avg_entry_price": average_price or current_price or 0,
            "current_price": current_price or average_price or 0,
            "current_value": current_value,
            "total_cost": self._safe_float(wallet.get("totalCost")),
            "unrealized_pnl": self._safe_float(wallet.get("unrealizedProfitLoss")),
            "opened_at": item.get("createdAt"),
            "raw": item,
        }

    def _normalize_pie(self, item: dict[str, Any]) -> dict[str, Any]:
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        return {
            "id": item.get("id"),
            "status": item.get("status"),
            "cash": self._safe_float(item.get("cash")),
            "progress": self._safe_float(item.get("progress")),
            "current_value": self._safe_float(result.get("priceAvgValue")),
            "invested_value": self._safe_float(result.get("priceAvgInvestedValue")),
            "result": self._safe_float(result.get("priceAvgResult")),
            "result_pct": self._safe_float(result.get("priceAvgResultCoef")),
            "raw": item,
        }

    def _request_json(self, account: BrokerAccount, path: str) -> Any:
        credentials = self._resolve_credentials(account)
        if not credentials.success:
            raise ValueError(credentials.message)

        api_key = credentials.data["api_key"]
        api_secret = credentials.data["api_secret"]
        encoded = base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded}"}
        url = f"{self._resolve_base_url(account)}{path}"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ValueError(self._format_http_error(account, exc)) from exc
            return response.json()

    def _format_http_error(self, account: BrokerAccount, exc: httpx.HTTPStatusError) -> str:
        response = exc.response
        status_code = response.status_code
        base_url = self._resolve_base_url(account)

        if status_code == 401:
            return (
                "Trading212 rejected the credentials with 401 Unauthorized. "
                "Check that the API key and API secret are both correct and saved as a matching pair."
            )

        if status_code == 403:
            environment = "demo" if "demo.trading212.com" in base_url else "live"
            return (
                f"Trading212 returned 403 Forbidden on the {environment} environment. "
                "This usually means the credentials are recognized but not permitted for this request. "
                "Most common causes: the key was created for the other environment (demo vs live), "
                "the Trading212 account is not an Invest or Stocks ISA account, the API key has IP restrictions "
                "that do not allow this server, or the key permissions do not include account data access."
            )

        if status_code == 429:
            return "Trading212 rate limit reached. Please wait a few seconds and try validation again."

        return f"Trading212 request failed with HTTP {status_code} for {response.request.url}."

    def _resolve_credentials(self, account: BrokerAccount) -> BrokerResult:
        api_key = decrypt_secret(account.encrypted_api_key) if account.encrypted_api_key else settings.trading212_api_key
        api_secret = decrypt_secret(account.encrypted_api_secret) if account.encrypted_api_secret else settings.trading212_api_secret

        if not api_key or not api_secret:
            return BrokerResult(
                False,
                "Trading212 ticker validation needs both API key and API secret in backend broker settings or env vars.",
            )
        return BrokerResult(True, "Trading212 credentials ready", {"api_key": api_key, "api_secret": api_secret})

    def _resolve_base_url(self, account: BrokerAccount) -> str:
        configured = (account.base_url or "").rstrip("/")
        if configured.endswith("/api/v0"):
            return configured
        if "demo.trading212.com" in configured:
            return settings.trading212_demo_base_url.rstrip("/")
        if "live.trading212.com" in configured or "api.trading212.com" in configured:
            return settings.trading212_live_base_url.rstrip("/")
        if account.mode in {"simulation", "paper", "demo"}:
            return settings.trading212_demo_base_url.rstrip("/")
        return settings.trading212_live_base_url.rstrip("/")

    def _cache_key(self, account: BrokerAccount) -> str:
        credentials = self._resolve_credentials(account)
        api_key = credentials.data.get("api_key", "") if credentials.success else "missing"
        return f"{self._resolve_base_url(account)}::{account.mode}::{api_key}"

    def _match_instruments(self, instruments: list[dict[str, Any]], query: str) -> list[BrokerInstrumentMatch]:
        query_upper = query.upper()
        query_compact = query_upper.replace(".", "").replace("-", "")
        scored: list[tuple[int, BrokerInstrumentMatch]] = []

        for instrument in instruments:
            internal_ticker = str(instrument.get("ticker") or "").upper()
            if not internal_ticker:
                continue
            parsed = self._parse_ticker(internal_ticker)
            haystacks = [
                internal_ticker,
                parsed["symbol"],
                parsed["display_symbol"],
                str(instrument.get("name") or ""),
                str(instrument.get("shortName") or ""),
                str(instrument.get("isin") or ""),
            ]
            score = self._score_match(query_upper, query_compact, haystacks, internal_ticker, parsed["symbol"], parsed["display_symbol"])
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    BrokerInstrumentMatch(
                        symbol=parsed["display_symbol"],
                        display_symbol=parsed["display_symbol"],
                        name=str(instrument.get("name") or instrument.get("shortName") or parsed["display_symbol"]),
                        asset_type=str(instrument.get("type") or "stock").lower(),
                        currency=str(instrument.get("currencyCode") or "USD"),
                        exchange=parsed["exchange"],
                        broker_ticker=internal_ticker,
                        source="trading212",
                        source_label="Trading212 verified",
                        verified=True,
                    ),
                )
            )

        unique: dict[str, tuple[int, BrokerInstrumentMatch]] = {}
        for score, match in scored:
            existing = unique.get(match.broker_ticker or match.display_symbol)
            if existing is None or score > existing[0]:
                unique[match.broker_ticker or match.display_symbol] = (score, match)

        ordered = sorted(unique.values(), key=lambda item: (-item[0], item[1].display_symbol, item[1].name))
        return [item[1] for item in ordered[:8]]

    def _score_match(
        self,
        query_upper: str,
        query_compact: str,
        haystacks: list[str],
        internal_ticker: str,
        symbol: str,
        display_symbol: str,
    ) -> int:
        hay_upper = [value.upper() for value in haystacks if value]
        if query_upper == internal_ticker or query_upper == display_symbol or query_upper == symbol:
            return 120
        if query_compact == symbol.replace(".", "").replace("-", ""):
            return 115
        if internal_ticker.startswith(f"{query_compact}_") or internal_ticker.startswith(f"{query_upper}_"):
            return 110
        if any(value.startswith(query_upper) for value in hay_upper):
            return 95
        if any(query_upper in value for value in hay_upper):
            return 75
        return 0

    def _parse_ticker(self, ticker: str) -> dict[str, str | None]:
        parts = ticker.split("_")
        base_symbol = parts[0]
        exchange_code = parts[1] if len(parts) >= 3 else None
        if exchange_code and exchange_code not in {"US"}:
            display_symbol = f"{base_symbol}.{exchange_code}"
        else:
            display_symbol = base_symbol
        return {
            "symbol": base_symbol,
            "display_symbol": display_symbol,
            "exchange": exchange_code,
        }

    def _normalize_query(self, query: str) -> str:
        return query.strip().upper().replace(" ", "")

    def _safe_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
