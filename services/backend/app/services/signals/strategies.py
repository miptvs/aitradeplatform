from dataclasses import dataclass


@dataclass
class StrategyDecision:
    action: str
    confidence: float
    rationale: str


def trend_following(indicators: dict) -> StrategyDecision:
    sma_short = indicators.get("sma_10")
    sma_long = indicators.get("sma_30")
    macd_hist = indicators.get("macd_histogram")
    if sma_short and sma_long and macd_hist is not None and sma_short > sma_long and macd_hist > 0:
        return StrategyDecision("buy", 0.73, "Trend remains constructive with the short moving average above the long trend and MACD positive.")
    if sma_short and sma_long and macd_hist is not None and sma_short < sma_long and macd_hist < 0:
        return StrategyDecision("sell", 0.7, "Trend is weakening with short momentum below the long trend and MACD negative.")
    return StrategyDecision("hold", 0.46, "Trend confirmation is mixed, so the strategy remains neutral.")


def mean_reversion(indicators: dict) -> StrategyDecision:
    rsi_value = indicators.get("rsi_14")
    close = indicators.get("close")
    lower = indicators.get("bollinger_lower")
    upper = indicators.get("bollinger_upper")
    if rsi_value is not None and lower is not None and close <= lower and rsi_value < 35:
        return StrategyDecision("buy", 0.68, "Price is stretched below the lower Bollinger band with oversold RSI.")
    if rsi_value is not None and upper is not None and close >= upper and rsi_value > 65:
        return StrategyDecision("sell", 0.66, "Price is extended near the upper Bollinger band with RSI elevated.")
    return StrategyDecision("hold", 0.42, "Mean reversion thresholds are not strongly triggered.")


def breakout(indicators: dict) -> StrategyDecision:
    close = indicators.get("close")
    resistance = indicators.get("resistance")
    support = indicators.get("support")
    volume_ratio = indicators.get("volume_ratio")
    if close and resistance and volume_ratio and close >= resistance * 0.995 and volume_ratio > 1.1:
        return StrategyDecision("buy", 0.71, "Price is pressing resistance on stronger-than-average volume.")
    if close and support and volume_ratio and close <= support * 1.005 and volume_ratio > 1.1:
        return StrategyDecision("sell", 0.63, "Price is testing support with elevated volume and downside pressure.")
    return StrategyDecision("hold", 0.41, "Breakout conditions are not confirmed by volume and range expansion.")


def news_momentum(indicators: dict, sentiment: str | None, impact_score: float | None) -> StrategyDecision:
    if sentiment == "positive" and (impact_score or 0) >= 0.6:
        return StrategyDecision("buy", min(0.8, 0.55 + (impact_score or 0) * 0.3), "Recent news flow is positive and materially relevant for momentum continuation.")
    if sentiment == "negative" and (impact_score or 0) >= 0.6:
        return StrategyDecision("sell", min(0.8, 0.55 + (impact_score or 0) * 0.3), "Negative news flow increases downside momentum risk.")
    return StrategyDecision("hold", 0.4, "News momentum signal is neutral or low-impact.")


def event_driven(event_type: str | None, impact_score: float | None) -> StrategyDecision:
    if event_type in {"earnings", "guidance", "analyst"} and (impact_score or 0) > 0.65:
        return StrategyDecision("buy", 0.67, "Catalyst-driven setup detected from a company-specific event.")
    if event_type in {"regulation", "macro"} and (impact_score or 0) > 0.65:
        return StrategyDecision("sell", 0.64, "Event-driven downside risk increased after a macro or regulatory catalyst.")
    return StrategyDecision("hold", 0.39, "No strong catalyst event is active.")


def blended(decisions: list[StrategyDecision]) -> StrategyDecision:
    if not decisions:
        return StrategyDecision("hold", 0.4, "No inputs available.")
    score = 0.0
    for decision in decisions:
        if decision.action == "buy":
            score += decision.confidence
        elif decision.action == "sell":
            score -= decision.confidence
    if score > 0.3:
        return StrategyDecision("buy", min(0.85, 0.5 + abs(score) / max(len(decisions), 1)), "Blended signal favors upside after combining technical and news inputs.")
    if score < -0.3:
        return StrategyDecision("sell", min(0.85, 0.5 + abs(score) / max(len(decisions), 1)), "Blended signal favors downside after combining technical and news inputs.")
    return StrategyDecision("hold", 0.48, "Blended signal is balanced and does not justify a directional move.")
