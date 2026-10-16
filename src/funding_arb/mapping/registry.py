"""Version-controlled resolution of venue instruments to canonical assets."""

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Self, cast

from funding_arb.domain.enums import InstrumentType, MappingStatus, Venue
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.instruments import Instrument
from funding_arb.domain.spot_instruments import SpotInstrument
from funding_arb.domain.time import require_utc
from funding_arb.errors import MappingError


class MappingMethod(StrEnum):
    EXCHANGE_METADATA = "exchange_metadata"
    MANUAL_OVERRIDE = "manual_override"


@dataclass(frozen=True)
class InstrumentMapping:
    instrument_id: InstrumentId
    venue_base_asset: AssetId
    asset_id: AssetId | None
    canonical_units_per_base_unit: Decimal | None
    status: MappingStatus
    method: MappingMethod
    reason: str
    reviewed_at: datetime | None

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("mapping reason cannot be blank")
        if not isinstance(self.venue_base_asset, AssetId):
            raise TypeError("venue_base_asset must be an AssetId")
        if self.status is MappingStatus.VERIFIED and self.asset_id is None:
            raise ValueError("verified mapping requires an asset_id")
        conversion = self.canonical_units_per_base_unit
        if conversion is not None and not isinstance(conversion, Decimal):
            raise TypeError("canonical_units_per_base_unit must be a Decimal")
        if self.status is MappingStatus.VERIFIED:
            if conversion is None or not conversion.is_finite() or conversion <= Decimal("0"):
                raise ValueError(
                    "VERIFIED mappings require a positive finite "
                    "canonical_units_per_base_unit"
                )
        elif conversion is not None:
            raise ValueError("canonical_units_per_base_unit is allowed only for VERIFIED mappings")
        if self.reviewed_at is not None:
            require_utc(self.reviewed_at)

    def canonical_exposure(self, instrument: Instrument, order_quantity: Decimal) -> Decimal:
        self._require_instrument_binding(instrument)
        conversion = self.canonical_units_per_base_unit
        if (
            self.status is not MappingStatus.VERIFIED
            or self.asset_id is None
            or conversion is None
            or not conversion.is_finite()
            or conversion <= Decimal("0")
        ):
            raise MappingError("mapping does not have valid VERIFIED conversion semantics")
        return instrument.underlying_units(order_quantity) * conversion

    def _require_instrument_binding(self, instrument: Instrument | SpotInstrument) -> None:
        if instrument.id != self.instrument_id:
            raise MappingError(
                f"instrument identity mismatch: expected {self.instrument_id.key}, "
                f"observed {instrument.id.key}"
            )
        if instrument.base_asset != self.venue_base_asset:
            raise MappingError(
                f"reviewed venue base asset conflict for {self.instrument_id.key}: "
                f"expected {self.venue_base_asset.value}, "
                f"observed {instrument.base_asset.value}"
            )


