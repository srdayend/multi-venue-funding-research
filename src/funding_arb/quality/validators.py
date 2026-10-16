"""Pure validations at the canonical quality boundary."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal

from funding_arb.domain.enums import FundingType, MappingStatus
from funding_arb.domain.funding import FundingSettlement
from funding_arb.domain.instruments import Instrument
from funding_arb.domain.quality import QualityFinding, QualityReasonCode, QualitySeverity
from funding_arb.mapping.registry import InstrumentMapping

# This is an outlier-review threshold, not an annualized rate, forecast, or trading rule.
# A ten-percent settled rate is retained because it can be real, but always surfaced.
LARGE_FUNDING_RATE_WARNING_THRESHOLD = Decimal("0.10")


def validate_instrument(instrument: Instrument) -> list[QualityFinding]:
    """Report economically meaningful invalid instrument semantics without repair."""
    findings: list[QualityFinding] = []
    record_id = instrument.id.key
    if not _is_utc(instrument.observed_at):
        findings.append(_finding(QualityReasonCode.INVALID_TIMESTAMP, record_id, "observed_at"))
    for field_name in ("listed_at", "delisted_at"):
        value = getattr(instrument, field_name)
        if value is not None and not _is_utc(value):
            findings.append(_finding(QualityReasonCode.INVALID_TIMESTAMP, record_id, field_name))
    if instrument.listed_at is not None and instrument.delisted_at is not None:
        if instrument.delisted_at < instrument.listed_at:
            findings.append(
                _finding(
                    QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH,
                    record_id,
                    "delisted_at precedes listed_at",
                )
            )
    for field_name in ("underlying_units_per_contract", "quantity_step"):
        value = getattr(instrument, field_name)
        if not isinstance(value, Decimal) or not value.is_finite() or value <= Decimal("0"):
            findings.append(
                _finding(QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH, record_id, field_name)
            )
    tick_size = instrument.tick_size
    if tick_size is not None and (
        not isinstance(tick_size, Decimal)
        or not tick_size.is_finite()
        or tick_size <= Decimal("0")
    ):
        findings.append(
            _finding(QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH, record_id, "tick_size")
        )
    for field_name in ("min_quantity", "min_notional"):
        value = getattr(instrument, field_name)
        if value is not None and (
            not isinstance(value, Decimal) or not value.is_finite() or value < Decimal("0")
        ):
            findings.append(
                _finding(QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH, record_id, field_name)
            )
    return findings


def validate_instrument_mapping(
    mapping: InstrumentMapping,
    instrument: Instrument,
) -> list[QualityFinding]:
    """Keep PENDING and REJECTED mappings visible and outside valid research data."""
    record_id = instrument.id.key
    if mapping.instrument_id != instrument.id or mapping.venue_base_asset != instrument.base_asset:
        return [
            _finding(
                QualityReasonCode.AMBIGUOUS_ASSET_MAPPING,
                record_id,
                "mapping identity or reviewed venue-base asset does not match the instrument",
            )
        ]
    if mapping.status is MappingStatus.VERIFIED:
        return []
    if mapping.status is MappingStatus.PENDING:
        detail = "asset mapping is pending and is excluded from default research"
    else:
        detail = "asset mapping is rejected and is excluded from default research"
    return [_finding(QualityReasonCode.AMBIGUOUS_ASSET_MAPPING, record_id, detail)]


def validate_funding_settlement(
    settlement: FundingSettlement,
    instrument: Instrument,
) -> list[QualityFinding]:
    """Validate a settlement against the known instrument without changing it."""
    findings: list[QualityFinding] = []
    record_id = settlement.source_record_id
    if settlement.instrument_id != instrument.id or settlement.venue != instrument.id.venue:
        findings.append(
            _finding(
                QualityReasonCode.UNKNOWN_INSTRUMENT,
                record_id,
                "settlement does not reference the expected known instrument",
            )
        )
    for field_name in ("settlement_time", "ingested_at"):
        if not _is_utc(getattr(settlement, field_name)):
            findings.append(_finding(QualityReasonCode.INVALID_TIMESTAMP, record_id, field_name))
    if not isinstance(settlement.rate, Decimal) or not settlement.rate.is_finite():
        findings.append(
            _finding(QualityReasonCode.SCHEMA_SEMANTIC_MISMATCH, record_id, "funding rate")
        )
    elif abs(settlement.rate) >= LARGE_FUNDING_RATE_WARNING_THRESHOLD:
        findings.append(
            QualityFinding(
                severity=QualitySeverity.WARNING,
                code=QualityReasonCode.LARGE_FUNDING_RATE,
                record_id=record_id,
                message=(
                    "Funding rate meets the explicit outlier-review threshold "
                    f"of {LARGE_FUNDING_RATE_WARNING_THRESHOLD}."
                ),
            )
        )
    if settlement.funding_type is FundingType.UNKNOWN:
        findings.append(
            _finding(
                QualityReasonCode.UNKNOWN_FUNDING_TYPE,
                record_id,
                "funding subtype or critical meaning is unresolved and cannot enter "
                "default research",
            )
        )
    return findings


def validate_funding_settlements(
    settlements: Iterable[FundingSettlement],
) -> list[QualityFinding]:
    """Report conflicting same-logical-key observations; identical duplicates stay duplicates."""
    by_key: dict[tuple[str, datetime], list[FundingSettlement]] = defaultdict(list)
    for settlement in settlements:
        by_key[(settlement.instrument_id.key, settlement.settlement_time)].append(settlement)

    findings: list[QualityFinding] = []
    for (instrument_key, settlement_time), observations in sorted(by_key.items()):
        meanings = {(item.rate, item.funding_type) for item in observations}
        if len(meanings) > 1:
            findings.append(
                QualityFinding(
                    severity=QualitySeverity.ERROR,
                    code=QualityReasonCode.CONFLICTING_DUPLICATE,
                    record_id=f"{instrument_key}@{settlement_time.isoformat()}",
                    message="Same logical settlement key has conflicting funding semantics.",
                )
            )
    return findings


def _is_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _finding(code: QualityReasonCode, record_id: str, detail: str) -> QualityFinding:
    return QualityFinding(
        severity=QualitySeverity.ERROR,
        code=code,
        record_id=record_id,
        message=detail,
    )
