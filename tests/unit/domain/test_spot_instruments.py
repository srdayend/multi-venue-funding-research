from datetime import UTC, datetime
from decimal import Decimal

import pytest

from funding_arb.domain.enums import InstrumentStatus, InstrumentType, Venue
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.spot_instruments import SpotInstrument


@pytest.fixture
def spot_instrument() -> SpotInstrument:
    return SpotInstrument(
        id=InstrumentId(Venue.BINANCE, "BTCUSDT", InstrumentType.SPOT),
        base_asset=AssetId("btc"),
        quote_asset=AssetId("usdt"),
        tick_size=Decimal("0.01"),
        quantity_step=Decimal("0.00001"),
        min_quantity=Decimal("0.00001"),
        min_notional=Decimal("5"),
        listed_at=datetime(2020, 1, 1, tzinfo=UTC),
        delisted_at=None,
        status=InstrumentStatus.TRADING,
        observed_at=datetime(2026, 9, 12, tzinfo=UTC),
    )


def test_spot_instrument_has_no_derivative_only_semantics(
    spot_instrument: SpotInstrument,
) -> None:
    assert spot_instrument.id.instrument_type is InstrumentType.SPOT
    assert not hasattr(spot_instrument, "collateral_asset")
    assert not hasattr(spot_instrument, "underlying_units_per_contract")


@pytest.mark.parametrize(
    "field_name",
    ["tick_size", "quantity_step", "min_quantity", "min_notional"],
)
def test_spot_instrument_allows_missing_optional_constraints(
    spot_instrument: SpotInstrument,
    field_name: str,
) -> None:
    instrument = SpotInstrument(**(spot_instrument.__dict__ | {field_name: None}))

    assert getattr(instrument, field_name) is None


@pytest.mark.parametrize(
    "field_name",
    ["tick_size", "quantity_step", "min_quantity", "min_notional"],
)
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_spot_instrument_rejects_non_positive_constraints(
    spot_instrument: SpotInstrument,
    field_name: str,
    value: Decimal,
) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be positive"):
        SpotInstrument(**(spot_instrument.__dict__ | {field_name: value}))


@pytest.mark.parametrize(
    "field_name",
    ["tick_size", "quantity_step", "min_quantity", "min_notional"],
)
def test_spot_instrument_rejects_binary_float_constraints(
    spot_instrument: SpotInstrument,
    field_name: str,
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be a Decimal"):
        SpotInstrument(**(spot_instrument.__dict__ | {field_name: 1.0}))


@pytest.mark.parametrize("field_name", ["listed_at", "delisted_at", "observed_at"])
def test_spot_instrument_requires_utc_times(
    spot_instrument: SpotInstrument,
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        SpotInstrument(
            **(
                spot_instrument.__dict__
                | {field_name: datetime(2026, 9, 12)}
            )
        )


def test_spot_instrument_rejects_derivative_identity(
    spot_instrument: SpotInstrument,
) -> None:
    derivative_id = InstrumentId(
        Venue.BINANCE,
        "BTCUSDT",
        InstrumentType.LINEAR_PERPETUAL,
    )

    with pytest.raises(ValueError, match="SPOT identity"):
        SpotInstrument(**(spot_instrument.__dict__ | {"id": derivative_id}))
