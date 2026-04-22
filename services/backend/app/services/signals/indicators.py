import math


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    window_values = values[-window:]
    return sum(window_values) / len(window_values)


def ema(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    multiplier = 2 / (window + 1)
    ema_value = sum(values[:window]) / window
    for price in values[window:]:
        ema_value = (price - ema_value) * multiplier + ema_value
    return ema_value


def rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) <= window:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[:-1], values[1:]):
        delta = current - previous
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = sum(gains[-window:]) / window
    avg_loss = sum(losses[-window:]) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values: list[float]) -> dict[str, float | None]:
    ema_fast = ema(values, 12)
    ema_slow = ema(values, 26)
    if ema_fast is None or ema_slow is None:
        return {"macd": None, "signal": None, "histogram": None}
    macd_value = ema_fast - ema_slow
    histogram = macd_value * 0.15
    signal_value = macd_value - histogram
    return {"macd": macd_value, "signal": signal_value, "histogram": histogram}


def bollinger(values: list[float], window: int = 20, std_mult: float = 2.0) -> dict[str, float | None]:
    if len(values) < window:
        return {"middle": None, "upper": None, "lower": None}
    subset = values[-window:]
    mean = sum(subset) / window
    variance = sum((v - mean) ** 2 for v in subset) / window
    stdev = math.sqrt(variance)
    return {"middle": mean, "upper": mean + std_mult * stdev, "lower": mean - std_mult * stdev}


def momentum(values: list[float], window: int = 10) -> float | None:
    if len(values) < window:
        return None
    start = values[-window]
    end = values[-1]
    if start == 0:
        return None
    return (end - start) / start


def volatility(values: list[float], window: int = 20) -> float | None:
    if len(values) < window:
        return None
    returns = []
    for previous, current in zip(values[-window:-1], values[-window + 1 :]):
        if previous == 0:
            continue
        returns.append((current - previous) / previous)
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / len(returns)
    return math.sqrt(variance)


def support_resistance(values: list[float], window: int = 20) -> dict[str, float | None]:
    if len(values) < window:
        return {"support": None, "resistance": None}
    subset = values[-window:]
    return {"support": min(subset), "resistance": max(subset)}


def volume_ratio(volumes: list[float], window: int = 20) -> float | None:
    if len(volumes) < window:
        return None
    average = sum(volumes[-window:]) / window
    if average == 0:
        return None
    return volumes[-1] / average
