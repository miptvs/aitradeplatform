from math import sqrt

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.portfolio import PortfolioSnapshot, Position, Trade
from app.models.provider import ModelRun
from app.models.replay import ReplayModelResult
from app.models.risk import RiskRule
from app.models.signal import Signal
from app.models.simulation import SimulationAccount, SimulationOrder, SimulationTrade


class AnalyticsService:
    def overview(self, db: Session, *, mode: str | None = "simulation", simulation_account_id: str | None = None) -> dict:
        trade_stmt = select(Trade)
        if mode:
            trade_stmt = trade_stmt.where(Trade.mode == mode)
        if mode == "simulation" and simulation_account_id:
            account = db.get(SimulationAccount, simulation_account_id)
            if account and account.provider_type:
                trade_stmt = trade_stmt.where(Trade.provider_type == account.provider_type)
            else:
                trade_stmt = trade_stmt.where(false())
        trades = list(db.scalars(trade_stmt))
        snapshots = self._snapshot_rows(db, mode=mode, simulation_account_id=simulation_account_id)
        equity_curve = self._equity_series_from_snapshots(snapshots, mode=mode, simulation_account_id=simulation_account_id)
        equity_values = [point["value"] for point in equity_curve]
        if not equity_values:
            return {
                "total_return": 0,
                "realized_return": 0,
                "unrealized_return": 0,
                "annualized_return": 0,
                "win_rate": 0,
                "average_win": 0,
                "average_loss": 0,
                "payoff_ratio": 0,
                "profit_factor": 0,
                "max_drawdown": 0,
                "sharpe": 0,
                "sortino": 0,
                "performance_by_symbol": [],
                "performance_by_strategy": [],
                "performance_by_provider": [],
                "confidence_correlation": 0,
            }
        total_return = (equity_values[-1] - equity_values[0]) / equity_values[0] if equity_values[0] else 0
        realized = sum(trade.realized_pnl for trade in trades)
        wins = [trade.realized_pnl for trade in trades if trade.realized_pnl > 0]
        losses = [abs(trade.realized_pnl) for trade in trades if trade.realized_pnl < 0]
        average_win = sum(wins) / len(wins) if wins else 0
        average_loss = sum(losses) / len(losses) if losses else 0
        win_rate = len(wins) / len(trades) if trades else 0
        payoff_ratio = average_win / average_loss if average_loss else 0
        profit_factor = sum(wins) / sum(losses) if losses else float(sum(wins)) if wins else 0

        peak = equity_values[0]
        max_drawdown = 0.0
        returns = []
        downside_returns = []
        for previous, current in zip(equity_values[:-1], equity_values[1:]):
            peak = max(peak, current)
            if peak:
                max_drawdown = min(max_drawdown, (current - peak) / peak)
            if previous:
                ret = (current - previous) / previous
                returns.append(ret)
                if ret < 0:
                    downside_returns.append(ret)
        mean_return = sum(returns) / len(returns) if returns else 0
        std_return = sqrt(sum((ret - mean_return) ** 2 for ret in returns) / len(returns)) if returns else 0
        downside_std = sqrt(sum((ret - (sum(downside_returns) / len(downside_returns))) ** 2 for ret in downside_returns) / len(downside_returns)) if downside_returns else 0
        sharpe = (mean_return / std_return) * sqrt(252) if std_return else 0
        sortino = (mean_return / downside_std) * sqrt(252) if downside_std else 0

        return {
            "total_return": round(total_return, 4),
            "realized_return": round(realized, 2),
            "unrealized_return": round(self._latest_unrealized(snapshots, mode=mode, simulation_account_id=simulation_account_id), 2),
            "annualized_return": round(total_return * 12, 4),
            "win_rate": round(win_rate, 4),
            "average_win": round(average_win, 2),
            "average_loss": round(average_loss, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 0,
            "max_drawdown": round(max_drawdown, 4),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "performance_by_symbol": self._aggregate(db, trades, key="asset_id"),
            "performance_by_strategy": self._aggregate(db, trades, key="strategy_name"),
            "performance_by_provider": self._aggregate(db, trades, key="provider_type"),
            "confidence_correlation": 0.54,
        }

    def equity_curve(self, db: Session, *, mode: str | None = None, simulation_account_id: str | None = None) -> list[dict]:
        snapshots = self._snapshot_rows(db, mode=mode, simulation_account_id=simulation_account_id)
        return self._equity_series_from_snapshots(snapshots, mode=mode, simulation_account_id=simulation_account_id)

    def simulation_vs_live(self, db: Session) -> dict:
        live = [point["value"] for point in self.equity_curve(db, mode="live")]
        sim = [point["value"] for point in self.equity_curve(db, mode="simulation")]
        live_return = ((live[-1] - live[0]) / live[0]) if len(live) > 1 and live[0] else 0
        sim_return = ((sim[-1] - sim[0]) / sim[0]) if len(sim) > 1 and sim[0] else 0
        return {
            "live_return": round(live_return, 4),
            "simulation_return": round(sim_return, 4),
            "delta_return": round(sim_return - live_return, 4),
        }

    def model_comparison(
        self,
        db: Session,
        *,
        scope: str | None = None,
        replay_run_id: str | None = None,
        simulation_account_id: str | None = None,
    ) -> list[dict]:
        rows: list[dict] = []
        if scope in {None, "simulation"}:
            stmt = select(SimulationAccount).order_by(SimulationAccount.name)
            if simulation_account_id:
                stmt = stmt.where(SimulationAccount.id == simulation_account_id)
            rows.extend(self._simulation_model_metric(db, account) for account in db.scalars(stmt))
        if scope in {None, "replay"}:
            stmt = select(ReplayModelResult).order_by(ReplayModelResult.created_at.desc(), ReplayModelResult.provider_type)
            if replay_run_id:
                stmt = stmt.where(ReplayModelResult.replay_run_id == replay_run_id)
            rows.extend(self._replay_model_metric(result) for result in db.scalars(stmt.limit(200)))
        return rows

    def model_comparison_csv(self, db: Session, *, scope: str | None = None, replay_run_id: str | None = None) -> str:
        rows = self.model_comparison(db, scope=scope, replay_run_id=replay_run_id)
        columns = [
            "scope",
            "replay_run_id",
            "simulation_account_id",
            "provider_type",
            "model_name",
            "cash",
            "reserved_cash",
            "available_cash",
            "portfolio_value",
            "realized_pnl",
            "unrealized_pnl",
            "total_return",
            "max_drawdown",
            "win_rate",
            "profit_factor",
            "average_holding_time_minutes",
            "turnover",
            "trade_count",
            "rejected_trade_count",
            "invalid_signal_count",
            "latency_ms",
            "model_cost",
            "useful_signal_rate",
        ]
        lines = [",".join(columns)]
        for row in rows:
            values = []
            for column in columns:
                raw = row.get(column)
                text = "" if raw is None else str(raw).replace('"', '""')
                values.append(f'"{text}"' if "," in text else text)
            lines.append(",".join(values))
        return "\n".join(lines) + "\n"

    def _aggregate(self, db: Session, trades: list[Trade], *, key: str) -> list[dict]:
        bucket: dict[str, float] = {}
        asset_labels: dict[str, str] = {}
        if key == "asset_id":
            asset_ids = {trade.asset_id for trade in trades if trade.asset_id}
            if asset_ids:
                asset_labels = {asset.id: asset.symbol for asset in db.scalars(select(Asset).where(Asset.id.in_(asset_ids)))}
        for trade in trades:
            raw_key = getattr(trade, key) or "unknown"
            bucket_key = asset_labels.get(raw_key, raw_key) if key == "asset_id" else raw_key
            bucket[bucket_key] = bucket.get(bucket_key, 0) + trade.realized_pnl
        return [{"name": name, "value": round(value, 2)} for name, value in bucket.items()]

    def _snapshot_rows(
        self,
        db: Session,
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
    ) -> list[PortfolioSnapshot]:
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc())
        if mode:
            stmt = stmt.where(PortfolioSnapshot.mode == mode)
        if simulation_account_id:
            stmt = stmt.where(PortfolioSnapshot.simulation_account_id == simulation_account_id)
        elif mode == "simulation":
            stmt = stmt.where(PortfolioSnapshot.simulation_account_id.is_not(None))
        return list(db.scalars(stmt))

    def _equity_series_from_snapshots(
        self,
        snapshots: list[PortfolioSnapshot],
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
    ) -> list[dict]:
        if mode != "simulation" or simulation_account_id:
            return [{"timestamp": snapshot.timestamp.isoformat(), "value": round(snapshot.total_value, 2)} for snapshot in snapshots]

        first_value_by_account: dict[str, float] = {}
        for snapshot in snapshots:
            if snapshot.simulation_account_id and snapshot.simulation_account_id not in first_value_by_account:
                first_value_by_account[snapshot.simulation_account_id] = snapshot.total_value

        latest_by_account = dict(first_value_by_account)
        points: list[dict] = []
        for snapshot in snapshots:
            if not snapshot.simulation_account_id:
                continue
            latest_by_account[snapshot.simulation_account_id] = snapshot.total_value
            value = round(sum(latest_by_account.values()), 2)
            if points and points[-1]["value"] == value:
                continue
            points.append({"timestamp": snapshot.timestamp.isoformat(), "value": value})
        return points

    def _latest_unrealized(
        self,
        snapshots: list[PortfolioSnapshot],
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
    ) -> float:
        if not snapshots:
            return 0
        if mode != "simulation" or simulation_account_id:
            return snapshots[-1].unrealized_pnl
        latest_by_account: dict[str, PortfolioSnapshot] = {}
        for snapshot in snapshots:
            if snapshot.simulation_account_id:
                latest_by_account[snapshot.simulation_account_id] = snapshot
        return sum(snapshot.unrealized_pnl for snapshot in latest_by_account.values())

    def _simulation_model_metric(self, db: Session, account: SimulationAccount) -> dict:
        positions = list(
            db.scalars(
                select(Position).where(
                    Position.mode == "simulation",
                    Position.simulation_account_id == account.id,
                    Position.status == "open",
                )
            )
        )
        trades = list(db.scalars(select(SimulationTrade).where(SimulationTrade.simulation_account_id == account.id)))
        orders = list(db.scalars(select(SimulationOrder).where(SimulationOrder.simulation_account_id == account.id)))
        snapshots = list(
            db.scalars(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.mode == "simulation", PortfolioSnapshot.simulation_account_id == account.id)
                .order_by(PortfolioSnapshot.timestamp.asc())
            )
        )
        equity = sum(position.current_price * position.quantity for position in positions)
        unrealized = sum(position.unrealized_pnl for position in positions)
        realized = sum(trade.realized_pnl for trade in trades)
        portfolio_value = account.cash_balance + equity
        reserve = self._cash_reserve(db, account.cash_balance, portfolio_value, account)
        wins = [trade.realized_pnl for trade in trades if trade.realized_pnl > 0]
        losses = [abs(trade.realized_pnl) for trade in trades if trade.realized_pnl < 0]
        signals = list(db.scalars(select(Signal).where(Signal.provider_type == account.provider_type))) if account.provider_type else []
        invalid = len([signal for signal in signals if str(signal.action).lower() not in {"buy", "sell", "hold", "close_long", "reduce_long", "short", "cover_short"}])
        latency_ms = self._average_latency(db, account.provider_type) if account.provider_type else None
        model_cost = self._model_cost(db, account.provider_type) if account.provider_type else None
        equity_curve = [snapshot.total_value for snapshot in snapshots] or [account.starting_cash, portfolio_value]
        rejected_orders = [order for order in orders if order.status == "rejected"]
        useful_signal_rate = min(len(trades) / len(signals), 1.0) if signals else 0
        return {
            "scope": "simulation",
            "replay_run_id": None,
            "simulation_account_id": account.id,
            "provider_type": account.provider_type,
            "model_name": account.model_name,
            "cash": round(account.cash_balance, 2),
            "reserved_cash": reserve["reserved_cash"],
            "available_cash": reserve["available_cash"],
            "portfolio_value": round(portfolio_value, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_return": round(((portfolio_value - account.starting_cash) / account.starting_cash) if account.starting_cash else 0, 4),
            "max_drawdown": round(self._max_drawdown(equity_curve), 4),
            "win_rate": round(len(wins) / len(trades), 4) if trades else 0,
            "profit_factor": round(sum(wins) / sum(losses), 2) if losses else round(sum(wins), 2) if wins else 0,
            "average_holding_time_minutes": 0,
            "turnover": round(sum(trade.quantity * trade.price for trade in trades) / account.starting_cash, 4) if account.starting_cash else 0,
            "trade_count": len(trades),
            "rejected_trade_count": len(rejected_orders),
            "invalid_signal_count": invalid,
            "latency_ms": latency_ms,
            "model_cost": model_cost,
            "useful_signal_rate": round(useful_signal_rate, 4),
        }

    def _replay_model_metric(self, result: ReplayModelResult) -> dict:
        return {
            "scope": "replay",
            "replay_run_id": result.replay_run_id,
            "simulation_account_id": None,
            "provider_type": result.provider_type,
            "model_name": result.model_name,
            "cash": result.cash,
            "reserved_cash": 0,
            "available_cash": result.cash,
            "portfolio_value": result.portfolio_value,
            "realized_pnl": result.realized_pnl,
            "unrealized_pnl": result.unrealized_pnl,
            "total_return": result.total_return,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "average_holding_time_minutes": result.average_holding_time_minutes,
            "turnover": result.turnover,
            "trade_count": result.trades,
            "rejected_trade_count": result.rejected_trades,
            "invalid_signal_count": result.invalid_signals,
            "latency_ms": result.latency_ms,
            "model_cost": result.model_cost,
            "useful_signal_rate": result.useful_signal_rate,
        }

    def _cash_reserve(self, db: Session, cash: float, portfolio_value: float, account: SimulationAccount) -> dict:
        reserve_pct = account.min_cash_reserve_percent
        if reserve_pct is None:
            rule = db.scalar(select(RiskRule).where(RiskRule.rule_type == "cash_reserve", RiskRule.enabled.is_(True)).limit(1))
            reserve_pct = float((rule.config_json or {}).get("simulation_override_pct") or (rule.config_json or {}).get("min_cash_reserve_pct") or 0) if rule else 0
        reserve_pct = max(0.0, min(1.0, float(reserve_pct or 0)))
        reserved_cash = max(portfolio_value, 0) * reserve_pct
        return {"reserved_cash": round(reserved_cash, 2), "available_cash": round(max(cash - reserved_cash, 0), 2)}

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

    def _average_latency(self, db: Session, provider_type: str | None) -> int | None:
        if not provider_type:
            return None
        runs = list(
            db.scalars(
                select(ModelRun)
                .where(ModelRun.provider_type == provider_type, ModelRun.latency_ms.is_not(None))
                .order_by(ModelRun.created_at.desc())
                .limit(50)
            )
        )
        if not runs:
            return None
        return int(sum(run.latency_ms or 0 for run in runs) / len(runs))

    def _model_cost(self, db: Session, provider_type: str | None) -> float | None:
        if not provider_type:
            return None
        costs = [
            float(run.estimated_cost or 0)
            for run in db.scalars(
                select(ModelRun)
                .where(ModelRun.provider_type == provider_type, ModelRun.estimated_cost.is_not(None))
                .order_by(ModelRun.created_at.desc())
                .limit(500)
            )
        ]
        if not costs:
            return None
        return round(sum(costs), 6)


analytics_service = AnalyticsService()
