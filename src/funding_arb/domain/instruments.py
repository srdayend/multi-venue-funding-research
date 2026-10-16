from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from funding_arb.domain.enums import InstrumentStatus
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.time import require_utc


@dataclass(frozen=True)
class Instrument:
    id: InstrumentId
    base_asset: AssetId
    quote_asset: AssetId
    collateral_asset: AssetId
    underlying_units_per_contract: Decimal
    tick_size: Decimal | None
    quantity_step: Decimal
    min_quantity: Decimal | None
    min_notional: Decimal | None
    listed_at: datetime | None
    delisted_at: datetime | None
    status: InstrumentStatus
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_decimal("underlying_units_per_contract", self.underlying_units_per_contract)
        _require_decimal_if_provided("tick_size", self.tick_size)
        _require_decimal("quantity_step", self.quantity_step)
        _require_decimal_if_provided("min_quantity", self.min_quantity)
        _require_decimal_if_provided("min_notional", self.min_notional)
        _require_positive("underlying_units_per_contract", self.underlying_units_per_contract)
        _require_positive_if_provided("tick_size", self.tick_size)
        _require_positive("quantity_step", self.quantity_step)
        _require_non_negative_if_provided("min_quantity", self.min_quantity)
        _require_non_negative_if_provided("min_notional", self.min_notional)

        if self.listed_at is not None:
            require_utc(self.listed_at)
        if self.delisted_at is not None:
            require_utc(self.delisted_at)
        require_utc(self.observed_at)

    def underlying_units(self, quantity: Decimal) -> Decimal:
        _require_decimal("quantity", quantity)
        return quantity * self.underlying_units_per_contract


def _require_decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")


def _require_decimal_if_provided(name: str, value: Decimal | None) -> None:
    if value is not None:
        _require_decimal(name, value)


def _require_positive(name: str, value: Decimal) -> None:
    if value <= Decimal("0"):
        raise ValueError(f"{name} must be positive")


def _require_positive_if_provided(name: str, value: Decimal | None) -> None:
    if value is not None:
        _require_positive(name, value)


def _require_non_negative_if_provided(name: str, value: Decimal | None) -> None:
    if value is not None and value < Decimal("0"):
        raise ValueError(f"{name} must not be negative")
