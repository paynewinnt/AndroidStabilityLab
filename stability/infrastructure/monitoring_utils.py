"""Shared helpers for monitoring adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from stability.time_utils import utcnow


def safe_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric


def tail_text(value: Any, *, limit: int = 400) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[-limit:]


def mapping_number(payload: Any, *keys: str) -> float | None:
    if not isinstance(payload, Mapping):
        return None
    normalized_payload = {
        str(key or "").strip().replace(" ", "").replace("_", "").replace("-", "").lower(): value
        for key, value in payload.items()
    }
    for key in keys:
        numeric = safe_float(payload.get(key))
        if numeric is not None:
            return numeric
        numeric = safe_float(
            normalized_payload.get(
                str(key or "").strip().replace(" ", "").replace("_", "").replace("-", "").lower()
            )
        )
        if numeric is not None:
            return numeric
    return None


def metric_enabled(metrics: Mapping[str, bool], *keys: str) -> bool:
    if not metrics:
        return True
    if any(key in metrics for key in keys):
        return any(bool(metrics.get(key, False)) for key in keys)
    return True


def deep_merge_mapping(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {str(key): value for key, value in dict(base).items()}
    for key, value in dict(override).items():
        existing = merged.get(str(key))
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[str(key)] = deep_merge_mapping(existing, value)
        else:
            merged[str(key)] = value
    return merged


# Backward-compatible private helper aliases for modules that mirrored the
# original monitoring_adapter.py names.
_utcnow = utcnow
_safe_float = safe_float
_tail_text = tail_text
_mapping_number = mapping_number
_metric_enabled = metric_enabled
_deep_merge_mapping = deep_merge_mapping
