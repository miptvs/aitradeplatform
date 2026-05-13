import json
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.asset import Asset
from app.models.health import SystemHealthEvent
from app.models.news import ExtractedEvent, NewsArticle
from app.models.portfolio import Order, Position, PositionStopEvent, Trade
from app.models.signal import Signal, SignalEvaluation
from app.models.simulation import SimulationAccount
from app.models.strategy import Strategy
from app.services.portfolio.service import portfolio_service
from app.services.market_data.service import market_data_service
from app.services.mcp.client import mcp_client_service
from app.services.providers.service import provider_service
from app.services.signals.indicators import bollinger, macd, momentum, rsi, sma, support_resistance, volatility, volume_ratio
from app.services.signals.strategies import StrategyDecision, blended, breakout, event_driven, mean_reversion, news_momentum, trend_following
from app.utils.serialization import to_plain_dict
from app.utils.time import utcnow


class SignalService:
    def list_signals(self, db: Session, provider_type: str | None = None) -> list[dict]:
        query = select(Signal).where(Signal.source_kind == "agent")
        if provider_type:
            query = query.where(Signal.provider_type == provider_type)
        signals = list(db.scalars(query.order_by(desc(Signal.occurred_at)).limit(200)))
        return [self._signal_view(db, signal) for signal in signals]

    def get_signal(self, db: Session, signal_id: str) -> dict:
        signal = db.get(Signal, signal_id)
        if signal is None:
            raise ValueError("Signal not found.")
        return self._signal_detail_view(db, signal)

    def get_signal_trace(self, db: Session, signal_id: str) -> dict:
        signal = db.get(Signal, signal_id)
        if signal is None:
            raise ValueError("Signal not found.")
        return self._build_trace(db, signal=signal, entrypoint_type="signal", entrypoint_id=signal.id)

    def get_order_trace(self, db: Session, order_id: str) -> dict:
        order = db.get(Order, order_id)
        if order is None:
            raise ValueError("Order not found.")
        signal = db.get(Signal, order.signal_id) if order.signal_id else None
        return self._build_trace(db, signal=signal, entrypoint_type="order", entrypoint_id=order.id, seed_orders=[order])

    def get_trade_trace(self, db: Session, trade_id: str) -> dict:
        trade = db.get(Trade, trade_id)
        if trade is None:
            raise ValueError("Trade not found.")
        seed_orders = [db.get(Order, trade.order_id)] if trade.order_id else []
        seed_orders = [order for order in seed_orders if order is not None]
        signal = self._root_signal_from_components(db, orders=seed_orders, positions=[], trades=[trade])
        return self._build_trace(db, signal=signal, entrypoint_type="trade", entrypoint_id=trade.id, seed_orders=seed_orders, seed_trades=[trade])

    def get_position_trace(self, db: Session, position_id: str) -> dict:
        position = db.get(Position, position_id)
        if position is None:
            raise ValueError("Position not found.")
        seed_orders = list(db.scalars(select(Order).where(Order.position_id == position.id).order_by(desc(Order.created_at)).limit(50)))
        seed_trades = list(db.scalars(select(Trade).where(Trade.position_id == position.id).order_by(desc(Trade.executed_at)).limit(100)))
        signal = self._root_signal_from_components(db, orders=seed_orders, positions=[position], trades=seed_trades)
        return self._build_trace(
            db,
            signal=signal,
            entrypoint_type="position",
            entrypoint_id=position.id,
            seed_orders=seed_orders,
            seed_positions=[position],
            seed_trades=seed_trades,
        )

    def generate_signals(self, db: Session, provider_type: str | None = None, *, force_refresh: bool = False) -> list[Signal]:
        if provider_type:
            return self._generate_for_provider(db, provider_type, force_refresh=force_refresh)

        created: list[Signal] = []
        for config in provider_service.list_configs(db):
            profile = provider_service.get_profile(config.provider_type)
            if not config.enabled or profile.trading_mode != "simulation":
                continue
            try:
                created.extend(self._generate_for_provider(db, config.provider_type, force_refresh=force_refresh))
            except Exception:
                continue
        return created

    def latest_generation_diagnostics(self, db: Session, provider_type: str | None = None) -> dict:
        events = list(
            db.scalars(
                select(SystemHealthEvent)
                .where(SystemHealthEvent.component == "signals.refresh")
                .order_by(desc(SystemHealthEvent.observed_at))
                .limit(50)
            )
        )
        event = None
        if provider_type:
            for candidate in events:
                metadata = candidate.metadata_json or {}
                if metadata.get("provider_type") == provider_type:
                    event = candidate
                    break
            if event is None:
                for candidate in events:
                    metadata = candidate.metadata_json or {}
                    if metadata.get("provider_type") == "all":
                        event = candidate
                        break
        elif events:
            event = events[0]
        if event is None:
            return {
                "provider_type": provider_type or "all",
                "status": "none",
                "run_type": "none",
                "observed_at": None,
                "created_signal_ids": [],
                "created_count": 0,
                "message": "No signal refresh has been recorded yet.",
                "detail": None,
                "market_report": {},
                "news_report": {},
            }
        metadata = event.metadata_json or {}
        return {
            "provider_type": metadata.get("provider_type", provider_type or "all"),
            "status": metadata.get("status", event.status),
            "run_type": metadata.get("run_type", "manual"),
            "observed_at": event.observed_at.isoformat(),
            "created_signal_ids": metadata.get("created_signal_ids", []),
            "created_count": metadata.get("created_count", 0),
            "message": event.message,
            "detail": metadata.get("detail"),
            "market_report": metadata.get("market_report", {}),
            "news_report": metadata.get("news_report", {}),
        }

    def record_generation_diagnostics(
        self,
        db: Session,
        *,
        provider_type: str | None,
        status: str,
        run_type: str,
        message: str,
        created_signal_ids: list[str] | None = None,
        created_count: int = 0,
        detail: str | None = None,
        market_report: dict | None = None,
        news_report: dict | None = None,
        observed_at=None,
    ) -> dict:
        observed = observed_at or utcnow()
        metadata = {
            "provider_type": provider_type or "all",
            "status": status,
            "run_type": run_type,
            "created_signal_ids": created_signal_ids or [],
            "created_count": created_count,
            "detail": detail,
            "market_report": market_report or {},
            "news_report": news_report or {},
        }
        db.add(
            SystemHealthEvent(
                component="signals.refresh",
                status=status,
                message=message,
                metadata_json=metadata,
                observed_at=observed,
            )
        )
        return {
            **metadata,
            "observed_at": observed.isoformat(),
            "message": message,
        }

    def _generate_for_provider(self, db: Session, provider_type: str, *, force_refresh: bool = False) -> list[Signal]:
        config = provider_service.get_config(db, provider_type)
        if config is None:
            raise ValueError(f"Provider config not found for {provider_type}")
        if not config.enabled:
            raise ValueError(f"Provider profile {provider_type} is disabled")

        profile = provider_service.get_profile(provider_type)
        strategies = {strategy.slug: strategy for strategy in db.scalars(select(Strategy))}
        recent_news = self._recent_real_news(db)
        created: list[Signal] = []
        provider_errors: list[str] = []
        candidate_limit = 1 if profile.deployment_scope == "local" else 2
        provider_timeout = 12 if profile.deployment_scope == "local" else 20
        simulation_account = self._simulation_account_for_provider(db, provider_type)
        held_asset_ids = {
            item
            for item in db.scalars(
                select(Position.asset_id).where(*self._provider_position_filters(provider_type, simulation_account))
            ).all()
            if item is not None
        }

        candidates: list[dict[str, Any]] = []
        for asset in self._eligible_assets(db):
            history = market_data_service.get_history(db, asset.id, limit=90)
            if len(history) < 30 or not self._history_is_real(history):
                continue

            latest_existing = db.scalar(
                select(Signal)
                .where(Signal.asset_id == asset.id, Signal.provider_type == provider_type, Signal.source_kind == "agent")
                .order_by(desc(Signal.occurred_at))
                .limit(1)
            )
            if not force_refresh and latest_existing and (utcnow() - latest_existing.occurred_at).total_seconds() < 900:
                continue

            closes = [item.close_price for item in history]
            volumes = [item.volume for item in history]
            latest_news = self._latest_news_for_symbol(recent_news, asset.symbol)
            latest_event = self._latest_event_for_symbol(db, asset.symbol)
            indicator_payload = self._build_indicator_payload(closes, volumes)
            decisions = self._build_strategy_decisions(indicator_payload, latest_news, latest_event)
            preferred_slug, preferred_decision = self._select_preferred_decision(decisions)
            is_held = asset.id in held_asset_ids
            score = preferred_decision.confidence
            if preferred_decision.action != "hold":
                score += 0.15
            if is_held:
                score += 0.04
            if is_held and preferred_decision.action == "sell":
                score += 0.18
            if latest_news and latest_news.impact_score:
                score += latest_news.impact_score * 0.1
            if latest_event and latest_event.impact_score:
                score += latest_event.impact_score * 0.1
            candidates.append(
                {
                    "asset": asset,
                    "indicator_payload": indicator_payload,
                    "decisions": decisions,
                    "preferred_slug": preferred_slug,
                    "preferred_decision": preferred_decision,
                    "latest_news": latest_news,
                    "latest_event": latest_event,
                    "is_held": is_held,
                    "score": score,
                }
            )

        ranked_candidates = sorted(candidates, key=lambda item: item["score"], reverse=True)
        selected_candidates: list[dict[str, Any]] = []
        exit_candidate = next(
            (
                item
                for item in ranked_candidates
                if item["is_held"] and item["preferred_decision"].action == "sell"
            ),
            None,
        )
        if exit_candidate is not None:
            selected_candidates.append(exit_candidate)
        for candidate in ranked_candidates:
            if candidate in selected_candidates:
                continue
            if len(selected_candidates) >= candidate_limit:
                break
            selected_candidates.append(candidate)

        for candidate in selected_candidates:
            asset = candidate["asset"]
            indicator_payload = candidate["indicator_payload"]
            decisions = candidate["decisions"]
            preferred_slug = candidate["preferred_slug"]
            preferred_decision = candidate["preferred_decision"]
            latest_news = candidate["latest_news"]
            latest_event = candidate["latest_event"]
            is_held = candidate["is_held"]
            strategy = strategies.get(preferred_slug)
            mcp_context = mcp_client_service.get_signal_context(symbol=asset.symbol, mode=profile.trading_mode)
            prompt = self._signal_prompt(
                asset=asset,
                indicators=indicator_payload,
                decisions=decisions,
                preferred_slug=preferred_slug,
                latest_news=latest_news,
                latest_event=latest_event,
                profile_title=profile.title,
                mcp_context=mcp_context,
            )

            try:
                result = provider_service.run_task(
                    db,
                    task_name="signal_generation",
                    prompt=prompt,
                    provider_type=provider_type,
                    timeout_seconds=provider_timeout,
                    allow_fallback=False,
                    metadata={"symbol": asset.symbol, "preferred_strategy": preferred_slug},
                )
            except Exception as exc:
                provider_errors.append(f"{asset.symbol}: {exc}")
                if profile.deployment_scope == "local":
                    break
                continue

            parsed = self._parse_model_response(result.text)
            model_action = self._normalize_action(parsed.get("action"), preferred_decision.action)
            action = self._normalize_action_for_position_state(model_action, is_held=is_held, simulation_account=simulation_account)
            confidence = self._clamp_confidence(parsed.get("confidence", preferred_decision.confidence))
            strategy_slug = self._normalize_strategy(parsed.get("strategy"), preferred_slug)
            strategy = strategies.get(strategy_slug, strategy)

            suggested_entry = self._safe_float(parsed.get("suggested_entry")) or indicator_payload["close"]
            default_stop, default_target = self._default_protective_levels(suggested_entry, action)
            suggested_stop_loss = self._safe_float(parsed.get("suggested_stop_loss")) or default_stop
            suggested_take_profit = self._safe_float(parsed.get("suggested_take_profit")) or default_target
            estimated_risk_reward = self._safe_float(parsed.get("estimated_risk_reward"))
            if estimated_risk_reward is None and suggested_stop_loss is not None and suggested_take_profit is not None:
                estimated_risk_reward = self._risk_reward(suggested_entry, suggested_stop_loss, suggested_take_profit, action)
            suggested_size_type, suggested_size_value = self._normalize_position_size_suggestion(
                parsed.get("suggested_position_size_type"),
                parsed.get("suggested_position_size_value"),
                action,
            )
            fallback_quantity = self._safe_float(parsed.get("fallback_quantity"), precision=6)

            signal = Signal(
                asset_id=asset.id,
                strategy_id=strategy.id if strategy else None,
                action=action,
                confidence=confidence,
                status="candidate",
                occurred_at=utcnow(),
                indicators_json={
                    **indicator_payload,
                    "strategy_votes": {
                        slug: {
                            "action": decision.action,
                            "confidence": decision.confidence,
                            "rationale": decision.rationale,
                        }
                        for slug, decision in decisions.items()
                    },
                },
                related_news_ids=[latest_news.id] if latest_news else [],
                related_event_ids=[latest_event.id] if latest_event else [],
                ai_rationale=(parsed.get("rationale") or result.text).strip(),
                suggested_entry=suggested_entry,
                suggested_stop_loss=suggested_stop_loss,
                suggested_take_profit=suggested_take_profit,
                estimated_risk_reward=estimated_risk_reward,
                suggested_position_size_type=suggested_size_type,
                suggested_position_size_value=suggested_size_value,
                fallback_quantity=fallback_quantity,
                provider_type=provider_type,
                model_name=result.model_name,
                mode="both",
                source_kind="agent",
                metadata_json={
                    "symbol": asset.symbol,
                    "provider_vendor": profile.vendor_key,
                    "preferred_strategy": preferred_slug,
                    "generation_profile_mode": profile.trading_mode,
                    "trade_intent": self._trade_intent(action, is_held),
                    "is_held_asset": is_held,
                    "model_action": model_action,
                    "normalized_from_model_action": model_action if model_action != action else None,
                    "news_title": latest_news.title if latest_news else None,
                    "event_type": latest_event.event_type if latest_event else None,
                    "mcp_context_used": bool(mcp_context),
                },
            )
            db.add(signal)
            db.flush()
            created.append(signal)

        created.extend(
            self._generate_position_exit_signals(
                db,
                provider_type=provider_type,
                config=config,
                profile=profile,
                strategies=strategies,
                recent_news=recent_news,
                force_refresh=force_refresh,
            )
        )

        if not created and provider_errors:
            if len(provider_errors) == 1:
                raise ValueError(provider_errors[0])
            raise ValueError(f"{provider_errors[0]} (+{len(provider_errors) - 1} more provider errors)")

        return created

    def _generate_position_exit_signals(
        self,
        db: Session,
        *,
        provider_type: str,
        config,
        profile,
        strategies: dict[str, Strategy],
        recent_news: list[NewsArticle],
        force_refresh: bool = False,
    ) -> list[Signal]:
        created: list[Signal] = []
        positions = list(
            db.scalars(
                select(Position)
                .where(
                    *self._provider_position_filters(
                        provider_type,
                        self._simulation_account_for_provider(db, provider_type),
                    ),
                    Position.quantity > 0,
                )
                .order_by(desc(Position.updated_at))
                .limit(12)
            )
        )
        if not positions:
            return created

        strategy = strategies.get("blended")
        for position in positions:
            asset = db.get(Asset, position.asset_id)
            if asset is None:
                continue

            if not force_refresh and self._recent_close_signal_exists(db, asset.id, provider_type):
                continue

            history = market_data_service.get_history(db, asset.id, limit=90)
            if len(history) < 30 or not self._history_is_real(history):
                continue

            closes = [item.close_price for item in history]
            volumes = [item.volume for item in history]
            latest_news = self._latest_news_for_symbol(recent_news, asset.symbol)
            latest_event = self._latest_event_for_symbol(db, asset.symbol)
            indicator_payload = self._build_indicator_payload(closes, volumes)
            decisions = self._build_strategy_decisions(indicator_payload, latest_news, latest_event)
            exit_decision = self._position_exit_decision(position, asset.symbol, indicator_payload, decisions)
            if exit_decision is None:
                continue

            signal = Signal(
                asset_id=asset.id,
                strategy_id=strategy.id if strategy else None,
                action="close_long",
                confidence=exit_decision["confidence"],
                status="candidate",
                occurred_at=utcnow(),
                indicators_json={
                    **indicator_payload,
                    "strategy_votes": {
                        slug: {
                            "action": decision.action,
                            "confidence": decision.confidence,
                            "rationale": decision.rationale,
                        }
                        for slug, decision in decisions.items()
                    },
                    "position_context": {
                        "position_id": position.id,
                        "quantity": position.quantity,
                        "avg_entry_price": position.avg_entry_price,
                        "current_price": position.current_price,
                        "unrealized_pnl": position.unrealized_pnl,
                        "stop_loss": position.stop_loss,
                        "take_profit": position.take_profit,
                        "trailing_stop": position.trailing_stop,
                    },
                },
                related_news_ids=[latest_news.id] if latest_news else [],
                related_event_ids=[latest_event.id] if latest_event else [],
                ai_rationale=exit_decision["rationale"],
                suggested_entry=round(float(position.current_price or indicator_payload["close"]), 2),
                suggested_stop_loss=None,
                suggested_take_profit=None,
                estimated_risk_reward=None,
                suggested_position_size_type="percentage",
                suggested_position_size_value=100.0,
                fallback_quantity=position.quantity,
                provider_type=provider_type,
                model_name=f"{config.default_model or profile.default_model}+exit-rules",
                mode="both",
                source_kind="agent",
                metadata_json={
                    "symbol": asset.symbol,
                    "provider_vendor": profile.vendor_key,
                    "preferred_strategy": "blended",
                    "generation_profile_mode": profile.trading_mode,
                    "generation_stage": "position_exit_scan",
                    "trade_intent": "close_long",
                    "is_held_asset": True,
                    "position_id": position.id,
                    "exit_trigger": exit_decision["trigger"],
                    "news_title": latest_news.title if latest_news else None,
                    "event_type": latest_event.event_type if latest_event else None,
                    "mcp_context_used": False,
                },
            )
            db.add(signal)
            db.flush()
            created.append(signal)
            if len(created) >= 3:
                break

        return created

    def _simulation_account_for_provider(self, db: Session, provider_type: str) -> SimulationAccount | None:
        return db.scalar(select(SimulationAccount).where(SimulationAccount.provider_type == provider_type).limit(1))

    def _provider_position_filters(
        self,
        provider_type: str,
        simulation_account: SimulationAccount | None,
    ) -> list[Any]:
        filters: list[Any] = [Position.status == "open", Position.mode == "simulation"]
        if simulation_account is not None:
            filters.append(Position.simulation_account_id == simulation_account.id)
        else:
            filters.append(Position.provider_type == provider_type)
        return filters

    def _normalize_action_for_position_state(
        self,
        action: str,
        *,
        is_held: bool,
        simulation_account: SimulationAccount | None,
    ) -> str:
        normalized = str(action).lower()
        if is_held:
            return normalized
        if normalized in {"sell", "close_long", "reduce_long"} and simulation_account and simulation_account.short_enabled:
            return "short"
        if normalized in {"close_long", "reduce_long", "cover_short"}:
            return "hold"
        return normalized

    def _recent_close_signal_exists(self, db: Session, asset_id: str, provider_type: str) -> bool:
        recent_signals = list(
            db.scalars(
                select(Signal)
                .where(
                    Signal.asset_id == asset_id,
                    Signal.provider_type == provider_type,
                    Signal.source_kind == "agent",
                    Signal.action.in_(["sell", "close_long", "reduce_long"]),
                )
                .order_by(desc(Signal.occurred_at))
                .limit(5)
            )
        )
        for signal in recent_signals:
            if signal.metadata_json.get("trade_intent") != "close_long":
                continue
            if (utcnow() - signal.occurred_at).total_seconds() < 900:
                return True
        return False

    def _position_exit_decision(
        self,
        position: Position,
        symbol: str,
        indicators: dict[str, float],
        decisions: dict[str, StrategyDecision],
    ) -> dict[str, Any] | None:
        current = float(position.current_price or indicators["close"])
        avg_entry = float(position.avg_entry_price or current)

        if position.stop_loss and current <= float(position.stop_loss):
            return {
                "confidence": 0.95,
                "trigger": "stop_loss_breached",
                "rationale": (
                    f"Close signal: {symbol} is at {current:.2f}, below the configured stop loss "
                    f"of {float(position.stop_loss):.2f}. Exit review is required before the loss expands."
                ),
            }
        if position.take_profit and current >= float(position.take_profit):
            return {
                "confidence": 0.9,
                "trigger": "take_profit_reached",
                "rationale": (
                    f"Close signal: {symbol} reached the configured take-profit level. "
                    "The position should be reviewed for a full or partial exit."
                ),
            }

        sell_votes = [decision for decision in decisions.values() if decision.action == "sell"]
        buy_votes = [decision for decision in decisions.values() if decision.action == "buy"]
        strongest_sell = max((decision.confidence for decision in sell_votes), default=0.0)
        strongest_buy = max((decision.confidence for decision in buy_votes), default=0.0)
        momentum_negative = (indicators.get("momentum_10") or 0) < 0
        macd_negative = (indicators.get("macd_histogram") or 0) < 0
        below_trend = current < float(indicators.get("sma_30") or current)

        if strongest_sell >= 0.62 and strongest_sell >= strongest_buy:
            return {
                "confidence": round(min(0.86, strongest_sell + 0.08), 2),
                "trigger": "bearish_strategy_vote",
                "rationale": (
                    f"Close signal: strategy votes have turned bearish for the open {symbol} position. "
                    "A sell candidate was generated so the position can be reviewed or reduced."
                ),
            }
        if current < avg_entry and momentum_negative and (macd_negative or below_trend) and strongest_buy < 0.62:
            return {
                "confidence": 0.61,
                "trigger": "capital_protection",
                "rationale": (
                    f"Close signal: {symbol} is below entry while momentum is negative and the strategy stack "
                    "does not show a strong buy thesis. This is a capital-protection exit candidate."
                ),
            }
        if strongest_sell >= 0.60 and current < avg_entry and (momentum_negative or macd_negative or below_trend):
            return {
                "confidence": round(max(0.52, min(0.57, strongest_sell - 0.05)), 2),
                "trigger": "mixed_exit_watch",
                "rationale": (
                    f"Close watch: {symbol} has a credible bearish strategy vote while the position is below entry, "
                    "but the broader thesis is mixed. This sell signal is intentionally below the default automation "
                    "threshold so it shows up for review without auto-closing the position."
                ),
            }
        return None

    def _eligible_assets(self, db: Session) -> list[Asset]:
        return list(db.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.symbol).limit(16)))

    def _history_is_real(self, history: list[Any]) -> bool:
        return any(str(item.source).startswith("stooq") or str(item.source).startswith("yahoo") for item in history)

    def _recent_real_news(self, db: Session) -> list[NewsArticle]:
        return list(
            db.scalars(
                select(NewsArticle)
                .where(NewsArticle.provider_type != "system", ~NewsArticle.url.like("https://local.demo/%"))
                .order_by(desc(NewsArticle.published_at))
                .limit(150)
            )
        )

    def _latest_event_for_symbol(self, db: Session, symbol: str) -> ExtractedEvent | None:
        events = list(
            db.scalars(
                select(ExtractedEvent)
                .where(ExtractedEvent.symbol == symbol)
                .order_by(desc(ExtractedEvent.created_at))
                .limit(8)
            )
        )
        for event in events:
            if not event.news_article_id:
                return event
            article = db.get(NewsArticle, event.news_article_id)
            if article and article.provider_type != "system" and not article.url.startswith("https://local.demo/"):
                return event
        return None

    def _build_strategy_decisions(
        self,
        indicators: dict[str, float],
        latest_news: NewsArticle | None,
        latest_event: ExtractedEvent | None,
    ) -> dict[str, StrategyDecision]:
        decisions = {
            "trend-following": trend_following(indicators),
            "mean-reversion": mean_reversion(indicators),
            "breakout": breakout(indicators),
            "news-momentum": news_momentum(
                indicators,
                latest_news.sentiment if latest_news else None,
                latest_news.impact_score if latest_news else None,
            ),
            "event-driven": event_driven(
                latest_event.event_type if latest_event else None,
                latest_event.impact_score if latest_event else None,
            ),
        }
        decisions["blended"] = blended(list(decisions.values()))
        return decisions

    def _select_preferred_decision(self, decisions: dict[str, StrategyDecision]) -> tuple[str, StrategyDecision]:
        blended_decision = decisions["blended"]
        if blended_decision.action != "hold" and blended_decision.confidence >= 0.52:
            return "blended", blended_decision

        directional = [(slug, decision) for slug, decision in decisions.items() if decision.action != "hold"]
        if directional:
            directional.sort(key=lambda item: item[1].confidence, reverse=True)
            return directional[0]

        return "blended", blended_decision

    def _build_indicator_payload(self, closes: list[float], volumes: list[float]) -> dict[str, float]:
        macd_payload = macd(closes)
        bands = bollinger(closes)
        sr = support_resistance(closes)
        return {
            "close": closes[-1],
            "sma_10": sma(closes, 10),
            "sma_30": sma(closes, 30),
            "rsi_14": rsi(closes, 14),
            "macd": macd_payload["macd"],
            "macd_signal": macd_payload["signal"],
            "macd_histogram": macd_payload["histogram"],
            "bollinger_middle": bands["middle"],
            "bollinger_upper": bands["upper"],
            "bollinger_lower": bands["lower"],
            "momentum_10": momentum(closes, 10),
            "volatility_20": volatility(closes, 20),
            "support": sr["support"],
            "resistance": sr["resistance"],
            "volume_ratio": volume_ratio(volumes, 20),
        }

    def _signal_view(self, db: Session, signal: Signal) -> dict:
        asset = db.get(Asset, signal.asset_id)
        strategy = db.get(Strategy, signal.strategy_id) if signal.strategy_id else None
        return {
            **to_plain_dict(signal),
            "symbol": asset.symbol if asset else signal.asset_id,
            "asset_name": asset.name if asset else signal.asset_id,
            "strategy_slug": strategy.slug if strategy else None,
            "strategy_name": strategy.name if strategy else None,
            "signal_flavor": self._signal_flavor(signal, strategy.slug if strategy else None),
            "fresh_news_used": bool(signal.related_news_ids or signal.related_event_ids),
            "lane_statuses": self._lane_statuses(db, signal.id),
        }

    def _signal_detail_view(self, db: Session, signal: Signal) -> dict:
        base = self._signal_view(db, signal)
        related_news = [db.get(NewsArticle, item_id) for item_id in signal.related_news_ids]
        related_events = [db.get(ExtractedEvent, item_id) for item_id in signal.related_event_ids]
        return {
            **base,
            "related_news": [to_plain_dict(item) for item in related_news if item is not None],
            "related_events": [to_plain_dict(item) for item in related_events if item is not None],
        }

    def _build_trace(
        self,
        db: Session,
        *,
        signal: Signal | None,
        entrypoint_type: str,
        entrypoint_id: str,
        seed_orders: list[Order] | None = None,
        seed_positions: list[Position] | None = None,
        seed_trades: list[Trade] | None = None,
    ) -> dict:
        orders = self._merge_by_id(seed_orders or [])
        positions = self._merge_by_id(seed_positions or [])
        trades = self._merge_by_id(seed_trades or [])

        if signal is not None:
            signal_orders = list(db.scalars(select(Order).where(Order.signal_id == signal.id).order_by(desc(Order.created_at)).limit(50)))
            orders = self._merge_by_id([*orders, *signal_orders])

        if orders:
            order_position_ids = [order.position_id for order in orders if order.position_id]
            if order_position_ids:
                positions = self._merge_by_id([*positions, *[item for item in (db.get(Position, item_id) for item_id in order_position_ids) if item is not None]])
            order_ids = [order.id for order in orders]
            trades = self._merge_by_id(
                [
                    *trades,
                    *list(db.scalars(select(Trade).where(Trade.order_id.in_(order_ids)).order_by(desc(Trade.executed_at)).limit(100))),
                ]
            )

        if positions:
            position_ids = [position.id for position in positions]
            orders = self._merge_by_id(
                [
                    *orders,
                    *list(db.scalars(select(Order).where(Order.position_id.in_(position_ids)).order_by(desc(Order.created_at)).limit(100))),
                ]
            )
            trades = self._merge_by_id(
                [
                    *trades,
                    *list(db.scalars(select(Trade).where(Trade.position_id.in_(position_ids)).order_by(desc(Trade.executed_at)).limit(100))),
                ]
            )

        if signal is None:
            signal = self._root_signal_from_components(db, orders=orders, positions=positions, trades=trades)
            if signal is not None:
                signal_orders = list(db.scalars(select(Order).where(Order.signal_id == signal.id).order_by(desc(Order.created_at)).limit(50)))
                orders = self._merge_by_id([*orders, *signal_orders])

        evaluations = []
        if signal is not None:
            evaluations = list(
                db.scalars(
                    select(SignalEvaluation)
                    .where(SignalEvaluation.signal_id == signal.id)
                    .order_by(desc(SignalEvaluation.created_at))
                    .limit(50)
                )
            )

        target_ids = {
            entrypoint_id,
            *(item.id for item in ([signal] if signal is not None else [])),
            *(order.id for order in orders),
            *(position.id for position in positions),
            *(trade.id for trade in trades),
        }
        audit_logs = (
            list(
                db.scalars(
                    select(AuditLog)
                    .where(AuditLog.target_id.in_(list(target_ids)))
                    .order_by(desc(AuditLog.occurred_at))
                    .limit(100)
                )
            )
            if target_ids
            else []
        )

        stop_events = self._stop_events(db, signal=signal, orders=orders, positions=positions)

        return {
            "signal": self._signal_detail_view(db, signal) if signal is not None else None,
            "entrypoint": self._entrypoint_view(db, entrypoint_type, entrypoint_id),
            "summary": self._trace_summary(signal, orders, positions, trades),
            "risk_checks": self._risk_checks_from_orders(orders),
            "stop_history": self._stop_history(signal, orders, positions, audit_logs, stop_events),
            "evaluations": [to_plain_dict(item) for item in evaluations],
            "orders": [portfolio_service._order_view(db, order) for order in orders],
            "positions": [portfolio_service._position_view(db, position) for position in positions],
            "trades": [portfolio_service._trade_view(db, trade) for trade in trades],
            "audit_logs": [to_plain_dict(item) for item in audit_logs],
        }

    def _root_signal_from_components(
        self,
        db: Session,
        *,
        orders: list[Order],
        positions: list[Position],
        trades: list[Trade],
    ) -> Signal | None:
        for order in orders:
            if order.signal_id:
                signal = db.get(Signal, order.signal_id)
                if signal is not None:
                    return signal
        order_ids = [trade.order_id for trade in trades if trade.order_id]
        if order_ids:
            order = db.scalar(select(Order).where(Order.id.in_(order_ids), Order.signal_id.is_not(None)).order_by(desc(Order.created_at)).limit(1))
            if order and order.signal_id:
                return db.get(Signal, order.signal_id)
        position_ids = [position.id for position in positions]
        if position_ids:
            order = db.scalar(select(Order).where(Order.position_id.in_(position_ids), Order.signal_id.is_not(None)).order_by(desc(Order.created_at)).limit(1))
            if order and order.signal_id:
                return db.get(Signal, order.signal_id)
        return None

    def _entrypoint_view(self, db: Session, entrypoint_type: str, entrypoint_id: str) -> dict[str, Any]:
        if entrypoint_type == "signal":
            signal = db.get(Signal, entrypoint_id)
            return {"type": "signal", "id": entrypoint_id, "label": signal.action if signal else "signal"}
        if entrypoint_type == "order":
            order = db.get(Order, entrypoint_id)
            return {"type": "order", "id": entrypoint_id, "label": f"{order.side} order" if order else "order"}
        if entrypoint_type == "trade":
            trade = db.get(Trade, entrypoint_id)
            return {"type": "trade", "id": entrypoint_id, "label": f"{trade.side} trade" if trade else "trade"}
        if entrypoint_type == "position":
            position = db.get(Position, entrypoint_id)
            return {"type": "position", "id": entrypoint_id, "label": position.status if position else "position"}
        return {"type": entrypoint_type, "id": entrypoint_id, "label": entrypoint_type}

    def _trace_summary(self, signal: Signal | None, orders: list[Order], positions: list[Position], trades: list[Trade]) -> dict[str, Any]:
        primary_order = orders[0] if orders else None
        primary_position = positions[0] if positions else None
        primary_trade = trades[0] if trades else None
        mode = (primary_order or primary_position or primary_trade).mode if (primary_order or primary_position or primary_trade) else None
        manual = primary_order.manual if primary_order is not None else primary_position.manual if primary_position is not None else None
        return {
            "mode": mode or (signal.mode if signal is not None else None),
            "execution_mode": "manual" if manual is True else "auto" if manual is False else "signal-only",
            "signal_linked": signal is not None,
            "strategy": (
                (primary_order.strategy_name if primary_order else None)
                or (primary_position.strategy_name if primary_position else None)
                or (primary_trade.strategy_name if primary_trade else None)
                or (signal.metadata_json.get("preferred_strategy") if signal else None)
            ),
            "provider_type": (
                (primary_order.provider_type if primary_order else None)
                or (primary_position.provider_type if primary_position else None)
                or (primary_trade.provider_type if primary_trade else None)
                or (signal.provider_type if signal else None)
            ),
            "model_name": (
                (primary_order.model_name if primary_order else None)
                or (primary_position.model_name if primary_position else None)
                or (primary_trade.model_name if primary_trade else None)
                or (signal.model_name if signal else None)
            ),
            "orders_count": len(orders),
            "positions_count": len(positions),
            "trades_count": len(trades),
        }

    def _risk_checks_from_orders(self, orders: list[Order]) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        for order in orders:
            for index, check in enumerate((order.audit_context or {}).get("risk_checks", [])):
                checks.append(
                    {
                        **check,
                        "order_id": order.id,
                        "order_status": order.status,
                        "order_rejection_reason": order.rejection_reason,
                        "index": index,
                    }
                )
        return checks

    def _stop_history(
        self,
        signal: Signal | None,
        orders: list[Order],
        positions: list[Position],
        audit_logs: list[AuditLog],
        stop_events: list[PositionStopEvent] | None = None,
    ) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for event in stop_events or []:
            history.append(
                {
                    "source": event.source,
                    "label": event.event_type.replace("_", " ").title(),
                    "position_id": event.position_id,
                    "order_id": event.order_id,
                    "signal_id": event.signal_id,
                    "stop_loss": event.stop_loss,
                    "take_profit": event.take_profit,
                    "trailing_stop": event.trailing_stop,
                    "triggered_price": event.triggered_price,
                    "notes": event.notes,
                    "metadata": event.metadata_json,
                    "observed_at": event.observed_at.isoformat(),
                }
            )
        if signal is not None and any([signal.suggested_stop_loss, signal.suggested_take_profit]):
            history.append(
                {
                    "source": "signal_suggestion",
                    "label": "Initial AI/strategy suggestion",
                    "signal_id": signal.id,
                    "stop_loss": signal.suggested_stop_loss,
                    "take_profit": signal.suggested_take_profit,
                    "trailing_stop": None,
                    "observed_at": signal.occurred_at.isoformat(),
                }
            )
        for order in orders:
            protective_levels = (order.audit_context or {}).get("protective_levels", {})
            if any(protective_levels.get(key) is not None for key in ("stop_loss", "take_profit", "trailing_stop")):
                history.append(
                    {
                        "source": "order_ticket",
                        "label": "Order ticket protective levels",
                        "order_id": order.id,
                        "stop_loss": protective_levels.get("stop_loss"),
                        "take_profit": protective_levels.get("take_profit"),
                        "trailing_stop": protective_levels.get("trailing_stop"),
                        "observed_at": order.created_at.isoformat(),
                    }
                )
        for position in positions:
            if any([position.stop_loss, position.take_profit, position.trailing_stop]):
                history.append(
                    {
                        "source": "manual_override" if position.manual_override else "current_position",
                        "label": "Current position stop settings",
                        "position_id": position.id,
                        "stop_loss": position.stop_loss,
                        "take_profit": position.take_profit,
                        "trailing_stop": position.trailing_stop,
                        "observed_at": position.updated_at.isoformat(),
                    }
                )
        for audit in audit_logs:
            if audit.action != "position.update":
                continue
            details = audit.details_json or {}
            if any(key in details for key in ("stop_loss", "take_profit", "trailing_stop")):
                history.append(
                    {
                        "source": "manual_edit",
                        "label": "Manual stop edit",
                        "position_id": audit.target_id,
                        "stop_loss": details.get("stop_loss"),
                        "take_profit": details.get("take_profit"),
                        "trailing_stop": details.get("trailing_stop"),
                        "observed_at": audit.occurred_at.isoformat(),
                    }
                )
        return sorted(history, key=lambda item: str(item.get("observed_at") or ""))

    def _stop_events(
        self,
        db: Session,
        *,
        signal: Signal | None,
        orders: list[Order],
        positions: list[Position],
    ) -> list[PositionStopEvent]:
        clauses = []
        order_ids = [order.id for order in orders]
        position_ids = [position.id for position in positions]
        if signal is not None:
            clauses.append(PositionStopEvent.signal_id == signal.id)
        if order_ids:
            clauses.append(PositionStopEvent.order_id.in_(order_ids))
        if position_ids:
            clauses.append(PositionStopEvent.position_id.in_(position_ids))
        if not clauses:
            return []
        return list(
            db.scalars(
                select(PositionStopEvent)
                .where(or_(*clauses))
                .order_by(PositionStopEvent.observed_at.asc())
                .limit(100)
            )
        )

    def _merge_by_id(self, items: list[Any]) -> list[Any]:
        merged: dict[str, Any] = {}
        for item in items:
            if item is not None:
                merged[item.id] = item
        return list(merged.values())

    def _latest_news_for_symbol(self, recent_news: list[NewsArticle], symbol: str) -> NewsArticle | None:
        for article in recent_news:
            if symbol in (article.affected_symbols or []):
                return article
        return None

    def _signal_prompt(
        self,
        *,
        asset: Asset,
        indicators: dict[str, float],
        decisions: dict[str, StrategyDecision],
        preferred_slug: str,
        latest_news: NewsArticle | None,
        latest_event: ExtractedEvent | None,
        profile_title: str,
        mcp_context: dict[str, Any] | None,
    ) -> str:
        news_block = "No symbol-specific real news found in the latest RSS refresh."
        if latest_news:
            news_block = (
                f"Latest real news title: {latest_news.title}\n"
                f"Sentiment: {latest_news.sentiment or 'unknown'}\n"
                f"Impact score: {latest_news.impact_score or 0:.2f}\n"
                f"Summary: {latest_news.summary or 'No summary available.'}"
            )

        event_block = "No extracted event."
        if latest_event:
            event_block = (
                f"Event type: {latest_event.event_type}\n"
                f"Event confidence: {latest_event.confidence:.2f}\n"
                f"Impact score: {latest_event.impact_score:.2f}\n"
                f"Event summary: {latest_event.summary}"
            )

        decision_lines = "\n".join(
            f"- {slug}: action={decision.action}, confidence={decision.confidence:.2f}, rationale={decision.rationale}"
            for slug, decision in decisions.items()
        )
        mcp_block = "MCP server context unavailable for this symbol."
        if mcp_context:
            mcp_block = json.dumps(mcp_context, indent=2)

        return (
            f"You are generating a real trading signal for {asset.symbol} ({asset.name}) using the {profile_title} workspace.\n"
            "Use the technical inputs, real RSS news context, extracted event context, and MCP tool context below. "
            "Return only JSON with keys: action, confidence, strategy, rationale, suggested_entry, suggested_stop_loss, suggested_take_profit, estimated_risk_reward, suggested_position_size_type, suggested_position_size_value, fallback_quantity.\n"
            "Action must be one of BUY, SELL, HOLD, CLOSE_LONG, REDUCE_LONG, SHORT, COVER_SHORT. "
            "Use CLOSE_LONG or REDUCE_LONG for existing long holdings that should be exited or trimmed. "
            "Use SELL for bearish/exit pressure when a long exists or when shorting is not assumed. "
            "Use SHORT only for a clear bearish opportunity that should be simulated as a short; live brokers may not support it. "
            "Confidence must be between 0 and 1. Strategy must be one of: trend-following, mean-reversion, breakout, news-momentum, event-driven, blended.\n"
            "Sizing must be fractional-aware and capital-efficient: prefer suggested_position_size_type as percentage or amount, with suggested_position_size_value such as 5 for 5% of portfolio or 150 for $150 notional. "
            "Use fallback_quantity only when an exact quantity is essential, and fractional quantities such as 0.25 are allowed. "
            "Scale positions gradually; avoid all-in/all-out sizing unless the action is CLOSE_LONG or COVER_SHORT.\n"
            "Use hold if the setup is weak or conflicted.\n\n"
            f"Technical indicators:\n{json.dumps(indicators, indent=2)}\n\n"
            f"Rule-engine strategy votes:\n{decision_lines}\n"
            f"Preferred baseline strategy: {preferred_slug}\n\n"
            f"News context:\n{news_block}\n\n"
            f"Event context:\n{event_block}\n\n"
            f"MCP signal context:\n{mcp_block}\n"
        )

    def _parse_model_response(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            return {}

        try:
            payload = json.loads(cleaned)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            return {}

        try:
            payload = json.loads(cleaned[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _clamp_confidence(self, value: Any) -> float:
        try:
            parsed = float(value)
        except Exception:
            parsed = 0.5
        return round(max(0.0, min(1.0, parsed)), 2)

    def _normalize_action(self, value: Any, fallback: str) -> str:
        candidate = str(value or fallback).strip().lower().replace("-", "_").replace(" ", "_")
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
        normalized = aliases.get(candidate, candidate)
        allowed = {"buy", "sell", "hold", "close_long", "reduce_long", "short", "cover_short"}
        fallback_normalized = aliases.get(str(fallback).strip().lower().replace("-", "_").replace(" ", "_"), str(fallback).strip().lower())
        return normalized if normalized in allowed else (fallback_normalized if fallback_normalized in allowed else "hold")

    def _default_protective_levels(self, entry: float, action: str) -> tuple[float | None, float | None]:
        if action in {"short", "sell"}:
            return round(entry * 1.03, 2), round(entry * 0.94, 2)
        if action in {"buy"}:
            return round(entry * 0.97, 2), round(entry * 1.06, 2)
        return None, None

    def _trade_intent(self, action: str, is_held: bool) -> str:
        if action == "buy":
            return "open_long"
        if action == "short":
            return "open_short"
        if action == "cover_short":
            return "cover_short"
        if action in {"close_long", "reduce_long"}:
            return action
        if action == "sell" and is_held:
            return "close_long"
        if action == "sell":
            return "bearish_watch"
        return "observe"

    def _normalize_strategy(self, value: Any, fallback: str) -> str:
        candidate = str(value or fallback).strip().lower()
        allowed = {
            "trend-following",
            "mean-reversion",
            "breakout",
            "news-momentum",
            "event-driven",
            "blended",
        }
        return candidate if candidate in allowed else fallback

    def _normalize_position_size_suggestion(self, size_type: Any, size_value: Any, action: str) -> tuple[str | None, float | None]:
        normalized = str(size_type or "").strip().lower().replace("-", "_").replace("fixed_", "")
        aliases = {
            "percent": "percentage",
            "portfolio_percent": "percentage",
            "notional": "amount",
            "currency": "amount",
            "cash": "amount",
        }
        normalized = aliases.get(normalized, normalized)
        numeric = self._safe_float(size_value)
        if normalized not in {"percentage", "amount"} or numeric is None or numeric <= 0:
            if action in {"buy", "short", "reduce_long"}:
                return "percentage", 5.0
            if action in {"close_long", "cover_short"}:
                return "percentage", 100.0
            return None, None
        if normalized == "percentage":
            numeric = min(numeric, 100.0)
        return normalized, numeric

    def _safe_float(self, value: Any, *, precision: int = 2) -> float | None:
        try:
            return round(float(value), precision)
        except Exception:
            return None

    def _risk_reward(self, entry: float, stop_loss: float, take_profit: float, action: str = "buy") -> float:
        if action in {"short", "sell"}:
            risk = max(stop_loss - entry, 0.01)
            reward = max(entry - take_profit, 0.0)
            return round(reward / risk, 2)
        risk = max(entry - stop_loss, 0.01)
        reward = max(take_profit - entry, 0.0)
        return round(reward / risk, 2)

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
            evaluation = self._latest_mode_evaluation(db, signal_id, lane)
            statuses[lane] = evaluation.outcome if evaluation and evaluation.outcome else "candidate"
        return statuses

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

    def _signal_positions(self, db: Session, signal: Signal, orders: list[Order]) -> list[Position]:
        position_ids = {order.position_id for order in orders if order.position_id}
        positions = [db.get(Position, position_id) for position_id in position_ids]
        return [item for item in positions if item is not None]

    def _signal_trades(self, db: Session, orders: list[Order], positions: list[Position]) -> list[Trade]:
        order_ids = {order.id for order in orders}
        position_ids = {position.id for position in positions}
        trades = list(
            db.scalars(
                select(Trade)
                .where((Trade.order_id.in_(list(order_ids)) if order_ids else False) | (Trade.position_id.in_(list(position_ids)) if position_ids else False))
                .order_by(desc(Trade.executed_at))
                .limit(100)
            )
        ) if order_ids or position_ids else []
        return trades


signal_service = SignalService()
