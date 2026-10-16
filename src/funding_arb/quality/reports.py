"""Deterministic aggregation of explicit Milestone 1 quality evidence."""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from funding_arb.domain.enums import MappingStatus, Venue
from funding_arb.domain.funding import FundingSettlement
from funding_arb.domain.instruments import Instrument
from funding_arb.domain.provenance import DatasetManifest, FundingCoverage
from funding_arb.domain.quality import QualityCheckedRecord, QualityStatus
from funding_arb.mapping.registry import InstrumentMapping


@dataclass(frozen=True)
class DatasetQualityReport:
    """Separate record, mapping, endpoint-coverage, and conflict evidence."""

    dataset_manifest_id: str
    schema_versions: Mapping[str, str]
    instrument_counts_by_venue: Mapping[str, int]
    mapping_status_counts: Mapping[str, int]
    funding_row_count: int
    funding_row_counts_by_venue: Mapping[str, int]
    instrument_quality_status_counts: Mapping[str, int]
    funding_quality_status_counts: Mapping[str, int]
    funding_coverage: Mapping[str, FundingCoverage]
    identical_duplicate_count: int
    conflicting_duplicate_count: int
    quarantine_reason_counts: Mapping[str, int]
    quality_finding_counts: Mapping[str, int]


def build_quality_report(
    *,
    manifest: DatasetManifest,
    instruments: Iterable[QualityCheckedRecord[Instrument]],
    mappings: Iterable[InstrumentMapping],
    funding: Iterable[QualityCheckedRecord[FundingSettlement]],
    identical_duplicate_count: int,
    conflicting_duplicate_count: int,
) -> DatasetQualityReport:
    """Aggregate canonical evidence without collecting data or claiming completeness."""
    instrument_records = list(instruments)
    mapping_records = list(mappings)
    funding_records = list(funding)
    _require_manifest_count(manifest, "instruments", len(instrument_records))
    _require_manifest_count(manifest, "mappings", len(mapping_records))
    _require_manifest_count(manifest, "funding", len(funding_records))
    _require_non_negative("identical_duplicate_count", identical_duplicate_count)
    _require_non_negative("conflicting_duplicate_count", conflicting_duplicate_count)

    instrument_venues = Counter(item.record.id.venue.value for item in instrument_records)
    funding_venues = Counter(item.record.venue.value for item in funding_records)
    mapping_statuses = Counter(item.status.value for item in mapping_records)
    instrument_quality = Counter(item.quality_status.value for item in instrument_records)
    funding_quality = Counter(item.quality_status.value for item in funding_records)

    return DatasetQualityReport(
        dataset_manifest_id=manifest.dataset_id,
        schema_versions=_immutable_strings(
            {
                "funding": manifest.schema_version,
                "instruments": manifest.schema_version,
                "mappings": manifest.schema_version,
            }
        ),
        instrument_counts_by_venue=_enum_counts(Venue, instrument_venues),
        mapping_status_counts=_enum_counts(MappingStatus, mapping_statuses),
        funding_row_count=len(funding_records),
        funding_row_counts_by_venue=_enum_counts(Venue, funding_venues),
        instrument_quality_status_counts=_enum_counts(QualityStatus, instrument_quality),
        funding_quality_status_counts=_enum_counts(QualityStatus, funding_quality),
        funding_coverage=MappingProxyType(dict(manifest.funding_coverage)),
        identical_duplicate_count=identical_duplicate_count,
        conflicting_duplicate_count=conflicting_duplicate_count,
        quarantine_reason_counts=_immutable_counts(manifest.quarantine_counts),
        quality_finding_counts=_immutable_counts(manifest.quality_finding_counts),
    )


def _require_manifest_count(manifest: DatasetManifest, kind: str, actual: int) -> None:
    if manifest.row_counts.get(kind) != actual:
        raise ValueError(f"manifest {kind[:-1] if kind.endswith('s') else kind} row count mismatch")


def _require_non_negative(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _enum_counts(
    enum_type: type[Venue] | type[MappingStatus] | type[QualityStatus],
    counts: Counter[str],
) -> Mapping[str, int]:
    return MappingProxyType(
        {
            member.value: counts[member.value]
            for member in sorted(enum_type, key=lambda item: item.value)
        }
    )


def _immutable_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(values.items())))


def _immutable_strings(values: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(sorted(values.items())))
