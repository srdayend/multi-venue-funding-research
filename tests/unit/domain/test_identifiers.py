import pytest

from funding_arb.domain.enums import InstrumentType, Venue
from funding_arb.domain.identifiers import AssetId, InstrumentId


def test_asset_id_is_normalized_to_lowercase() -> None:
    assert AssetId("PEPE").value == "pepe"


def test_asset_id_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="AssetId cannot be blank"):
        AssetId("  ")


def test_instrument_id_is_venue_scoped() -> None:
    instrument_id = InstrumentId(
        venue=Venue.BINANCE,
        symbol="1000PEPEUSDT",
        instrument_type=InstrumentType.LINEAR_PERPETUAL,
    )
    assert instrument_id.key == "binance:1000PEPEUSDT:linear_perpetual"


def test_spot_instrument_id_preserves_product_family() -> None:
    instrument_id = InstrumentId(
        venue=Venue.BINANCE,
        symbol="BTCUSDT",
        instrument_type=InstrumentType.SPOT,
    )

    assert instrument_id.key == "binance:BTCUSDT:spot"
