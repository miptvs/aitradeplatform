from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.broker import BrokerAccount
from app.models.portfolio import PortfolioSnapshot, Position
from app.models.signal import Signal, SignalEvaluation
from app.models.simulation import SimulationAccount
from app.models.strategy import Strategy
from app.models.trading import TradingAutomationProfile
from app.schemas.portfolio import OrderCreate
from app.schemas.trading import PositionActionRead, TradingAutomationProfileUpsert
from app.services.audit.service import audit_service
from app.services.alerts.service import alert_service
from app.services.brokers.service import broker_service
from app.services.market_data.service import market_data_service
from app.services.portfolio.service import portfolio_service
from app.services.simulation.service import simulation_service
from app.services.strategies.service import strategy_service
from app.utils.time import utcnow

settings = get_settings()


class TradingWorkspaceService:
    _terminal_lane_outcomes = {
        "approved",
        "sent_to_live_workflow",
        "simulated",
        "executed_live",
        "manual_rejected",
        "rejected",
        "blocked_by_risk",
    }

    def get_or_create_profile(self, db: Session, mode: str) -> TradingAutomationProfile:
        profile = db.scalar(select(TradingAutomationProfile).where(TradingAutomationProfile.mode == mode))
        if profile is not None:
            return profile

        defaults = self._default_profile_values(mode)
        profile = TradingAutomationProfile(mode=mode, **defaults)
        db.add(profile)
        db.flush()
        return profile

    def upsert_profile(self, db: Session, mode: str, payload: TradingAutomationProfileUpsert) -> TradingAutomationProfile:
        profile = self.get_or_create_profile(db, mode)
        updates = payload.model_dump()
        inherit_from_live = bool(updates.pop("inherit_from_live", False))
        config_updates = updates.pop("config_json", {})
        profile.config_json = {
            **(profile.config_json or {}),
            **config_updates,
            "inherit_from_live": inherit_from_live,
        }
        for key, value in updates.items():
            setattr(profile, key, value)
        db.flush()
        audit_service.log(
            db,
            actor="system",
            action="automation.profile.update",
            target_type="trading_automation_profile",
            target_id=profile.id,
            mode=mode,
            details={
                "automation_enabled": profile.automation_enabled,
                "scheduled_execution_enabled": profile.scheduled_execution_enabled,
                "execution_interval_seconds": profile.execution_interval_seconds,
                "inherit_from_live": inherit_from_live,
                "approval_mode": profile.approval_mode,
                "confidence_threshold": profile.confidence_threshold,
            },
        )
        return profile

    def resolve_profile_pair(
        self,
        db: Session,
        mode: str,
    ) -> tuple[TradingAutomationProfile, TradingAutomationProfile, bool]:
        stored_profile = self.get_or_create_profile(db, mode)
        inherit_from_live = mode == "simulation" and bool((stored_profile.config_json or {}).get("inherit_from_live"))
        source_profile = self.get_or_create_profile(db, "live") if inherit_from_live else stored_profile
        return stored_profile, source_profile, inherit_from_live

    def serialize_profile(
        self,
        stored_profile: TradingAutomationProfile,
        source_profile: TradingAutomationProfile | None = None,
        inherit_from_live: bool = False,
    ) -> dict:
        effective_profile = source_profile or stored_profile
        return {
            "id": stored_profile.id,
            "mode": stored_profile.mode,
            "name": stored_profile.name,
            "enabled": stored_profile.enabled,
            "automation_enabled": effective_profile.automation_enabled,
            "scheduled_execution_enabled": effective_profile.scheduled_execution_enabled,
            "execution_interval_seconds": effective_profile.execution_interval_seconds,
            "inherit_from_live": inherit_from_live,
            "effective_source_mode": effective_profile.mode,
            "approval_mode": effective_profile.approval_mode,
            "allowed_strategy_slugs": effective_profile.allowed_strategy_slugs,
            "tradable_actions": effective_profile.tradable_actions,
            "allowed_provider_types": effective_profile.allowed_provider_types,
            "confidence_threshold": effective_profile.confidence_threshold,
            "default_order_notional": effective_profile.default_order_notional,
            "stop_loss_pct": effective_profile.stop_loss_pct,
            "take_profit_pct": effective_profile.take_profit_pct,
            "trailing_stop_pct": effective_profile.trailing_stop_pct,
            "max_orders_per_run": effective_profile.max_orders_per_run,
            "risk_profile": effective_profile.risk_profile,
            "notes": effective_profile.notes,
            "last_run_at": stored_profile.last_run_at,
            "last_scheduled_run_at": stored_profile.last_scheduled_run_at,
            "next_scheduled_run_at": self._next_scheduled_run_at(stored_profile, effective_profile),
            "last_run_status": stored_profile.last_run_status,
            "last_run_message": stored_profile.last_run_message,
            "config_json": stored_profile.config_json,
        }

    def _next_scheduled_run_at(
        self,
        stored_profile: TradingAutomationProfile,
        effective_profile: TradingAutomationProfile,
    ):
        if not effective_profile.scheduled_execution_enabled:
            return None
        interval = max(int(effective_profile.execution_interval_seconds or 300), 60)
        anchor = stored_profile.last_scheduled_run_at or stored_profile.last_run_at
        if anchor is None:
            return utcnow()
        return anchor + timedelta(seconds=interval)

    def get_workspace(self, db: Session, mode: str, *, simulation_account_id: str | None = None) -> dict:
        stored_profile, effective_profile, inherit_from_live = self.resolve_profile_pair(db, mode)
        if mode == "live":
            account_summary, controls = self._live_account_summary(db)
            positions = portfolio_service.list_positions(db, mode="live")
            orders = portfolio_service.list_orders(db, mode="live")
            trades = portfolio_service.list_trades(db, mode="live")
        else:
            simulation_account = self._resolve_simulation_account(db, simulation_account_id)
            account_summary, controls = self._simulation_account_summary(db, simulation_account)
            positions = portfolio_service.list_positions(db, mode="simulation", simulation_account_id=simulation_account.id if simulation_account else None)
            orders = portfolio_service.list_orders(db, mode="simulation", simulation_account_id=simulation_account.id if simulation_account else None)
            trades = portfolio_service.list_trades(db, mode="simulation", simulation_account_id=simulation_account.id if simulation_account else None)

        return {
            "mode": mode,
            "account": account_summary,
            "automation": self.serialize_profile(stored_profile, effective_profile, inherit_from_live),
            "positions": positions,
            "orders": orders,
            "trades": trades,
            "signals": self._workspace_signals(db, mode),
            "recommendations": self._workspace_recommendations(db, mode),
            "alerts": alert_service.list_alerts(db, mode=mode),
            "assets": market_data_service.list_asset_views(db),
            "strategies": [self._strategy_view(item) for item in strategy_service.list_strategies(db)],
            "controls": controls,
        }

    def run_automation(
        self,
        db: Session,
        mode: str,
        *,
        simulation_account_id: str | None = None,
        broker_account_id: str | None = None,
    ) -> dict:
        stored_profile, profile, inherit_from_live = self.resolve_profile_pair(db, mode)
        if not stored_profile.enabled:
            return self._finalize_profile_run(stored_profile, "blocked", "Automation profile is disabled.", [])
        if not profile.automation_enabled:
            return self._finalize_profile_run(stored_profile, "blocked", "Automation toggle is off for this workspace.", [])

        decisions: list[dict[str, Any]] = []
        submitted_orders = 0
        approved_recommendations = 0
        rejected_signals = 0

        active_broker = self._resolve_live_broker(db, broker_account_id) if mode == "live" else None
        active_simulation = self._resolve_simulation_account(db, simulation_account_id) if mode == "simulation" else None

        if mode == "live" and active_broker is None:
            return self._finalize_profile_run(stored_profile, "blocked", "No enabled live broker account is configured for automation.", decisions)
        if mode == "simulation" and active_simulation is None:
            return self._finalize_profile_run(stored_profile, "blocked", "No simulation account is available for automation.", decisions)

        candidates = self._automation_candidates(db, mode, profile)
        if not candidates:
            return self._finalize_profile_run(stored_profile, "noop", "No eligible candidate signals matched the current automation policy.", decisions)

        processed = 0
        for signal in candidates[: profile.max_orders_per_run]:
            processed += 1
            asset = db.get(Asset, signal.asset_id)
            if asset is None:
                decisions.append(self._reject_signal(db, signal, mode, "Signal asset is missing from the current asset universe."))
                rejected_signals += 1
                continue
            if signal.action not in {"buy", "sell"}:
                decisions.append(self._reject_signal(db, signal, mode, "Only buy and sell signals are tradable."))
                rejected_signals += 1
                continue

            entry_price = signal.suggested_entry or market_data_service.get_latest_price(db, signal.asset_id)
            if entry_price <= 0:
                decisions.append(self._reject_signal(db, signal, mode, "Signal entry price is invalid."))
                rejected_signals += 1
                continue

            quantity = round(profile.default_order_notional / entry_price, 8)
            if quantity <= 0:
                decisions.append(self._reject_signal(db, signal, mode, "Configured default notional is too small for this symbol."))
                rejected_signals += 1
                continue

            stop_loss = signal.suggested_stop_loss or self._protective_level(entry_price, profile.stop_loss_pct, signal.action, direction="down")
            take_profit = signal.suggested_take_profit or self._protective_level(entry_price, profile.take_profit_pct, signal.action, direction="up")
            trailing_stop = self._trailing_distance(entry_price, profile.trailing_stop_pct)
            decision_reason = f"{profile.approval_mode.replace('_', ' ')} automation from signal {signal.id}"

            if profile.approval_mode in {"manual_only", "semi_automatic"}:
                queued_outcome = "sent_to_live_workflow" if mode == "live" else "approved"
                db.add(
                    SignalEvaluation(
                        signal_id=signal.id,
                        approved=True,
                        evaluator=f"{mode}-automation",
                        reason="Eligible candidate approved for manual review.",
                        expected_return=signal.estimated_risk_reward,
                        outcome=queued_outcome,
                    )
                )
                approved_recommendations += 1
                decisions.append(
                    {
                        "signal_id": signal.id,
                        "symbol": asset.symbol,
                        "action": signal.action,
                        "confidence": signal.confidence,
                        "strategy_slug": signal.metadata_json.get("preferred_strategy"),
                        "provider_type": signal.provider_type,
                        "outcome": queued_outcome,
                        "reason": "Prepared for manual approval. Review the ticket in the trading workspace before sending it.",
                        "order_id": None,
                    }
                )
                continue

            order = portfolio_service.create_order(
                db,
                OrderCreate(
                    asset_id=signal.asset_id,
                    mode=mode,
                    side=signal.action,
                    quantity=quantity,
                    requested_price=entry_price,
                    order_type="market",
                    signal_id=signal.id,
                    strategy_name=signal.metadata_json.get("preferred_strategy") or signal.metadata_json.get("strategy_slug"),
                    provider_type=signal.provider_type,
                    model_name=signal.model_name,
                    manual=False,
                    entry_reason=decision_reason,
                    broker_account_id=active_broker.id if active_broker else None,
                    simulation_account_id=active_simulation.id if active_simulation else None,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    trailing_stop=trailing_stop,
                ),
            )
            success = order.status in {"accepted", "filled"}
            if success:
                execution_outcome = "executed_live" if mode == "live" else "simulated"
            else:
                execution_outcome = "blocked_by_risk" if order.audit_context.get("rejection_stage") == "risk" else "rejected"
            db.add(
                SignalEvaluation(
                    signal_id=signal.id,
                    approved=success,
                    evaluator=f"{mode}-automation",
                    reason=order.rejection_reason or decision_reason,
                    expected_return=signal.estimated_risk_reward,
                    outcome=execution_outcome,
                )
            )
            if success:
                submitted_orders += 1
                decisions.append(
                    {
                        "signal_id": signal.id,
                        "symbol": asset.symbol,
                        "action": signal.action,
                        "confidence": signal.confidence,
                        "strategy_slug": signal.metadata_json.get("preferred_strategy"),
                        "provider_type": signal.provider_type,
                        "outcome": execution_outcome,
                        "reason": "Order submitted through the shared trading workflow.",
                        "order_id": order.id,
                    }
                )
            else:
                rejected_signals += 1
                decisions.append(
                    {
                        "signal_id": signal.id,
                        "symbol": asset.symbol,
                        "action": signal.action,
                        "confidence": signal.confidence,
                        "strategy_slug": signal.metadata_json.get("preferred_strategy"),
                        "provider_type": signal.provider_type,
                        "outcome": execution_outcome,
                        "reason": order.rejection_reason or "Order rejected by the execution workflow.",
                        "order_id": order.id,
                    }
                )

        status = "success" if submitted_orders or approved_recommendations else "warn"
        message_parts = []
        if submitted_orders:
            message_parts.append(f"{submitted_orders} order{'s' if submitted_orders != 1 else ''} submitted")
        if approved_recommendations:
            message_parts.append(f"{approved_recommendations} recommendation{'s' if approved_recommendations != 1 else ''} queued")
        if rejected_signals:
            message_parts.append(f"{rejected_signals} signal{'s' if rejected_signals != 1 else ''} rejected")
        message = ", ".join(message_parts) if message_parts else "Automation reviewed candidates but no orders were sent."
        result = self._finalize_profile_run(stored_profile, status, message, decisions)
        result["processed_signals"] = processed
        result["submitted_orders"] = submitted_orders
        result["approved_recommendations"] = approved_recommendations
        result["rejected_signals"] = rejected_signals
        audit_service.log(
            db,
            actor="system",
            action="automation.run",
            target_type="trading_automation_profile",
            target_id=stored_profile.id,
            mode=mode,
            details={
                "status": status,
                "submitted_orders": submitted_orders,
                "approved_recommendations": approved_recommendations,
                "rejected_signals": rejected_signals,
                "inherit_from_live": inherit_from_live,
            },
        )
        return result

    def run_scheduled_automation(self, db: Session, mode: str) -> dict:
        stored_profile, effective_profile, inherit_from_live = self.resolve_profile_pair(db, mode)
        now = utcnow()
        interval = max(int(effective_profile.execution_interval_seconds or 300), 60)
        next_run_at = self._next_scheduled_run_at(stored_profile, effective_profile)

        if not stored_profile.enabled:
            return self._scheduled_skip_result(mode, "Automation profile is disabled.", next_run_at, inherit_from_live)
        if not effective_profile.scheduled_execution_enabled:
            return self._scheduled_skip_result(mode, "Scheduled automation is off for this workspace.", None, inherit_from_live)
        if not effective_profile.automation_enabled:
            return self._scheduled_skip_result(mode, "Automation toggle is off for this workspace.", next_run_at, inherit_from_live)
        if next_run_at is not None and next_run_at > now:
            return self._scheduled_skip_result(
                mode,
                f"Next scheduled automation run is due in {int((next_run_at - now).total_seconds())} seconds.",
                next_run_at,
                inherit_from_live,
            )

        result = self.run_automation(db, mode)
        stored_profile.last_scheduled_run_at = now
        result["scheduled"] = True
        result["interval_seconds"] = interval
        result["next_scheduled_run_at"] = (now + timedelta(seconds=interval)).isoformat()
        result["inherit_from_live"] = inherit_from_live
        return result

    def _scheduled_skip_result(
        self,
        mode: str,
        message: str,
        next_run_at,
        inherit_from_live: bool,
    ) -> dict:
        return {
            "mode": mode,
            "status": "skipped",
            "message": message,
            "processed_signals": 0,
            "submitted_orders": 0,
            "approved_recommendations": 0,
            "rejected_signals": 0,
            "decisions": [],
            "scheduled": True,
            "next_scheduled_run_at": next_run_at.isoformat() if next_run_at else None,
            "inherit_from_live": inherit_from_live,
        }

    def _default_profile_values(self, mode: str) -> dict[str, Any]:
        name = "Live Trading Automation" if mode == "live" else "Simulation Automation"
        return {
            "name": name,
            "enabled": True,
            "automation_enabled": False,
            "scheduled_execution_enabled": False,
            "execution_interval_seconds": 300,
            "approval_mode": "semi_automatic",
            "allowed_strategy_slugs": [],
            "tradable_actions": ["buy", "sell"],
            "allowed_provider_types": [],
            "confidence_threshold": 0.58,
            "default_order_notional": 100.0,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
            "trailing_stop_pct": 0.02,
            "max_orders_per_run": 1,
            "risk_profile": "balanced",
            "notes": "Signals always pass through the risk engine before any simulated or live order attempt.",
            "config_json": {"semi_auto_requires_manual_ticket_review": True},
        }

    def _finalize_profile_run(
        self,
        profile: TradingAutomationProfile,
        status: str,
        message: str,
        decisions: list[dict[str, Any]],
    ) -> dict:
        profile.last_run_at = utcnow()
        profile.last_run_status = status
        profile.last_run_message = message
        return {
            "mode": profile.mode,
            "status": status,
            "message": message,
            "processed_signals": len(decisions),
            "submitted_orders": 0,
            "approved_recommendations": 0,
            "rejected_signals": 0,
            "decisions": decisions,
        }

    def _reject_signal(self, db: Session, signal: Signal, mode: str, reason: str) -> dict[str, Any]:
        db.add(
            SignalEvaluation(
                signal_id=signal.id,
                approved=False,
                evaluator=f"{mode}-automation",
                reason=reason,
                expected_return=signal.estimated_risk_reward,
                outcome="rejected",
            )
        )
        asset = db.get(Asset, signal.asset_id)
        return {
            "signal_id": signal.id,
            "symbol": asset.symbol if asset else signal.asset_id,
            "action": signal.action,
            "confidence": signal.confidence,
            "strategy_slug": signal.metadata_json.get("preferred_strategy"),
            "provider_type": signal.provider_type,
            "outcome": "rejected",
            "reason": reason,
            "order_id": None,
        }

    def _workspace_signals(self, db: Session, mode: str) -> list[dict]:
        signals = list(db.scalars(select(Signal).order_by(desc(Signal.occurred_at)).limit(40)))
        return [self._signal_view(db, signal) for signal in signals[:12]]

    def _workspace_recommendations(self, db: Session, mode: str) -> list[dict]:
        signals = list(
            db.scalars(
                select(Signal).order_by(desc(Signal.occurred_at)).limit(40)
            )
        )
        recommendations: list[dict[str, Any]] = []
        for signal in signals:
            evaluation = self._latest_mode_evaluation(db, signal.id, mode)
            if evaluation is None or evaluation.outcome not in self._recommendation_outcomes(mode):
                continue
            recommendations.append(self._recommendation_view(db, signal, evaluation))
            if len(recommendations) >= 10:
                break
        return recommendations

    def reject_recommendation(self, db: Session, mode: str, signal_id: str, reason: str | None = None) -> dict[str, Any]:
        signal = db.get(Signal, signal_id)
        if signal is None:
            raise ValueError("Recommendation signal not found.")
        evaluation = self._latest_mode_evaluation(db, signal.id, mode)
        if evaluation is None or evaluation.outcome not in self._recommendation_outcomes(mode):
            raise ValueError("This signal is no longer waiting for operator review.")

        final_reason = reason or "Rejected from the operator approval queue."
        db.add(
            SignalEvaluation(
                signal_id=signal.id,
                approved=False,
                evaluator=f"{mode}-operator",
                reason=final_reason,
                expected_return=signal.estimated_risk_reward,
                outcome="manual_rejected",
            )
        )
        audit_service.log(
            db,
            actor="system",
            action="recommendation.reject",
            target_type="signal",
            target_id=signal.id,
            mode=mode,
            details={"reason": final_reason},
        )
        asset = db.get(Asset, signal.asset_id)
        return {
            "signal_id": signal.id,
            "symbol": asset.symbol if asset else signal.asset_id,
            "action": signal.action,
            "confidence": signal.confidence,
            "strategy_slug": signal.metadata_json.get("preferred_strategy"),
            "provider_type": signal.provider_type,
            "outcome": "rejected",
            "reason": final_reason,
            "order_id": None,
        }

    def approve_signal(self, db: Session, mode: str, signal_id: str, reason: str | None = None) -> dict[str, Any]:
        signal = db.get(Signal, signal_id)
        if signal is None:
            raise ValueError("Signal not found.")

        latest_mode_evaluation = self._latest_mode_evaluation(db, signal.id, mode)
        if latest_mode_evaluation and latest_mode_evaluation.outcome in self._terminal_lane_outcomes:
            raise ValueError("This signal already has a live/simulation review outcome in the selected lane.")

        outcome = "sent_to_live_workflow" if mode == "live" else "approved"
        final_reason = reason or (
            "Sent to the live review queue for guarded operator approval."
            if mode == "live"
            else "Approved for simulation review and ready to load into the ticket."
        )
        db.add(
            SignalEvaluation(
                signal_id=signal.id,
                approved=True,
                evaluator=f"{mode}-operator",
                reason=final_reason,
                expected_return=signal.estimated_risk_reward,
                outcome=outcome,
            )
        )
        audit_service.log(
            db,
            actor="system",
            action="signal.approve",
            target_type="signal",
            target_id=signal.id,
            mode=mode,
            details={"outcome": outcome, "reason": final_reason},
        )
        asset = db.get(Asset, signal.asset_id)
        return {
            "signal_id": signal.id,
            "symbol": asset.symbol if asset else signal.asset_id,
            "action": signal.action,
            "confidence": signal.confidence,
            "strategy_slug": signal.metadata_json.get("preferred_strategy"),
            "provider_type": signal.provider_type,
            "outcome": outcome,
            "reason": final_reason,
            "order_id": None,
        }

    def _automation_candidates(self, db: Session, mode: str, profile: TradingAutomationProfile) -> list[Signal]:
        signals = list(
            db.scalars(
                select(Signal)
                .where(Signal.source_kind == "agent")
                .order_by(desc(Signal.occurred_at))
                .limit(60)
            )
        )

        results: list[Signal] = []
        for signal in signals:
            latest_mode_evaluation = self._latest_mode_evaluation(db, signal.id, mode)
            if latest_mode_evaluation and latest_mode_evaluation.outcome in self._terminal_lane_outcomes:
                continue
            if signal.action not in profile.tradable_actions:
                continue
            if signal.confidence < profile.confidence_threshold:
                continue
            preferred_strategy = signal.metadata_json.get("preferred_strategy")
            if profile.allowed_strategy_slugs and preferred_strategy not in profile.allowed_strategy_slugs:
                continue
            if profile.allowed_provider_types and signal.provider_type not in profile.allowed_provider_types:
                continue
            results.append(signal)
        return results

    def _strategy_view(self, strategy: Strategy) -> dict[str, Any]:
        return {
            "id": strategy.id,
            "name": strategy.name,
            "slug": strategy.slug,
            "category": strategy.category,
            "description": strategy.description,
            "enabled": strategy.enabled,
            "config_json": strategy.config_json,
        }

    def _resolve_live_broker(self, db: Session, broker_account_id: str | None = None) -> BrokerAccount | None:
        if broker_account_id:
            return db.get(BrokerAccount, broker_account_id)
        return db.scalar(
            select(BrokerAccount)
            .where(BrokerAccount.mode == "live", BrokerAccount.enabled.is_(True))
            .order_by(BrokerAccount.live_trading_enabled.desc(), BrokerAccount.updated_at.desc())
            .limit(1)
        )

    def _resolve_simulation_account(self, db: Session, simulation_account_id: str | None = None) -> SimulationAccount | None:
        if simulation_account_id:
            return db.get(SimulationAccount, simulation_account_id)
        return db.scalar(
            select(SimulationAccount).order_by(SimulationAccount.is_active.desc(), SimulationAccount.updated_at.desc()).limit(1)
        )

    def _live_account_summary(self, db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
        broker_account = self._resolve_live_broker(db)
        live_positions = portfolio_service.list_positions(db, mode="live")
        live_orders = portfolio_service.list_orders(db, mode="live")
        live_trades = portfolio_service.list_trades(db, mode="live")
        latest_snapshot = db.scalar(
            select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "live").order_by(desc(PortfolioSnapshot.timestamp)).limit(1)
        )

        fallback_cash = 0.0
        base_currency = "USD"
        broker_status = "scaffolded"
        broker_type = None
        supports_execution = False
        if broker_account is not None:
            fallback_cash = float(broker_account.settings_json.get("available_cash", 0) or 0)
            base_currency = str(broker_account.settings_json.get("currency", "USD"))
            broker_status = broker_account.status
            broker_type = broker_account.broker_type
            adapter = broker_service.get_adapter(broker_account.broker_type)
            supports_execution = adapter.capability.supports_execution

        equity = sum(position["current_price"] * position["quantity"] for position in live_positions)
        cash = latest_snapshot.cash if latest_snapshot else fallback_cash
        total_value = latest_snapshot.total_value if latest_snapshot else cash + equity
        realized = latest_snapshot.realized_pnl if latest_snapshot else sum(trade["realized_pnl"] for trade in live_trades)
        unrealized = latest_snapshot.unrealized_pnl if latest_snapshot else sum(position["unrealized_pnl"] for position in live_positions)

        account = {
            "mode": "live",
            "account_id": broker_account.id if broker_account else None,
            "account_label": broker_account.name if broker_account else "No live broker configured",
            "broker_type": broker_type,
            "status": broker_status,
            "base_currency": base_currency,
            "total_value": round(total_value, 2),
            "cash_available": round(cash, 2),
            "equity": round(equity, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "open_positions_count": len(live_positions),
            "active_orders_count": len([order for order in live_orders if order["status"] in {"pending", "accepted"}]),
            "total_trades_count": len(live_trades),
            "safety_message": "Live execution remains backend-guarded and passes through the risk engine before any broker call.",
            "live_execution_enabled": settings.enable_live_trading and bool(broker_account and broker_account.live_trading_enabled),
            "manual_position_supported": True,
            "metadata": {
                "supports_execution": supports_execution,
                "backend_live_trading_enabled": settings.enable_live_trading,
            },
        }
        controls = {
            "backend_live_trading_enabled": settings.enable_live_trading,
            "broker_execution_supported": supports_execution,
            "active_broker_account_id": broker_account.id if broker_account else None,
            "broker_accounts": [broker_service.serialize_runtime_account(db, account) for account in broker_service.list_accounts(db)],
        }
        return account, controls

    def _simulation_account_summary(self, db: Session, account: SimulationAccount | None) -> tuple[dict[str, Any], dict[str, Any]]:
        if account is None:
            return (
                {
                    "mode": "simulation",
                    "account_id": None,
                    "account_label": "No simulation account configured",
                    "broker_type": None,
                    "status": "warning",
                    "base_currency": "USD",
                    "total_value": 0,
                    "cash_available": 0,
                    "equity": 0,
                    "realized_pnl": 0,
                    "unrealized_pnl": 0,
                    "open_positions_count": 0,
                    "active_orders_count": 0,
                    "total_trades_count": 0,
                    "safety_message": "Create or select a simulation account to mirror the live trading workflow.",
                    "live_execution_enabled": False,
                    "manual_position_supported": True,
                    "metadata": {},
                },
                {"simulation_accounts": []},
            )

        simulation_summary = simulation_service.summary(db, account.id)
        positions = portfolio_service.list_positions(db, mode="simulation", simulation_account_id=account.id)
        orders = portfolio_service.list_orders(db, mode="simulation", simulation_account_id=account.id)
        account_summary = {
            "mode": "simulation",
            "account_id": account.id,
            "account_label": account.name,
            "broker_type": "simulation",
            "status": "ok",
            "base_currency": "USD",
            "total_value": round(account.cash_balance + sum(position["current_price"] * position["quantity"] for position in positions), 2),
            "cash_available": round(account.cash_balance, 2),
            "equity": round(sum(position["current_price"] * position["quantity"] for position in positions), 2),
            "realized_pnl": round(sum(position["realized_pnl"] for position in positions), 2),
            "unrealized_pnl": round(sum(position["unrealized_pnl"] for position in positions), 2),
            "open_positions_count": len(positions),
            "active_orders_count": len([order for order in orders if order["status"] in {"pending", "accepted"}]),
            "total_trades_count": simulation_summary["total_trades"],
            "safety_message": "Simulation mirrors the live workflow but uses virtual cash, fees, and fills.",
            "live_execution_enabled": False,
            "manual_position_supported": True,
            "metadata": {
                "fees_bps": account.fees_bps,
                "slippage_bps": account.slippage_bps,
                "latency_ms": account.latency_ms,
                "reset_count": account.reset_count,
            },
        }
        controls = {
            "active_simulation_account_id": account.id,
            "simulation_accounts": [
                {
                    "id": item.id,
                    "name": item.name,
                    "starting_cash": item.starting_cash,
                    "cash_balance": item.cash_balance,
                    "fees_bps": item.fees_bps,
                    "slippage_bps": item.slippage_bps,
                    "latency_ms": item.latency_ms,
                    "is_active": item.is_active,
                }
                for item in simulation_service.list_accounts(db)
            ],
        }
        return account_summary, controls

    def _protective_level(self, entry_price: float, pct: float | None, side: str, *, direction: str) -> float | None:
        if pct is None:
            return None
        if direction == "down":
            return round(entry_price * (1 - pct), 4) if side == "buy" else round(entry_price * (1 + pct), 4)
        return round(entry_price * (1 + pct), 4) if side == "buy" else round(entry_price * (1 - pct), 4)

    def _trailing_distance(self, entry_price: float, pct: float | None) -> float | None:
        if pct is None:
            return None
        return round(entry_price * pct, 4)

    def _signal_view(self, db: Session, signal: Signal) -> dict[str, Any]:
        asset = db.get(Asset, signal.asset_id)
        strategy_slug = signal.metadata_json.get("preferred_strategy")
        return {
            "id": signal.id,
            "asset_id": signal.asset_id,
            "symbol": asset.symbol if asset else signal.asset_id,
            "asset_name": asset.name if asset else signal.asset_id,
            "strategy_name": strategy_slug,
            "strategy_slug": strategy_slug,
            "action": signal.action,
            "confidence": signal.confidence,
            "status": signal.status,
            "occurred_at": signal.occurred_at,
            "ai_rationale": signal.ai_rationale,
            "suggested_entry": signal.suggested_entry,
            "suggested_stop_loss": signal.suggested_stop_loss,
            "suggested_take_profit": signal.suggested_take_profit,
            "estimated_risk_reward": signal.estimated_risk_reward,
            "provider_type": signal.provider_type,
            "model_name": signal.model_name,
            "indicators_json": signal.indicators_json,
            "related_news_ids": signal.related_news_ids,
            "related_event_ids": signal.related_event_ids,
            "mode": self._display_signal_mode(signal.mode),
            "source_kind": signal.source_kind,
            "signal_flavor": self._signal_flavor(signal, strategy_slug),
            "fresh_news_used": bool(signal.related_news_ids or signal.related_event_ids),
            "lane_statuses": self._lane_statuses(db, signal.id),
        }

    def _recommendation_view(self, db: Session, signal: Signal, evaluation: SignalEvaluation) -> dict[str, Any]:
        asset = db.get(Asset, signal.asset_id)
        queued_at = evaluation.created_at if evaluation else signal.occurred_at
        reason = evaluation.reason if evaluation.reason else "Approved by automation and waiting for operator review."
        return {
            "signal_id": signal.id,
            "asset_id": signal.asset_id,
            "symbol": asset.symbol if asset else signal.asset_id,
            "asset_name": asset.name if asset else signal.asset_id,
            "action": signal.action,
            "confidence": signal.confidence,
            "strategy_slug": signal.metadata_json.get("preferred_strategy"),
            "provider_type": signal.provider_type,
            "model_name": signal.model_name,
            "status": "approved",
            "mode": self._display_signal_mode(signal.mode),
            "occurred_at": signal.occurred_at,
            "queued_at": queued_at,
            "reason": reason,
            "suggested_entry": signal.suggested_entry,
            "suggested_stop_loss": signal.suggested_stop_loss,
            "suggested_take_profit": signal.suggested_take_profit,
            "estimated_risk_reward": signal.estimated_risk_reward,
        }

    def _latest_mode_evaluation(self, db: Session, signal_id: str, mode: str) -> SignalEvaluation | None:
        return db.scalar(
            select(SignalEvaluation)
            .where(
                SignalEvaluation.signal_id == signal_id,
                SignalEvaluation.evaluator.startswith(f"{mode}-"),
            )
            .order_by(desc(SignalEvaluation.created_at))
            .limit(1)
        )

    def _lane_statuses(self, db: Session, signal_id: str) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for lane in ("simulation", "live"):
            latest = self._latest_mode_evaluation(db, signal_id, lane)
            statuses[lane] = latest.outcome if latest and latest.outcome else "candidate"
        return statuses

    def _recommendation_outcomes(self, mode: str) -> set[str]:
        return {"sent_to_live_workflow"} if mode == "live" else {"approved"}

    def _signal_flavor(self, signal: Signal, strategy_slug: str | None) -> str:
        has_news = bool(signal.related_news_ids or signal.related_event_ids)
        has_indicators = bool(signal.indicators_json)
        if has_news and strategy_slug == "blended":
            return "blended"
        if has_news:
            return "news-enriched"
        if has_indicators and signal.ai_rationale:
            return "technical+ai"
        if signal.ai_rationale:
            return "ai-only"
        return "technical-only"

    def _display_signal_mode(self, stored_mode: str | None) -> str:
        if stored_mode in {"live", "simulation", "both", "shared", None}:
            return "shared"
        return stored_mode

    def position_actions(self, db: Session, position_id: str) -> list[dict[str, Any]]:
        position = db.get(Position, position_id)
        if position is None:
            raise ValueError("Position not found.")
        if position.status != "open":
            return []
        actions = [
            PositionActionRead(
                key="details",
                label="View details",
                description="Open the position detail sheet with provider, notes, and execution context.",
            ),
            PositionActionRead(
                key="edit_stop_loss",
                label="Edit stop loss",
                description="Adjust the protective stop-loss level for this position.",
            ),
            PositionActionRead(
                key="edit_take_profit",
                label="Edit take profit",
                description="Adjust the take-profit target for this position.",
            ),
            PositionActionRead(
                key="edit_trailing_stop",
                label="Edit trailing stop",
                description="Adjust the trailing-stop distance for this position.",
            ),
            PositionActionRead(
                key="close_partial",
                label="Close partially",
                description="Close part of the position by percentage while keeping the rest open.",
                requires_confirmation=True,
            ),
            PositionActionRead(
                key="close_full",
                label="Close fully",
                description="Close the entire open position.",
                destructive=True,
                requires_confirmation=True,
            ),
            PositionActionRead(
                key="add_note",
                label="Add note / tag",
                description="Attach notes or tags to explain manual overrides or trade context.",
            ),
            PositionActionRead(
                key="mark_manual_override",
                label="Mark manual override",
                description="Marks this position as manually managed so automation does not silently override operator intent.",
            ),
        ]
        return [item.model_dump() for item in actions]


trading_workspace_service = TradingWorkspaceService()
