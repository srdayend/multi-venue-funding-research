from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from funding_arb.domain.enums import FundingType, Venue
from funding_arb.domain.identifiers import InstrumentId
from funding_arb.domain.time import require_utc


@dataclass(frozen=True)
class FundingSettlement:
    venue: Venue
    instrument_id: InstrumentId
    settlement_time: datetime
    rate: Decimal
    funding_type: FundingType
    source_record_id: str
    ingested_at: datetime

    def __post_init__(self) -> None:
        _require_matching_venue(self.venue, self.instrument_id)
        _require_decimal("rate", self.rate)
        require_utc(self.settlement_time)
        require_utc(self.ingested_at)
        _require_source_record_id(self.source_record_id)


@dataclass(frozen=True)
class FundingRuleObservation:
    venue: Venue
    instrument_id: InstrumentId
    interval_seconds: int
    cap: Decimal | None
    floor: Decimal | None
    effective_at: datetime | None
    observed_at: datetime
    source_record_id: str

    def __post_init__(self) -> None:
        _require_matching_venue(self.venue, self.instrument_id)
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        _require_decimal_if_provided("cap", self.cap)
        _require_decimal_if_provided("floor", self.floor)
        if self.effective_at is not None:
            require_utc(self.effective_at)
        require_utc(self.observed_at)
        _require_source_record_id(self.source_record_id)


def _require_matching_venue(venue: Venue, instrument_id: InstrumentId) -> None:
    if venue != instrument_id.venue:
        raise ValueError("venue must match instrument_id.venue")


def _require_decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")


def _require_decimal_if_provided(name: str, value: Decimal | None) -> None:
    if value is not None:
        _require_decimal(name, value)


def _require_source_record_id(source_record_id: str) -> None:
    if not source_record_id.strip():
        raise ValueError("source_record_id cannot be blank")
