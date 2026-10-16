from enum import StrEnum


class Venue(StrEnum):
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    HYPERLIQUID = "hyperliquid"


class InstrumentType(StrEnum):
    LINEAR_PERPETUAL = "linear_perpetual"
    SPOT = "spot"


class InstrumentStatus(StrEnum):
    TRADING = "trading"
    UNKNOWN = "unknown"


class FundingType(StrEnum):
    REGULAR = "regular"
    SPECIAL = "special"
    UNCLASSIFIED = "unclassified"
    UNKNOWN = "unknown"


class FundingStateKind(StrEnum):
    INDICATIVE = "indicative"
    CURRENT_PUBLISHED = "current_published"
    PROCESSING = "processing"


class ReferencePriceKind(StrEnum):
    MARK = "mark"
    INDEX = "index"
    ORACLE = "oracle"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class StreamEventKind(StrEnum):
    SESSION_STARTED = "session_started"
    RECONNECTED = "reconnected"
    GAP = "gap"
    RESNAPSHOT = "resnapshot"
    SESSION_ENDED = "session_ended"


class CaptureMode(StrEnum):
    BROAD = "broad"
    HIGH_RESOLUTION = "high_resolution"


class MappingStatus(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"
    REJECTED = "rejected"
