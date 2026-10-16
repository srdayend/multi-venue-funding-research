"""Truthful spot-market identity and public metadata."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from funding_arb.domain.enums import InstrumentStatus, InstrumentType
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.time import require_utc


@dataclass(frozen=True)
class SpotInstrument:
    """Venue-declared spot metadata without derivative-only semantics."""

    id: InstrumentId
    base_asset: AssetId
    quote_asset: AssetId
    tick_size: Decimal | None
    quantity_step: Decimal | None
    min_quantity: Decimal | None
    min_notional: Decimal | None
    listed_at: datetime | None
    delisted_at: datetime | None
    status: InstrumentStatus
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.id.instrument_type is not InstrumentType.SPOT:
            raise ValueError("SpotInstrument requires a SPOT identity")
        for field_name in ("tick_size", "quantity_step", "min_quantity", "min_notional"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal")
            if not value.is_finite() or value <= Decimal("0"):
                raise ValueError(f"{field_name} must be positive")
        if self.listed_at is not None:
            require_utc(self.listed_at)
        if self.delisted_at is not None:
            require_utc(self.delisted_at)
        require_utc(self.observed_at)
