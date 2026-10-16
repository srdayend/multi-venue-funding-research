import json
from datetime import UTC, datetime

from funding_arb.domain.event_package import EventPackageManifest, manifest_bytes


def test_manifest_bytes_are_deterministic_and_canonical() -> None:
    manifest = EventPackageManifest(
        package_id="event-001",
        created_at=datetime(2026, 9, 11, 1, 2, 3, tzinfo=UTC),
        capture_session_key="BTC-20260911",
        git_commit="abc123",
        schema_version="1",
        config_sha256="c" * 64,
        archive_object_key="events/event-001.tar.gz",
        object_sha256="a" * 64,
        object_bytes=42,
        coverage_truncated=False,
        artifacts=("settlements.parquet", "raw/checkpoint.json"),
        metrics={"requests": 4, "note": None, "bytes": 42},
    )

    first = manifest_bytes(manifest)
    second = manifest_bytes(manifest)

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first) == {
        "archive_object_key": "events/event-001.tar.gz",
        "artifacts": ["settlements.parquet", "raw/checkpoint.json"],
        "capture_session_key": "BTC-20260911",
        "config_sha256": "c" * 64,
        "coverage_truncated": False,
        "created_at": "2026-09-11T01:02:03Z",
        "git_commit": "abc123",
        "metrics": {"bytes": 42, "note": None, "requests": 4},
        "object_bytes": 42,
        "object_sha256": "a" * 64,
        "package_id": "event-001",
        "schema_version": "1",
    }
