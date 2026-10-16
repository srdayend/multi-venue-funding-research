"""Canonical decision-time observations kept separate from settled funding."""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from funding_arb.domain.enums import FundingStateKind, ReferencePriceKind, TradeSide, Venue
from funding_arb.domain.identifiers import InstrumentId
from funding_arb.domain.time import require_utc

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ObservationTransport(StrEnum):
    REST = "rest"
    WEBSOCKET = "websocket"


@dataclass(frozen=True)
class ObservationRawRef:
    record_id: str
    path: str
    item_index: int | None
    sha256: str

    def __post_init__(self) -> None:
        _non_blank("record_id", self.record_id)
        _non_blank("path", self.path)
        if self.item_index is not None and self.item_index < 0:
            raise ValueError("item_index must be non-negative")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class ObservationProvenance:
    transport: ObservationTransport
    source_event_at: datetime | None
    received_at: datetime
    raw_ref: ObservationRawRef
    session_id: str | None = None
    sequence: int | None = None
    previous_sequence: int | None = None
    gap_before: bool = False

    def __post_init__(self) -> None:
        if self.source_event_at is not None:
            require_utc(self.source_event_at)
        require_utc(self.received_at)
        if self.transport is ObservationTransport.WEBSOCKET:
            if self.session_id is None:
                raise ValueError("session_id is required for WebSocket provenance")
            _non_blank("session_id", self.session_id)
        elif self.transport is ObservationTransport.REST:
            if any(
                value is not None
                for value in (self.session_id, self.sequence, self.previous_sequence)
            ):
                raise ValueError("REST provenance cannot contain stream session or sequence fields")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if self.previous_sequence is not None and self.previous_sequence < 0:
            raise ValueError("previous_sequence must be non-negative")
        if self.previous_sequence is not None and self.sequence is None:
            raise ValueError("previous_sequence requires sequence")


@dataclass(frozen=True)
class FundingStateObservation:
    venue: Venue
    instrument_id: InstrumentId
    target_funding_time: datetime
    rate: Decimal | None
    state_kind: FundingStateKind
    provenance: ObservationProvenance
    target_time_source: str

    def __post_init__(self) -> None:
        _venue(self.venue, self.instrument_id)
        require_utc(self.target_funding_time)
        _non_blank("target_time_source", self.target_time_source)
        if self.rate is not None:
            _decimal("rate", self.rate)


@dataclass(frozen=True)
class BestQuoteObservation:
    venue: Venue
    instrument_id: InstrumentId
    bid_price: Decimal
    bid_quantity: Decimal
    ask_price: Decimal
    ask_quantity: Decimal
    quantity_semantics: str
    provenance: ObservationProvenance

    def __post_init__(self) -> None:
        _venue(self.venue, self.instrument_id)
        _non_blank("quantity_semantics", self.quantity_semantics)
        for name in ("bid_price", "bid_quantity", "ask_price", "ask_quantity"):
            _positive_decimal(name, getattr(self, name))
        if self.bid_price > self.ask_price:
            raise ValueError("bid_price cannot exceed ask_price")


@dataclass(frozen=True)
class PublicTradeObservation:
    venue: Venue
    instrument_id: InstrumentId
    trade_id: str
    price: Decimal
    quantity: Decimal
    maker_side: TradeSide | None
    aggressor_side: TradeSide | None
    quantity_semantics: str
    provenance: ObservationProvenance

    def __post_init__(self) -> None:
        _venue(self.venue, self.instrument_id)
        _non_blank("trade_id", self.trade_id)
        _non_blank("quantity_semantics", self.quantity_semantics)
        _positive_decimal("price", self.price)
        _positive_decimal("quantity", self.quantity)


@dataclass(frozen=True)
class ReferencePriceObservation:
    venue: Venue
    instrument_id: InstrumentId
    kind: ReferencePriceKind
    price: Decimal
    provenance: ObservationProvenance

    def __post_init__(self) -> None:
        _venue(self.venue, self.instrument_id)
        _positive_decimal("price", self.price)


CanonicalObservation = (
    FundingStateObservation
    | BestQuoteObservation
    | PublicTradeObservation
    | ReferencePriceObservation
)


def _venue(venue: Venue, instrument_id: InstrumentId) -> None:
    if venue is not instrument_id.venue:
        raise ValueError("venue must match instrument_id.venue")


def _decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")


def _positive_decimal(name: str, value: Decimal) -> None:
    _decimal(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _non_blank(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} cannot be blank")
