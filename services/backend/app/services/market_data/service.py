import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from urllib.parse import quote_plus

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.asset import Asset, MarketSnapshot
from app.services.brokers.service import broker_service
from app.utils.serialization import to_plain_dict
from app.utils.time import utcnow


class MarketDataService:
    def list_assets(self, db: Session) -> list[Asset]:
        return list(db.scalars(select(Asset).order_by(Asset.symbol)))

    def search_assets(self, db: Session, query: str) -> dict:
        normalized = query.strip().upper()
        if not normalized:
            return {
                "query": query,
                "validation_source": None,
                "validation_status": "local_only",
                "message": "Showing assets already stored in this workspace.",
                "results": self._local_search_results(db, ""),
            }

        local_results = self._local_search_results(db, normalized)
        results = list(local_results)
        seen_symbols = {item["symbol"] for item in results}
        has_exact_local = any(item["symbol"] == normalized for item in local_results)

        if has_exact_local:
            return {
                "query": normalized,
                "validation_source": "local",
                "validation_status": "local_only",
                "message": "Found an exact local asset match in this workspace.",
                "results": results[:8],
            }

        lookup = broker_service.search_instruments(db, "trading212", normalized)
        if lookup["success"]:
            for match in lookup["data"].get("matches", []):
                if match["symbol"] in seen_symbols:
                    continue
                results.append(
                    {
                        "key": f"trading212:{match['broker_ticker'] or match['symbol']}",
                        "asset_id": None,
                        "symbol": match["symbol"],
                        "display_symbol": match["display_symbol"],
                        "name": match["name"],
                        "asset_type": match["asset_type"],
                        "exchange": match.get("exchange"),
                        "currency": match["currency"],
                        "latest_price": match.get("latest_price"),
                        "source": match["source"],
                        "source_label": match["source_label"],
                        "verified": match.get("verified", True),
                        "broker_ticker": match.get("broker_ticker"),
                    }
                )
                seen_symbols.add(match["symbol"])

            validation_status = "verified" if lookup["data"].get("matches") else "no_match"
            message = lookup["message"]
        else:
            validation_status = "unavailable"
            message = lookup["message"]

        if not results and validation_status == "unavailable":
            message = f"No local match yet. {message}"
        elif not results and validation_status == "no_match":
            message = f"Trading212 did not confirm an accessible instrument for {normalized}."

        return {
            "query": normalized,
            "validation_source": "trading212",
            "validation_status": validation_status,
            "message": message,
            "results": results[:8],
        }

    def list_asset_views(self, db: Session) -> list[dict]:
        assets = self.list_assets(db)
        views: list[dict] = []
        for asset in assets:
            latest = db.scalar(
                select(MarketSnapshot)
                .where(MarketSnapshot.asset_id == asset.id)
                .order_by(desc(MarketSnapshot.timestamp))
                .limit(1)
            )
            views.append(
                {
                    **to_plain_dict(asset),
                    "latest_price": latest.close_price if latest else None,
                }
            )
        return views

    def get_asset_by_symbol(self, db: Session, symbol: str) -> Asset | None:
        normalized = symbol.strip().upper()
        if not normalized:
            return None
        return db.scalar(select(Asset).where(Asset.symbol == normalized))

    def get_or_create_manual_asset(
        self,
        db: Session,
        *,
        symbol: str,
        name: str | None = None,
        asset_type: str = "stock",
        currency: str = "USD",
        exchange: str | None = None,
    ) -> Asset:
        normalized = symbol.strip().upper()
        existing = self.get_asset_by_symbol(db, normalized)
        if existing is not None:
            return existing

        asset = Asset(
            symbol=normalized,
            name=(name or normalized).strip() or normalized,
            asset_type=asset_type,
            exchange=exchange or "MANUAL",
            currency=currency or "USD",
        )
        db.add(asset)
        db.flush()
        return asset

    def record_manual_price(self, db: Session, *, asset_id: str, price: float, source: str = "manual") -> MarketSnapshot:
        snapshot = MarketSnapshot(
            asset_id=asset_id,
            timestamp=utcnow(),
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=0,
            source=source,
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    def list_latest_snapshots(self, db: Session, limit: int = 50) -> list[MarketSnapshot]:
        return list(db.scalars(select(MarketSnapshot).order_by(desc(MarketSnapshot.timestamp)).limit(limit)))

    def get_latest_price(self, db: Session, asset_id: str) -> float:
        snapshot = db.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.asset_id == asset_id)
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(1)
        )
        if snapshot is None:
            raise ValueError("No market data for asset")
        return snapshot.close_price

    def get_history(self, db: Session, asset_id: str, limit: int = 60) -> list[MarketSnapshot]:
        snapshots = list(
            db.scalars(
                select(MarketSnapshot)
                .where(MarketSnapshot.asset_id == asset_id)
                .order_by(desc(MarketSnapshot.timestamp))
                .limit(limit)
            )
        )
        snapshots.reverse()
        return snapshots

    def refresh_market_data(self, db: Session) -> dict:
        assets = list(db.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.symbol)))
        snapshots_created = 0
        snapshots_updated = 0
        assets_refreshed = 0
        assets_failed = 0
        errors: list[str] = []

        for asset in assets:
            try:
                created, updated = self._refresh_asset_history(db, asset)
                snapshots_created += created
                snapshots_updated += updated
                if created or updated:
                    assets_refreshed += 1
            except Exception as exc:
                assets_failed += 1
                errors.append(f"{asset.symbol}: {exc}")

        db.flush()
        return {
            "snapshots_created": snapshots_created,
            "snapshots_updated": snapshots_updated,
            "assets_refreshed": assets_refreshed,
            "assets_failed": assets_failed,
            "errors": errors[:10],
        }

    def refresh_demo_market_data(self, db: Session) -> int:
        report = self.refresh_market_data(db)
        return int(report["snapshots_created"]) + int(report["snapshots_updated"])

    def _refresh_asset_history(self, db: Session, asset: Asset, lookback_days: int = 120) -> tuple[int, int]:
        rows = self._fetch_remote_history(asset)
        if not rows:
            return 0, 0

        history_start = utcnow() - timedelta(days=lookback_days)
        existing_snapshots = list(
            db.scalars(
                select(MarketSnapshot)
                .where(MarketSnapshot.asset_id == asset.id, MarketSnapshot.timestamp >= history_start)
                .order_by(MarketSnapshot.timestamp)
            )
        )
        snapshots_by_day = {self._snapshot_day(snapshot.timestamp): snapshot for snapshot in existing_snapshots}

        created = 0
        updated = 0
        for row in rows:
            snapshot_day = row["date"]
            if snapshot_day is None:
                continue

            timestamp = self._market_timestamp(snapshot_day)
            payload = {
                "open_price": row["open_price"],
                "high_price": row["high_price"],
                "low_price": row["low_price"],
                "close_price": row["close_price"],
                "volume": row["volume"],
                "source": row["source"],
            }
            existing = snapshots_by_day.get(snapshot_day)
            if existing is None:
                db.add(MarketSnapshot(asset_id=asset.id, timestamp=timestamp, **payload))
                created += 1
                continue

            if self._is_manual_source(existing.source):
                continue

            changed = existing.timestamp != timestamp
            for field, value in payload.items():
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            if changed:
                existing.timestamp = timestamp
                updated += 1

        db.flush()
        return created, updated

    def _fetch_remote_history(self, asset: Asset) -> list[dict]:
        try:
            return self._fetch_yahoo_history(asset)
        except Exception:
            return self._fetch_stooq_history(asset)

    def _fetch_yahoo_history(self, asset: Asset) -> list[dict]:
        symbol = self._yahoo_symbol(asset)
        response = httpx.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(symbol)}?range=6mo&interval=1d&includePrePost=false",
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        payload = response.json()
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if not result:
            return []

        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        rows: list[dict] = []
        for idx, timestamp in enumerate(timestamps):
            try:
                open_price = float(opens[idx])
                high_price = float(highs[idx])
                low_price = float(lows[idx])
                close_price = float(closes[idx])
                volume = float(volumes[idx] or 0)
            except Exception:
                continue

            if min(open_price, high_price, low_price, close_price) <= 0:
                continue

            rows.append(
                {
                    "date": datetime.fromtimestamp(timestamp, tz=timezone.utc).date(),
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": close_price,
                    "volume": volume,
                    "source": "yahoo-chart",
                }
            )
        return rows

    def _fetch_stooq_history(self, asset: Asset) -> list[dict]:
        symbol = self._stooq_symbol(asset)
        response = httpx.get(
            f"https://stooq.com/q/d/l/?s={symbol}&i=d",
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "ai-trader-platform/0.1"},
        )
        response.raise_for_status()
        return self._parse_stooq_csv(response.text)

    def _parse_stooq_csv(self, document: str) -> list[dict]:
        if not document.strip() or "No data" in document:
            return []

        reader = csv.DictReader(StringIO(document))
        rows: list[dict] = []
        for row in reader:
            try:
                snapshot_day = date.fromisoformat((row.get("Date") or "").strip())
                open_price = float(row.get("Open") or 0)
                high_price = float(row.get("High") or 0)
                low_price = float(row.get("Low") or 0)
                close_price = float(row.get("Close") or 0)
                volume = float(row.get("Volume") or 0)
            except Exception:
                continue

            if min(open_price, high_price, low_price, close_price) <= 0:
                continue

            rows.append(
                {
                    "date": snapshot_day,
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": close_price,
                    "volume": volume,
                    "source": "stooq-daily",
                }
            )

        return rows

    def _stooq_symbol(self, asset: Asset) -> str:
        normalized = asset.symbol.strip().lower()
        if "." in normalized:
            return normalized

        exchange = (asset.exchange or "").upper()
        if exchange in {"NASDAQ", "NYSE", "NYSEARCA", "AMEX", "BATS"} or asset.currency.upper() == "USD":
            return f"{normalized}.us"
        return normalized

    def _yahoo_symbol(self, asset: Asset) -> str:
        return asset.symbol.strip().upper()

    def _snapshot_day(self, timestamp: datetime) -> date:
        if timestamp.tzinfo is None:
            return timestamp.date()
        return timestamp.astimezone(timezone.utc).date()

    def _market_timestamp(self, snapshot_day: date) -> datetime:
        return datetime.combine(snapshot_day, time(hour=20, minute=0, tzinfo=timezone.utc))

    def _is_manual_source(self, source: str | None) -> bool:
        normalized = (source or "").lower()
        return normalized.startswith("manual")

    def _local_search_results(self, db: Session, query: str, limit: int = 8) -> list[dict]:
        query_lower = query.lower()
        results: list[dict] = []
        for asset in self.list_asset_views(db):
            haystack = f"{asset['symbol']} {asset['name']}".lower()
            if query and query_lower not in haystack:
                continue
            results.append(
                {
                    "key": f"local:{asset['id']}",
                    "asset_id": asset["id"],
                    "symbol": asset["symbol"],
                    "display_symbol": asset["symbol"],
                    "name": asset["name"],
                    "asset_type": asset["asset_type"],
                    "exchange": asset.get("exchange"),
                    "currency": asset["currency"],
                    "latest_price": asset.get("latest_price"),
                    "source": "local",
                    "source_label": "Local asset",
                    "verified": True,
                    "broker_ticker": None,
                }
            )
            if len(results) >= limit:
                break
        return results


market_data_service = MarketDataService()
