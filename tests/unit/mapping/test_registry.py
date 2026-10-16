from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from funding_arb.domain.enums import (
    InstrumentStatus,
    InstrumentType,
    MappingStatus,
    Venue,
)
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.instruments import Instrument
from funding_arb.domain.spot_instruments import SpotInstrument
from funding_arb.errors import MappingError
from funding_arb.mapping.registry import (
    AssetMappingRegistry,
    InstrumentMapping,
    MappingMethod,
)

MAPPING_CONFIG = Path("config/asset_mappings.toml")
REVIEWED_AT = datetime(2026, 9, 9, tzinfo=UTC)
REVIEWED_SIMPLE_UNIT_ASSET_IDS = (
    "ace",
    "ark",
    "astr",
    "axl",
    "bank",
    "cap",
    "cvc",
    "esports",
    "glm",
    "hemi",
    "hive",
    "iost",
    "la",
    "lsk",
    "mtl",
    "ong",
    "pha",
    "polyx",
    "power",
    "powr",
    "pundix",
    "rez",
    "rvn",
    "soph",
    "steem",
    "storj",
    "t",
    "tree",
    "vtho",
    "waxp",
    "zil",
)
DEFERRED_ASSET_IDS = (
    "1000btt",
    "b3",
    "peaq",
    "playsout",
    "puffer",
    "xcn",
    "cnpy",
    "one",
)

REVIEWED_EXACT_MAPPINGS = (
    (Venue.BYBIT, "1000BTTUSDT", "1000btt", "btt", "1000", "1"),
    (Venue.BYBIT, "B3USDT", "b3", "b3", "1", "1"),
    (Venue.BYBIT, "PEAQUSDT", "peaq", "peaq", "1", "1"),
    (Venue.BYBIT, "PLAYSOUTUSDT", "playsout", "playsout", "1", "1"),
    (Venue.BYBIT, "PUFFERUSDT", "puffer", "puffer", "1", "1"),
    (Venue.BYBIT, "XCNUSDT", "xcn", "xcn", "1", "1"),
    (Venue.OKX, "CAP-USDT-SWAP", "cap", "cap", "1", "10"),
    (Venue.OKX, "CNPY-USDT-SWAP", "cnpy", "cnpy", "1", "10"),
    (Venue.OKX, "GLM-USDT-SWAP", "glm", "glm", "1", "10"),
    (Venue.OKX, "IOST-USDT-SWAP", "iost", "iost", "1", "10"),
    (Venue.OKX, "LA-USDT-SWAP", "la", "la", "1", "10"),
    (Venue.OKX, "ONE-USDT-SWAP", "one", "one", "1", "10"),
    (Venue.OKX, "RVN-USDT-SWAP", "rvn", "rvn", "1", "10"),
    (Venue.OKX, "SOPH-USDT-SWAP", "soph", "soph", "1", "10"),
    (Venue.OKX, "ZIL-USDT-SWAP", "zil", "zil", "1", "10"),
)


def _instrument(
    *,
    symbol: str,
    base_asset: str,
    multiplier: str = "1",
    venue: Venue = Venue.BINANCE,
) -> Instrument:
    return Instrument(
        id=InstrumentId(
            venue=venue,
            symbol=symbol,
            instrument_type=InstrumentType.LINEAR_PERPETUAL,
        ),
        base_asset=AssetId(base_asset),
        quote_asset=AssetId("usdt"),
        collateral_asset=AssetId("usdt"),
        underlying_units_per_contract=Decimal(multiplier),
        tick_size=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
        min_quantity=None,
        min_notional=None,
        listed_at=None,
        delisted_at=None,
        status=InstrumentStatus.TRADING,
        observed_at=datetime(2026, 9, 9, 1, tzinfo=UTC),
    )


def test_registry_can_parse_already_loaded_toml_bytes() -> None:
    data = MAPPING_CONFIG.read_bytes()

    from_bytes = AssetMappingRegistry.from_toml_bytes(data)
    from_path = AssetMappingRegistry.from_toml(MAPPING_CONFIG)
    instrument = _instrument(symbol="STORJUSDT", base_asset="storj")

    assert from_bytes.resolve(instrument) == from_path.resolve(instrument)


@pytest.mark.parametrize("base_asset", ["storj", "lsk", "rvn"])
def test_simple_unit_asset_without_explicit_authorization_remains_pending(
    base_asset: str,
) -> None:
    registry = AssetMappingRegistry()

    mapping = registry.resolve(
        _instrument(symbol=f"{base_asset.upper()}USDT", base_asset=base_asset)
    )

    assert mapping.asset_id is None
    assert mapping.status is MappingStatus.PENDING
    assert mapping.method is MappingMethod.EXCHANGE_METADATA
    assert mapping.reviewed_at is None
    assert mapping.venue_base_asset == AssetId(base_asset)
    assert mapping.canonical_units_per_base_unit is None


