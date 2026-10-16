"""Source-native stream envelopes and explicit connection-quality events."""

from dataclasses import dataclass
from datetime import datetime

from funding_arb.domain.enums import StreamEventKind, Venue
from funding_arb.domain.time import require_utc


@dataclass(frozen=True)
class RawStreamMessage:
    venue: Venue
    channel: str
    payload_text: str
    received_at: datetime
    session_id: str
    source_event_at: datetime | None = None
    sequence: int | None = None
    previous_sequence: int | None = None

    def __post_init__(self) -> None:
        _non_blank("channel", self.channel)
        _non_blank("payload_text", self.payload_text)
        _non_blank("session_id", self.session_id)
        require_utc(self.received_at)
        if self.source_event_at is not None:
            require_utc(self.source_event_at)
        _sequence_pair(self.sequence, self.previous_sequence)


@dataclass(frozen=True)
class StreamEvent:
    venue: Venue
    channel: str
    session_id: str
    kind: StreamEventKind
    occurred_at: datetime
    sequence: int | None = None
    previous_sequence: int | None = None
    downtime_seconds: float | None = None

    def __post_init__(self) -> None:
        _non_blank("channel", self.channel)
        _non_blank("session_id", self.session_id)
        require_utc(self.occurred_at)
        _sequence_pair(self.sequence, self.previous_sequence)
        if self.downtime_seconds is not None and self.downtime_seconds < 0:
            raise ValueError("downtime_seconds must be non-negative")


def _sequence_pair(sequence: int | None, previous: int | None) -> None:
    if sequence is not None and sequence < 0:
        raise ValueError("sequence must be non-negative")
    if previous is not None and previous < 0:
        raise ValueError("previous_sequence must be non-negative")
    if previous is not None and sequence is None:
        raise ValueError("previous_sequence requires sequence")


def _non_blank(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} cannot be blank")
