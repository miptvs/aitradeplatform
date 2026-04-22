from enum import StrEnum


class ProviderType(StrEnum):
    LOCAL = "local"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


class TradingMode(StrEnum):
    SIMULATION = "simulation"
    LIVE = "live"
    BOTH = "both"


class SignalAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalStatus(StrEnum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    PENDING = "pending"
    REJECTED = "rejected"
    FILLED = "filled"
    CANCELLED = "cancelled"
    ACCEPTED = "accepted"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class BrokerType(StrEnum):
    PAPER = "paper"
    TRADING212 = "trading212"


class BrokerSyncStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class HealthStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class RiskRuleScope(StrEnum):
    GLOBAL = "global"
    STRATEGY = "strategy"
    BROKER = "broker"
    SIMULATION = "simulation"


class RiskRuleType(StrEnum):
    KILL_SWITCH = "kill_switch"
    MAX_POSITION_SIZE = "max_position_size"
    MAX_CAPITAL_PER_ASSET = "max_capital_per_asset"
    MAX_OPEN_POSITIONS = "max_open_positions"
    MAX_SECTOR_EXPOSURE = "max_sector_exposure"
    DAILY_MAX_LOSS = "daily_max_loss"
    MAX_DRAWDOWN_HALT = "max_drawdown_halt"
    LOSS_STREAK_COOLDOWN = "loss_streak_cooldown"
    PER_TRADE_RISK = "per_trade_risk"
    MARKET_HOURS = "market_hours"


class NewsSentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class EventType(StrEnum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    ANALYST = "analyst"
    MACRO = "macro"
    MA = "m_and_a"
    REGULATION = "regulation"
    LEADERSHIP = "leadership"
    SECTOR = "sector"


class ModelRunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AssetType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"


class OrderSourceKind(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