def _spot(*, symbol: str, base_asset: str) -> SpotInstrument:
    return SpotInstrument(
        InstrumentId(Venue.BINANCE, symbol, InstrumentType.SPOT),
        AssetId(base_asset),
        AssetId("usdt"),
        Decimal("0.01"),
        Decimal("0.001"),
        None,
        None,
        None,
        None,
        InstrumentStatus.TRADING,
        datetime(2026, 9, 9, 1, tzinfo=UTC),
    )


def test_spot_natural_base_units_do_not_prove_canonical_identity() -> None:
    mapping = AssetMappingRegistry().resolve(_spot(symbol="STORJUSDT", base_asset="storj"))

    assert mapping.instrument_id.instrument_type is InstrumentType.SPOT
    assert mapping.asset_id is None
    assert mapping.status is MappingStatus.PENDING
    assert mapping.canonical_units_per_base_unit is None


def test_version_controlled_automatic_asset_id_can_verify_simple_perp_and_spot() -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    perp_mapping = registry.resolve(_instrument(symbol="BTCUSDT", base_asset="btc"))
    spot_mapping = registry.resolve(_spot(symbol="BTCUSDT", base_asset="btc"))

    for mapping in (perp_mapping, spot_mapping):
        assert mapping.asset_id == AssetId("btc")
        assert mapping.status is MappingStatus.VERIFIED
        assert mapping.canonical_units_per_base_unit == Decimal("1")


@pytest.mark.parametrize("base_asset", REVIEWED_SIMPLE_UNIT_ASSET_IDS)
def test_controller_reviewed_simple_unit_asset_resolves_verified(
    base_asset: str,
) -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(symbol=f"{base_asset.upper()}USDT", base_asset=base_asset)
    )

    assert mapping.status is MappingStatus.VERIFIED
    assert mapping.asset_id == AssetId(base_asset)
    assert mapping.canonical_units_per_base_unit == Decimal("1")


@pytest.mark.parametrize("base_asset", DEFERRED_ASSET_IDS)
def test_controller_deferred_asset_remains_pending(base_asset: str) -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(symbol=f"{base_asset.upper()}USDT", base_asset=base_asset)
    )

    assert mapping.status is MappingStatus.PENDING
    assert mapping.asset_id is None
    assert mapping.canonical_units_per_base_unit is None


@pytest.mark.parametrize(
    ("venue", "symbol", "venue_base", "canonical_asset", "conversion", "multiplier"),
    REVIEWED_EXACT_MAPPINGS,
)
def test_controller_reviewed_exact_instrument_mapping_is_verified(
    venue: Venue,
    symbol: str,
    venue_base: str,
    canonical_asset: str,
    conversion: str,
    multiplier: str,
) -> None:
    """Defect: reviewed exact overrides remain PENDING or fold OKX ctVal into mapping."""
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(
            venue=venue,
            symbol=symbol,
            base_asset=venue_base,
            multiplier=multiplier,
        )
    )

    assert mapping.status is MappingStatus.VERIFIED
    assert mapping.asset_id == AssetId(canonical_asset)
    assert mapping.canonical_units_per_base_unit == Decimal(conversion)
    assert mapping.method is MappingMethod.MANUAL_OVERRIDE


@pytest.mark.parametrize(
    ("symbol", "base_asset"),
    (("B3USDT", "b3"), ("ONEUSDT", "one"), ("CNPYUSDT", "cnpy")),
)
def test_exact_manual_review_does_not_expand_automatic_asset_policy(
    symbol: str,
    base_asset: str,
) -> None:
    """Defect: an exact approval accidentally authorizes same-ticker instruments globally."""
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(venue=Venue.BINANCE, symbol=symbol, base_asset=base_asset)
    )

    assert mapping.status is MappingStatus.PENDING
    assert mapping.asset_id is None


def test_reviewed_asset_with_non_unit_contract_remains_pending() -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(
            venue=Venue.OKX,
            symbol="ACE-USDT-SWAP",
            base_asset="ace",
            multiplier="10",
        )
    )

    assert mapping.status is MappingStatus.PENDING
    assert mapping.asset_id is None
    assert mapping.reason == "Non-unit multiplier requires an explicit asset mapping."
    assert mapping.canonical_units_per_base_unit is None


@pytest.mark.parametrize("venue", [Venue.BINANCE, Venue.BYBIT])
def test_explicit_multiplier_mapping_resolves_1000pepe_to_pepe(venue: Venue) -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(
            symbol="1000PEPEUSDT",
            base_asset="1000pepe",
            multiplier="1",
            venue=venue,
        )
    )

    assert mapping.asset_id == AssetId("pepe")
    assert mapping.status is MappingStatus.VERIFIED
    assert mapping.method is MappingMethod.MANUAL_OVERRIDE
    assert mapping.reason == "Contract represents 1000 units of the PEPE underlying."
    assert mapping.reviewed_at == REVIEWED_AT
    assert mapping.venue_base_asset == AssetId("1000pepe")
    assert mapping.canonical_units_per_base_unit == Decimal("1000")


