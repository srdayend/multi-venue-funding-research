from dataclasses import dataclass

from funding_arb.domain.enums import InstrumentType, Venue


@dataclass(frozen=True)
class AssetId:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not normalized:
            raise ValueError("AssetId cannot be blank")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class InstrumentId:
    venue: Venue
    symbol: str
    instrument_type: InstrumentType

    @property
    def key(self) -> str:
        return f"{self.venue.value}:{self.symbol}:{self.instrument_type.value}"
