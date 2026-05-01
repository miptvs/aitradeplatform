from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models.asset import Asset
from app.utils.time import utcnow


@dataclass(frozen=True)
class MarketHoursResult:
    is_open: bool
    reason: str
    details: dict


class MarketHoursService:
    """Small exchange-hours scaffold for risk/simulation/replay.

    This is intentionally a deterministic guard, not a full exchange calendar.
    Holidays can be supplied through risk/replay config as ISO dates.
    """

    EXCHANGE_PROFILES = {
        "NASDAQ": ("America/New_York", time(9, 30), time(16, 0)),
        "NYSE": ("America/New_York", time(9, 30), time(16, 0)),
        "ARCA": ("America/New_York", time(9, 30), time(16, 0)),
        "AMEX": ("America/New_York", time(9, 30), time(16, 0)),
        "LSE": ("Europe/London", time(8, 0), time(16, 30)),
        "LONDON": ("Europe/London", time(8, 0), time(16, 30)),
        "XETRA": ("Europe/Berlin", time(9, 0), time(17, 30)),
        "FWB": ("Europe/Berlin", time(9, 0), time(17, 30)),
    }

    def check_asset(
        self,
        asset: Asset | None,
        *,
        at: datetime | None = None,
        config: dict | None = None,
    ) -> MarketHoursResult:
        config = config or {}
        observed_at = at or utcnow()
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=ZoneInfo("UTC"))

        exchange = (asset.exchange if asset else None) or ""
        normalized_exchange = exchange.strip().upper()
        if normalized_exchange in {"", "TEST", "MANUAL"}:
            return MarketHoursResult(
                True,
                "Market-hours check skipped for manual/test exchange.",
                {"exchange": normalized_exchange or None, "observed_at": observed_at.isoformat(), "known_exchange": False},
            )

        profile = self.EXCHANGE_PROFILES.get(normalized_exchange)
        if profile is None:
            allow_unknown = bool(config.get("allow_unknown_exchanges", True))
            return MarketHoursResult(
                allow_unknown,
                "Unknown exchange allowed by market-hours scaffold." if allow_unknown else "Unknown exchange blocked by market-hours scaffold.",
                {"exchange": normalized_exchange, "observed_at": observed_at.isoformat(), "known_exchange": False},
            )

        timezone_name, open_time, close_time = profile
        local_time = observed_at.astimezone(ZoneInfo(timezone_name))
        holiday_dates = {str(item) for item in config.get("holiday_dates", [])}
        if local_time.date().isoformat() in holiday_dates:
            return MarketHoursResult(
                False,
                "Exchange holiday configured for market-hours scaffold.",
                self._details(normalized_exchange, timezone_name, local_time, open_time, close_time),
            )
        if local_time.weekday() >= 5:
            return MarketHoursResult(
                False,
                "Exchange is closed on weekends.",
                self._details(normalized_exchange, timezone_name, local_time, open_time, close_time),
            )
        opened = open_time <= local_time.time() <= close_time
        return MarketHoursResult(
            opened,
            "Within configured exchange session." if opened else "Outside configured exchange session.",
            self._details(normalized_exchange, timezone_name, local_time, open_time, close_time),
        )

    def _details(
        self,
        exchange: str,
        timezone_name: str,
        local_time: datetime,
        open_time: time,
        close_time: time,
    ) -> dict:
        return {
            "exchange": exchange,
            "timezone": timezone_name,
            "local_time": local_time.isoformat(),
            "session_open": open_time.isoformat(timespec="minutes"),
            "session_close": close_time.isoformat(timespec="minutes"),
            "known_exchange": True,
        }


market_hours_service = MarketHoursService()
