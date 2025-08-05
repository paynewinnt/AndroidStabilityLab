from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Sequence

from stability.domain import Device
from stability.time_utils import format_beijing_datetime


def health_metadata(device: Device) -> Dict[str, Any]:
    """Return the mutable health metadata bucket for one device."""
    raw = device.metadata.get("automation_health")
    if isinstance(raw, dict):
        return raw
    health: Dict[str, Any] = {}
    device.metadata["automation_health"] = health
    return health


def isoformat_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return format_beijing_datetime(value)


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_strings(values: Sequence[Any] | Any) -> List[str]:
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",")]
    if not isinstance(values, Sequence):
        return []
    return sorted({str(item).strip() for item in values if str(item).strip()})
