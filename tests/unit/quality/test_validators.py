from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from funding_arb.domain.enums import (
    FundingType,
    InstrumentStatus,
    InstrumentType,
    MappingStatus,
    Venue,
)
from funding_arb.domain.funding import FundingSettlement
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.instruments import Instrument
from funding_arb.domain.quality import (
    QualityCheckedRecord,
    QualityReasonCode,
    QualitySeverity,
    QualityStatus,
)
from funding_arb.mapping.registry import InstrumentMapping, MappingMethod
from funding_arb.quality.validators import (
    LARGE_FUNDING_RATE_WARNING_THRESHOLD,
    validate_funding_settlement,
    validate_funding_settlements,
    validate_instrument,
    validate_instrument_mapping,
)


def _instrument() -> Instrument:
    return Instrument(
        id=InstrumentId(Venue.BINANCE, "BTCUSDT", InstrumentType.LINEAR_PERPETUAL),
        base_asset=AssetId("btc"),
        quote_asset=AssetId("usdt"),
        collateral_asset=AssetId("usdt"),
        underlying_units_per_contract=Decimal("1"),
        tick_size=Decimal("0.1"),
        quantity_step=Decimal("0.001"),
        min_quantity=Decimal("0.001"),
        min_notional=Decimal("5"),
        listed_at=datetime(2026, 1, 1, tzinfo=UTC),
        delisted_at=None,
        status=InstrumentStatus.TRADING,
        observed_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def _settlement(instrument: Instrument, **changes: object) -> FundingSettlement:
    values: dict[str, object] = {
        "venue": instrument.id.venue,
        "instrument_id": instrument.id,
        "settlement_time": datetime(2026, 9, 8, tzinfo=UTC),
        "rate": Decimal("0.0001"),
        "funding_type": FundingType.REGULAR,
        "source_record_id": "raw-1",
        "ingested_at": datetime(2026, 9, 9, tzinfo=UTC),
    }
    values.update(changes)
    return FundingSettlement(**values)  # type: ignore[arg-type]


def _invalid_instrument(instrument: Instrument, **changes: object) -> Instrument:
    """Construct an impossible-at-runtime state solely to exercise the quality boundary."""
    invalid = object.__new__(Instrument)
    for name, value in (instrument.__dict__ | changes).items():
        object.__setattr__(invalid, name, value)
    return invalid


def test_instrument_lifecycle_ordering_is_reported() -> None:
    instrument = _invalid_instrument(
        _instrument(),
        delisted_at=datetime(2025, 12, 31, tzinfo=UTC),
    )

    findings = validate_instrument(instrument)

    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.ERROR, QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH)
    ]


def test_instrument_non_positive_quantity_step_is_reported() -> None:
    instrument = _invalid_instrument(_instrument(), quantity_step=Decimal("0"))

    findings = validate_instrument(instrument)

    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.ERROR, QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH)
    ]


def test_missing_fixed_tick_is_valid_when_no_single_tick_applies() -> None:
    instrument = replace(_instrument(), tick_size=None)

    assert validate_instrument(instrument) == []


def test_funding_for_mismatched_instrument_is_an_error() -> None:
    expected = _instrument()
    other = replace(
        expected,
        id=InstrumentId(Venue.BINANCE, "ETHUSDT", InstrumentType.LINEAR_PERPETUAL),
    )

    findings = validate_funding_settlement(_settlement(other), expected)

    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.ERROR, QualityReasonCode.UNKNOWN_INSTRUMENT)
    ]


def test_unknown_funding_type_is_an_error() -> None:
    instrument = _instrument()

    findings = validate_funding_settlement(
        _settlement(instrument, funding_type=FundingType.UNKNOWN), instrument
    )

    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.ERROR, QualityReasonCode.UNKNOWN_FUNDING_TYPE)
    ]


def test_unclassified_funding_type_remains_valid_without_other_errors() -> None:
    instrument = _instrument()
    settlement = _settlement(instrument, funding_type=FundingType.UNCLASSIFIED)

    findings = validate_funding_settlement(settlement, instrument)
    checked = QualityCheckedRecord(settlement, tuple(findings))

    assert findings == []
    assert checked.quality_status is QualityStatus.VALID


def test_large_parseable_funding_is_retained_as_a_warning() -> None:
    instrument = _instrument()
    settlement = _settlement(instrument, rate=LARGE_FUNDING_RATE_WARNING_THRESHOLD)

    findings = validate_funding_settlement(settlement, instrument)

    assert settlement.rate == LARGE_FUNDING_RATE_WARNING_THRESHOLD
    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.WARNING, QualityReasonCode.LARGE_FUNDING_RATE)
    ]


def test_conflicting_duplicate_is_an_error_finding() -> None:
    instrument = _instrument()
    first = _settlement(instrument, source_record_id="raw-1")
    conflicting = _settlement(instrument, source_record_id="raw-2", rate=Decimal("0.0002"))

    findings = validate_funding_settlements([first, conflicting])

    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.ERROR, QualityReasonCode.CONFLICTING_DUPLICATE)
    ]


def test_pending_mapping_is_visible_and_excluded_from_default_research() -> None:
    instrument = _instrument()
    mapping = InstrumentMapping(
        instrument_id=instrument.id,
        venue_base_asset=instrument.base_asset,
        asset_id=None,
        canonical_units_per_base_unit=None,
        status=MappingStatus.PENDING,
        method=MappingMethod.EXCHANGE_METADATA,
        reason="Needs reviewed identity evidence.",
        reviewed_at=None,
    )

    findings = validate_instrument_mapping(mapping, instrument)

    assert [(finding.severity, finding.code) for finding in findings] == [
        (QualitySeverity.ERROR, QualityReasonCode.AMBIGUOUS_ASSET_MAPPING)
    ]
