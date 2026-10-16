from datetime import UTC, datetime, timedelta, timezone

import pytest

from funding_arb.domain.time import require_utc


def test_require_utc_accepts_aware_utc() -> None:
    value = datetime(2026, 9, 9, 4, 0, tzinfo=UTC)
    assert require_utc(value) is value


def test_require_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        require_utc(datetime(2026, 9, 9, 4, 0))


def test_require_utc_rejects_non_utc_datetime() -> None:
    value = datetime(2026, 9, 9, 13, 0, tzinfo=timezone(timedelta(hours=9)))
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        require_utc(value)
