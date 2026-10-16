from datetime import UTC, datetime
from decimal import Decimal

import pytest

from funding_arb.domain.enums import (
    FundingStateKind,
    InstrumentType,
    ReferencePriceKind,
    Venue,
)
from funding_arb.domain.identifiers import InstrumentId
from funding_arb.domain.observations import (
    BestQuoteObservation,
    FundingStateObservation,
    ObservationProvenance,
    ObservationRawRef,
    ObservationTransport,
    PublicTradeObservation,
    ReferencePriceObservation,
)

NOW = datetime(2026, 9, 10, 1, 2, 3, tzinfo=UTC)
TARGET = datetime(2026, 9, 10, 8, tzinfo=UTC)
INSTRUMENT = InstrumentId(Venue.BINANCE, "BTCUSDT", InstrumentType.LINEAR_PERPETUAL)
RAW_REF = ObservationRawRef("chunk-1", "raw/binance/chunk-1.ndjson.gz", 4, "a" * 64)
PROVENANCE = ObservationProvenance(
    ObservationTransport.WEBSOCKET, NOW, NOW, RAW_REF, "session-1", 11, 10
)


def test_rest_provenance_needs_no_fake_stream_session() -> None:
    """Catches REST evidence being forced to fabricate WebSocket lineage."""
    provenance = ObservationProvenance(
        transport=ObservationTransport.REST,
        source_event_at=None,
        received_at=NOW,
        raw_ref=ObservationRawRef("scan-1", "raw/scan.json.gz", 0, "a" * 64),
    )

    assert provenance.session_id is None


def test_websocket_provenance_requires_session_id() -> None:
    """Catches WebSocket evidence losing the session needed for continuity audit."""
    with pytest.raises(ValueError, match="session_id"):
        ObservationProvenance(
            transport=ObservationTransport.WEBSOCKET,
            source_event_at=None,
            received_at=NOW,
            raw_ref=ObservationRawRef("chunk-1", "raw/chunk.gz", 0, "a" * 64),
        )


def test_distinct_observation_families_preserve_decision_time_and_lineage() -> None:
    """Catches collapsing executable, reference, trade, and funding state into one blob."""
    funding = FundingStateObservation(
        Venue.BINANCE,
        INSTRUMENT,
        TARGET,
        Decimal("0.0001"),
        FundingStateKind.INDICATIVE,
        PROVENANCE,
        "source_field:T",
    )
    quote = BestQuoteObservation(
        Venue.BINANCE,
        INSTRUMENT,
        Decimal("60000"),
        Decimal("1.25"),
        Decimal("60000.1"),
        Decimal("0.8"),
        "base_asset",
        PROVENANCE,
    )
    trade = PublicTradeObservation(
        Venue.BINANCE,
        INSTRUMENT,
        "trade-1",
        Decimal("60000.05"),
        Decimal("0.02"),
        None,
        None,
        "base_asset",
        PROVENANCE,
    )
    reference = ReferencePriceObservation(
        Venue.BINANCE,
        INSTRUMENT,
        ReferencePriceKind.MARK,
        Decimal("59999.9"),
        PROVENANCE,
    )

    assert funding.target_funding_time == TARGET
    assert quote.bid_price < quote.ask_price
    assert trade.maker_side is None
    assert reference.kind is ReferencePriceKind.MARK
    assert funding.provenance.received_at == NOW
    assert funding.provenance.raw_ref.item_index == 4


def test_observation_contracts_fail_closed_on_invalid_availability_and_economics() -> None:
    """Catches accepting naive receive times or non-executable quantities."""
    with pytest.raises(ValueError, match="UTC"):
        ObservationProvenance(
            ObservationTransport.WEBSOCKET,
            None,
            NOW.replace(tzinfo=None),
            RAW_REF,
            "session-1",
        )
    with pytest.raises(ValueError, match="positive"):
        BestQuoteObservation(
            Venue.BINANCE,
            INSTRUMENT,
            Decimal("60000"),
            Decimal("0"),
            Decimal("60001"),
            Decimal("1"),
            "base_asset",
            PROVENANCE,
        )
