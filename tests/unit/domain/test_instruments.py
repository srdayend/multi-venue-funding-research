from datetime import UTC, datetime
from decimal import Decimal

import pytest

from funding_arb.domain.enums import InstrumentStatus, InstrumentType, Venue
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.instruments import Instrument


@pytest.fixture
def linear_perp_instrument() -> Instrument:
    return Instrument(
        id=InstrumentId(
            venue=Venue.BINANCE,
            symbol="1000PEPEUSDT",
            instrument_type=InstrumentType.LINEAR_PERPETUAL,
        ),
        base_asset=AssetId("pepe"),
        quote_asset=AssetId("usdt"),
        collateral_asset=AssetId("usdt"),
        underlying_units_per_contract=Decimal("1000"),
        tick_size=Decimal("0.000001"),
        quantity_step=Decimal("1"),
        min_quantity=Decimal("0"),
        min_notional=Decimal("5"),
        listed_at=datetime(2026, 1, 1, tzinfo=UTC),
        delisted_at=None,
        status=InstrumentStatus.TRADING,
        observed_at=datetime(2026, 9, 9, 4, 0, tzinfo=UTC),
    )


def test_underlying_exposure_uses_multiplier(linear_perp_instrument: Instrument) -> None:
    assert linear_perp_instrument.underlying_units(Decimal("3")) == Decimal("3000")


@pytest.mark.parametrize(
    "field_name",
    [
        "underlying_units_per_contract",
        "tick_size",
        "quantity_step",
        "min_quantity",
        "min_notional",
    ],
)
def test_instrument_rejects_float_trading_values(
    linear_perp_instrument: Instrument,
    field_name: str,
) -> None:
    values = linear_perp_instrument.__dict__ | {field_name: 1.0}

    with pytest.raises(TypeError, match=f"{field_name} must be a Decimal"):
        Instrument(**values)


def test_instrument_allows_missing_optional_minimums(
    linear_perp_instrument: Instrument,
) -> None:
    values = linear_perp_instrument.__dict__ | {"min_quantity": None, "min_notional": None}

    instrument = Instrument(**values)

    assert instrument.min_quantity is None
    assert instrument.min_notional is None


def test_instrument_allows_missing_fixed_tick_when_venue_has_dynamic_price_rules(
    linear_perp_instrument: Instrument,
) -> None:
    instrument = Instrument(**(linear_perp_instrument.__dict__ | {"tick_size": None}))

    assert instrument.tick_size is None


def test_underlying_units_rejects_float_quantity(linear_perp_instrument: Instrument) -> None:
    with pytest.raises(TypeError, match="quantity must be a Decimal"):
        linear_perp_instrument.underlying_units(3.0)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("underlying_units_per_contract", Decimal("0")),
        ("tick_size", Decimal("0")),
        ("quantity_step", Decimal("0")),
    ],
)
def test_instrument_rejects_non_positive_trading_values(
    linear_perp_instrument: Instrument,
    field_name: str,
    value: Decimal,
) -> None:
    values = linear_perp_instrument.__dict__ | {field_name: value}

    with pytest.raises(ValueError, match=f"{field_name} must be positive"):
        Instrument(**values)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("min_quantity", Decimal("-1")),
        ("min_notional", Decimal("-0.01")),
    ],
)
def test_instrument_rejects_negative_optional_minimums(
    linear_perp_instrument: Instrument,
    field_name: str,
    value: Decimal,
) -> None:
    values = linear_perp_instrument.__dict__ | {field_name: value}

    with pytest.raises(ValueError, match=f"{field_name} must not be negative"):
        Instrument(**values)


@pytest.mark.parametrize("field_name", ["listed_at", "delisted_at", "observed_at"])
def test_instrument_rejects_non_utc_lifecycle_and_observation_times(
    linear_perp_instrument: Instrument,
    field_name: str,
) -> None:
    values = linear_perp_instrument.__dict__ | {field_name: datetime(2026, 9, 9, 4, 0)}

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        Instrument(**values)
