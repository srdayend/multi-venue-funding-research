"""Replayable event-package manifest contracts."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from funding_arb.domain.time import require_utc

MetricValue = int | float | str | None


@dataclass(frozen=True)
class EventPackageManifest:
    package_id: str
    created_at: datetime
    capture_session_key: str
    git_commit: str
    schema_version: str
    config_sha256: str
    archive_object_key: str
    object_sha256: str
    object_bytes: int
    coverage_truncated: bool
    artifacts: tuple[str, ...]
    metrics: Mapping[str, MetricValue]
    event_window_start: datetime | None = None
    event_window_end: datetime | None = None
    venues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_utc(self.created_at)
        if self.object_bytes < 0:
            raise ValueError("object_bytes must be non-negative")
        if (self.event_window_start is None) != (self.event_window_end is None):
            raise ValueError("event window requires both start and end")
        if self.event_window_start is not None and self.event_window_end is not None:
            require_utc(self.event_window_start)
            require_utc(self.event_window_end)
            if self.event_window_start > self.event_window_end:
                raise ValueError("event window must be ordered")
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
        object.__setattr__(self, "venues", tuple(sorted(set(self.venues))))


def manifest_bytes(manifest: EventPackageManifest) -> bytes:
    """Serialize a manifest to canonical, deterministic UTF-8 JSON."""
    payload = {
        "package_id": manifest.package_id,
        "created_at": manifest.created_at.isoformat().replace("+00:00", "Z"),
        "capture_session_key": manifest.capture_session_key,
        "git_commit": manifest.git_commit,
        "schema_version": manifest.schema_version,
        "config_sha256": manifest.config_sha256,
        "archive_object_key": manifest.archive_object_key,
        "object_sha256": manifest.object_sha256,
        "object_bytes": manifest.object_bytes,
        "coverage_truncated": manifest.coverage_truncated,
        "artifacts": manifest.artifacts,
        "metrics": dict(manifest.metrics),
    }
    if manifest.event_window_start is not None and manifest.event_window_end is not None:
        payload["event_window_start"] = manifest.event_window_start.isoformat().replace(
            "+00:00", "Z"
        )
        payload["event_window_end"] = manifest.event_window_end.isoformat().replace("+00:00", "Z")
        payload["venues"] = manifest.venues
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
