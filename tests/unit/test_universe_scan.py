from datetime import UTC, datetime
from decimal import Decimal

import pytest

from funding_arb.domain.enums import FundingStateKind, InstrumentType, Venue
from funding_arb.domain.identifiers import InstrumentId
from funding_arb.domain.observations import (
    FundingStateObservation,
    ObservationProvenance,
    ObservationRawRef,
    ObservationTransport,
)
from funding_arb.domain.provenance import RawRecordRef
from funding_arb.domain.universe_scan import ScanInstrumentState, UniverseScanSnapshot

NOW = datetime(2026, 9, 11, 1, tzinfo=UTC)
INSTRUMENT = InstrumentId(Venue.BINANCE, "DOGEUSDT", InstrumentType.LINEAR_PERPETUAL)


def _funding() -> FundingStateObservation:
    return FundingStateObservation(
        Venue.BINANCE,
        INSTRUMENT,
        datetime(2026, 9, 11, 8, tzinfo=UTC),
        Decimal("0.0012"),
        FundingStateKind.INDICATIVE,
        ObservationProvenance(
            ObservationTransport.REST,
            None,
            NOW,
            ObservationRawRef("scan-1", "raw/scan.json.gz", 0, "a" * 64),
        ),
        "source_field:nextFundingTime",
    )


def test_universe_snapshot_is_immutable_and_preserves_scan_cost_lineage() -> None:
    """Catches scan results losing exact bulk-response lineage or request accounting."""
    state = ScanInstrumentState(INSTRUMENT, NOW, _funding(), True)
    snapshot = UniverseScanSnapshot(
        Venue.BINANCE,
        NOW,
        (state,),
        RawRecordRef("scan-1", "raw/scan.json.gz", "a" * 64),
        request_weight=10,
        attempts=1,
        payload_bytes=123,
    )

    assert snapshot.states == (state,)
    assert snapshot.request_weight == 10
    with pytest.raises(AttributeError):
        snapshot.payload_bytes = 0  # type: ignore[misc]


@pytest.mark.parametrize("field", ["request_weight", "attempts", "payload_bytes"])
def test_universe_snapshot_rejects_invalid_cost_accounting(field: str) -> None:
    """Catches negative costs or a zero-attempt response entering scan evidence."""
    values = {"request_weight": 10, "attempts": 1, "payload_bytes": 123}
    values[field] = 0 if field == "attempts" else -1
    with pytest.raises(ValueError, match=field):
        UniverseScanSnapshot(
            Venue.BINANCE,
            NOW,
            (ScanInstrumentState(INSTRUMENT, NOW, _funding(), True),),
            RawRecordRef("scan-1", "raw/scan.json.gz", "a" * 64),
            **values,
        )
