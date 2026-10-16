"""Filesystem retention for canonical candidates excluded by quality findings."""

import hashlib
import json
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from funding_arb.domain.provenance import RawRecordRef
from funding_arb.domain.quality import QualityFinding
from funding_arb.errors import StorageError


class QuarantineStore:
    """Write content-addressed, auditable quarantine evidence under one dataset/run."""

    def __init__(self, root: Path, dataset_or_run_id: str) -> None:
        _require_safe_path_component(dataset_or_run_id)
        self._directory = root / dataset_or_run_id

    def write(
        self,
        record: object,
        findings: list[QualityFinding],
        raw_record_refs: list[RawRecordRef],
    ) -> str:
        document = {
            "canonical_candidate": _serialize(record),
            "findings": [_serialize(finding) for finding in findings],
            "raw_record_refs": [_serialize(reference) for reference in raw_record_refs],
        }
        payload = (
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        target = self._directory / f"{digest}.json"
        self._directory.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8", newline="\n") as quarantine_file:
                quarantine_file.write(payload)
        except FileExistsError:
            existing = target.read_text(encoding="utf-8")
            if existing != payload:
                raise StorageError(f"conflicting quarantine evidence at {target}") from None
        return str(target)


def _serialize(value: object) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("quarantine timestamps must be timezone-aware UTC")
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    raise TypeError(f"cannot serialize quarantine value of type {type(value).__name__}")


def _require_safe_path_component(value: str) -> None:
    if value in {"", ".", ".."} or "/" in value or "\\" in value:
        raise ValueError("dataset_or_run_id must be a single path component")
    if value.endswith((".", " ")) or ":" in value:
        raise ValueError("dataset_or_run_id cannot be represented exactly")
