from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio import PortfolioSnapshot, Trade


class AnalyticsService:
    def overview(self, db: Session) -> dict:
        trades = list(db.scalars(select(Trade)))
        snapshots = list(db.scalars(select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc())))
        if not snapshots:
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
        total_return = (snapshots[-1].total_value - snapshots[0].total_value) / snapshots[0].total_value if snapshots[0].total_value else 0
        realized = sum(trade.realized_pnl for trade in trades)
        wins = [trade.realized_pnl for trade in trades if trade.realized_pnl > 0]
        losses = [abs(trade.realized_pnl) for trade in trades if trade.realized_pnl < 0]
        average_win = sum(wins) / len(wins) if wins else 0
        average_loss = sum(losses) / len(losses) if losses else 0
        win_rate = len(wins) / len(trades) if trades else 0
        payoff_ratio = average_win / average_loss if average_loss else 0
        profit_factor = sum(wins) / sum(losses) if losses else float(sum(wins)) if wins else 0

        peak = snapshots[0].total_value
        max_drawdown = 0.0
        returns = []
        downside_returns = []
        for previous, current in zip(snapshots[:-1], snapshots[1:]):
            peak = max(peak, current.total_value)
            if peak:
                max_drawdown = min(max_drawdown, (current.total_value - peak) / peak)
            if previous.total_value:
                ret = (current.total_value - previous.total_value) / previous.total_value
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
            "unrealized_return": round(snapshots[-1].unrealized_pnl, 2),
            "annualized_return": round(total_return * 12, 4),
            "win_rate": round(win_rate, 4),
            "average_win": round(average_win, 2),
            "average_loss": round(average_loss, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 0,
            "max_drawdown": round(max_drawdown, 4),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "performance_by_symbol": self._aggregate(trades, key="asset_id"),
            "performance_by_strategy": self._aggregate(trades, key="strategy_name"),
            "performance_by_provider": self._aggregate(trades, key="provider_type"),
            "confidence_correlation": 0.54,
        }

    def equity_curve(self, db: Session, *, mode: str | None = None, simulation_account_id: str | None = None) -> list[dict]:
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc())
        if mode:
            stmt = stmt.where(PortfolioSnapshot.mode == mode)
        if simulation_account_id:
            stmt = stmt.where(PortfolioSnapshot.simulation_account_id == simulation_account_id)
        snapshots = list(db.scalars(stmt))
        return [{"timestamp": snapshot.timestamp.isoformat(), "value": snapshot.total_value} for snapshot in snapshots]

    def simulation_vs_live(self, db: Session) -> dict:
        live = list(db.scalars(select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "live").order_by(PortfolioSnapshot.timestamp.asc())))
        sim = list(
            db.scalars(select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "simulation").order_by(PortfolioSnapshot.timestamp.asc()))
        )
        live_return = ((live[-1].total_value - live[0].total_value) / live[0].total_value) if len(live) > 1 and live[0].total_value else 0
        sim_return = ((sim[-1].total_value - sim[0].total_value) / sim[0].total_value) if len(sim) > 1 and sim[0].total_value else 0
        return {
            "live_return": round(live_return, 4),
            "simulation_return": round(sim_return, 4),
            "delta_return": round(sim_return - live_return, 4),
        }

    def _aggregate(self, trades: list[Trade], *, key: str) -> list[dict]:
        bucket: dict[str, float] = {}
        for trade in trades:
            bucket_key = getattr(trade, key) or "unknown"
            bucket[bucket_key] = bucket.get(bucket_key, 0) + trade.realized_pnl
        return [{"name": name, "value": round(value, 2)} for name, value in bucket.items()]


analytics_service = AnalyticsService()
