from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.broker import BrokerAccount
from app.models.portfolio import Order, PortfolioSnapshot, Position, PositionStopEvent, Trade
from app.schemas.portfolio import OrderCreate, PositionCreate, PositionUpdate
from app.schemas.risk import RiskValidationRequest
from app.services.alerts.service import alert_service
from app.services.audit.service import audit_service
from app.services.brokers.service import broker_service
from app.services.events.service import publish_event
from app.services.market_data.service import market_data_service
from app.services.order_sizing import OrderSizingResult, resolve_order_sizing
from app.services.risk.service import risk_service
from app.services.simulation.service import simulation_service
from app.utils.serialization import to_plain_dict
from app.utils.time import utcnow


OPENING_SIDES = {"buy", "short"}
EXIT_SIDES = {"sell", "close_long", "reduce_long", "cover_short"}
RESIZABLE_RISK_RULES = {
    "cash_availability",
    "cash_reserve",
    "max_position_size",
    "max_capital_per_asset",
    "max_sector_exposure",
    "position_holding",
}
NON_RESIZABLE_RISK_RULES = {
    "mode_consistency",
    "live_mode_disabled",
    "live_broker_required",
    "simulation_account_required",
    "duplicate_order",
    "protective_levels",
    "kill_switch",
    "daily_max_loss",
    "max_drawdown_halt",
    "loss_streak_cooldown",
    "per_trade_risk",
    "market_hours",
}


