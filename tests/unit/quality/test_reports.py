from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
from funding_arb.domain.provenance import DatasetManifest, FundingCoverage
from funding_arb.domain.quality import (
    QualityCheckedRecord,
    QualityFinding,
    QualityReasonCode,
    QualitySeverity,
)
from funding_arb.mapping.registry import InstrumentMapping, MappingMethod
from funding_arb.quality.reports import build_quality_report

REQUESTED_START = datetime(2026, 8, 1, tzinfo=UTC)
REQUESTED_END = datetime(2026, 8, 31, 23, 59, 59, 999000, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 9, 1, tzinfo=UTC)


def _instrument(venue: Venue, symbol: str, multiplier: str = "1") -> Instrument:
    return Instrument(
        id=InstrumentId(venue, symbol, InstrumentType.LINEAR_PERPETUAL),
        base_asset=AssetId("btc"),
        quote_asset=AssetId("usdt"),
        collateral_asset=AssetId("usdt"),
        underlying_units_per_contract=Decimal(multiplier),
        tick_size=Decimal("0.1"),
        quantity_step=Decimal("0.001"),
        min_quantity=None,
        min_notional=None,
        listed_at=None,
        delisted_at=None,
        status=InstrumentStatus.TRADING,
        observed_at=OBSERVED_AT,
    )


def _mapping(instrument: Instrument, status: MappingStatus) -> InstrumentMapping:
    verified = status is MappingStatus.VERIFIED
    return InstrumentMapping(
        instrument_id=instrument.id,
        venue_base_asset=instrument.base_asset,
        asset_id=instrument.base_asset if verified else None,
        canonical_units_per_base_unit=Decimal("1") if verified else None,
        status=status,
        method=MappingMethod.EXCHANGE_METADATA,
        reason=f"{status.value} fixture mapping",
        reviewed_at=None,
    )


def _funding(
    instrument: Instrument,
    finding: QualityFinding | None = None,
) -> QualityCheckedRecord[FundingSettlement]:
    return QualityCheckedRecord(
        FundingSettlement(
            venue=instrument.id.venue,
            instrument_id=instrument.id,
            settlement_time=datetime(2026, 8, 1, 8, tzinfo=UTC),
            rate=Decimal("0.0001"),
            funding_type=FundingType.REGULAR,
            source_record_id=f"raw-{instrument.id.venue.value}",
            ingested_at=OBSERVED_AT,
        ),
        (finding,) if finding is not None else (),
    )


def _coverage(instrument: Instrument) -> FundingCoverage:
    return FundingCoverage(
        requested_start=REQUESTED_START,
        requested_end=REQUESTED_END,
        observed_start=datetime(2026, 8, 1, 8, tzinfo=UTC),
        observed_end=datetime(2026, 8, 1, 8, tzinfo=UTC),
        observed_row_count=1,
    )


def _manifest(instruments: list[Instrument]) -> DatasetManifest:
    return DatasetManifest(
        dataset_id="quality-report",
        created_at=OBSERVED_AT,
        git_commit="a" * 40,
        schema_version="1",
        collection_config_sha256="b" * 64,
        mapping_config_sha256="c" * 64,
        raw_record_refs=(),
        row_counts={"instruments": 2, "mappings": 2, "funding": 2},
        quarantine_counts={"ambiguous_asset_mapping": 1},
        quality_finding_counts={
            "ambiguous_asset_mapping": 1,
            "unknown_funding_type": 1,
        },
        funding_coverage={instrument.id.key: _coverage(instrument) for instrument in instruments},
        canonical_output_sha256={
            "instruments.parquet": "d" * 64,
            "mappings.parquet": "e" * 64,
            "funding.parquet": "f" * 64,
        },
    )


def test_quality_report_keeps_quality_mapping_coverage_and_conflicts_separate() -> None:
    binance = _instrument(Venue.BINANCE, "BTCUSDT")
    okx = _instrument(Venue.OKX, "BTC-USDT-SWAP", "0.01")
    funding_error = QualityFinding(
        QualitySeverity.ERROR,
        QualityReasonCode.UNKNOWN_FUNDING_TYPE,
        "raw-okx",
        "fixture error",
    )

    report = build_quality_report(
        manifest=_manifest([binance, okx]),
        instruments=[QualityCheckedRecord(binance), QualityCheckedRecord(okx)],
        mappings=[
            _mapping(binance, MappingStatus.VERIFIED),
            _mapping(okx, MappingStatus.PENDING),
        ],
        funding=[_funding(binance), _funding(okx, funding_error)],
        identical_duplicate_count=3,
        conflicting_duplicate_count=1,
    )

    assert report.dataset_manifest_id == "quality-report"
    assert report.instrument_counts_by_venue == {
        "binance": 1,
        "bybit": 0,
        "hyperliquid": 0,
        "okx": 1,
    }
    assert report.mapping_status_counts == {"pending": 1, "rejected": 0, "verified": 1}
    assert report.funding_row_count == 2
    assert report.funding_row_counts_by_venue == {
        "binance": 1,
        "bybit": 0,
        "hyperliquid": 0,
        "okx": 1,
    }
    assert report.instrument_quality_status_counts == {"invalid": 0, "valid": 2}
    assert report.funding_quality_status_counts == {"invalid": 1, "valid": 1}
    assert report.identical_duplicate_count == 3
    assert report.conflicting_duplicate_count == 1
    assert report.quarantine_reason_counts == {"ambiguous_asset_mapping": 1}
    assert report.quality_finding_counts == {
        "ambiguous_asset_mapping": 1,
        "unknown_funding_type": 1,
    }
    assert report.schema_versions == {"funding": "1", "instruments": "1", "mappings": "1"}
    assert set(report.funding_coverage) == {binance.id.key, okx.id.key}
    with pytest.raises(TypeError):
        report.mapping_status_counts["verified"] = 2  # type: ignore[index]


def test_quality_report_rejects_manifest_row_count_mismatch() -> None:
    binance = _instrument(Venue.BINANCE, "BTCUSDT")

    with pytest.raises(ValueError, match=r"manifest.*instrument.*row count"):
        build_quality_report(
            manifest=_manifest([binance]),
            instruments=[QualityCheckedRecord(binance)],
            mappings=[_mapping(binance, MappingStatus.VERIFIED)],
            funding=[_funding(binance)],
            identical_duplicate_count=0,
            conflicting_duplicate_count=0,
        )
