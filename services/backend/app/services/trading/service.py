from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.broker import BrokerAccount
from app.models.portfolio import Order, PortfolioSnapshot, Position
from app.models.risk import RiskRule
from app.models.signal import Signal, SignalEvaluation
from app.models.simulation import SimulationAccount, SimulationOrder
from app.models.strategy import Strategy
from app.models.trading import TradingAutomationProfile
from app.schemas.portfolio import OrderCreate
from app.schemas.trading import PositionActionRead, TradingAutomationProfileUpsert
from app.services.audit.service import audit_service
from app.services.alerts.service import alert_service
from app.services.brokers.service import broker_service
from app.services.market_data.service import market_data_service
from app.services.portfolio.service import portfolio_service
from app.services.providers.service import provider_service
from app.services.simulation.service import simulation_service
from app.services.strategies.service import strategy_service
from app.utils.time import utcnow

settings = get_settings()


class TradingWorkspaceService:
    _terminal_lane_outcomes = {
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
        previous_live_model_provider = (profile.config_json or {}).get("live_model_provider_type") if mode == "live" else None
        updates = payload.model_dump()
        inherit_from_live = bool(updates.pop("inherit_from_live", False))
        config_updates = updates.pop("config_json", {})
        profile.config_json = {
            **(profile.config_json or {}),
            **config_updates,
            "inherit_from_live": inherit_from_live,
        }
        if mode == "live":
            live_model_provider = profile.config_json.get("live_model_provider_type")
            if live_model_provider:
                updates["allowed_provider_types"] = [str(live_model_provider)]
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
        if mode == "live":
            next_live_model_provider = (profile.config_json or {}).get("live_model_provider_type")
            if previous_live_model_provider != next_live_model_provider:
                audit_service.log(
                    db,
                    actor="system",
                    action="live_model.change",
                    target_type="trading_automation_profile",
                    target_id=profile.id,
                    mode="live",
                    details={
                        "previous_provider_type": previous_live_model_provider,
                        "next_provider_type": next_live_model_provider,
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
            "allowed_provider_types": self._effective_allowed_providers(effective_profile),
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
            "alerts": self._workspace_alerts(db, mode, simulation_account if mode == "simulation" else None),
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
            return self._blocked_run_with_audit(db, stored_profile, mode, "Trading212 is not connected. Live automation cannot use a fake balance.", decisions)
        if mode == "simulation" and active_simulation is None:
            return self._finalize_profile_run(stored_profile, "blocked", "No simulation account is available for automation.", decisions)
        if mode == "live":
            live_model_error = self._live_model_block_reason(db, profile)
            if live_model_error:
                return self._blocked_run_with_audit(db, stored_profile, mode, live_model_error, decisions)

        candidates = self._automation_candidates(
            db,
            mode,
            profile,
            simulation_account=active_simulation,
            broker_account=active_broker,
        )
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
            order_side = self._order_side_for_signal(signal.action, mode=mode, simulation_account=active_simulation)
            if order_side is None:
                decisions.append(self._reject_signal(db, signal, mode, f"{signal.action.upper()} is not executable in this workspace."))
                rejected_signals += 1
                continue

            entry_price = signal.suggested_entry or market_data_service.get_latest_price(db, signal.asset_id)
            if entry_price <= 0:
                decisions.append(self._reject_signal(db, signal, mode, "Signal entry price is invalid."))
                rejected_signals += 1
                continue

            sizing = self._automation_quantity(
                db,
                mode=mode,
                signal=signal,
                side=order_side,
                entry_price=entry_price,
                profile=profile,
                simulation_account=active_simulation,
                broker_account=active_broker,
                submitted_orders=submitted_orders,
            )
            if not sizing["executable"]:
                decisions.append(self._reject_signal(db, signal, mode, sizing["reason"], outcome="blocked_by_risk"))
                rejected_signals += 1
                continue
            quantity = round(float(sizing["quantity"]), 8)
            if quantity <= 0:
                decisions.append(self._reject_signal(db, signal, mode, "Configured default notional is too small for this symbol."))
                rejected_signals += 1
                continue

            stop_loss = signal.suggested_stop_loss or self._protective_level(entry_price, profile.stop_loss_pct, order_side, direction="down")
            take_profit = signal.suggested_take_profit or self._protective_level(entry_price, profile.take_profit_pct, order_side, direction="up")
            trailing_stop = self._trailing_distance(entry_price, profile.trailing_stop_pct)
            decision_reason = f"{profile.approval_mode.replace('_', ' ')} automation from signal {signal.id}"
            if sizing.get("sizing_note"):
                decision_reason = f"{decision_reason}. {sizing['sizing_note']}"

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
                    side=order_side,
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
            "tradable_actions": ["buy", "sell", "close_long", "reduce_long"],
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

    def _blocked_run_with_audit(
        self,
        db: Session,
        profile: TradingAutomationProfile,
        mode: str,
        message: str,
        decisions: list[dict[str, Any]],
    ) -> dict:
        audit_service.log(
            db,
            actor="system",
            action="automation.blocked",
            target_type="trading_automation_profile",
            target_id=profile.id,
            mode=mode,
            details={"reason": message},
        )
        return self._finalize_profile_run(profile, "blocked", message, decisions)

    def _reject_signal(self, db: Session, signal: Signal, mode: str, reason: str, *, outcome: str = "rejected") -> dict[str, Any]:
        db.add(
            SignalEvaluation(
                signal_id=signal.id,
                approved=False,
                evaluator=f"{mode}-automation",
                reason=reason,
                expected_return=signal.estimated_risk_reward,
                outcome=outcome,
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
            "outcome": outcome,
            "reason": reason,
            "order_id": None,
        }

    def _automation_quantity(
        self,
        db: Session,
        *,
        mode: str,
        signal: Signal,
        side: str,
        entry_price: float,
        profile: TradingAutomationProfile,
        simulation_account: SimulationAccount | None,
        broker_account: BrokerAccount | None,
        submitted_orders: int,
    ) -> dict[str, Any]:
        desired_notional = max(float(profile.default_order_notional or 0), 0.0)
        if side in {"sell", "cover_short"}:
            held_quantity = self._held_quantity(db, signal.asset_id, mode, simulation_account, broker_account)
            closeable_quantity = abs(held_quantity) if side == "cover_short" and held_quantity < 0 else max(held_quantity, 0.0)
            if closeable_quantity <= 0:
                return {
                    "executable": False,
                    "reason": f"{signal.action.upper()} was not processed because this account has no matching position to close or reduce.",
                }
            desired_quantity = desired_notional / entry_price if desired_notional > 0 else closeable_quantity
            quantity = min(closeable_quantity, desired_quantity)
            return {
                "executable": quantity > 0,
                "quantity": quantity,
                "sizing_note": f"Sized to {round(quantity, 6)} because the account currently holds {round(closeable_quantity, 6)} shares.",
            }

        available_to_trade = self._available_to_trade_for_mode(db, mode, simulation_account, broker_account)
        if available_to_trade <= 0:
            return {
                "executable": False,
                "reason": "Order not processed because the cash reserve rule leaves no available-to-trade cash.",
            }

        remaining_slots = max(int(profile.max_orders_per_run or 1) - submitted_orders, 1)
        per_order_budget = max(available_to_trade / remaining_slots, 0.0)
        order_notional = min(desired_notional or per_order_budget, per_order_budget)
        if order_notional <= 0.01:
            return {
                "executable": False,
                "reason": "Order not processed because available-to-trade cash is below the minimum fractional order budget.",
            }

        sizing_note = None
        if desired_notional and order_notional < desired_notional:
            sizing_note = (
                f"Fractional sizing reduced notional from {desired_notional:.2f} to {order_notional:.2f} "
                "to respect cash reserve and leave room for other positions."
            )
        return {
            "executable": True,
            "quantity": order_notional / entry_price,
            "sizing_note": sizing_note,
        }

    def _workspace_signals(self, db: Session, mode: str) -> list[dict]:
        signals = list(db.scalars(select(Signal).order_by(desc(Signal.occurred_at)).limit(40)))
        return [self._signal_view(db, signal) for signal in signals[:12]]

    def _workspace_alerts(self, db: Session, mode: str, simulation_account: SimulationAccount | None = None) -> list:
        alerts = alert_service.list_alerts(db, mode=mode)
        if mode != "simulation" or simulation_account is None:
            return alerts

        scoped_alerts = []
        for alert in alerts:
            if alert.mode in {None, "system"}:
                scoped_alerts.append(alert)
                continue
            if not alert.source_ref:
                scoped_alerts.append(alert)
                continue
            order = db.get(Order, alert.source_ref)
            if order is None:
                continue
            if (order.audit_context or {}).get("simulation_account_id") == simulation_account.id:
                scoped_alerts.append(alert)
        return scoped_alerts

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
        if mode == "live":
            _, profile, _ = self.resolve_profile_pair(db, "live")
            live_model_error = self._live_model_block_reason(db, profile)
            if live_model_error:
                raise ValueError(live_model_error)
            configured_provider = self._configured_live_provider(profile)
            if configured_provider and signal.provider_type != configured_provider:
                raise ValueError(
                    f"Live trading is locked to {configured_provider}; this signal came from {signal.provider_type or 'unknown'}."
                )

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

    def _automation_candidates(
        self,
        db: Session,
        mode: str,
        profile: TradingAutomationProfile,
        *,
        simulation_account: SimulationAccount | None = None,
        broker_account: BrokerAccount | None = None,
    ) -> list[Signal]:
        signals = list(
            db.scalars(
                select(Signal)
                .where(Signal.source_kind == "agent")
                .order_by(desc(Signal.occurred_at))
                .limit(1000)
            )
        )

        approved_results: list[Signal] = []
        fresh_results: list[Signal] = []
        for signal in signals:
            latest_mode_evaluation = self._latest_mode_evaluation(db, signal.id, mode)
            if latest_mode_evaluation and latest_mode_evaluation.outcome in self._terminal_lane_outcomes:
                continue
            manually_approved = bool(latest_mode_evaluation and latest_mode_evaluation.outcome == "approved")
            if not manually_approved:
                if signal.action not in self._effective_tradable_actions(profile, simulation_account):
                    continue
                if signal.confidence < profile.confidence_threshold:
                    continue
                if not self._signal_matches_strategy_allowlist(signal, profile.allowed_strategy_slugs):
                    continue
                allowed_provider_types = self._effective_allowed_providers(profile)
                if allowed_provider_types and signal.provider_type not in allowed_provider_types:
                    continue
            order_side = self._order_side_for_signal(signal.action, mode=mode, simulation_account=simulation_account)
            if order_side is None:
                continue
            if order_side in {"sell", "cover_short"}:
                held_quantity = self._held_quantity(db, signal.asset_id, mode, simulation_account, broker_account)
                if order_side == "cover_short" and held_quantity >= 0:
                    continue
                if order_side == "sell" and held_quantity <= 0:
                    continue
            if manually_approved:
                approved_results.append(signal)
            else:
                fresh_results.append(signal)
        return [*approved_results, *fresh_results]

    def _effective_tradable_actions(self, profile: TradingAutomationProfile, simulation_account: SimulationAccount | None = None) -> set[str]:
        actions = {str(action).lower() for action in (profile.tradable_actions or [])}
        # If selling is enabled, exit-style signal actions should be eligible
        # too. They still require an actual held position before execution.
        if "sell" in actions:
            actions.update({"close_long", "reduce_long"})
        if simulation_account and simulation_account.short_enabled:
            if "short" in actions:
                actions.add("cover_short")
        return actions

    def _signal_matches_strategy_allowlist(self, signal: Signal, allowed_strategy_slugs: list[str] | None) -> bool:
        if not allowed_strategy_slugs:
            return True
        metadata = signal.metadata_json or {}
        preferred_strategy = metadata.get("preferred_strategy") or metadata.get("strategy_slug")
        if preferred_strategy in allowed_strategy_slugs:
            return True

        # Blended signals often carry the winning component votes. Treat a blended
        # signal as eligible when an allowed component agreed with the final action.
        strategy_votes = (signal.indicators_json or {}).get("strategy_votes") or {}
        normalized_action = str(signal.action).lower()
        for slug in allowed_strategy_slugs:
            vote = strategy_votes.get(slug)
            if not isinstance(vote, dict):
                continue
            vote_action = str(vote.get("action") or "").lower()
            vote_confidence = float(vote.get("confidence") or 0)
            if vote_action == normalized_action and vote_confidence > 0:
                return True
        return False

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
            account = db.get(BrokerAccount, broker_account_id)
            return account if account and account.broker_type == "trading212" else None
        return db.scalar(
            select(BrokerAccount)
            .where(BrokerAccount.mode == "live", BrokerAccount.enabled.is_(True), BrokerAccount.broker_type == "trading212")
            .order_by(BrokerAccount.updated_at.desc())
            .limit(1)
        )

    def _resolve_simulation_account(self, db: Session, simulation_account_id: str | None = None) -> SimulationAccount | None:
        simulation_service.ensure_model_accounts(db)
        if simulation_account_id:
            return db.get(SimulationAccount, simulation_account_id)
        return db.scalar(
            select(SimulationAccount).order_by(SimulationAccount.is_active.desc(), SimulationAccount.updated_at.desc()).limit(1)
        )

    def _effective_allowed_providers(self, profile: TradingAutomationProfile) -> list[str]:
        configured_live_provider = self._configured_live_provider(profile)
        if profile.mode == "live" and configured_live_provider:
            return [configured_live_provider]
        return profile.allowed_provider_types or []

    def _configured_live_provider(self, profile: TradingAutomationProfile) -> str | None:
        value = (profile.config_json or {}).get("live_model_provider_type")
        if value:
            return str(value)
        if profile.mode == "live" and len(profile.allowed_provider_types or []) == 1:
            return profile.allowed_provider_types[0]
        return None

    def _live_model_block_reason(self, db: Session, profile: TradingAutomationProfile) -> str | None:
        configured_provider = self._configured_live_provider(profile)
        if not configured_provider:
            return "Live automation requires exactly one configured Live trading model in Settings."
        config = provider_service.get_config(db, configured_provider)
        if config is None:
            return f"Configured live model profile {configured_provider} does not exist."
        try:
            provider_profile = provider_service.get_profile(configured_provider)
        except ValueError as exc:
            return str(exc)
        if provider_profile.trading_mode != "live":
            return f"{configured_provider} is not a live/actual-trading provider profile."
        if not config.enabled:
            return f"Configured live model profile {configured_provider} is disabled."
        if config.last_health_status == "error":
            return f"Configured live model profile {configured_provider} is unhealthy: {config.last_health_message or 'provider health check failed'}."
        return None

    def _order_side_for_signal(
        self,
        action: str,
        *,
        mode: str,
        simulation_account: SimulationAccount | None = None,
    ) -> str | None:
        normalized = str(action).strip().lower()
        if normalized in {"buy", "sell"}:
            return normalized
        if normalized in {"close_long", "reduce_long"}:
            return "sell"
        if normalized == "short":
            if mode == "simulation" and simulation_account and simulation_account.short_enabled:
                return "short"
            return None
        if normalized == "cover_short":
            if mode == "simulation" and simulation_account and simulation_account.short_enabled:
                return "cover_short"
            return None
        return None

    def _cash_reserve_summary(
        self,
        db: Session,
        mode: str,
        cash_balance: float,
        total_value: float,
        simulation_account: SimulationAccount | None = None,
    ) -> dict[str, float]:
        rule = db.scalar(select(RiskRule).where(RiskRule.rule_type == "cash_reserve", RiskRule.enabled.is_(True)).limit(1))
        reserve_pct = 0.0
        if rule is not None:
            if mode == "simulation" and simulation_account and simulation_account.min_cash_reserve_percent is not None:
                reserve_pct = float(simulation_account.min_cash_reserve_percent)
            else:
                mode_key = "simulation_override_pct" if mode == "simulation" else "live_override_pct"
                reserve_pct = float((rule.config_json or {}).get(mode_key) or (rule.config_json or {}).get("min_cash_reserve_pct") or 0)
        reserve_pct = max(0.0, min(1.0, reserve_pct))
        reserve_amount = max(total_value, 0.0) * reserve_pct
        return {
            "cash_reserve_percent": round(reserve_pct, 4),
            "cash_reserve_amount": round(reserve_amount, 2),
            "available_to_trade_cash": round(max(cash_balance - reserve_amount, 0.0), 2),
        }

    def _available_to_trade_for_mode(
        self,
        db: Session,
        mode: str,
        simulation_account: SimulationAccount | None,
        broker_account: BrokerAccount | None,
    ) -> float:
        if mode == "simulation" and simulation_account is not None:
            positions = [
                position
                for position in portfolio_service.list_positions(db, mode="simulation", simulation_account_id=simulation_account.id)
                if position["status"] == "open"
            ]
            total_value = simulation_account.cash_balance + sum(position["current_price"] * position["quantity"] for position in positions)
            return float(self._cash_reserve_summary(db, "simulation", simulation_account.cash_balance, total_value, simulation_account)["available_to_trade_cash"])
        if mode == "live" and broker_account is not None:
            cash = float(broker_account.settings_json.get("available_cash") or broker_account.settings_json.get("cash_balance") or 0)
            total_value = float(broker_account.settings_json.get("total_value") or cash)
            return float(self._cash_reserve_summary(db, "live", cash, total_value)["available_to_trade_cash"])
        return 0.0

    def _held_quantity(
        self,
        db: Session,
        asset_id: str,
        mode: str,
        simulation_account: SimulationAccount | None,
        broker_account: BrokerAccount | None,
    ) -> float:
        stmt = select(Position).where(Position.asset_id == asset_id, Position.mode == mode, Position.status == "open")
        if simulation_account is not None:
            stmt = stmt.where(Position.simulation_account_id == simulation_account.id)
        if broker_account is not None:
            stmt = stmt.where(Position.broker_account_id == broker_account.id)
        position = db.scalar(stmt.limit(1))
        return float(position.quantity if position else 0)

    def _simulation_account_comparison_item(self, db: Session, account: SimulationAccount) -> dict[str, Any]:
        positions = [position for position in portfolio_service.list_positions(db, mode="simulation", simulation_account_id=account.id) if position["status"] == "open"]
        trades = portfolio_service.list_trades(db, mode="simulation", simulation_account_id=account.id)
        rejected_orders = list(
            db.scalars(
                select(SimulationOrder).where(
                    SimulationOrder.simulation_account_id == account.id,
                    SimulationOrder.status == "rejected",
                )
            )
        )
        signals = list(db.scalars(select(Signal).where(Signal.provider_type == account.provider_type))) if account.provider_type else []
        invalid_signals = [
            signal
            for signal in signals
            if str(signal.action).lower() not in {"buy", "sell", "hold", "close_long", "reduce_long", "short", "cover_short"}
        ]
        equity = sum(position["current_price"] * position["quantity"] for position in positions)
        total_value = account.cash_balance + equity
        reserve = self._cash_reserve_summary(db, "simulation", account.cash_balance, total_value, account)
        wins = [trade for trade in trades if trade["realized_pnl"] > 0]
        losses = [abs(trade["realized_pnl"]) for trade in trades if trade["realized_pnl"] < 0]
        equity_curve = [
            snapshot.total_value
            for snapshot in db.scalars(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.mode == "simulation", PortfolioSnapshot.simulation_account_id == account.id)
                .order_by(PortfolioSnapshot.timestamp.asc())
                .limit(200)
            )
        ]
        peak = equity_curve[0] if equity_curve else account.starting_cash
        max_drawdown = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            if peak:
                max_drawdown = min(max_drawdown, (value - peak) / peak)
        return {
            "id": account.id,
            "name": account.name,
            "provider_type": account.provider_type,
            "model_name": account.model_name,
            "starting_cash": account.starting_cash,
            "cash_balance": account.cash_balance,
            "reserved_cash": reserve["cash_reserve_amount"],
            "portfolio_value": round(total_value, 2),
            "available_to_trade_cash": reserve["available_to_trade_cash"],
            "cash_reserve_percent": reserve["cash_reserve_percent"],
            "cash_reserve_amount": reserve["cash_reserve_amount"],
            "fees_bps": account.fees_bps,
            "slippage_bps": account.slippage_bps,
            "latency_ms": account.latency_ms,
            "short_enabled": account.short_enabled,
            "short_borrow_fee_bps": account.short_borrow_fee_bps,
            "short_margin_requirement": account.short_margin_requirement,
            "partial_fill_ratio": account.partial_fill_ratio,
            "enforce_market_hours": account.enforce_market_hours,
            "is_active": account.is_active,
            "realized_pnl": round(sum(trade["realized_pnl"] for trade in trades), 2),
            "unrealized_pnl": round(sum(position["unrealized_pnl"] for position in positions), 2),
            "total_return": round(((total_value - account.starting_cash) / account.starting_cash) if account.starting_cash else 0, 4),
            "win_rate": round((len(wins) / len(trades)) if trades else 0, 4),
            "profit_factor": round((sum(trade["realized_pnl"] for trade in wins) / sum(losses)) if losses else sum(trade["realized_pnl"] for trade in wins), 2) if trades else 0,
            "max_drawdown": round(max_drawdown, 4),
            "trade_count": len(trades),
            "rejected_trade_count": len(rejected_orders),
            "invalid_signal_count": len(invalid_signals),
            "invalid_signal_rate": round((len(invalid_signals) / len(signals)) if signals else 0, 4),
            "useful_signal_rate": round((len(trades) / len(signals)) if signals else 0, 4),
            "reset_count": account.reset_count,
        }

    def _live_account_summary(self, db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
        broker_account = self._resolve_live_broker(db)
        live_positions = [position for position in portfolio_service.list_positions(db, mode="live") if position["status"] == "open"]
        live_orders = portfolio_service.list_orders(db, mode="live")
        live_trades = portfolio_service.list_trades(db, mode="live")

        base_currency = "USD"
        broker_status = "disconnected"
        broker_type = None
        supports_execution = False
        cash = 0.0
        total_value = 0.0
        equity = 0.0
        realized = sum(trade["realized_pnl"] for trade in live_trades)
        unrealized = sum(position["unrealized_pnl"] for position in live_positions)
        last_sync_error = None
        last_successful_sync_at = None
        synced = False
        if broker_account is not None:
            synced = broker_account.settings_json.get("available_cash") is not None or broker_account.settings_json.get("total_value") is not None
            cash = float(broker_account.settings_json.get("available_cash") or broker_account.settings_json.get("cash_balance") or 0)
            equity = float(broker_account.settings_json.get("invested_value") or 0)
            total_value = float(broker_account.settings_json.get("total_value") or cash + equity)
            realized = float(broker_account.settings_json.get("realized_pnl") or realized)
            unrealized = float(broker_account.settings_json.get("unrealized_pnl") or unrealized)
            base_currency = str(broker_account.settings_json.get("currency", "USD"))
            broker_status = broker_account.status
            broker_type = broker_account.broker_type
            adapter = broker_service.get_adapter(broker_account.broker_type)
            supports_execution = adapter.capability.supports_execution
            latest_sync = broker_service.latest_sync_event(db, broker_account.id)
            latest_successful_sync = broker_service.latest_successful_sync_event(db, broker_account.id)
            if latest_successful_sync and latest_successful_sync.completed_at:
                last_successful_sync_at = latest_successful_sync.completed_at.isoformat()
            if latest_sync and latest_sync.status in {"error", "warn"}:
                last_sync_error = (
                    (latest_sync.details_json or {}).get("account_message")
                    or (latest_sync.details_json or {}).get("positions_message")
                    or (latest_sync.details_json or {}).get("message")
                )

        reserve = self._cash_reserve_summary(db, "live", cash, total_value)
        if broker_account is None:
            safety_message = "Trading212 not connected. Live balances are hidden until a real broker sync succeeds."
        elif not synced:
            safety_message = "Trading212 is configured but no live cash balance has been synced yet. Use Sync now."
        else:
            safety_message = "Trading212 live cash was synced. Live execution remains backend-guarded and risk-validated."

        account = {
            "mode": "live",
            "account_id": broker_account.id if broker_account else None,
            "account_label": broker_account.name if broker_account else "No live broker configured",
            "broker_type": broker_type,
            "status": broker_status,
            "base_currency": base_currency,
            "total_value": round(total_value, 2),
            "total_cash": round(cash, 2),
            "cash_available": round(cash, 2),
            "available_to_trade_cash": reserve["available_to_trade_cash"],
            "cash_reserve_percent": reserve["cash_reserve_percent"],
            "cash_reserve_amount": reserve["cash_reserve_amount"],
            "equity": round(equity, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "open_positions_count": len(live_positions),
            "active_orders_count": len([order for order in live_orders if order["status"] in {"pending", "accepted"}]),
            "total_trades_count": len(live_trades),
            "safety_message": safety_message,
            "live_execution_enabled": settings.enable_live_trading and bool(broker_account and broker_account.live_trading_enabled),
            "manual_position_supported": True,
            "metadata": {
                "supports_execution": supports_execution,
                "backend_live_trading_enabled": settings.enable_live_trading,
                "broker_synced": synced,
                "last_sync_error": last_sync_error,
                "last_successful_sync_at": last_successful_sync_at,
                "last_synced_at": broker_account.settings_json.get("last_synced_at") if broker_account else None,
                "synced_positions": broker_account.settings_json.get("synced_positions", []) if broker_account else [],
                "synced_pies": broker_account.settings_json.get("synced_pies", []) if broker_account else [],
                "short_supported": False,
                "live_model_provider_type": self._configured_live_provider(self.get_or_create_profile(db, "live")),
            },
        }
        controls = {
            "backend_live_trading_enabled": settings.enable_live_trading,
            "broker_execution_supported": supports_execution,
            "active_broker_account_id": broker_account.id if broker_account else None,
            "broker_accounts": [broker_service.serialize_runtime_account(db, account) for account in broker_service.list_accounts(db)],
            "synced_pies": broker_account.settings_json.get("synced_pies", []) if broker_account else [],
            "live_model_provider_type": self._configured_live_provider(self.get_or_create_profile(db, "live")),
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
                    "total_cash": 0,
                    "cash_available": 0,
                    "available_to_trade_cash": 0,
                    "cash_reserve_percent": 0,
                    "cash_reserve_amount": 0,
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
        all_positions = portfolio_service.list_positions(db, mode="simulation", simulation_account_id=account.id)
        positions = [position for position in all_positions if position["status"] == "open"]
        orders = portfolio_service.list_orders(db, mode="simulation", simulation_account_id=account.id)
        signed_equity = sum(position["current_price"] * position["quantity"] for position in positions)
        total_value = account.cash_balance + signed_equity
        reserve = self._cash_reserve_summary(db, "simulation", account.cash_balance, total_value, account)
        account_summary = {
            "mode": "simulation",
            "account_id": account.id,
            "account_label": account.name,
            "broker_type": "simulation",
            "status": "ok",
            "base_currency": "USD",
            "total_value": round(total_value, 2),
            "total_cash": round(account.cash_balance, 2),
            "cash_available": round(account.cash_balance, 2),
            "available_to_trade_cash": reserve["available_to_trade_cash"],
            "cash_reserve_percent": reserve["cash_reserve_percent"],
            "cash_reserve_amount": reserve["cash_reserve_amount"],
            "equity": round(signed_equity, 2),
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
                "provider_type": account.provider_type,
                "model_name": account.model_name,
                "short_enabled": account.short_enabled,
                "short_borrow_fee_bps": account.short_borrow_fee_bps,
                "short_margin_requirement": account.short_margin_requirement,
                "partial_fill_ratio": account.partial_fill_ratio,
                "enforce_market_hours": account.enforce_market_hours,
            },
        }
        controls = {
            "active_simulation_account_id": account.id,
            "simulation_accounts": [self._simulation_account_comparison_item(db, item) for item in simulation_service.list_accounts(db)],
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
