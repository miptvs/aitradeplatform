from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.portfolio import Fill, PortfolioSnapshot, Position, Trade
from app.models.simulation import SimulationAccount, SimulationOrder, SimulationTrade
from app.schemas.simulation import SimulationAccountCreate, SimulationAccountUpdate
from app.services.events.service import publish_event
from app.services.market_data.service import market_data_service
from app.utils.time import utcnow


class SimulationService:
    def list_accounts(self, db: Session) -> list[SimulationAccount]:
        return list(db.scalars(select(SimulationAccount).order_by(SimulationAccount.name)))

    def get_account(self, db: Session, account_id: str) -> SimulationAccount | None:
        return db.get(SimulationAccount, account_id)

    def create_account(self, db: Session, payload: SimulationAccountCreate) -> SimulationAccount:
        account = SimulationAccount(
            name=payload.name,
            starting_cash=payload.starting_cash,
            cash_balance=payload.starting_cash,
            fees_bps=payload.fees_bps,
            slippage_bps=payload.slippage_bps,
            latency_ms=payload.latency_ms,
        )
        db.add(account)
        db.flush()
        self.create_snapshot(db, account)
        return account

    def update_account(self, db: Session, account_id: str, payload: SimulationAccountUpdate) -> SimulationAccount:
        account = self.get_account(db, account_id)
        if account is None:
            raise ValueError("Simulation account not found")
        updates = payload.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in updates.items():
            setattr(account, key, value)
        db.flush()
        return account

    def reset_account(self, db: Session, account_id: str) -> SimulationAccount:
        account = self.get_account(db, account_id)
        if account is None:
            raise ValueError("Simulation account not found")
        for position in list(
            db.scalars(select(Position).where(Position.simulation_account_id == account_id, Position.mode == "simulation"))
        ):
            db.delete(position)
        for order in list(db.scalars(select(SimulationOrder).where(SimulationOrder.simulation_account_id == account_id))):
            db.delete(order)
        for trade in list(db.scalars(select(SimulationTrade).where(SimulationTrade.simulation_account_id == account_id))):
            db.delete(trade)
        for snapshot in list(
            db.scalars(
                select(PortfolioSnapshot).where(
                    PortfolioSnapshot.mode == "simulation",
                    PortfolioSnapshot.simulation_account_id == account_id,
                )
            )
        ):
            db.delete(snapshot)
        account.cash_balance = account.starting_cash
        account.reset_count += 1
        db.flush()
        self.create_snapshot(db, account)
        return account

    def execute_order_from_order(self, db: Session, *, order, simulation_account_id: str):
        account = self.get_account(db, simulation_account_id)
        if account is None:
            raise ValueError("Simulation account not found")
        base_price = order.requested_price or market_data_service.get_latest_price(db, order.asset_id)
        slip = base_price * (account.slippage_bps / 10_000)
        executed_price = round(base_price + slip if order.side == "buy" else base_price - slip, 4)
        fees = round(executed_price * order.quantity * (account.fees_bps / 10_000), 4)
        sim_order = SimulationOrder(
            simulation_account_id=account.id,
            asset_id=order.asset_id,
            signal_id=order.signal_id,
            side=order.side,
            quantity=order.quantity,
            requested_price=base_price,
            executed_price=executed_price,
            fees=fees,
            status="filled",
            reason=order.entry_reason or order.exit_reason,
            manual=order.manual,
            strategy_name=order.strategy_name,
            provider_type=order.provider_type,
            model_name=order.model_name,
            executed_at=utcnow(),
        )
        db.add(sim_order)
        db.flush()

        position = db.scalar(
            select(Position).where(
                Position.asset_id == order.asset_id,
                Position.simulation_account_id == account.id,
                Position.mode == "simulation",
                Position.status == "open",
            )
        )
        protective_levels = (order.audit_context or {}).get("protective_levels", {})

        realized_pnl = 0.0
        if order.side == "buy":
            total_cost = executed_price * order.quantity + fees
            account.cash_balance -= total_cost
            if position:
                new_qty = position.quantity + order.quantity
                position.avg_entry_price = ((position.quantity * position.avg_entry_price) + (order.quantity * executed_price)) / new_qty
                position.quantity = new_qty
                position.current_price = executed_price
                position.unrealized_pnl = (executed_price - position.avg_entry_price) * position.quantity
                if protective_levels.get("stop_loss") is not None:
                    position.stop_loss = protective_levels.get("stop_loss")
                if protective_levels.get("take_profit") is not None:
                    position.take_profit = protective_levels.get("take_profit")
                if protective_levels.get("trailing_stop") is not None:
                    position.trailing_stop = protective_levels.get("trailing_stop")
            else:
                position = Position(
                    asset_id=order.asset_id,
                    simulation_account_id=account.id,
                    mode="simulation",
                    manual=order.manual,
                    strategy_name=order.strategy_name,
                    provider_type=order.provider_type,
                    model_name=order.model_name,
                    quantity=order.quantity,
                    avg_entry_price=executed_price,
                    current_price=executed_price,
                    stop_loss=protective_levels.get("stop_loss"),
                    take_profit=protective_levels.get("take_profit"),
                    trailing_stop=protective_levels.get("trailing_stop"),
                    notes=order.entry_reason,
                )
                db.add(position)
                db.flush()
        else:
            if position is None or position.quantity < order.quantity:
                raise ValueError("Simulation sell order exceeds current holdings")
            proceeds = executed_price * order.quantity - fees
            account.cash_balance += proceeds
            realized_pnl = (executed_price - position.avg_entry_price) * order.quantity - fees
            remaining_qty = position.quantity - order.quantity
            if remaining_qty <= 0:
                position.quantity = 0
                position.current_price = executed_price
                position.realized_pnl += realized_pnl
                position.status = "closed"
                position.closed_at = utcnow()
            else:
                position.quantity = remaining_qty
                position.current_price = executed_price
                position.realized_pnl += realized_pnl
                position.unrealized_pnl = (executed_price - position.avg_entry_price) * remaining_qty

        trade = Trade(
            asset_id=order.asset_id,
            order_id=order.id,
            position_id=position.id if position else None,
            mode="simulation",
            side=order.side,
            quantity=order.quantity,
            price=executed_price,
            fees=fees,
            realized_pnl=realized_pnl,
            entry_reason=order.entry_reason,
            exit_reason=order.exit_reason,
            strategy_name=order.strategy_name,
            provider_type=order.provider_type,
            model_name=order.model_name,
            executed_at=utcnow(),
        )
        db.add(trade)
        db.flush()

        fill = Fill(
            order_id=order.id,
            quantity=order.quantity,
            price=executed_price,
            fees=fees,
            filled_at=trade.executed_at,
        )
        db.add(fill)

        sim_trade = SimulationTrade(
            simulation_account_id=account.id,
            simulation_order_id=sim_order.id,
            asset_id=order.asset_id,
            side=order.side,
            quantity=order.quantity,
            price=executed_price,
            fees=fees,
            realized_pnl=realized_pnl,
            rationale=order.entry_reason or order.exit_reason,
            executed_at=trade.executed_at,
        )
        db.add(sim_trade)
        db.flush()

        order.position_id = position.id if position else None
        self.create_snapshot(db, account)
        publish_event(
            "simulation.trade.executed",
            {
                "simulation_account_id": account.id,
                "order_id": order.id,
                "asset_id": order.asset_id,
                "side": order.side,
                "price": executed_price,
                "quantity": order.quantity,
            },
        )
        return sim_order, sim_trade, position

    def create_snapshot(self, db: Session, account: SimulationAccount) -> PortfolioSnapshot:
        positions = list(
            db.scalars(
                select(Position).where(
                    Position.mode == "simulation",
                    Position.simulation_account_id == account.id,
                    Position.status == "open",
                )
            )
        )
        total_equity = 0.0
        sector_breakdown: dict[str, float] = {}
        for position in positions:
            latest_price = market_data_service.get_latest_price(db, position.asset_id)
            position.current_price = latest_price
            position.unrealized_pnl = (latest_price - position.avg_entry_price) * position.quantity
            total_equity += latest_price * position.quantity
        total_value = account.cash_balance + total_equity
        previous = db.scalar(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.mode == "simulation", PortfolioSnapshot.simulation_account_id == account.id)
            .order_by(desc(PortfolioSnapshot.timestamp))
            .limit(1)
        )
        baseline = previous.total_value if previous else account.starting_cash
        daily_return = ((total_value - baseline) / baseline) if baseline else 0
        snapshot = PortfolioSnapshot(
            mode="simulation",
            simulation_account_id=account.id,
            timestamp=utcnow(),
            total_value=round(total_value, 2),
            cash=round(account.cash_balance, 2),
            equity=round(total_equity, 2),
            realized_pnl=round(sum(position.realized_pnl for position in positions), 2),
            unrealized_pnl=round(sum(position.unrealized_pnl for position in positions), 2),
            daily_return=round(daily_return, 4),
            weekly_return=round(daily_return * 2.2, 4),
            monthly_return=round(daily_return * 4.1, 4),
            exposure_json=sector_breakdown,
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    def summary(self, db: Session, account_id: str) -> dict:
        account = self.get_account(db, account_id)
        if account is None:
            raise ValueError("Simulation account not found")
        equity_curve = [
            {"timestamp": snapshot.timestamp.isoformat(), "value": snapshot.total_value}
            for snapshot in db.scalars(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.mode == "simulation", PortfolioSnapshot.simulation_account_id == account_id)
                .order_by(PortfolioSnapshot.timestamp.asc())
                .limit(120)
            )
        ]
        orders = list(
            db.scalars(
                select(SimulationOrder)
                .where(SimulationOrder.simulation_account_id == account_id)
                .order_by(desc(SimulationOrder.created_at))
                .limit(10)
            )
        )
        order_views = []
        for order in orders:
            asset = db.get(Asset, order.asset_id)
            order_views.append(
                {
                    "id": order.id,
                    "asset_id": order.asset_id,
                    "symbol": asset.symbol if asset else order.asset_id,
                    "asset_name": asset.name if asset else order.asset_id,
                    "mode": "simulation",
                    "side": order.side,
                    "order_type": "market",
                    "quantity": order.quantity,
                    "requested_price": order.requested_price,
                    "filled_price": order.executed_price,
                    "fees": order.fees,
                    "status": order.status,
                    "manual": order.manual,
                    "strategy_name": order.strategy_name,
                    "provider_type": order.provider_type,
                    "model_name": order.model_name,
                    "entry_reason": order.reason,
                    "exit_reason": None,
                    "rejection_reason": order.rejection_reason,
                    "created_at": order.created_at.isoformat(),
                    "executed_at": order.executed_at.isoformat() if order.executed_at else None,
                }
            )
        open_positions = len(
            list(
                db.scalars(
                    select(Position).where(
                        Position.mode == "simulation",
                        Position.simulation_account_id == account_id,
                        Position.status == "open",
                    )
                )
            )
        )
        trade_count = len(list(db.scalars(select(SimulationTrade).where(SimulationTrade.simulation_account_id == account_id))))
        latest_value = equity_curve[-1]["value"] if equity_curve else account.starting_cash
        return {
            "account": account,
            "equity_curve": equity_curve,
            "open_positions": open_positions,
            "total_trades": trade_count,
            "hypothetical_pnl": round(latest_value - account.starting_cash, 2),
            "latest_orders": order_views,
        }


simulation_service = SimulationService()
