"""Provenance models for unmodified external source evidence."""

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from funding_arb.domain.enums import Venue
from funding_arb.domain.time import require_utc

RequestParamValue = str | int | float | bool | None
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class RawResponseEnvelope:
    """One externally received response before any parsing or normalization."""

    record_id: str
    venue: Venue
    operation: str
    request_params: Mapping[str, RequestParamValue]
    retrieved_at: datetime
    status_code: int
    response_headers: Mapping[str, str]
    body_text: str
    attempts: int = 1
    body_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_blank("record_id", self.record_id)
        _require_non_blank("operation", self.operation)
        require_utc(self.retrieved_at)
        if not isinstance(self.status_code, int) or isinstance(self.status_code, bool):
            raise TypeError("status_code must be an int")
        if not isinstance(self.body_text, str):
            raise TypeError("body_text must be a str")
        if not isinstance(self.attempts, int) or isinstance(self.attempts, bool):
            raise TypeError("attempts must be an int")
        if self.attempts <= 0:
            raise ValueError("attempts must be positive")
        object.__setattr__(self, "request_params", MappingProxyType(dict(self.request_params)))
        object.__setattr__(self, "response_headers", MappingProxyType(dict(self.response_headers)))
        object.__setattr__(
            self,
            "body_sha256",
            hashlib.sha256(self.body_text.encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class RawRecordRef:
    """Stable reference to an append-only archived raw response."""

    record_id: str
    path: str
    body_sha256: str

    def __post_init__(self) -> None:
        _require_non_blank("record_id", self.record_id)
        _require_non_blank("path", self.path)
        _require_sha256("body_sha256", self.body_sha256)


@dataclass(frozen=True)
class FundingCoverage:
    """Endpoint-observed funding bounds for one explicitly requested interval."""

    requested_start: datetime
    requested_end: datetime
    observed_start: datetime | None
    observed_end: datetime | None
    observed_row_count: int

    def __post_init__(self) -> None:
        require_utc(self.requested_start)
        require_utc(self.requested_end)
        if self.requested_start > self.requested_end:
            raise ValueError("requested funding coverage range is invalid")
        if not isinstance(self.observed_row_count, int) or isinstance(
            self.observed_row_count, bool
        ):
            raise TypeError("observed_row_count must be an int")
        if self.observed_row_count < 0:
            raise ValueError("observed_row_count must be non-negative")
        if self.observed_row_count == 0:
            if self.observed_start is not None or self.observed_end is not None:
                raise ValueError("zero observations require no observed bounds")
            return
        if self.observed_start is None or self.observed_end is None:
            raise ValueError("positive observations require both observed bounds")
        require_utc(self.observed_start)
        require_utc(self.observed_end)
        if self.observed_start > self.observed_end:
            raise ValueError("observed funding coverage bounds must be ordered")
        if self.observed_start < self.requested_start or self.observed_end > self.requested_end:
            raise ValueError("observed funding coverage bounds must lie in requested range")


@dataclass(frozen=True)
class DatasetManifest:
    """Pure reproducibility and audit evidence for one canonical dataset build."""

    dataset_id: str
    created_at: datetime
    git_commit: str
    schema_version: str
    collection_config_sha256: str
    mapping_config_sha256: str
    raw_record_refs: tuple[RawRecordRef, ...]
    row_counts: Mapping[str, int]
    quarantine_counts: Mapping[str, int]
    quality_finding_counts: Mapping[str, int]
    funding_coverage: Mapping[str, FundingCoverage]
    canonical_output_sha256: Mapping[str, str]

    def __post_init__(self) -> None:
        _require_non_blank("dataset_id", self.dataset_id)
        require_utc(self.created_at)
        _require_non_blank("git_commit", self.git_commit)
        _require_non_blank("schema_version", self.schema_version)
        _require_sha256("collection_config_sha256", self.collection_config_sha256)
        _require_sha256("mapping_config_sha256", self.mapping_config_sha256)
        object.__setattr__(
            self,
            "raw_record_refs",
            canonical_raw_record_refs(self.raw_record_refs),
        )
        object.__setattr__(self, "row_counts", _immutable_counts("row_counts", self.row_counts))
        object.__setattr__(
            self,
            "quarantine_counts",
            _immutable_counts("quarantine_counts", self.quarantine_counts),
        )
        object.__setattr__(
            self,
            "quality_finding_counts",
            _immutable_counts("quality_finding_counts", self.quality_finding_counts),
        )
        object.__setattr__(
            self,
            "funding_coverage",
            canonical_funding_coverage(self.funding_coverage),
        )
        object.__setattr__(
            self,
            "canonical_output_sha256",
            _immutable_hashes("canonical_output_sha256", self.canonical_output_sha256),
        )


def canonical_raw_record_refs(
    references: Iterable[RawRecordRef],
) -> tuple[RawRecordRef, ...]:
    """Return stable unique lineage while rejecting one ID pointing to different evidence."""
    by_record_id: dict[str, RawRecordRef] = {}
    for reference in references:
        if not isinstance(reference, RawRecordRef):
            raise TypeError("raw_record_refs must contain RawRecordRef values")
        existing = by_record_id.get(reference.record_id)
        if existing is not None and existing != reference:
            raise ValueError(f"conflicting raw record refs for {reference.record_id}")
        by_record_id[reference.record_id] = reference
    return tuple(by_record_id[key] for key in sorted(by_record_id))


def canonical_funding_coverage(
    coverage: Mapping[str, FundingCoverage],
) -> Mapping[str, FundingCoverage]:
    """Return stable immutable endpoint coverage keyed by canonical instrument identity."""
    result: dict[str, FundingCoverage] = {}
    for instrument_key, value in sorted(coverage.items()):
        _require_non_blank("funding_coverage key", instrument_key)
        if not isinstance(value, FundingCoverage):
            raise TypeError("funding_coverage values must be FundingCoverage")
        result[instrument_key] = value
    return MappingProxyType(result)


def _require_non_blank(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value:
        raise ValueError(f"{name} cannot be blank")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _immutable_counts(name: str, values: Mapping[str, int]) -> Mapping[str, int]:
    result: dict[str, int] = {}
    for key, value in sorted(values.items()):
        _require_non_blank(f"{name} key", key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name}[{key!r}] must be an int")
        if value < 0:
            raise ValueError(f"{name}[{key!r}] cannot be negative")
        result[key] = value
    return MappingProxyType(result)


def _immutable_hashes(name: str, values: Mapping[str, str]) -> Mapping[str, str]:
    result: dict[str, str] = {}
    for key, value in sorted(values.items()):
        _require_non_blank(f"{name} key", key)
        _require_sha256(f"{name}[{key!r}]", value)
        result[key] = value
    return MappingProxyType(result)
