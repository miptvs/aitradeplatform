import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.news import ExtractedEvent, NewsArticle
from app.models.signal import Signal
from app.models.strategy import Strategy
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

    def generate_signals(self, db: Session, provider_type: str | None = None) -> list[Signal]:
        if provider_type:
            return self._generate_for_provider(db, provider_type)

        created: list[Signal] = []
        for config in provider_service.list_configs(db):
            profile = provider_service.get_profile(config.provider_type)
            if not config.enabled or profile.trading_mode != "simulation":
                continue
            try:
                created.extend(self._generate_for_provider(db, config.provider_type))
            except Exception:
                continue
        return created

    def _generate_for_provider(self, db: Session, provider_type: str) -> list[Signal]:
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
            if latest_existing and (utcnow() - latest_existing.occurred_at).total_seconds() < 900:
                continue

            closes = [item.close_price for item in history]
            volumes = [item.volume for item in history]
            latest_news = self._latest_news_for_symbol(recent_news, asset.symbol)
            latest_event = self._latest_event_for_symbol(db, asset.symbol)
            indicator_payload = self._build_indicator_payload(closes, volumes)
            decisions = self._build_strategy_decisions(indicator_payload, latest_news, latest_event)
            preferred_slug, preferred_decision = self._select_preferred_decision(decisions)
            score = preferred_decision.confidence
            if preferred_decision.action != "hold":
                score += 0.15
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
                    "score": score,
                }
            )

        for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True)[:candidate_limit]:
            asset = candidate["asset"]
            indicator_payload = candidate["indicator_payload"]
            decisions = candidate["decisions"]
            preferred_slug = candidate["preferred_slug"]
            preferred_decision = candidate["preferred_decision"]
            latest_news = candidate["latest_news"]
            latest_event = candidate["latest_event"]
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
            action = self._normalize_action(parsed.get("action"), preferred_decision.action)
            confidence = self._clamp_confidence(parsed.get("confidence", preferred_decision.confidence))
            strategy_slug = self._normalize_strategy(parsed.get("strategy"), preferred_slug)
            strategy = strategies.get(strategy_slug, strategy)

            suggested_entry = self._safe_float(parsed.get("suggested_entry")) or indicator_payload["close"]
            suggested_stop_loss = self._safe_float(parsed.get("suggested_stop_loss")) or round(suggested_entry * 0.97, 2)
            suggested_take_profit = self._safe_float(parsed.get("suggested_take_profit")) or round(suggested_entry * 1.06, 2)
            estimated_risk_reward = self._safe_float(parsed.get("estimated_risk_reward")) or self._risk_reward(
                suggested_entry,
                suggested_stop_loss,
                suggested_take_profit,
            )

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
                provider_type=provider_type,
                model_name=result.model_name,
                mode="both",
                source_kind="agent",
                metadata_json={
                    "symbol": asset.symbol,
                    "provider_vendor": profile.vendor_key,
                    "preferred_strategy": preferred_slug,
                    "generation_profile_mode": profile.trading_mode,
                    "news_title": latest_news.title if latest_news else None,
                    "event_type": latest_event.event_type if latest_event else None,
                    "mcp_context_used": bool(mcp_context),
                },
            )
            db.add(signal)
            db.flush()
            created.append(signal)

        if not created and provider_errors:
            if len(provider_errors) == 1:
                raise ValueError(provider_errors[0])
            raise ValueError(f"{provider_errors[0]} (+{len(provider_errors) - 1} more provider errors)")

        return created

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
        }

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
            "Return only JSON with keys: action, confidence, strategy, rationale, suggested_entry, suggested_stop_loss, suggested_take_profit, estimated_risk_reward.\n"
            "Confidence must be between 0 and 1. Strategy must be one of: trend-following, mean-reversion, breakout, news-momentum, event-driven, blended.\n"
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
        candidate = str(value or fallback).strip().lower()
        return candidate if candidate in {"buy", "sell", "hold"} else fallback

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

    def _safe_float(self, value: Any) -> float | None:
        try:
            return round(float(value), 2)
        except Exception:
            return None

    def _risk_reward(self, entry: float, stop_loss: float, take_profit: float) -> float:
        risk = max(entry - stop_loss, 0.01)
        reward = max(take_profit - entry, 0.0)
        return round(reward / risk, 2)


signal_service = SignalService()
