"""Identity contracts for venue funding events and bounded capture sessions."""

from dataclasses import dataclass
from datetime import datetime

from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.time import require_utc


@dataclass(frozen=True)
class FundingEventKey:
    instrument_id: InstrumentId
    target_funding_time: datetime

    def __post_init__(self) -> None:
        require_utc(self.target_funding_time)


@dataclass(frozen=True)
class CaptureSessionKey:
    """Exact capture subject plus bounded event window.

    A session is either canonical-asset scoped or exact-source-instrument scoped.
    Source scope preserves evidence when canonical identity is unresolved without
    fabricating an AssetId or cross-venue relationship.
    """

    underlying_id: AssetId | None
    window_start: datetime
    window_end: datetime
    source_instrument_id: InstrumentId | None = None

    def __post_init__(self) -> None:
        if self.underlying_id is not None and not isinstance(self.underlying_id, AssetId):
            raise TypeError("underlying_id must be an AssetId when present")
        if self.source_instrument_id is not None and not isinstance(
            self.source_instrument_id, InstrumentId
        ):
            raise TypeError("source_instrument_id must be an InstrumentId when present")
        if (self.underlying_id is None) == (self.source_instrument_id is None):
            raise ValueError(
                "capture session requires exactly one canonical asset or source instrument subject"
            )
        require_utc(self.window_start)
        require_utc(self.window_end)
        if self.window_start >= self.window_end:
            raise ValueError("capture window start must precede end")

    @property
    def subject_kind(self) -> str:
        return "canonical_asset" if self.underlying_id is not None else "source_instrument"

    @property
    def subject_key(self) -> str:
        if self.underlying_id is not None:
            return f"asset:{self.underlying_id.value}"
        assert self.source_instrument_id is not None
        return f"instrument:{self.source_instrument_id.key}"
