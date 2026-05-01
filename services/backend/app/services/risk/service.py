from collections import Counter

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.portfolio import Order, PortfolioSnapshot, Position, Trade
from app.models.risk import RiskRule
from app.schemas.risk import RiskCheck, RiskValidationRequest, RiskValidationResponse
from app.services.audit.service import audit_service
from app.services.market_data.service import market_data_service
from app.services.market_hours.service import market_hours_service
from app.utils.time import utcnow

settings = get_settings()


BUY_LIKE_ACTIONS = {"buy", "short"}
SELL_LIKE_ACTIONS = {"sell", "close_long", "reduce_long", "cover_short"}
LONG_EXIT_ACTIONS = {"sell", "close_long", "reduce_long"}
SHORT_ACTIONS = {"short", "cover_short"}


class RiskService:
    def list_rules(self, db: Session) -> list[RiskRule]:
        return list(db.scalars(select(RiskRule).order_by(RiskRule.name)))

    def upsert_rule(self, db: Session, payload) -> RiskRule:
        rule = db.scalar(select(RiskRule).where(RiskRule.name == payload.name))
        if rule is None:
            rule = RiskRule(name=payload.name, rule_type=payload.rule_type)
            db.add(rule)
        rule.scope = payload.scope
        rule.rule_type = payload.rule_type
        rule.enabled = payload.enabled
        rule.auto_close = payload.auto_close
        rule.description = payload.description
        rule.config_json = payload.config_json
        db.flush()
        if rule.rule_type in {"cash_reserve", "kill_switch"}:
            audit_service.log(
                db,
                actor="system",
                action=f"risk.{rule.rule_type}.update",
                target_type="risk_rule",
                target_id=rule.id,
                status="enabled" if rule.enabled else "disabled",
                mode=rule.scope,
                details={"config_json": rule.config_json, "enabled": rule.enabled},
            )
        return rule

    def validate_order(self, db: Session, payload: RiskValidationRequest) -> RiskValidationResponse:
        checks: list[RiskCheck] = []
        price = payload.requested_price or market_data_service.get_latest_price(db, payload.asset_id)
        side = self._normalize_side(payload.side)
        notional = payload.quantity * price
        rules = [rule for rule in self.list_rules(db) if rule.enabled]

        checks.append(self._core_mode_check(payload))
        checks.append(self._cash_check(db, payload, price))
        checks.append(self._duplicate_order_check(db, payload))
        checks.append(self._holding_check(db, payload))
        checks.append(self._protective_levels_check(payload, price))
        account_hours_check = self._simulation_account_market_hours_check(db, payload)
        if account_hours_check is not None:
            checks.append(account_hours_check)

        for rule in rules:
            if rule.rule_type == "kill_switch":
                checks.append(self._kill_switch_check(rule))
            elif rule.rule_type == "cash_reserve":
                checks.append(self._cash_reserve_check(db, rule, payload, price))
            elif rule.rule_type == "max_position_size":
                checks.append(self._max_position_size_check(rule, abs(notional), payload.quantity))
            elif rule.rule_type == "max_capital_per_asset":
                checks.append(self._max_capital_per_asset_check(db, rule, payload, notional))
            elif rule.rule_type == "max_open_positions":
                checks.append(self._max_open_positions_check(db, rule, payload))
            elif rule.rule_type == "max_sector_exposure":
                checks.append(self._max_sector_exposure_check(db, rule, payload, notional))
            elif rule.rule_type == "daily_max_loss":
                checks.append(self._daily_max_loss_check(db, rule, payload))
            elif rule.rule_type == "max_drawdown_halt":
                checks.append(self._max_drawdown_check(db, rule, payload))
            elif rule.rule_type == "loss_streak_cooldown":
                checks.append(self._loss_streak_check(db, rule, payload))
            elif rule.rule_type == "per_trade_risk":
                checks.append(self._per_trade_risk_check(rule, payload, price))
            elif rule.rule_type == "market_hours":
                checks.append(self._market_hours_check(db, rule, payload))

        rejection_reasons = [check.reason for check in checks if not check.passed]
        return RiskValidationResponse(
            approved=not rejection_reasons,
            checks=checks,
            rejection_reasons=rejection_reasons,
        )

    def _core_mode_check(self, payload: RiskValidationRequest) -> RiskCheck:
        if payload.mode == "live" and not settings.enable_live_trading:
            return RiskCheck(rule="live_mode_disabled", passed=False, reason="Live trading is disabled by backend configuration.")
        if payload.mode == "live" and not payload.broker_account_id:
            return RiskCheck(rule="live_broker_required", passed=False, reason="Live orders require a broker account.")
        if payload.mode == "simulation" and not payload.simulation_account_id:
            return RiskCheck(rule="simulation_account_required", passed=False, reason="Simulation orders require a simulation account.")
        return RiskCheck(rule="mode_consistency", passed=True, reason="Mode consistency check passed.")

    def _cash_check(self, db: Session, payload: RiskValidationRequest, price: float) -> RiskCheck:
        side = self._normalize_side(payload.side)
        if side in SELL_LIKE_ACTIONS:
            return RiskCheck(rule="cash_availability", passed=True, reason="This action does not require new cash.")
        notional = payload.quantity * price
        if payload.mode == "simulation":
            from app.models.simulation import SimulationAccount

            account = db.get(SimulationAccount, payload.simulation_account_id)
            if account is None:
                return RiskCheck(rule="cash_availability", passed=False, reason="Simulation account not found.")
            if side == "short" and not account.short_enabled:
                return RiskCheck(
                    rule="cash_availability",
                    passed=False,
                    reason="Short simulation is disabled for this simulation account.",
                    details={"short_enabled": account.short_enabled},
                )
            if side == "short":
                margin_requirement = max(float(account.short_margin_requirement or 1.0), 1.0)
                required_margin = notional * margin_requirement
                passed = account.cash_balance >= required_margin
                return RiskCheck(
                    rule="cash_availability",
                    passed=passed,
                    reason="Sufficient simulated short margin." if passed else "Short order exceeds simulated margin requirement.",
                    details={
                        "cash_balance": account.cash_balance,
                        "required_margin": required_margin,
                        "short_margin_requirement": margin_requirement,
                    },
                )
            passed = account.cash_balance >= notional
            return RiskCheck(
                rule="cash_availability",
                passed=passed,
                reason="Sufficient simulation cash." if passed else "Insufficient simulation cash balance.",
                details={"cash_balance": account.cash_balance, "required": notional},
            )
        if side == "short":
            return RiskCheck(
                rule="cash_availability",
                passed=False,
                reason="Live short execution is not supported by the configured broker adapter.",
            )
        available_cash = self._cash_balance(db, payload.mode, payload.simulation_account_id, payload.broker_account_id)
        passed = available_cash >= notional
        return RiskCheck(
            rule="cash_availability",
            passed=passed,
            reason="Sufficient live cash." if passed else "Insufficient live cash or unavailable broker cash snapshot.",
            details={"cash_balance": available_cash, "required": notional},
        )

    def _duplicate_order_check(self, db: Session, payload: RiskValidationRequest) -> RiskCheck:
        existing = list(
            db.scalars(
                select(Order).where(
                    Order.asset_id == payload.asset_id,
                    Order.mode == payload.mode,
                    Order.side == payload.side,
                    Order.status.in_(["pending", "accepted"]),
                )
            )
        )
        if payload.simulation_account_id:
            existing = [
                order
                for order in existing
                if (order.audit_context or {}).get("simulation_account_id") == payload.simulation_account_id
                or (
                    order.position_id
                    and (position := db.get(Position, order.position_id))
                    and position.simulation_account_id == payload.simulation_account_id
                )
            ]
        if payload.broker_account_id:
            existing = [order for order in existing if order.broker_account_id == payload.broker_account_id]
        passed = len(existing) == 0
        return RiskCheck(
            rule="duplicate_order",
            passed=passed,
            reason="No conflicting open orders." if passed else "Conflicting open order already exists for this asset/mode/side.",
        )

    def _holding_check(self, db: Session, payload: RiskValidationRequest) -> RiskCheck:
        side = self._normalize_side(payload.side)
        if side not in SELL_LIKE_ACTIONS:
            return RiskCheck(rule="position_holding", passed=True, reason="Opening actions do not require an existing position.")
        position = self._current_position(db, payload)
        held = position.quantity if position else 0
        if side == "cover_short":
            coverable = abs(held) if held < 0 else 0
            passed = coverable >= payload.quantity
            return RiskCheck(
                rule="position_holding",
                passed=passed,
                reason="Cover quantity is within current short exposure." if passed else "Cover quantity exceeds current short exposure.",
                details={"held_short_quantity": coverable, "requested": payload.quantity},
            )
        passed = held >= payload.quantity
        return RiskCheck(
            rule="position_holding",
            passed=passed,
            reason="Sell/reduce quantity is covered by current long position." if passed else "Sell/reduce quantity exceeds current long holdings.",
            details={"held": held, "requested": payload.quantity},
        )

    def _protective_levels_check(self, payload: RiskValidationRequest, price: float) -> RiskCheck:
        side = self._normalize_side(payload.side)
        if side == "buy" and payload.stop_loss is not None and payload.stop_loss >= price:
            return RiskCheck(rule="protective_levels", passed=False, reason="Stop loss must be below entry price for long buy orders.")
        if side == "short" and payload.stop_loss is not None and payload.stop_loss <= price:
            return RiskCheck(rule="protective_levels", passed=False, reason="Stop loss must be above entry price for simulated short orders.")
        return RiskCheck(rule="protective_levels", passed=True, reason="Protective levels check passed.")

    def _kill_switch_check(self, rule: RiskRule) -> RiskCheck:
        active = bool(rule.config_json.get("active", False))
        return RiskCheck(
            rule=rule.rule_type,
            passed=not active,
            reason="Kill switch not active." if not active else "Kill switch is active.",
        )

    def _max_position_size_check(self, rule: RiskRule, notional: float, quantity: float) -> RiskCheck:
        max_quantity = rule.config_json.get("max_quantity")
        max_notional = rule.config_json.get("max_notional")
        passed = True
        reason = "Position size within configured limits."
        if max_quantity is not None and quantity > float(max_quantity):
            passed = False
            reason = "Requested quantity exceeds the configured max position size."
        if max_notional is not None and notional > float(max_notional):
            passed = False
            reason = "Requested notional exceeds the configured max position size."
        return RiskCheck(rule=rule.rule_type, passed=passed, reason=reason, details={"notional": notional, "quantity": quantity})

    def _cash_reserve_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest, price: float) -> RiskCheck:
        side = self._normalize_side(payload.side)
        if side not in BUY_LIKE_ACTIONS:
            return RiskCheck(rule=rule.rule_type, passed=True, reason="Cash reserve does not apply to reductions or closes.")
        if payload.mode == "live" and side == "short":
            return RiskCheck(rule=rule.rule_type, passed=False, reason="Live shorts are unsupported; cash reserve cannot approve this action.")

        reserve_pct = self._cash_reserve_percent(db, rule, payload.mode, payload.simulation_account_id)
        if reserve_pct <= 0:
            return RiskCheck(rule=rule.rule_type, passed=True, reason="Cash reserve rule is configured at 0%.")

        cash_balance = self._cash_balance(db, payload.mode, payload.simulation_account_id, payload.broker_account_id)
        portfolio_value = max(self._portfolio_value(db, payload.mode, payload.simulation_account_id, payload.broker_account_id), cash_balance)
        reserve_amount = portfolio_value * reserve_pct
        available_to_trade = max(cash_balance - reserve_amount, 0.0)
        required = payload.quantity * price
        passed = required <= available_to_trade
        if passed:
            reason = f"Order keeps at least {reserve_pct:.0%} of account value in cash."
        elif available_to_trade <= 0:
            reason = (
                f"Order not processed because the {reserve_pct:.0%} cash reserve leaves no available-to-trade cash."
            )
        else:
            reason = (
                f"Order not processed because it would breach the {reserve_pct:.0%} cash reserve. "
                f"Available to trade is {available_to_trade:.2f}."
            )
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason=reason,
            details={
                "cash_balance": round(cash_balance, 2),
                "portfolio_value": round(portfolio_value, 2),
                "reserve_pct": reserve_pct,
                "reserve_amount": round(reserve_amount, 2),
                "available_to_trade": round(available_to_trade, 2),
                "required": round(required, 2),
            },
        )

    def _max_capital_per_asset_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest, notional: float) -> RiskCheck:
        portfolio_value = self._portfolio_value(db, payload.mode, payload.simulation_account_id, payload.broker_account_id)
        positions_stmt = select(Position).where(Position.asset_id == payload.asset_id, Position.mode == payload.mode, Position.status == "open")
        if payload.simulation_account_id:
            positions_stmt = positions_stmt.where(Position.simulation_account_id == payload.simulation_account_id)
        if payload.broker_account_id:
            positions_stmt = positions_stmt.where(Position.broker_account_id == payload.broker_account_id)
        asset_exposure = sum(p.current_price * p.quantity for p in db.scalars(positions_stmt))
        limit_pct = float(rule.config_json.get("max_pct", 0.25))
        passed = portfolio_value == 0 or ((asset_exposure + notional) / portfolio_value) <= limit_pct
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason="Asset exposure within capital limit." if passed else "Asset exposure would exceed configured capital allocation.",
            details={"portfolio_value": portfolio_value, "asset_exposure": asset_exposure, "limit_pct": limit_pct},
        )

    def _max_open_positions_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest) -> RiskCheck:
        max_positions = int(rule.config_json.get("max_open_positions", 10))
        stmt = select(Position).where(Position.mode == payload.mode, Position.status == "open")
        if payload.simulation_account_id:
            stmt = stmt.where(Position.simulation_account_id == payload.simulation_account_id)
        if payload.broker_account_id:
            stmt = stmt.where(Position.broker_account_id == payload.broker_account_id)
        open_positions = len(list(db.scalars(stmt)))
        passed = open_positions < max_positions
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason="Open positions count is within the configured limit." if passed else "Open positions limit reached.",
            details={"open_positions": open_positions, "limit": max_positions},
        )

    def _max_sector_exposure_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest, notional: float) -> RiskCheck:
        asset = db.get(Asset, payload.asset_id)
        sector = asset.sector if asset else None
        if not sector:
            return RiskCheck(rule=rule.rule_type, passed=True, reason="Sector unknown; sector exposure check skipped.")
        portfolio_value = self._portfolio_value(db, payload.mode, payload.simulation_account_id, payload.broker_account_id)
        sector_exposure = 0.0
        positions_stmt = select(Position).where(Position.mode == payload.mode, Position.status == "open")
        if payload.simulation_account_id:
            positions_stmt = positions_stmt.where(Position.simulation_account_id == payload.simulation_account_id)
        if payload.broker_account_id:
            positions_stmt = positions_stmt.where(Position.broker_account_id == payload.broker_account_id)
        positions = list(db.scalars(positions_stmt))
        for position in positions:
            position_asset = db.get(Asset, position.asset_id)
            if position_asset and position_asset.sector == sector:
                sector_exposure += position.current_price * position.quantity
        limit_pct = float(rule.config_json.get("max_sector_pct", 0.4))
        passed = portfolio_value == 0 or ((sector_exposure + notional) / portfolio_value) <= limit_pct
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason="Sector exposure within configured limit." if passed else f"Sector exposure for {sector} would exceed the configured limit.",
            details={"sector": sector, "sector_exposure": sector_exposure, "portfolio_value": portfolio_value},
        )

    def _daily_max_loss_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest) -> RiskCheck:
        today = utcnow().date()
        trades_stmt = select(Trade).where(Trade.mode == payload.mode)
        trades = list(db.scalars(trades_stmt))
        if payload.simulation_account_id:
            trades = [
                trade
                for trade in trades
                if not trade.position_id
                or (
                    (position := db.get(Position, trade.position_id))
                    and position.simulation_account_id == payload.simulation_account_id
                )
            ]
        if payload.broker_account_id:
            trades = [
                trade
                for trade in trades
                if not trade.position_id
                or (
                    (position := db.get(Position, trade.position_id))
                    and position.broker_account_id == payload.broker_account_id
                )
            ]
        losses = sum(
            min(trade.realized_pnl, 0)
            for trade in trades
            if trade.executed_at.date() == today
        )
        account_value = max(self._portfolio_value(db, payload.mode, payload.simulation_account_id, payload.broker_account_id), 0.0)
        limit_pct = abs(float(rule.config_json.get("max_daily_loss_pct", 0)))
        if limit_pct <= 0:
            legacy_limit_abs = abs(float(rule.config_json.get("max_daily_loss", 1500)))
            limit_abs = legacy_limit_abs
            limit_pct = legacy_limit_abs / account_value if account_value else 0.0
        else:
            limit_abs = account_value * limit_pct
        passed = abs(losses) <= limit_abs
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason="Daily loss is within the configured share of account value." if passed else "Daily max loss threshold reached as a share of account value.",
            details={"daily_loss": losses, "account_value": account_value, "limit_pct": limit_pct, "limit_amount": -limit_abs},
        )

    def _max_drawdown_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest) -> RiskCheck:
        stmt = select(PortfolioSnapshot).where(PortfolioSnapshot.mode == payload.mode)
        if payload.simulation_account_id:
            stmt = stmt.where(PortfolioSnapshot.simulation_account_id == payload.simulation_account_id)
        if payload.broker_account_id:
            stmt = stmt.where(PortfolioSnapshot.broker_account_id == payload.broker_account_id)
        snapshots = list(db.scalars(stmt.order_by(PortfolioSnapshot.timestamp.asc()).limit(200)))
        if len(snapshots) < 2:
            return RiskCheck(rule=rule.rule_type, passed=True, reason="Not enough data for drawdown check.")
        peak = snapshots[0].total_value
        max_drawdown = 0.0
        for snapshot in snapshots:
            peak = max(peak, snapshot.total_value)
            if peak:
                max_drawdown = min(max_drawdown, (snapshot.total_value - peak) / peak)
        limit_pct = -abs(float(rule.config_json.get("max_drawdown_pct", 0.12)))
        passed = max_drawdown >= limit_pct
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason="Drawdown within configured limit." if passed else "Max drawdown halt is active.",
            details={"max_drawdown": max_drawdown, "limit_pct": limit_pct},
        )

    def _loss_streak_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest) -> RiskCheck:
        streak_limit = int(rule.config_json.get("loss_streak", 3))
        cooldown_minutes = int(rule.config_json.get("cooldown_minutes", 60))
        trades = list(db.scalars(select(Trade).where(Trade.mode == payload.mode).order_by(desc(Trade.executed_at)).limit(50)))
        if payload.simulation_account_id:
            trades = [
                trade
                for trade in trades
                if not trade.position_id
                or (
                    (position := db.get(Position, trade.position_id))
                    and position.simulation_account_id == payload.simulation_account_id
                )
            ]
        if payload.broker_account_id:
            trades = [
                trade
                for trade in trades
                if not trade.position_id
                or (
                    (position := db.get(Position, trade.position_id))
                    and position.broker_account_id == payload.broker_account_id
                )
            ]
        trades = trades[:streak_limit]
        consecutive_losses = 0
        last_loss_time = None
        for trade in trades:
            if trade.realized_pnl < 0:
                consecutive_losses += 1
                last_loss_time = trade.executed_at
            else:
                break
        in_cooldown = False
        if consecutive_losses >= streak_limit and last_loss_time:
            elapsed_minutes = (utcnow() - last_loss_time).total_seconds() / 60
            in_cooldown = elapsed_minutes < cooldown_minutes
        return RiskCheck(
            rule=rule.rule_type,
            passed=not in_cooldown,
            reason="Loss streak cooldown is clear." if not in_cooldown else "Trading cooldown active after consecutive losses.",
            details={"consecutive_losses": consecutive_losses, "cooldown_minutes": cooldown_minutes},
        )

    def _per_trade_risk_check(self, rule: RiskRule, payload: RiskValidationRequest, price: float) -> RiskCheck:
        max_risk_pct = float(rule.config_json.get("max_risk_pct", 0.015))
        if payload.stop_loss is None:
            require_stop = bool(rule.config_json.get("require_stop_loss", False))
            return RiskCheck(
                rule=rule.rule_type,
                passed=not require_stop,
                reason="Stop loss not required for this order." if not require_stop else "Stop loss is required for per-trade risk validation.",
            )
        risk_per_share = abs(price - payload.stop_loss)
        risk_amount = risk_per_share * payload.quantity
        account_value = float(rule.config_json.get("reference_account_value", 100000))
        max_risk_amount = account_value * max_risk_pct
        passed = risk_amount <= max_risk_amount
        return RiskCheck(
            rule=rule.rule_type,
            passed=passed,
            reason="Per-trade risk is within the configured threshold." if passed else "Per-trade risk exceeds the configured threshold.",
            details={"risk_amount": risk_amount, "max_risk_amount": max_risk_amount},
        )

    def _simulation_account_market_hours_check(self, db: Session, payload: RiskValidationRequest) -> RiskCheck | None:
        if payload.mode != "simulation" or not payload.simulation_account_id:
            return None
        from app.models.simulation import SimulationAccount

        account = db.get(SimulationAccount, payload.simulation_account_id)
        if account is None or not account.enforce_market_hours:
            return None
        return self._market_hours_guard(
            db,
            payload,
            config={"enforce_market_hours": True, "source": "simulation_account"},
            rule_name="market_hours",
        )

    def _market_hours_check(self, db: Session, rule: RiskRule, payload: RiskValidationRequest) -> RiskCheck:
        if not rule.config_json.get("enforce_market_hours", False):
            return RiskCheck(rule=rule.rule_type, passed=True, reason="Market-hours rule disabled.")
        return self._market_hours_guard(db, payload, config=rule.config_json, rule_name=rule.rule_type)

    def _market_hours_guard(
        self,
        db: Session,
        payload: RiskValidationRequest,
        *,
        config: dict,
        rule_name: str,
    ) -> RiskCheck:
        asset = db.get(Asset, payload.asset_id)
        result = market_hours_service.check_asset(asset, at=payload.observed_at, config=config)
        return RiskCheck(
            rule=rule_name,
            passed=result.is_open,
            reason=result.reason if result.is_open else f"Order blocked by market-hours guard: {result.reason}",
            details=result.details,
        )

    def _portfolio_value(self, db: Session, mode: str, simulation_account_id: str | None, broker_account_id: str | None = None) -> float:
        if mode == "simulation" and simulation_account_id:
            snapshot = db.scalar(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.mode == mode, PortfolioSnapshot.simulation_account_id == simulation_account_id)
                .order_by(desc(PortfolioSnapshot.timestamp))
                .limit(1)
            )
        elif mode == "live" and broker_account_id:
            snapshot = db.scalar(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.mode == mode, PortfolioSnapshot.broker_account_id == broker_account_id)
                .order_by(desc(PortfolioSnapshot.timestamp))
                .limit(1)
            )
        else:
            snapshot = db.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.mode == mode).order_by(desc(PortfolioSnapshot.timestamp)).limit(1))
        if snapshot:
            return snapshot.total_value
        cash = self._cash_balance(db, mode, simulation_account_id, broker_account_id)
        stmt = select(Position).where(Position.mode == mode, Position.status == "open")
        if simulation_account_id:
            stmt = stmt.where(Position.simulation_account_id == simulation_account_id)
        if broker_account_id:
            stmt = stmt.where(Position.broker_account_id == broker_account_id)
        positions = list(db.scalars(stmt))
        return cash + sum(position.current_price * position.quantity for position in positions)

    def _cash_balance(
        self,
        db: Session,
        mode: str,
        simulation_account_id: str | None,
        broker_account_id: str | None,
    ) -> float:
        if mode == "simulation" and simulation_account_id:
            from app.models.simulation import SimulationAccount

            account = db.get(SimulationAccount, simulation_account_id)
            return float(account.cash_balance if account else 0)
        if mode == "live" and broker_account_id:
            from app.models.broker import BrokerAccount

            broker_account = db.get(BrokerAccount, broker_account_id)
            if broker_account is not None:
                return float(
                    broker_account.settings_json.get("available_cash")
                    or broker_account.settings_json.get("cash_balance")
                    or 0
                )
        snapshot = db.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.mode == mode).order_by(desc(PortfolioSnapshot.timestamp)).limit(1))
        return float(snapshot.cash if snapshot else 0)

    def _cash_reserve_percent(self, db: Session, rule: RiskRule, mode: str, simulation_account_id: str | None) -> float:
        if mode == "simulation" and simulation_account_id:
            from app.models.simulation import SimulationAccount

            account = db.get(SimulationAccount, simulation_account_id)
            if account and account.min_cash_reserve_percent is not None:
                return max(0.0, min(1.0, float(account.min_cash_reserve_percent)))
        mode_key = "simulation_override_pct" if mode == "simulation" else "live_override_pct"
        configured = rule.config_json.get(mode_key)
        if configured is None:
            configured = rule.config_json.get("min_cash_reserve_pct", rule.config_json.get("min_cash_reserve_percent", 0))
        return max(0.0, min(1.0, float(configured or 0)))

    def _current_position(self, db: Session, payload: RiskValidationRequest) -> Position | None:
        stmt = select(Position).where(
            Position.asset_id == payload.asset_id,
            Position.mode == payload.mode,
            Position.status == "open",
        )
        if payload.simulation_account_id:
            stmt = stmt.where(Position.simulation_account_id == payload.simulation_account_id)
        if payload.broker_account_id:
            stmt = stmt.where(Position.broker_account_id == payload.broker_account_id)
        return db.scalar(stmt)

    def _normalize_side(self, side: str) -> str:
        normalized = str(side).strip().lower()
        aliases = {
            "cover": "cover_short",
            "buy_to_cover": "cover_short",
        }
        return aliases.get(normalized, normalized)


risk_service = RiskService()
