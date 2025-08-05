from __future__ import annotations

from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo

_DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")
_DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def utcnow() -> datetime:
    """Return a naive UTC datetime without using deprecated datetime.utcnow()."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_beijing_string() -> str:
    """Return the canonical user-facing Beijing time string."""

    return format_beijing_datetime(utcnow()) or ""


def coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or _DATE_ONLY_PATTERN.fullmatch(raw):
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_beijing_datetime(value: object) -> str | None:
    parsed = coerce_datetime(value)
    if parsed is None:
        return None
    aware = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    return aware.astimezone(_BEIJING_TZ).strftime(_DISPLAY_FORMAT)


def format_beijing_datetime_or_original(value: object) -> str | None:
    formatted = format_beijing_datetime(value)
    if formatted is not None:
        return formatted
    if isinstance(value, str):
        raw = value.strip()
        return raw or None
    return None


def serialize_datetime(value: object) -> str | None:
    """Serialize a datetime-like value for Web/CLI/API output."""

    return format_beijing_datetime(value)


def serialize_datetime_or_original(value: object) -> str | None:
    """Serialize datetime-like values and preserve non-empty non-date strings."""

    return format_beijing_datetime_or_original(value)
