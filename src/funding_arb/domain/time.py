from datetime import datetime, timedelta


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("canonical timestamps must be timezone-aware UTC")
    return value
