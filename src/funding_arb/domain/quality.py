"""Stable, machine-readable results from data-quality validation."""

from dataclasses import dataclass
from enum import StrEnum


class QualitySeverity(StrEnum):
    """The research-eligibility impact of a quality finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class QualityStatus(StrEnum):
    """Stable default-research eligibility derived from quality findings."""

    VALID = "valid"
    INVALID = "invalid"


class QualityReasonCode(StrEnum):
    """Stable codes; consumers must use these instead of parsing messages."""

    AMBIGUOUS_ASSET_MAPPING = "ambiguous_asset_mapping"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    INVALID_TIMESTAMP = "invalid_timestamp"
    LARGE_FUNDING_RATE = "large_funding_rate"
    UNKNOWN_FUNDING_TYPE = "unknown_funding_type"
    UNKNOWN_INSTRUMENT = "unknown_instrument"
    SCHEMA_SEMANTIC_MISMATCH = "schema_semantic_mismatch"


@dataclass(frozen=True)
class QualityFinding:
    severity: QualitySeverity
    code: QualityReasonCode
    record_id: str
    message: str

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id cannot be blank")
        if not self.message:
            raise ValueError("message cannot be blank")


def derive_quality_status(findings: tuple[QualityFinding, ...]) -> QualityStatus:
    """An ERROR makes a record invalid; WARNING and INFO remain research-eligible."""
    if any(finding.severity is QualitySeverity.ERROR for finding in findings):
        return QualityStatus.INVALID
    return QualityStatus.VALID


@dataclass(frozen=True)
class QualityCheckedRecord[RecordT]:
    """A canonical candidate paired with every finding used to derive eligibility."""

    record: RecordT
    findings: tuple[QualityFinding, ...] = ()

    @property
    def quality_status(self) -> QualityStatus:
        return derive_quality_status(self.findings)
