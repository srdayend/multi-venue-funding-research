"""Canonical contracts for cheap, source-truthful perpetual universe scans."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from funding_arb.domain.enums import Venue
from funding_arb.domain.identifiers import InstrumentId
from funding_arb.domain.observations import FundingStateObservation
from funding_arb.domain.provenance import RawRecordRef
from funding_arb.domain.time import require_utc


@dataclass(frozen=True)
class ScanInstrumentState:
    instrument_id: InstrumentId
    observed_at: datetime
    funding: FundingStateObservation
    trading_active: bool
    funding_interval_minutes: int | None = None
    funding_cap: Decimal | None = None
    funding_floor: Decimal | None = None
    mark_price: Decimal | None = None
    index_price: Decimal | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    open_interest: Decimal | None = None
    open_interest_semantics: str | None = None
    turnover_24h: Decimal | None = None
    turnover_semantics: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.observed_at)
        if self.funding.instrument_id != self.instrument_id:
            raise ValueError("funding instrument_id must match scan instrument_id")
        if self.funding.venue is not self.instrument_id.venue:
            raise ValueError("funding venue must match scan instrument venue")
        if self.funding_interval_minutes is not None and self.funding_interval_minutes <= 0:
            raise ValueError("funding_interval_minutes must be positive")
        for name in (
            "funding_cap",
            "funding_floor",
            "mark_price",
            "index_price",
            "best_bid",
            "best_ask",
            "open_interest",
            "turnover_24h",
        ):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
                raise ValueError(f"{name} must be a finite Decimal")
        if self.open_interest is not None and not self.open_interest_semantics:
            raise ValueError("open_interest requires explicit semantics")
        if self.turnover_24h is not None and not self.turnover_semantics:
            raise ValueError("turnover_24h requires explicit semantics")


@dataclass(frozen=True)
class UniverseScanSnapshot:
    venue: Venue
    observed_at: datetime
    states: tuple[ScanInstrumentState, ...]
    raw_ref: RawRecordRef
    request_weight: int
    attempts: int
    payload_bytes: int

    def __post_init__(self) -> None:
        require_utc(self.observed_at)
        if any(state.instrument_id.venue is not self.venue for state in self.states):
            raise ValueError("all scan states must match snapshot venue")
        _non_negative_int("request_weight", self.request_weight)
        _positive_int("attempts", self.attempts)
        _non_negative_int("payload_bytes", self.payload_bytes)


@dataclass(frozen=True)
class AdmissionDecision:
    instrument_id: InstrumentId
    target_funding_time: datetime
    rate: Decimal
    admitted: bool
    reason: str

    def __post_init__(self) -> None:
        require_utc(self.target_funding_time)
        if not isinstance(self.rate, Decimal) or not self.rate.is_finite():
            raise ValueError("rate must be a finite Decimal")
        if not self.reason.strip():
            raise ValueError("reason cannot be blank")


def _non_negative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _positive_int(name: str, value: int) -> None:
    _non_negative_int(name, value)
    if value == 0:
        raise ValueError(f"{name} must be positive")