def test_canonical_exposure_composes_both_exact_conversion_factors() -> None:
    instrument = _instrument(
        symbol="TWO-BASE-UNITS",
        base_asset="venue-base",
        multiplier="2",
    )
    mapping = InstrumentMapping(
        instrument_id=instrument.id,
        venue_base_asset=AssetId("venue-base"),
        asset_id=AssetId("canonical-asset"),
        canonical_units_per_base_unit=Decimal("3"),
        status=MappingStatus.VERIFIED,
        method=MappingMethod.EXCHANGE_METADATA,
        reason="Exercise the complete canonical exposure formula.",
        reviewed_at=None,
    )

    assert mapping.canonical_exposure(instrument, Decimal("4")) == Decimal("24")


def test_explicit_rejected_mapping_remains_rejected() -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(_instrument(symbol="AMBIGUSDT", base_asset="ambig"))

    assert mapping.asset_id is None
    assert mapping.status is MappingStatus.REJECTED
    assert mapping.method is MappingMethod.MANUAL_OVERRIDE
    assert mapping.reason == "Ticker identity is ambiguous and is not approved for canonical use."
    assert mapping.reviewed_at == REVIEWED_AT
    assert mapping.venue_base_asset == AssetId("ambig")
    assert mapping.canonical_units_per_base_unit is None


def test_unknown_multiplier_instrument_fails_closed_to_pending() -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(symbol="2000MYSTERYUSDT", base_asset="mystery", multiplier="2000")
    )

    assert mapping.asset_id is None
    assert mapping.status is MappingStatus.PENDING
    assert mapping.method is MappingMethod.EXCHANGE_METADATA
    assert mapping.reason == "Non-unit multiplier requires an explicit asset mapping."
    assert mapping.reviewed_at is None
    assert mapping.venue_base_asset == AssetId("mystery")
    assert mapping.canonical_units_per_base_unit is None


def test_unapproved_unit_asset_fails_closed_to_pending(tmp_path: Path) -> None:
    mapping_file = tmp_path / "asset_mappings.toml"
    mapping_file.write_text(
        'automatic_asset_ids = ["btc"]\n',
        encoding="utf-8",
    )
    registry = AssetMappingRegistry.from_toml(mapping_file)

    mapping = registry.resolve(_instrument(symbol="MYSTERYUSDT", base_asset="mystery"))

    assert mapping.asset_id is None
    assert mapping.status is MappingStatus.PENDING
    assert mapping.method is MappingMethod.EXCHANGE_METADATA
    assert mapping.reason == "Base asset is not approved for automatic mapping."
    assert mapping.reviewed_at is None
    assert mapping.venue_base_asset == AssetId("mystery")
    assert mapping.canonical_units_per_base_unit is None


def test_manual_mapping_rejects_unreviewed_venue_base_asset() -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)
    unexpected = _instrument(
        symbol="1000PEPEUSDT",
        base_asset="pepe",
        multiplier="1",
    )

    with pytest.raises(
        MappingError,
        match=r"expected.*1000pepe.*observed.*pepe",
    ):
        registry.resolve(unexpected)


def test_canonical_exposure_rejects_mismatched_venue_base_asset() -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)
    reviewed = _instrument(
        symbol="1000PEPEUSDT",
        base_asset="1000pepe",
        multiplier="1",
    )
    mapping = registry.resolve(reviewed)
    unexpected = _instrument(
        symbol="1000PEPEUSDT",
        base_asset="pepe",
        multiplier="1",
    )

    with pytest.raises(
        MappingError,
        match=r"expected.*1000pepe.*observed.*pepe",
    ):
        mapping.canonical_exposure(unexpected, Decimal("1"))


def test_manual_mapping_takes_precedence_over_automatic_metadata(tmp_path: Path) -> None:
    mapping_file = tmp_path / "asset_mappings.toml"
    mapping_file.write_text(
        """
[[mapping]]
venue = "binance"
venue_symbol = "BTCUSDT"
venue_base_asset = "btc"
status = "rejected"
method = "manual_override"
reason = "Manual review found that this fixture must not enter canonical use."
reviewed_at = 2026-09-09T00:00:00Z
""".strip(),
        encoding="utf-8",
    )
    registry = AssetMappingRegistry.from_toml(mapping_file)

    mapping = registry.resolve(_instrument(symbol="BTCUSDT", base_asset="btc"))

    assert mapping.asset_id is None
    assert mapping.status is MappingStatus.REJECTED
    assert mapping.method is MappingMethod.MANUAL_OVERRIDE
    assert mapping.reason == "Manual review found that this fixture must not enter canonical use."
    assert mapping.reviewed_at == REVIEWED_AT
    assert mapping.venue_base_asset == AssetId("btc")
    assert mapping.canonical_units_per_base_unit is None


