from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from funding_arb.domain.provenance import DatasetManifest, FundingCoverage, RawRecordRef

REQUESTED_START = datetime(2026, 8, 1, tzinfo=UTC)
REQUESTED_END = datetime(2026, 8, 31, 23, 59, 59, 999000, tzinfo=UTC)


def _manifest(**changes: object) -> DatasetManifest:
    values: dict[str, object] = {
        "dataset_id": "dataset-001",
        "created_at": datetime(2026, 9, 10, tzinfo=UTC),
        "git_commit": "c61841a9f5156fdf187cac978aeccf90fed2814a",
        "schema_version": "1",
        "collection_config_sha256": "a" * 64,
        "mapping_config_sha256": "b" * 64,
        "raw_record_refs": (
            RawRecordRef("raw-b", "raw/binance/b.json", "d" * 64),
            RawRecordRef("raw-a", "raw/binance/a.json", "c" * 64),
            RawRecordRef("raw-a", "raw/binance/a.json", "c" * 64),
        ),
        "row_counts": {"funding": 2, "instruments": 1, "mappings": 1},
        "quarantine_counts": {"conflicting_duplicate": 1},
        "quality_finding_counts": {"error": 1, "warning": 2},
        "funding_coverage": {
            "binance:BTCUSDT:linear_perpetual": FundingCoverage(
                requested_start=REQUESTED_START,
                requested_end=REQUESTED_END,
                observed_start=REQUESTED_START,
                observed_end=REQUESTED_END,
                observed_row_count=2,
            )
        },
        "canonical_output_sha256": {
            "funding.parquet": "e" * 64,
            "instruments.parquet": "f" * 64,
            "mappings.parquet": "0" * 64,
        },
    }
    values.update(changes)
    return DatasetManifest(**values)  # type: ignore[arg-type]


def test_dataset_manifest_is_frozen_and_canonicalizes_audit_collections() -> None:
    manifest = _manifest()

    assert [reference.record_id for reference in manifest.raw_record_refs] == [
        "raw-a",
        "raw-b",
    ]
    assert list(manifest.row_counts) == ["funding", "instruments", "mappings"]
    with pytest.raises(FrozenInstanceError):
        manifest.dataset_id = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        manifest.row_counts["funding"] = 3  # type: ignore[index]
    with pytest.raises(TypeError):
        manifest.funding_coverage["new"] = manifest.funding_coverage[  # type: ignore[index]
            "binance:BTCUSDT:linear_perpetual"
        ]


def test_dataset_manifest_rejects_conflicting_refs_for_one_record_id() -> None:
    with pytest.raises(ValueError, match=r"conflicting raw record refs.*raw-a"):
        _manifest(
            raw_record_refs=(
                RawRecordRef("raw-a", "raw/binance/a.json", "c" * 64),
                RawRecordRef("raw-a", "raw/binance/other.json", "d" * 64),
            )
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"created_at": datetime(2026, 9, 10)}, "timezone-aware UTC"),
        ({"collection_config_sha256": "not-a-hash"}, "collection_config_sha256"),
        ({"row_counts": {"funding": -1}}, "row_counts"),
        ({"quality_finding_counts": {"error": True}}, "quality_finding_counts"),
    ],
)
def test_dataset_manifest_rejects_invalid_reproducibility_inputs(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        _manifest(**changes)


def test_raw_record_ref_requires_a_valid_content_hash() -> None:
    with pytest.raises(ValueError, match="body_sha256"):
        RawRecordRef("raw-a", "raw/binance/a.json", "not-a-hash")


def test_funding_coverage_accepts_zero_or_bounded_positive_observations() -> None:
    empty = FundingCoverage(
        requested_start=REQUESTED_START,
        requested_end=REQUESTED_END,
        observed_start=None,
        observed_end=None,
        observed_row_count=0,
    )
    observed = FundingCoverage(
        requested_start=REQUESTED_START,
        requested_end=REQUESTED_END,
        observed_start=REQUESTED_START + timedelta(hours=8),
        observed_end=REQUESTED_END - timedelta(hours=8),
        observed_row_count=3,
    )

    assert empty.observed_start is None
    assert observed.observed_row_count == 3


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"requested_start": datetime(2026, 8, 1)}, "timezone-aware UTC"),
        ({"requested_start": REQUESTED_END, "requested_end": REQUESTED_START}, "range"),
        ({"observed_row_count": -1}, "non-negative"),
        (
            {"observed_row_count": 0, "observed_start": REQUESTED_START},
            "zero observations",
        ),
        (
            {"observed_row_count": 1, "observed_start": None, "observed_end": None},
            "positive observations",
        ),
        (
            {"observed_start": REQUESTED_START - timedelta(milliseconds=1)},
            "requested range",
        ),
        (
            {
                "observed_start": REQUESTED_END,
                "observed_end": REQUESTED_START,
            },
            "ordered",
        ),
    ],
)
def test_funding_coverage_rejects_invalid_ranges(
    changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "requested_start": REQUESTED_START,
        "requested_end": REQUESTED_END,
        "observed_start": REQUESTED_START,
        "observed_end": REQUESTED_END,
        "observed_row_count": 2,
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError), match=message):
        FundingCoverage(**values)  # type: ignore[arg-type]
