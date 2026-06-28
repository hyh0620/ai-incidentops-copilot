from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_isoformat(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def elapsed_hours(start: datetime, end: datetime) -> float:
    return (ensure_utc(end) - ensure_utc(start)).total_seconds() / 3600
