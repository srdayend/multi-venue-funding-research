import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from funding_arb.domain.enums import FundingType, InstrumentStatus, InstrumentType, Venue
from funding_arb.domain.funding import FundingSettlement
from funding_arb.domain.identifiers import AssetId, InstrumentId
from funding_arb.domain.instruments import Instrument
from funding_arb.domain.provenance import RawRecordRef
from funding_arb.domain.quality import QualityFinding, QualityReasonCode, QualitySeverity
from funding_arb.quality.quarantine import QuarantineStore


def _instrument() -> Instrument:
    return Instrument(
        id=InstrumentId(Venue.BINANCE, "BTCUSDT", InstrumentType.LINEAR_PERPETUAL),
        base_asset=AssetId("btc"),
        quote_asset=AssetId("usdt"),
        collateral_asset=AssetId("usdt"),
        underlying_units_per_contract=Decimal("1"),
        tick_size=Decimal("0.1"),
        quantity_step=Decimal("0.001"),
        min_quantity=None,
        min_notional=None,
        listed_at=datetime(2026, 1, 1, tzinfo=UTC),
        delisted_at=None,
        status=InstrumentStatus.TRADING,
        observed_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_quarantine_write_is_deterministic_and_preserves_audit_evidence(tmp_path: Path) -> None:
    instrument = _instrument()
    settlement = FundingSettlement(
        venue=Venue.BINANCE,
        instrument_id=instrument.id,
        settlement_time=datetime(2026, 9, 8, 0, 0, 0, 123456, tzinfo=UTC),
        rate=Decimal("0.1234500"),
        funding_type=FundingType.UNKNOWN,
        source_record_id="raw-1",
        ingested_at=datetime(2026, 9, 9, tzinfo=UTC),
    )
    findings = [
        QualityFinding(
            severity=QualitySeverity.ERROR,
            code=QualityReasonCode.UNKNOWN_FUNDING_TYPE,
            record_id="raw-1",
            message="Funding type is unknown.",
        )
    ]
    raw_refs = [RawRecordRef("raw-1", "raw/binance/funding/raw-1.json.gz", "a" * 64)]
    store = QuarantineStore(tmp_path / "data" / "quarantine", "run-20260909")

    first_path = store.write(settlement, findings, raw_refs)
    second_path = store.write(settlement, findings, raw_refs)

    assert first_path == second_path
    assert Path(first_path).parent == tmp_path / "data" / "quarantine" / "run-20260909"
    document = json.loads(Path(first_path).read_text(encoding="utf-8"))
    assert document["canonical_candidate"]["rate"] == "0.1234500"
    assert document["canonical_candidate"]["settlement_time"] == "2026-09-08T00:00:00.123456Z"
    assert document["findings"] == [
        {
            "code": "unknown_funding_type",
            "message": "Funding type is unknown.",
            "record_id": "raw-1",
            "severity": "error",
        }
    ]
    assert document["raw_record_refs"] == [
        {
            "body_sha256": "a" * 64,
            "path": "raw/binance/funding/raw-1.json.gz",
            "record_id": "raw-1",
        }
    ]
