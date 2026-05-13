from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.asset import Asset, MarketSnapshot
from app.models.news import NewsArticle
from app.models.provider import ModelRun
from app.models.replay import ReplayModelResult, ReplayRun
from app.models.signal import Signal
from app.schemas.replay import ReplayRunCreate
from app.services.audit.service import audit_service
from app.services.providers.service import provider_service
from app.utils.time import utcnow


VALID_REPLAY_ACTIONS = {"buy", "sell", "hold", "close_long", "reduce_long", "short", "cover_short"}


@dataclass
class ReplayPosition:
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    opened_at: datetime | None = None


@dataclass
class ReplayLedger:
    cash: float
    starting_cash: float
    fees_bps: float
    slippage_bps: float
    cash_reserve_percent: float
    short_enabled: bool
    enforce_market_hours: bool
    positions: dict[str, ReplayPosition] = field(default_factory=dict)
    realized_pnl: float = 0.0
    trades: int = 0
    rejected_trades: int = 0
    invalid_signals: int = 0
    useful_signals: int = 0
    directional_signals: int = 0
    turnover: float = 0.0
    wins: list[float] = field(default_factory=list)
    losses: list[float] = field(default_factory=list)
    holding_minutes: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)


class ReplayService:
    def list_runs(self, db: Session) -> list[dict[str, Any]]:
        runs = list(db.scalars(select(ReplayRun).order_by(desc(ReplayRun.created_at)).limit(50)))
        return [self._run_view(db, run) for run in runs]

    def get_run(self, db: Session, replay_run_id: str) -> dict[str, Any]:
        run = db.get(ReplayRun, replay_run_id)
        if run is None:
            raise ValueError("Replay run not found")
        return self._run_view(db, run)

    def create_run(self, db: Session, payload: ReplayRunCreate) -> dict[str, Any]:
        if payload.date_end <= payload.date_start:
            raise ValueError("Replay end date must be after start date.")
        model_keys = payload.selected_models or self._default_simulation_models(db)
        if not model_keys:
            raise ValueError("Select at least one simulation model/provider for replay.")
        symbols = [symbol.upper() for symbol in payload.symbols] or self._default_symbols(db)
        if not symbols:
            raise ValueError("Select at least one symbol or seed assets before running replay.")
        enforce_market_hours = bool(payload.config_json.get("enforce_market_hours", False))

        run = ReplayRun(
            name=payload.name or f"Replay {payload.date_start.date()} to {payload.date_end.date()}",
            status="running",
            started_at=utcnow(),
            date_start=payload.date_start,
            date_end=payload.date_end,
            starting_cash=payload.starting_cash,
            fees_bps=payload.fees_bps,
            slippage_bps=payload.slippage_bps,
            cash_reserve_percent=payload.cash_reserve_percent,
            short_enabled=payload.short_enabled,
            selected_models=model_keys,
            symbols=symbols,
            config_json={
                **payload.config_json,
                "enforce_market_hours": enforce_market_hours,
                "execution_model": "scaffold",
                "future_leakage_guard": "prices/signals are read at or before each replay timestamp only",
            },
            notes=payload.notes or "Replay/backtest scaffold using stored market snapshots and stored model signals.",
        )
        db.add(run)
        db.flush()

        assets = list(db.scalars(select(Asset).where(Asset.symbol.in_(symbols))))
        input_manifest = self._input_manifest(db, run, assets)
        for provider_type in model_keys:
            result = self._run_model_replay(db, run, provider_type, assets, input_manifest)
            db.add(result)

        run.status = "completed"
        run.completed_at = utcnow()
        audit_service.log(
            db,
            actor="system",
            action="replay.run.create",
            target_type="replay_run",
            target_id=run.id,
            mode="simulation",
            details={
                "models": model_keys,
                "symbols": symbols,
                "starting_cash": payload.starting_cash,
                "cash_reserve_percent": payload.cash_reserve_percent,
                "short_enabled": payload.short_enabled,
            },
        )
        db.flush()
        return self._run_view(db, run)

    def _run_model_replay(
        self,
        db: Session,
        run: ReplayRun,
        provider_type: str,
        assets: list[Asset],
        input_manifest: dict[str, Any],
    ) -> ReplayModelResult:
        config = provider_service.get_config(db, provider_type)
        ledger = ReplayLedger(
            cash=run.starting_cash,
            starting_cash=run.starting_cash,
            fees_bps=run.fees_bps,
            slippage_bps=run.slippage_bps,
            cash_reserve_percent=run.cash_reserve_percent,
            short_enabled=run.short_enabled,
            enforce_market_hours=bool(run.config_json.get("enforce_market_hours", False)),
            equity_curve=[run.starting_cash],
        )
        asset_by_id = {asset.id: asset for asset in assets}
        signals = list(
            db.scalars(
                select(Signal)
                .where(
                    Signal.provider_type == provider_type,
                    Signal.asset_id.in_(list(asset_by_id.keys())),
                    Signal.occurred_at >= run.date_start,
                    Signal.occurred_at <= run.date_end,
                    Signal.source_kind == "agent",
                )
                .order_by(Signal.occurred_at.asc(), Signal.created_at.asc())
            )
        )
        for signal in signals:
            action = self._normalize_action(signal.action)
            if action == "hold":
                continue
            ledger.directional_signals += 1
            if action not in VALID_REPLAY_ACTIONS:
                ledger.invalid_signals += 1
                continue
            asset = asset_by_id.get(signal.asset_id)
            if asset is None:
                ledger.invalid_signals += 1
                continue
            if ledger.enforce_market_hours:
                from app.services.market_hours.service import market_hours_service

                hours = market_hours_service.check_asset(asset, at=signal.occurred_at, config=run.config_json)
                if not hours.is_open:
                    ledger.rejected_trades += 1
                    continue
            price = self._price_at_or_before(db, asset.id, signal.occurred_at)
            if price is None or price <= 0:
                ledger.rejected_trades += 1
                continue
            if self._apply_signal(ledger, asset.symbol, action, price, signal.occurred_at):
                ledger.useful_signals += 1
                ledger.equity_curve.append(self._portfolio_value(db, ledger, assets, signal.occurred_at))

        final_value = self._portfolio_value(db, ledger, assets, run.date_end)
        ledger.equity_curve.append(final_value)
        max_drawdown = self._max_drawdown(ledger.equity_curve)
        returns = self._returns(ledger.equity_curve)
        gross_profit = sum(ledger.wins)
        gross_loss = sum(abs(loss) for loss in ledger.losses)
        useful_rate = ledger.useful_signals / ledger.directional_signals if ledger.directional_signals else 0
        latency_ms = self._average_latency(db, provider_type, run.date_start, run.date_end)
        model_cost = self._model_cost(db, provider_type, run.date_start, run.date_end)
        metrics = {
            "scaffold": True,
            "limited_historical_data": True,
            "chronological_input_count": input_manifest["chronological_input_count"],
            "market_snapshot_count": input_manifest["market_snapshot_count"],
            "news_count": input_manifest["news_count"],
            "input_hash": input_manifest["input_hash"],
            "future_leakage_guard": "No price after the signal timestamp is used for fills.",
            "signals_considered": len(signals),
            "directional_signals": ledger.directional_signals,
            "enforce_market_hours": ledger.enforce_market_hours,
        }
        return ReplayModelResult(
            replay_run_id=run.id,
            provider_type=provider_type,
            model_name=config.default_model if config else None,
            status="completed",
            cash=round(ledger.cash, 2),
            portfolio_value=round(final_value, 2),
            realized_pnl=round(ledger.realized_pnl, 2),
            unrealized_pnl=round(final_value - ledger.cash - ledger.realized_pnl, 2),
            total_return=round(((final_value - run.starting_cash) / run.starting_cash) if run.starting_cash else 0, 4),
            max_drawdown=round(max_drawdown, 4),
            sharpe=round(self._sharpe(returns), 2),
            sortino=round(self._sortino(returns), 2),
            win_rate=round(len(ledger.wins) / ledger.trades if ledger.trades else 0, 4),
            profit_factor=round(gross_profit / gross_loss if gross_loss else gross_profit if gross_profit else 0, 2),
            average_holding_time_minutes=round(sum(ledger.holding_minutes) / len(ledger.holding_minutes), 2)
            if ledger.holding_minutes
            else 0,
            turnover=round(ledger.turnover / run.starting_cash if run.starting_cash else 0, 4),
            trades=ledger.trades,
            rejected_trades=ledger.rejected_trades,
            invalid_signals=ledger.invalid_signals,
            useful_signal_rate=round(useful_rate, 4),
            latency_ms=latency_ms,
            model_cost=model_cost,
            metrics_json=metrics,
        )

    def _apply_signal(self, ledger: ReplayLedger, symbol: str, action: str, price: float, timestamp: datetime) -> bool:
        position = ledger.positions.setdefault(symbol, ReplayPosition())
        portfolio_value = ledger.cash + sum(pos.quantity * pos.avg_entry_price for pos in ledger.positions.values())
        reserve_amount = max(portfolio_value, 0) * ledger.cash_reserve_percent
        available_cash = max(ledger.cash - reserve_amount, 0)
        default_notional = max(min(available_cash, ledger.starting_cash * 0.1), 0)
        slip = price * (ledger.slippage_bps / 10_000)

        if action == "buy":
            if default_notional <= 0:
                ledger.rejected_trades += 1
                return False
            fill_price = price + slip
            quantity = default_notional / fill_price
            fees = default_notional * (ledger.fees_bps / 10_000)
            if ledger.cash < default_notional + fees:
                ledger.rejected_trades += 1
                return False
            if position.quantity < 0:
                ledger.rejected_trades += 1
                return False
            new_qty = position.quantity + quantity
            position.avg_entry_price = ((position.quantity * position.avg_entry_price) + (quantity * fill_price)) / new_qty
            position.quantity = new_qty
            position.opened_at = position.opened_at or timestamp
            ledger.cash -= default_notional + fees
            ledger.turnover += default_notional
            ledger.trades += 1
            return True

        if action == "short":
            if not ledger.short_enabled or default_notional <= 0 or position.quantity > 0:
                ledger.rejected_trades += 1
                return False
            fill_price = price - slip
            quantity = default_notional / fill_price
            fees = default_notional * (ledger.fees_bps / 10_000)
            existing_qty = abs(position.quantity)
            new_qty = existing_qty + quantity
            position.avg_entry_price = ((existing_qty * position.avg_entry_price) + (quantity * fill_price)) / new_qty
            position.quantity = -new_qty
            position.opened_at = position.opened_at or timestamp
            ledger.cash += default_notional - fees
            ledger.turnover += default_notional
            ledger.trades += 1
            return True

        if action in {"sell", "close_long", "reduce_long"}:
            if position.quantity <= 0:
                ledger.rejected_trades += 1
                return False
            close_qty = position.quantity
            if action == "reduce_long":
                close_qty = max(position.quantity * 0.5, 0)
            return self._close_long(ledger, position, close_qty, price - slip, timestamp)

        if action == "cover_short":
            if position.quantity >= 0:
                ledger.rejected_trades += 1
                return False
            return self._cover_short(ledger, position, abs(position.quantity), price + slip, timestamp)

        return False

    def _close_long(self, ledger: ReplayLedger, position: ReplayPosition, quantity: float, fill_price: float, timestamp: datetime) -> bool:
        notional = fill_price * quantity
        fees = notional * (ledger.fees_bps / 10_000)
        realized = (fill_price - position.avg_entry_price) * quantity - fees
        ledger.cash += notional - fees
        ledger.realized_pnl += realized
        ledger.turnover += notional
        ledger.trades += 1
        self._record_closed_trade(ledger, position, realized, timestamp)
        position.quantity = round(position.quantity - quantity, 8)
        if position.quantity <= 0:
            position.quantity = 0
            position.avg_entry_price = 0
            position.opened_at = None
        return True

    def _cover_short(self, ledger: ReplayLedger, position: ReplayPosition, quantity: float, fill_price: float, timestamp: datetime) -> bool:
        notional = fill_price * quantity
        fees = notional * (ledger.fees_bps / 10_000)
        if ledger.cash < notional + fees:
            ledger.rejected_trades += 1
            return False
        realized = (position.avg_entry_price - fill_price) * quantity - fees
        ledger.cash -= notional + fees
        ledger.realized_pnl += realized
        ledger.turnover += notional
        ledger.trades += 1
        self._record_closed_trade(ledger, position, realized, timestamp)
        position.quantity = round(position.quantity + quantity, 8)
        if position.quantity >= 0:
            position.quantity = 0
            position.avg_entry_price = 0
            position.opened_at = None
        return True

    def _record_closed_trade(self, ledger: ReplayLedger, position: ReplayPosition, realized: float, timestamp: datetime) -> None:
        if realized >= 0:
            ledger.wins.append(realized)
        else:
            ledger.losses.append(realized)
        if position.opened_at:
            ledger.holding_minutes.append(max((timestamp - position.opened_at).total_seconds() / 60, 0))

    def _portfolio_value(self, db: Session, ledger: ReplayLedger, assets: list[Asset], timestamp: datetime) -> float:
        value = ledger.cash
        for asset in assets:
            position = ledger.positions.get(asset.symbol)
            if position is None or position.quantity == 0:
                continue
            price = self._price_at_or_before(db, asset.id, timestamp) or position.avg_entry_price
            value += position.quantity * price
        return value

    def _price_at_or_before(self, db: Session, asset_id: str, timestamp: datetime) -> float | None:
        snapshot = db.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.asset_id == asset_id, MarketSnapshot.timestamp <= timestamp)
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(1)
        )
        return float(snapshot.close_price) if snapshot else None

    def _input_manifest(self, db: Session, run: ReplayRun, assets: list[Asset]) -> dict[str, Any]:
        asset_ids = [asset.id for asset in assets]
        market_snapshots = list(
            db.scalars(
                select(MarketSnapshot)
                .where(
                    MarketSnapshot.asset_id.in_(asset_ids),
                    MarketSnapshot.timestamp >= run.date_start,
                    MarketSnapshot.timestamp <= run.date_end,
                )
                .order_by(MarketSnapshot.timestamp.asc())
            )
        )
        news = list(
            db.scalars(
                select(NewsArticle)
                .where(NewsArticle.published_at >= run.date_start, NewsArticle.published_at <= run.date_end)
                .order_by(NewsArticle.published_at.asc())
                .limit(500)
            )
        )
        hash_input = "|".join(
            [
                *(f"m:{item.asset_id}:{item.timestamp.isoformat()}:{item.close_price}" for item in market_snapshots),
                *(f"n:{item.id}:{item.published_at.isoformat()}" for item in news),
            ]
        )
        return {
            "market_snapshot_count": len(market_snapshots),
            "news_count": len(news),
            "chronological_input_count": len(market_snapshots) + len(news),
            "input_hash": hashlib.sha256(hash_input.encode("utf-8")).hexdigest() if hash_input else "empty",
        }

    def _default_simulation_models(self, db: Session) -> list[str]:
        models = []
        for config in provider_service.list_configs(db):
            try:
                profile = provider_service.get_profile(config.provider_type)
            except ValueError:
                continue
            if profile.trading_mode == "simulation" and config.enabled:
                models.append(config.provider_type)
        return models

    def _default_symbols(self, db: Session) -> list[str]:
        return [asset.symbol for asset in db.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.symbol).limit(8))]

    def _run_view(self, db: Session, run: ReplayRun) -> dict[str, Any]:
        results = list(
            db.scalars(select(ReplayModelResult).where(ReplayModelResult.replay_run_id == run.id).order_by(ReplayModelResult.provider_type.asc()))
        )
        return {
            **{column.name: getattr(run, column.name) for column in run.__table__.columns},
            "results": results,
        }

    def _normalize_action(self, action: str) -> str:
        candidate = str(action or "hold").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "long": "buy",
            "open_long": "buy",
            "exit": "close_long",
            "close": "close_long",
            "close_position": "close_long",
            "reduce": "reduce_long",
            "trim": "reduce_long",
            "bearish": "sell",
            "buy_to_cover": "cover_short",
            "cover": "cover_short",
        }
        return aliases.get(candidate, candidate)

    def _returns(self, values: list[float]) -> list[float]:
        returns = []
        for previous, current in zip(values[:-1], values[1:]):
            if previous:
                returns.append((current - previous) / previous)
        return returns

    def _max_drawdown(self, values: list[float]) -> float:
        if not values:
            return 0
        peak = values[0]
        drawdown = 0.0
        for value in values:
            peak = max(peak, value)
            if peak:
                drawdown = min(drawdown, (value - peak) / peak)
        return drawdown

    def _sharpe(self, returns: list[float]) -> float:
        if not returns:
            return 0
        mean_return = sum(returns) / len(returns)
        variance = sum((item - mean_return) ** 2 for item in returns) / len(returns)
        std = math.sqrt(variance)
        return (mean_return / std) * math.sqrt(252) if std else 0

    def _sortino(self, returns: list[float]) -> float:
        downside = [item for item in returns if item < 0]
        if not downside:
            return 0
        mean_return = sum(returns) / len(returns) if returns else 0
        downside_mean = sum(downside) / len(downside)
        downside_std = math.sqrt(sum((item - downside_mean) ** 2 for item in downside) / len(downside))
        return (mean_return / downside_std) * math.sqrt(252) if downside_std else 0

    def _average_latency(self, db: Session, provider_type: str, date_start: datetime, date_end: datetime) -> int | None:
        runs = list(
            db.scalars(
                select(ModelRun)
                .where(
                    ModelRun.provider_type == provider_type,
                    ModelRun.created_at >= date_start,
                    ModelRun.created_at <= date_end,
                    ModelRun.latency_ms.is_not(None),
                )
                .order_by(desc(ModelRun.created_at))
                .limit(100)
            )
        )
        if not runs:
            return None
        return int(sum(run.latency_ms or 0 for run in runs) / len(runs))

    def _model_cost(self, db: Session, provider_type: str, date_start: datetime, date_end: datetime) -> float | None:
        runs = list(
            db.scalars(
                select(ModelRun)
                .where(
                    ModelRun.provider_type == provider_type,
                    ModelRun.created_at >= date_start,
                    ModelRun.created_at <= date_end,
                    ModelRun.estimated_cost.is_not(None),
                )
                .order_by(desc(ModelRun.created_at))
                .limit(500)
            )
        )
        if not runs:
            return None
        return round(sum(float(run.estimated_cost or 0) for run in runs), 6)


replay_service = ReplayService()