@pytest.mark.parametrize(
    ("symbol", "base_asset"),
    [("kPEPE", "kpepe"), ("1000PEPEUSDT", "1000pepe")],
)
def test_prefix_assets_need_no_denylist_and_do_not_silently_map_to_pepe(
    symbol: str,
    base_asset: str,
) -> None:
    registry = AssetMappingRegistry.from_toml(MAPPING_CONFIG)

    mapping = registry.resolve(
        _instrument(
            venue=Venue.HYPERLIQUID,
            symbol=symbol,
            base_asset=base_asset,
        )
    )

    assert mapping.status is MappingStatus.PENDING
    assert mapping.asset_id is None
    assert mapping.reason == "Base asset is not approved for automatic mapping."


def test_manual_spot_rejection_takes_precedence_over_automatic_metadata(
    tmp_path: Path,
) -> None:
    mapping_file = tmp_path / "asset_mappings.toml"
    mapping_file.write_text(
        """
[[mapping]]
venue = "binance"
venue_symbol = "@7"
instrument_type = "spot"
venue_base_asset = "ambig"
status = "rejected"
method = "manual_override"
reason = "Source token identity is ambiguous."
reviewed_at = 2026-09-09T00:00:00Z
""".strip(),
        encoding="utf-8",
    )
    registry = AssetMappingRegistry.from_toml(mapping_file)

    mapping = registry.resolve(_spot(symbol="@7", base_asset="ambig"))

    assert mapping.status is MappingStatus.REJECTED
    assert mapping.method is MappingMethod.MANUAL_OVERRIDE
    assert mapping.asset_id is None


@pytest.mark.parametrize(
    "conversion",
    [None, Decimal("0"), Decimal("-1"), Decimal("NaN")],
)
def test_verified_mapping_requires_positive_finite_conversion(
    conversion: Decimal | None,
) -> None:
    with pytest.raises(ValueError, match=r"positive.*canonical_units_per_base_unit"):
        InstrumentMapping(
            instrument_id=InstrumentId(
                venue=Venue.BINANCE,
                symbol="BTCUSDT",
                instrument_type=InstrumentType.LINEAR_PERPETUAL,
            ),
            venue_base_asset=AssetId("btc"),
            asset_id=AssetId("btc"),
            status=MappingStatus.VERIFIED,
            method=MappingMethod.EXCHANGE_METADATA,
            reason="Test invalid conversion.",
            reviewed_at=None,
            canonical_units_per_base_unit=conversion,
        )


def test_mapping_conversion_rejects_binary_float() -> None:
    with pytest.raises(TypeError, match="must be a Decimal"):
        InstrumentMapping(
            instrument_id=InstrumentId(
                venue=Venue.BINANCE,
                symbol="BTCUSDT",
                instrument_type=InstrumentType.LINEAR_PERPETUAL,
            ),
            venue_base_asset=AssetId("btc"),
            asset_id=AssetId("btc"),
            status=MappingStatus.VERIFIED,
            method=MappingMethod.EXCHANGE_METADATA,
            reason="Test binary float conversion.",
            reviewed_at=None,
            canonical_units_per_base_unit=1.0,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("status", [MappingStatus.PENDING, MappingStatus.REJECTED])
def test_non_verified_mapping_rejects_fabricated_conversion(status: MappingStatus) -> None:
    with pytest.raises(ValueError, match=r"only.*VERIFIED"):
        InstrumentMapping(
            instrument_id=InstrumentId(
                venue=Venue.BINANCE,
                symbol="AMBIGUSDT",
                instrument_type=InstrumentType.LINEAR_PERPETUAL,
            ),
            venue_base_asset=AssetId("ambig"),
            asset_id=None,
            status=status,
            method=MappingMethod.EXCHANGE_METADATA,
            reason="Test non-verified conversion.",
            reviewed_at=None,
            canonical_units_per_base_unit=Decimal("1"),
        )


def test_manual_verified_conversion_must_be_a_decimal_string(tmp_path: Path) -> None:
    mapping_file = tmp_path / "asset_mappings.toml"
    mapping_file.write_text(
        """
[[mapping]]
venue = "binance"
venue_symbol = "1000PEPEUSDT"
venue_base_asset = "1000pepe"
asset_id = "pepe"
status = "verified"
method = "manual_override"
canonical_units_per_base_unit = 1000.0
reason = "Binary-float TOML values are forbidden."
reviewed_at = 2026-09-09T00:00:00Z
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="decimal string"):
        AssetMappingRegistry.from_toml(mapping_file)
