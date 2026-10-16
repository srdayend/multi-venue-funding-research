"""Explicit availability labels for observed and reconstructed evidence."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from funding_arb.domain.enums import Venue
from funding_arb.domain.identifiers import InstrumentId
from funding_arb.domain.provenance import RawRecordRef
from funding_arb.domain.time import require_utc


class EvidenceAvailability(StrEnum):
    OBSERVED_DECISION_TIME = "observed_decision_time"
    RECONSTRUCTED_RETROSPECTIVE = "reconstructed_retrospective"


@dataclass(frozen=True)
class BackfilledSeriesRef:
    venue: Venue
    instrument_id: InstrumentId
    kind: str
    start: datetime
    end: datetime
    availability: EvidenceAvailability
    raw_ref: RawRecordRef

    def __post_init__(self) -> None:
        if self.venue is not self.instrument_id.venue:
            raise ValueError("venue must match instrument_id.venue")
        if not self.kind.strip():
            raise ValueError("kind cannot be blank")
        require_utc(self.start)
        require_utc(self.end)
        if self.start > self.end:
            raise ValueError("backfilled series range is invalid")
        if self.availability is not EvidenceAvailability.RECONSTRUCTED_RETROSPECTIVE:
            raise ValueError("backfilled series must be reconstructed retrospective evidence")