class AssetMappingRegistry:
    def __init__(
        self,
        manual_mappings: Iterable[InstrumentMapping] = (),
        automatic_asset_ids: Iterable[AssetId] = (),
    ) -> None:
        by_instrument: dict[InstrumentId, InstrumentMapping] = {}
        for mapping in manual_mappings:
            if mapping.method is not MappingMethod.MANUAL_OVERRIDE:
                raise ValueError("version-controlled mappings must use manual_override")
            if mapping.reviewed_at is None:
                raise ValueError("manual mapping requires reviewed_at")
            if mapping.instrument_id in by_instrument:
                raise ValueError(f"duplicate manual mapping: {mapping.instrument_id.key}")
            by_instrument[mapping.instrument_id] = mapping
        self._manual_mappings = MappingProxyType(by_instrument)
        self._automatic_asset_ids = frozenset(automatic_asset_ids)

    @classmethod
    def from_toml(cls, path: Path) -> Self:
        return cls.from_toml_bytes(path.read_bytes())

    @classmethod
    def from_toml_bytes(cls, data: bytes) -> Self:
        document = tomllib.loads(data.decode("utf-8"))
        raw_mappings = document.get("mapping", [])
        if not isinstance(raw_mappings, list):
            raise ValueError("mapping must be an array of tables")
        automatic_asset_ids = _parse_asset_id_list(
            document,
            "automatic_asset_ids",
        )
        mappings: list[InstrumentMapping] = []
        for raw_mapping in raw_mappings:
            if not isinstance(raw_mapping, dict):
                raise ValueError("each mapping must be a table")
            mappings.append(_parse_manual_mapping(cast("Mapping[str, object]", raw_mapping)))
        return cls(mappings, automatic_asset_ids)

    def resolve(self, instrument: Instrument | SpotInstrument) -> InstrumentMapping:
        manual = self._manual_mappings.get(instrument.id)
        if manual is not None:
            manual._require_instrument_binding(instrument)
            return manual

        simple_units = isinstance(instrument, SpotInstrument) or (
            instrument.underlying_units_per_contract == Decimal("1")
        )
        if simple_units and instrument.base_asset in self._automatic_asset_ids:
            return InstrumentMapping(
                instrument_id=instrument.id,
                venue_base_asset=instrument.base_asset,
                asset_id=instrument.base_asset,
                canonical_units_per_base_unit=Decimal("1"),
                status=MappingStatus.VERIFIED,
                method=MappingMethod.EXCHANGE_METADATA,
                reason="Normalized metadata identifies an unambiguous unit-multiplier base asset.",
                reviewed_at=None,
            )

        if isinstance(instrument, Instrument) and (
            instrument.underlying_units_per_contract != Decimal("1")
        ):
            reason = "Non-unit multiplier requires an explicit asset mapping."
        else:
            reason = "Base asset is not approved for automatic mapping."

        return InstrumentMapping(
            instrument_id=instrument.id,
            venue_base_asset=instrument.base_asset,
            asset_id=None,
            canonical_units_per_base_unit=None,
            status=MappingStatus.PENDING,
            method=MappingMethod.EXCHANGE_METADATA,
            reason=reason,
            reviewed_at=None,
        )

    def exact_manual_mapping(self, instrument_id: InstrumentId) -> InstrumentMapping | None:
        """Return only a reviewed mapping bound to this exact venue instrument."""
        return self._manual_mappings.get(instrument_id)


def _parse_manual_mapping(entry: Mapping[str, object]) -> InstrumentMapping:
    method = MappingMethod(_required_str(entry, "method"))
    if method is not MappingMethod.MANUAL_OVERRIDE:
        raise ValueError("version-controlled mappings must use manual_override")

    reviewed_at = entry.get("reviewed_at")
    if not isinstance(reviewed_at, datetime):
        raise ValueError("manual mapping reviewed_at must be a TOML datetime")

    raw_asset_id = entry.get("asset_id")
    if raw_asset_id is not None and not isinstance(raw_asset_id, str):
        raise ValueError("asset_id must be a string when provided")

    conversion = _optional_decimal_string(entry, "canonical_units_per_base_unit")

    return InstrumentMapping(
        instrument_id=InstrumentId(
            venue=Venue(_required_str(entry, "venue")),
            symbol=_required_str(entry, "venue_symbol"),
            instrument_type=InstrumentType(
                _optional_str(entry, "instrument_type")
                or InstrumentType.LINEAR_PERPETUAL.value
            ),
        ),
        venue_base_asset=AssetId(_required_str(entry, "venue_base_asset")),
        asset_id=AssetId(raw_asset_id) if raw_asset_id is not None else None,
        canonical_units_per_base_unit=conversion,
        status=MappingStatus(_required_str(entry, "status")),
        method=method,
        reason=_required_str(entry, "reason"),
        reviewed_at=require_utc(reviewed_at),
    )


def _parse_asset_id_list(document: Mapping[str, object], key: str) -> list[AssetId]:
    raw_asset_ids = document.get(key, [])
    if not isinstance(raw_asset_ids, list):
        raise ValueError(f"{key} must be an array")
    asset_ids: list[AssetId] = []
    for raw_asset_id in raw_asset_ids:
        if not isinstance(raw_asset_id, str):
            raise ValueError(f"{key} entries must be strings")
        asset_ids.append(AssetId(raw_asset_id))
    return asset_ids


def _required_str(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-blank string")
    return value


def _optional_str(entry: Mapping[str, object], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-blank string when provided")
    return value


def _optional_decimal_string(entry: Mapping[str, object], key: str) -> Decimal | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a decimal string when provided")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{key} must be a valid decimal string") from error