class PortfolioService:
    def list_positions(
        self,
        db: Session,
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
        broker_account_id: str | None = None,
        include_archived: bool = False,
    ) -> list[dict]:
        stmt = select(Position).order_by(desc(Position.updated_at)).limit(200)
        if not include_archived:
            stmt = stmt.where(Position.status != "archived")
        if mode:
            stmt = stmt.where(Position.mode == mode)
        if simulation_account_id:
            stmt = stmt.where(Position.simulation_account_id == simulation_account_id)
        if broker_account_id:
            stmt = stmt.where(Position.broker_account_id == broker_account_id)
        positions = list(db.scalars(stmt))
        return [self._position_view(db, position) for position in positions]

    def create_manual_position(self, db: Session, payload: PositionCreate) -> Position:
        asset = self._resolve_position_asset(db, payload)
        market_data_service.record_manual_price(db, asset_id=asset.id, price=payload.current_price, source="manual-position")

        position_payload = payload.model_dump(
            exclude={"asset_symbol", "asset_name", "asset_type", "currency", "exchange"},
        )
        position_payload["asset_id"] = asset.id
        if payload.mode == "simulation" and not position_payload.get("simulation_account_id"):
            simulation_account = simulation_service.list_accounts(db)
            if simulation_account:
                position_payload["simulation_account_id"] = simulation_account[0].id
        if payload.mode == "live" and not position_payload.get("broker_account_id"):
            live_account = db.scalar(
                select(BrokerAccount)
                .where(BrokerAccount.mode == "live", BrokerAccount.enabled.is_(True))
                .order_by(BrokerAccount.live_trading_enabled.desc(), BrokerAccount.updated_at.desc())
                .limit(1)
            )
            if live_account:
                position_payload["broker_account_id"] = live_account.id
        position = Position(**position_payload)
        position.unrealized_pnl = (payload.current_price - payload.avg_entry_price) * payload.quantity
        db.add(position)
        db.flush()
        self._record_position_stop_event(
            db,
            position=position,
            source="manual_position",
            event_type="initial_levels",
            levels={
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "trailing_stop": position.trailing_stop,
            },
            notes="Initial protective levels from manual position entry.",
        )
        audit_service.log(
            db,
            actor="system",
            action="position.create",
            target_type="position",
            target_id=position.id,
            mode=position.mode,
            details={"manual": position.manual, "symbol": asset.symbol, "quantity": position.quantity},
        )
        publish_event("position.created", {"position_id": position.id, "mode": position.mode})
        return position

    def update_position(self, db: Session, position_id: str, payload: PositionUpdate) -> Position:
        position = db.get(Position, position_id)
        if position is None:
            raise ValueError("Position not found")
        updates = payload.model_dump(exclude_unset=True)
        previous_levels = {
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit,
            "trailing_stop": position.trailing_stop,
        }
        for key, value in updates.items():
            setattr(position, key, value)
        db.flush()
        if any(key in updates for key in ("stop_loss", "take_profit", "trailing_stop")):
            self._record_position_stop_event(
                db,
                position=position,
                source="manual_edit",
                event_type="levels_updated",
                levels={
                    "stop_loss": position.stop_loss,
                    "take_profit": position.take_profit,
                    "trailing_stop": position.trailing_stop,
                },
                notes="Protective levels updated on position.",
                metadata={"previous_levels": previous_levels},
            )
        audit_service.log(
            db,
            actor="system",
            action="position.update",
            target_type="position",
            target_id=position.id,
            mode=position.mode,
            details=updates,
        )
        publish_event("position.updated", {"position_id": position.id})
        return position

    def record_stop_event(
        self,
        db: Session,
        *,
        position: Position,
        source: str,
        event_type: str,
        levels: dict,
        order_id: str | None = None,
        signal_id: str | None = None,
        triggered_price: float | None = None,
        notes: str | None = None,
        metadata: dict | None = None,
    ) -> PositionStopEvent | None:
        return self._record_position_stop_event(
            db,
            position=position,
            source=source,
            event_type=event_type,
            levels=levels,
            order_id=order_id,
            signal_id=signal_id,
            triggered_price=triggered_price,
            notes=notes,
            metadata=metadata,
        )

    def close_position(
        self,
        db: Session,
        position_id: str,
        quantity: float | None = None,
        close_percent: float | None = None,
        exit_price: float | None = None,
    ) -> Position:
        position = db.get(Position, position_id)
        if position is None:
            raise ValueError("Position not found")
        if quantity is not None and close_percent is not None:
            raise ValueError("Provide either quantity or close_percent, not both")
        if position.status == "archived":
            raise ValueError("Archived positions cannot be closed.")
        if position.status == "closed" or abs(position.quantity) <= 1e-8:
            position.status = "closed"
            position.quantity = 0
            position.unrealized_pnl = 0
            position.closed_at = position.closed_at or utcnow()
            db.flush()
            return position

        position_size = abs(position.quantity)
        if close_percent is not None:
            if close_percent <= 0 or close_percent > 100:
                raise ValueError("close_percent must be between 0 and 100")
            close_quantity = position_size * (close_percent / 100)
        else:
            close_quantity = quantity or position_size

        close_quantity = round(close_quantity, 8)
        if close_quantity <= 0:
            raise ValueError("Close quantity must be positive")
        close_quantity = min(close_quantity, position_size)
        if close_quantity <= 0:
            raise ValueError("Close quantity exceeds current position size")
        if exit_price is not None:
            price = exit_price
        else:
            try:
                price = market_data_service.get_latest_price(db, position.asset_id)
            except ValueError:
                price = position.current_price or position.avg_entry_price
        is_short = position.quantity < 0
        realized_pnl = ((position.avg_entry_price - price) if is_short else (price - position.avg_entry_price)) * close_quantity
        side = "cover_short" if is_short else "sell"
        trade = Trade(
            asset_id=position.asset_id,
            position_id=position.id,
            mode=position.mode,
            side=side,
            quantity=close_quantity,
            price=price,
            fees=0,
            realized_pnl=realized_pnl,
            exit_reason="manual close",
            strategy_name=position.strategy_name,
            provider_type=position.provider_type,
            model_name=position.model_name,
            executed_at=utcnow(),
        )
        db.add(trade)
        if position.mode == "simulation" and position.simulation_account_id:
            from app.models.simulation import SimulationAccount

            account = db.get(SimulationAccount, position.simulation_account_id)
            if account:
                if is_short:
                    account.cash_balance -= price * close_quantity
                else:
                    account.cash_balance += price * close_quantity
        position.quantity = round(position.quantity + close_quantity if is_short else position.quantity - close_quantity, 8)
        position.realized_pnl += realized_pnl
        position.current_price = price
        if position.quantity < 0:
            position.unrealized_pnl = (position.avg_entry_price - position.current_price) * abs(position.quantity)
        else:
            position.unrealized_pnl = (position.current_price - position.avg_entry_price) * position.quantity
        if abs(position.quantity) <= 1e-8:
            position.quantity = 0
            position.status = "closed"
            position.unrealized_pnl = 0
            position.closed_at = utcnow()
        db.flush()
        publish_event("position.closed", {"position_id": position.id, "quantity": close_quantity})
        return position

    def archive_closed_positions(
        self,
        db: Session,
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
        broker_account_id: str | None = None,
    ) -> dict:
        stmt = select(Position).where(Position.status == "closed")
        if mode:
            stmt = stmt.where(Position.mode == mode)
        if simulation_account_id:
            stmt = stmt.where(Position.simulation_account_id == simulation_account_id)
        if broker_account_id:
            stmt = stmt.where(Position.broker_account_id == broker_account_id)
        positions = list(db.scalars(stmt))
        for position in positions:
            position.status = "archived"
            position.notes = self._append_note(position.notes, "Archived from closed-position cleanup.")
        db.flush()
        if positions:
            audit_service.log(
                db,
                actor="system",
                action="position.archive_closed",
                target_type="position",
                target_id=None,
                mode=mode,
                details={
                    "count": len(positions),
                    "simulation_account_id": simulation_account_id,
                    "broker_account_id": broker_account_id,
                },
            )
        return {"archived": len(positions)}

    def list_orders(
        self,
        db: Session,
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
        broker_account_id: str | None = None,
    ) -> list[dict]:
        stmt = select(Order).order_by(desc(Order.created_at)).limit(200)
        if mode:
            stmt = stmt.where(Order.mode == mode)
        if broker_account_id:
            stmt = stmt.where(Order.broker_account_id == broker_account_id)
        orders = list(db.scalars(stmt))
        if simulation_account_id:
            orders = [
                order
                for order in orders
                if order.audit_context.get("simulation_account_id") == simulation_account_id
                or (
                    order.position_id
                    and (position := db.get(Position, order.position_id))
                    and position.simulation_account_id == simulation_account_id
                )
            ]
        return [self._order_view(db, order) for order in orders]

    def list_trades(
        self,
        db: Session,
        *,
        mode: str | None = None,
        simulation_account_id: str | None = None,
        broker_account_id: str | None = None,
    ) -> list[dict]:
        stmt = select(Trade).order_by(desc(Trade.executed_at)).limit(200)
        if mode:
            stmt = stmt.where(Trade.mode == mode)
        trades = list(db.scalars(stmt))
        if simulation_account_id:
            trades = [
                trade
                for trade in trades
                if trade.position_id and (position := db.get(Position, trade.position_id)) and position.simulation_account_id == simulation_account_id
            ]
        if broker_account_id:
            trades = [
                trade
                for trade in trades
                if trade.position_id and (position := db.get(Position, trade.position_id)) and position.broker_account_id == broker_account_id
            ]
        return [self._trade_view(db, trade) for trade in trades]

    def create_order(self, db: Session, payload: OrderCreate) -> Order:
        correlation_id = str(uuid4())
        price = payload.requested_price or market_data_service.get_latest_price(db, payload.asset_id)
        simulation_account_id = payload.simulation_account_id
        simulation_account = None
        if payload.mode == "simulation" and not simulation_account_id:
            account = None
            if payload.provider_type:
                from app.models.simulation import SimulationAccount

                account = db.scalar(select(SimulationAccount).where(SimulationAccount.provider_type == payload.provider_type).limit(1))
            accounts = simulation_service.list_accounts(db)
            if account is None and accounts:
                account = accounts[0]
            if account:
                simulation_account_id = account.id
        if payload.mode == "simulation" and simulation_account_id:
            simulation_account = simulation_service.get_account(db, simulation_account_id)
        broker_account_id = payload.broker_account_id
        if payload.mode == "live" and not broker_account_id:
            broker = db.scalar(
                select(BrokerAccount)
                .where(BrokerAccount.mode == "live", BrokerAccount.enabled.is_(True), BrokerAccount.broker_type == "trading212")
                .order_by(BrokerAccount.live_trading_enabled.desc(), BrokerAccount.updated_at.desc())
                .limit(1)
            )
            broker_account_id = broker.id if broker else None
        broker_account = db.get(BrokerAccount, broker_account_id) if broker_account_id else None
        decimal_precision = self._quantity_precision(payload.mode, simulation_account, broker_account)
        portfolio_value = risk_service._portfolio_value(db, payload.mode, simulation_account_id, broker_account_id)
        sizing = resolve_order_sizing(
            sizing_mode=payload.sizing_mode,
            sizing_value=payload.sizing_value,
            quantity=payload.quantity,
            amount=payload.amount,
            price=price,
            portfolio_value=portfolio_value,
            decimal_precision=decimal_precision,
        )
        quantity = sizing.quantity
        if quantity <= 0:
            raise ValueError("Order quantity must be positive after resolving fractional sizing inputs.")
        risk_result = risk_service.validate_order(
            db,
            RiskValidationRequest(
                asset_id=payload.asset_id,
                mode=payload.mode,
                side=payload.side,
                quantity=quantity,
                requested_price=price,
                stop_loss=payload.stop_loss,
                simulation_account_id=simulation_account_id,
                broker_account_id=broker_account_id,
                strategy_name=payload.strategy_name,
            ),
        )
        resize_note = None
        if not risk_result.approved and payload.allow_fractional_resize:
            resized = self._resized_sizing_from_risk(
                original=sizing,
                risk_result=risk_result,
                side=payload.side,
                price=price,
                portfolio_value=portfolio_value,
                decimal_precision=decimal_precision,
            )
            if resized is not None and resized.quantity > 0 and resized.quantity < quantity:
                resized_risk = risk_service.validate_order(
                    db,
                    RiskValidationRequest(
                        asset_id=payload.asset_id,
                        mode=payload.mode,
                        side=payload.side,
                        quantity=resized.quantity,
                        requested_price=price,
                        stop_loss=payload.stop_loss,
                        simulation_account_id=simulation_account_id,
                        broker_account_id=broker_account_id,
                        strategy_name=payload.strategy_name,
                    ),
                )
                if resized_risk.approved:
                    resize_note = (
                        f"Order resized from {quantity:.8f} to {resized.quantity:.8f} shares "
                        f"({resized.order_value:.2f} notional) to stay inside risk limits."
                    )
                    sizing = resized
                    quantity = resized.quantity
                    risk_result = resized_risk
        protective_levels = {
            "stop_loss": payload.stop_loss,
            "take_profit": payload.take_profit,
            "trailing_stop": payload.trailing_stop,
        }
        order = Order(
            asset_id=payload.asset_id,
            broker_account_id=broker_account_id,
            signal_id=payload.signal_id,
            mode=payload.mode,
            broker_type=broker_account.broker_type if broker_account else None,
            manual=payload.manual,
            strategy_name=payload.strategy_name,
            provider_type=payload.provider_type,
            model_name=payload.model_name,
            side=payload.side,
            order_type=payload.order_type,
            quantity=quantity,
            limit_price=payload.limit_price,
            stop_price=payload.stop_price,
            requested_price=price,
            status="pending",
            entry_reason=payload.entry_reason,
            exit_reason=payload.exit_reason,
            audit_context={
                "correlation_id": correlation_id,
                "risk_checks": [check.model_dump() for check in risk_result.checks],
                "simulation_account_id": simulation_account_id,
                "protective_levels": protective_levels,
                "requested_amount": payload.amount,
                "sizing": sizing.as_audit_context(),
                "fractional_trading": {
                    "supported": True,
                    "decimal_precision": decimal_precision,
                    "broker_type": broker_account.broker_type if broker_account else None,
                    "execution_support": broker_service.get_adapter(broker_account.broker_type).capability.supports_execution
                    if broker_account
                    else payload.mode == "simulation",
                    "warning": sizing.rounding_warning,
                },
                "resize_note": resize_note,
            },
            submitted_at=utcnow(),
        )
        db.add(order)
        db.flush()
        if not risk_result.approved:
            order.status = "rejected"
            order.rejection_reason = "; ".join(risk_result.rejection_reasons)
            order.audit_context = {
                **(order.audit_context or {}),
                "rejection_stage": "risk",
            }
            alert_service.create_alert(
                db,
                category="risk",
                severity="warning",
                title="Order rejected by risk engine",
                message=order.rejection_reason,
                mode=payload.mode,
                source_ref=order.id,
            )
            audit_service.log(
                db,
                actor="system",
                action="order.rejected",
                target_type="order",
                target_id=order.id,
                status="rejected",
                mode=payload.mode,
                details={"reasons": risk_result.rejection_reasons},
            )
            publish_event("order.rejected", {"order_id": order.id, "mode": order.mode, "correlation_id": correlation_id})
            return order

        if payload.mode == "simulation":
            order.status = "accepted"
            sim_order, sim_trade, position = simulation_service.execute_order_from_order(
                db,
                order=order,
                simulation_account_id=simulation_account_id or "",
            )
            order.status = "filled"
            order.filled_price = sim_order.executed_price
            order.fees = sim_order.fees
            order.executed_at = sim_trade.executed_at
            order.position_id = position.id if position else None
        else:
            if broker_account is None:
                order.status = "rejected"
                order.rejection_reason = "Broker account not found."
                order.audit_context = {
                    **(order.audit_context or {}),
                    "rejection_stage": "execution",
                }
            else:
                adapter = broker_service.get_adapter(broker_account.broker_type)
                broker_result = adapter.place_order(
                    broker_account,
                    {
                        **payload.model_dump(),
                        "quantity": quantity,
                        "amount": sizing.order_value,
                        "sizing_mode": sizing.sizing_mode,
                        "sizing_value": sizing.sizing_value,
                        "order_notional": sizing.order_value,
                        "portfolio_percent": sizing.portfolio_percent,
                        "decimal_precision": decimal_precision,
                        "rounding_warning": sizing.rounding_warning,
                    },
                )
                if broker_result.success:
                    order.status = "accepted"
                else:
                    order.status = "rejected"
                    order.rejection_reason = broker_result.message
                    order.audit_context = {
                        **(order.audit_context or {}),
                        "rejection_stage": "execution",
                    }

        if order.status == "rejected":
            alert_service.create_alert(
                db,
                category="execution",
                severity="warning",
                title="Order not executed",
                message=order.rejection_reason or "Execution unavailable.",
                mode=payload.mode,
                source_ref=order.id,
            )
        audit_service.log(
            db,
            actor="system",
            action="order.create",
            target_type="order",
            target_id=order.id,
            status=order.status,
            mode=payload.mode,
            details={
                "manual": payload.manual,
                "quantity": quantity,
                "amount": sizing.order_value,
                "sizing": sizing.as_audit_context(),
                "protective_levels": protective_levels,
                "resize_note": resize_note,
            },
        )
        publish_event("order.updated", {"order_id": order.id, "status": order.status, "correlation_id": correlation_id})
        return order

    def _quantity_precision(self, mode: str, simulation_account, broker_account: BrokerAccount | None) -> int:
        if mode == "simulation" and simulation_account is not None:
            return int(simulation_account.decimal_precision or 6)
        if broker_account is not None:
            configured = (broker_account.settings_json or {}).get("decimal_precision")
            if configured is not None:
                return int(configured)
            if broker_account.broker_type == "trading212":
                return 6
        return 6

    def _resized_sizing_from_risk(
        self,
        *,
        original: OrderSizingResult,
        risk_result,
        side: str,
        price: float,
        portfolio_value: float,
        decimal_precision: int,
    ) -> OrderSizingResult | None:
        normalized_side = str(side).strip().lower()
        failed_checks = [check for check in risk_result.checks if not check.passed]
        if not failed_checks:
            return None
        if any(check.rule in NON_RESIZABLE_RISK_RULES for check in failed_checks):
            return None
        if any(check.rule not in RESIZABLE_RISK_RULES for check in failed_checks):
            return None

        max_values = [
            float(check.details["max_allowed_order_value"])
            for check in failed_checks
            if check.details.get("max_allowed_order_value") is not None
        ]
        max_quantities = [
            float(check.details["max_allowed_quantity"])
            for check in failed_checks
            if check.details.get("max_allowed_quantity") is not None
        ]
        if normalized_side in EXIT_SIDES and max_quantities:
            max_quantity = min(max_quantities)
            max_value = max_quantity * price
        elif max_values:
            max_value = min(max_values)
            max_quantity = max_value / price if price > 0 else 0.0
        elif max_quantities:
            max_quantity = min(max_quantities)
            max_value = max_quantity * price
        else:
            return None

        max_value = max(0.0, min(float(max_value), original.order_value))
        max_quantity = max(0.0, min(float(max_quantity), original.quantity))
        if max_value <= 0 or max_quantity <= 0:
            return None
        return resolve_order_sizing(
            sizing_mode="amount" if normalized_side in OPENING_SIDES else "quantity",
            sizing_value=max_value if normalized_side in OPENING_SIDES else max_quantity,
            quantity=None,
            amount=None,
            price=price,
            portfolio_value=portfolio_value,
            decimal_precision=decimal_precision,
        )

    def get_portfolio_summary(self, db: Session, mode: str | None = None) -> dict:
        open_positions_stmt = select(Position).where(Position.status == "open")
        trades_stmt = select(Trade)
        latest_snapshots: list[PortfolioSnapshot] = []

        if mode in {"live", "simulation"}:
            open_positions_stmt = open_positions_stmt.where(Position.mode == mode)
            trades_stmt = trades_stmt.where(Trade.mode == mode)
            latest_snapshot = db.scalar(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == mode).order_by(desc(PortfolioSnapshot.timestamp)).limit(1)
            )
            latest_snapshots = [snapshot for snapshot in [latest_snapshot] if snapshot]
        else:
            latest_live = db.scalar(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "live").order_by(desc(PortfolioSnapshot.timestamp)).limit(1)
            )
            latest_sim = db.scalar(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "simulation").order_by(desc(PortfolioSnapshot.timestamp)).limit(1)
            )
            latest_snapshots = [snapshot for snapshot in [latest_live, latest_sim] if snapshot]

        open_positions = list(db.scalars(open_positions_stmt))
        trades = list(db.scalars(trades_stmt))
        total_value = sum(snapshot.total_value for snapshot in latest_snapshots)
        cash = sum(snapshot.cash for snapshot in latest_snapshots)
        realized_pnl = sum(snapshot.realized_pnl for snapshot in latest_snapshots)
        unrealized_pnl = sum(snapshot.unrealized_pnl for snapshot in latest_snapshots)
        pnl_by_symbol = []
        for position in open_positions:
            asset = db.get(Asset, position.asset_id)
            pnl_by_symbol.append({"symbol": asset.symbol if asset else position.asset_id, "pnl": position.unrealized_pnl})
        pnl_by_symbol.sort(key=lambda item: item["pnl"], reverse=True)
        wins = [trade for trade in trades if trade.realized_pnl > 0]
        win_rate = (len(wins) / len(trades)) if trades else 0
        broker_status = {account.name: account.status for account in db.scalars(select(BrokerAccount))} if mode != "simulation" else {}
        return {
            "total_portfolio_value": round(total_value, 2),
            "cash_available": round(cash, 2),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "daily_return": round(sum(snapshot.daily_return for snapshot in latest_snapshots), 4),
            "weekly_return": round(sum(snapshot.weekly_return for snapshot in latest_snapshots), 4),
            "monthly_return": round(sum(snapshot.monthly_return for snapshot in latest_snapshots), 4),
            "win_rate": round(win_rate, 4),
            "open_positions_count": len(open_positions),
            "closed_trades_count": len([trade for trade in trades if trade.side == "sell"]),
            "best_performer": pnl_by_symbol[0] if pnl_by_symbol else {"symbol": "-", "pnl": 0},
            "worst_performer": pnl_by_symbol[-1] if pnl_by_symbol else {"symbol": "-", "pnl": 0},
            "risk_exposure_summary": {
                "gross_exposure": round(sum(abs(position.current_price * position.quantity) for position in open_positions), 2),
                "net_exposure": round(sum(position.current_price * position.quantity for position in open_positions), 2),
            },
            "broker_connection_status": broker_status,
            "provider_status": {},
            "automation_status": {"worker": "scheduled", "safety": "risk-engine-enforced", "scope": mode or "combined"},
        }

    def list_snapshots(self, db: Session, mode: str | None = None) -> list[PortfolioSnapshot]:
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc()).limit(200)
        if mode:
            stmt = stmt.where(PortfolioSnapshot.mode == mode)
        return list(db.scalars(stmt))

    def _position_view(self, db: Session, position: Position) -> dict:
        asset = db.get(Asset, position.asset_id)
        linked_order = db.scalar(
            select(Order)
            .where(Order.position_id == position.id, Order.signal_id.is_not(None))
            .order_by(desc(Order.created_at))
            .limit(1)
        )
        position_payload = to_plain_dict(position)
        if position.status == "closed" or abs(position.quantity) <= 1e-8:
            position_payload["unrealized_pnl"] = 0
        return {
            **position_payload,
            "symbol": asset.symbol if asset else position.asset_id,
            "asset_name": asset.name if asset else position.asset_id,
            "asset_currency": asset.currency if asset else "USD",
            "signal_id": linked_order.signal_id if linked_order else None,
        }

    def _order_view(self, db: Session, order: Order) -> dict:
        asset = db.get(Asset, order.asset_id)
        protective_levels = order.audit_context.get("protective_levels", {})
        sizing = (order.audit_context or {}).get("sizing", {})
        return {
            **to_plain_dict(order),
            "symbol": asset.symbol if asset else order.asset_id,
            "asset_name": asset.name if asset else order.asset_id,
            "sizing_mode": sizing.get("sizing_mode"),
            "sizing_value": sizing.get("sizing_value"),
            "order_notional": sizing.get("order_value"),
            "portfolio_percent": sizing.get("portfolio_percent"),
            "rounding_warning": sizing.get("rounding_warning"),
            "stop_loss": protective_levels.get("stop_loss"),
            "take_profit": protective_levels.get("take_profit"),
            "trailing_stop": protective_levels.get("trailing_stop"),
        }

    def _trade_view(self, db: Session, trade: Trade) -> dict:
        asset = db.get(Asset, trade.asset_id)
        order = db.get(Order, trade.order_id) if trade.order_id else None
        position = db.get(Position, trade.position_id) if trade.position_id else None
        return {
            **to_plain_dict(trade),
            "symbol": asset.symbol if asset else trade.asset_id,
            "asset_name": asset.name if asset else trade.asset_id,
            "signal_id": order.signal_id if order else None,
            "manual": order.manual if order is not None else position.manual if position is not None else True,
        }

    def _resolve_position_asset(self, db: Session, payload: PositionCreate) -> Asset:
        if payload.asset_id:
            asset = db.get(Asset, payload.asset_id)
            if asset is None:
                raise ValueError("Selected asset not found")
            return asset

        return market_data_service.get_or_create_manual_asset(
            db,
            symbol=payload.asset_symbol or "",
            name=payload.asset_name,
            asset_type=payload.asset_type,
            currency=payload.currency,
            exchange=payload.exchange,
        )

    def _record_position_stop_event(
        self,
        db: Session,
        *,
        position: Position,
        source: str,
        event_type: str,
        levels: dict,
        order_id: str | None = None,
        signal_id: str | None = None,
        triggered_price: float | None = None,
        notes: str | None = None,
        metadata: dict | None = None,
    ) -> PositionStopEvent | None:
        if not any(levels.get(key) is not None for key in ("stop_loss", "take_profit", "trailing_stop")) and triggered_price is None:
            return None
        event = PositionStopEvent(
            position_id=position.id,
            order_id=order_id,
            signal_id=signal_id,
            mode=position.mode,
            source=source,
            event_type=event_type,
            stop_loss=levels.get("stop_loss"),
            take_profit=levels.get("take_profit"),
            trailing_stop=levels.get("trailing_stop"),
            triggered_price=triggered_price,
            notes=notes,
            metadata_json=metadata or {},
            observed_at=utcnow(),
        )
        db.add(event)
        db.flush()
        return event

    def _append_note(self, existing: str | None, note: str) -> str:
        if not existing:
            return note
        if note in existing:
            return existing
        return f"{existing}\n{note}"


portfolio_service = PortfolioService()
