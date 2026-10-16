from datetime import UTC, datetime
from decimal import Decimal

import pytest

from funding_arb.domain.enums import FundingType, InstrumentType, Venue
from funding_arb.domain.funding import FundingRuleObservation, FundingSettlement
from funding_arb.domain.identifiers import InstrumentId


@pytest.fixture
def instrument_id() -> InstrumentId:
    return InstrumentId(
        venue=Venue.BINANCE,
        symbol="BTCUSDT",
        instrument_type=InstrumentType.LINEAR_PERPETUAL,
    )


def test_funding_rate_is_decimal_fraction(instrument_id: InstrumentId) -> None:
    settlement = FundingSettlement(
        venue=Venue.BINANCE,
        instrument_id=instrument_id,
        settlement_time=datetime(2026, 9, 8, 0, tzinfo=UTC),
        rate=Decimal("0.02"),
        funding_type=FundingType.REGULAR,
        source_record_id="raw-1",
        ingested_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
    )

    assert settlement.rate == Decimal("0.02")


def test_funding_type_distinguishes_unclassified_from_unknown() -> None:
    assert FundingType.UNCLASSIFIED.value == "unclassified"
    assert FundingType.UNCLASSIFIED is not FundingType.UNKNOWN


def test_funding_settlement_rejects_float_rate(instrument_id: InstrumentId) -> None:
    with pytest.raises(TypeError, match="rate must be a Decimal"):
        FundingSettlement(
            venue=Venue.BINANCE,
            instrument_id=instrument_id,
            settlement_time=datetime(2026, 9, 8, 0, tzinfo=UTC),
            rate=0.001,
            funding_type=FundingType.REGULAR,
            source_record_id="raw-1",
            ingested_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
        )


def test_funding_settlement_rejects_naive_time(instrument_id: InstrumentId) -> None:
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        FundingSettlement(
            venue=Venue.BINANCE,
            instrument_id=instrument_id,
            settlement_time=datetime(2026, 9, 8, 0),
            rate=Decimal("0.001"),
            funding_type=FundingType.REGULAR,
            source_record_id="raw-1",
            ingested_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
        )


def test_funding_settlement_rejects_naive_ingestion_time(
    instrument_id: InstrumentId,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        FundingSettlement(
            venue=Venue.BINANCE,
            instrument_id=instrument_id,
            settlement_time=datetime(2026, 9, 8, 0, tzinfo=UTC),
            rate=Decimal("0.001"),
            funding_type=FundingType.REGULAR,
            source_record_id="raw-1",
            ingested_at=datetime(2026, 9, 9, 0),
        )


def test_funding_settlement_rejects_cross_venue_instrument_id(
    instrument_id: InstrumentId,
) -> None:
    with pytest.raises(ValueError, match=r"venue must match instrument_id\.venue"):
        FundingSettlement(
            venue=Venue.OKX,
            instrument_id=instrument_id,
            settlement_time=datetime(2026, 9, 8, 0, tzinfo=UTC),
            rate=Decimal("0.001"),
            funding_type=FundingType.REGULAR,
            source_record_id="raw-1",
            ingested_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
        )


def test_funding_settlement_rejects_blank_source_record_id(
    instrument_id: InstrumentId,
) -> None:
    with pytest.raises(ValueError, match="source_record_id cannot be blank"):
        FundingSettlement(
            venue=Venue.BINANCE,
            instrument_id=instrument_id,
            settlement_time=datetime(2026, 9, 8, 0, tzinfo=UTC),
            rate=Decimal("0.001"),
            funding_type=FundingType.REGULAR,
            source_record_id=" ",
            ingested_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
        )


def test_funding_rule_observation_preserves_exact_fractional_bounds(
    instrument_id: InstrumentId,
) -> None:
    rule = FundingRuleObservation(
        venue=Venue.BINANCE,
        instrument_id=instrument_id,
        interval_seconds=28_800,
        cap=Decimal("0.0075"),
        floor=Decimal("-0.0075"),
        effective_at=datetime(2026, 9, 8, 0, tzinfo=UTC),
        observed_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
        source_record_id="raw-rule-1",
    )

    assert rule.cap == Decimal("0.0075")
    assert rule.floor == Decimal("-0.0075")


@pytest.mark.parametrize("field_name", ["cap", "floor"])
def test_funding_rule_observation_rejects_float_bounds(
    instrument_id: InstrumentId,
    field_name: str,
) -> None:
    values = {
        "venue": Venue.BINANCE,
        "instrument_id": instrument_id,
        "interval_seconds": 28_800,
        "cap": Decimal("0.0075"),
        "floor": Decimal("-0.0075"),
        "effective_at": datetime(2026, 9, 8, 0, tzinfo=UTC),
        "observed_at": datetime(2026, 9, 9, 0, tzinfo=UTC),
        "source_record_id": "raw-rule-1",
    } | {field_name: 0.0075}

    with pytest.raises(TypeError, match=f"{field_name} must be a Decimal"):
        FundingRuleObservation(**values)


def test_funding_rule_observation_leaves_missing_bounds_unknown(
    instrument_id: InstrumentId,
) -> None:
    rule = FundingRuleObservation(
        venue=Venue.BINANCE,
        instrument_id=instrument_id,
        interval_seconds=28_800,
        cap=None,
        floor=None,
        effective_at=None,
        observed_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
        source_record_id="raw-rule-1",
    )

    assert rule.cap is None
    assert rule.floor is None


def test_funding_rule_observation_rejects_non_positive_interval(
    instrument_id: InstrumentId,
) -> None:
    with pytest.raises(ValueError, match="interval_seconds must be positive"):
        FundingRuleObservation(
            venue=Venue.BINANCE,
            instrument_id=instrument_id,
            interval_seconds=0,
            cap=None,
            floor=None,
            effective_at=None,
            observed_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
            source_record_id="raw-rule-1",
        )


def test_funding_rule_observation_rejects_cross_venue_instrument_id(
    instrument_id: InstrumentId,
) -> None:
    with pytest.raises(ValueError, match=r"venue must match instrument_id\.venue"):
        FundingRuleObservation(
            venue=Venue.OKX,
            instrument_id=instrument_id,
            interval_seconds=28_800,
            cap=None,
            floor=None,
            effective_at=None,
            observed_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
            source_record_id="raw-rule-1",
        )


@pytest.mark.parametrize("field_name", ["effective_at", "observed_at"])
def test_funding_rule_observation_rejects_non_utc_rule_times(
    instrument_id: InstrumentId,
    field_name: str,
) -> None:
    values = {
        "venue": Venue.BINANCE,
        "instrument_id": instrument_id,
        "interval_seconds": 28_800,
        "cap": None,
        "floor": None,
        "effective_at": datetime(2026, 9, 8, 0, tzinfo=UTC),
        "observed_at": datetime(2026, 9, 9, 0, tzinfo=UTC),
        "source_record_id": "raw-rule-1",
    } | {field_name: datetime(2026, 9, 9, 0)}

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        FundingRuleObservation(**values)


def test_funding_rule_observation_rejects_blank_source_record_id(
    instrument_id: InstrumentId,
) -> None:
    with pytest.raises(ValueError, match="source_record_id cannot be blank"):
        FundingRuleObservation(
            venue=Venue.BINANCE,
            instrument_id=instrument_id,
            interval_seconds=28_800,
            cap=None,
            floor=None,
            effective_at=None,
            observed_at=datetime(2026, 9, 9, 0, tzinfo=UTC),
            source_record_id=" ",
        )
