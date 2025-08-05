from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from stability.domain import (
    PerformanceRiskThresholdConfig,
    PerformanceRiskThresholdOverride,
    PerformanceRiskThresholdValues,
)


class FileBackedPerformanceRiskThresholdProvider:
    """Load performance risk thresholds from a local JSON file."""

    _VALUE_FIELDS = tuple(PerformanceRiskThresholdValues().__dataclass_fields__.keys())

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> PerformanceRiskThresholdConfig:
        if not self._path.exists():
            return PerformanceRiskThresholdConfig()
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return PerformanceRiskThresholdConfig()
        if not isinstance(payload, dict):
            return PerformanceRiskThresholdConfig()
        defaults = self._threshold_values(payload.get("defaults"))
        overrides = tuple(
            override
            for item in payload.get("overrides", []) or []
            if (override := self._threshold_override(item)) is not None
        )
        return PerformanceRiskThresholdConfig(defaults=defaults, overrides=overrides)

    @classmethod
    def _threshold_values(cls, raw: Any) -> PerformanceRiskThresholdValues:
        values: dict[str, float] = {}
        if isinstance(raw, Mapping):
            for field_name in cls._VALUE_FIELDS:
                parsed = cls._optional_float(raw.get(field_name))
                if parsed is not None:
                    values[field_name] = parsed
        return PerformanceRiskThresholdValues(**values)

    @classmethod
    def _threshold_override(cls, raw: Any) -> PerformanceRiskThresholdOverride | None:
        if not isinstance(raw, Mapping):
            return None
        values: dict[str, Any] = {
            "package_name": str(raw.get("package_name", "") or ""),
            "device_id": str(raw.get("device_id", "") or ""),
            "scenario": str(raw.get("scenario", "") or ""),
            "template_type": str(raw.get("template_type", "") or ""),
            "source": str(raw.get("source", "") or "performance_thresholds.local"),
        }
        for field_name in cls._VALUE_FIELDS:
            values[field_name] = cls._optional_float(raw.get(field_name))
        if not any(values.get(key) for key in ("package_name", "device_id", "scenario", "template_type")):
            return None
        return PerformanceRiskThresholdOverride(**values)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
