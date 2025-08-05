from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from .comparison_models import ComparisonScope
from .quality_gate_models import QualityGateRiskItem


@dataclass(frozen=True)
class MetricTrendSummary:
    """Aggregated statistics for one metric within one comparison side."""

    metric_key: str
    label: str
    unit: str
    sample_count: int = 0
    session_count: int = 0
    average: float | None = None
    peak: float | None = None
    p95: float | None = None
    latest: float | None = None


@dataclass(frozen=True)
class ComparedMetricTrend:
    """One metric trend comparison across two scopes."""

    metric_key: str
    label: str
    unit: str
    higher_is_worse: bool
    left_summary: MetricTrendSummary
    right_summary: MetricTrendSummary
    average_delta: float | None = None
    peak_delta: float | None = None
    p95_delta: float | None = None
    latest_delta: float | None = None
    change_type: str = "insufficient_data"


@dataclass(frozen=True)
class PerformanceRiskThresholdValues:
    """Threshold values used by performance trend risk detection."""

    oom_memory_pss_peak_mb: float = 1536.0
    oom_memory_pss_p95_mb: float = 1024.0
    memory_growth_min_delta_mb: float = 128.0
    memory_growth_min_ratio: float = 0.2
    frame_time_p95_delta_ratio: float = 0.2
    frame_time_p95_delta_ms: float = 8.0
    fps_drop_ratio: float = 0.15

    def with_override(self, override: "PerformanceRiskThresholdOverride") -> "PerformanceRiskThresholdValues":
        values = {
            field_name: getattr(override, field_name)
            for field_name in self.__dataclass_fields__
            if getattr(override, field_name) is not None
        }
        return replace(self, **values)

    def as_details(self) -> dict[str, float]:
        return {
            "oom_memory_pss_peak_mb": self.oom_memory_pss_peak_mb,
            "oom_memory_pss_p95_mb": self.oom_memory_pss_p95_mb,
            "memory_growth_min_delta_mb": self.memory_growth_min_delta_mb,
            "memory_growth_min_ratio": self.memory_growth_min_ratio,
            "frame_time_p95_delta_ratio": self.frame_time_p95_delta_ratio,
            "frame_time_p95_delta_ms": self.frame_time_p95_delta_ms,
            "fps_drop_ratio": self.fps_drop_ratio,
        }


@dataclass(frozen=True)
class PerformanceRiskThresholdOverride:
    """Scoped override for performance risk thresholds.

    Empty scope fields are ignored; every non-empty scope field must match the
    comparison context for the override to apply.
    """

    package_name: str = ""
    device_id: str = ""
    scenario: str = ""
    template_type: str = ""
    source: str = "override"
    oom_memory_pss_peak_mb: float | None = None
    oom_memory_pss_p95_mb: float | None = None
    memory_growth_min_delta_mb: float | None = None
    memory_growth_min_ratio: float | None = None
    frame_time_p95_delta_ratio: float | None = None
    frame_time_p95_delta_ms: float | None = None
    fps_drop_ratio: float | None = None

    def matched_scope(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "package_name": self.package_name,
                "device_id": self.device_id,
                "scenario": self.scenario,
                "template_type": self.template_type,
            }.items()
            if value
        }

    def matches(self, context: Mapping[str, str]) -> bool:
        return all(context.get(key, "") == value for key, value in self.matched_scope().items())

    def specificity(self) -> int:
        return len(self.matched_scope())


@dataclass(frozen=True)
class PerformanceRiskThresholdMatch:
    values: PerformanceRiskThresholdValues
    threshold_source: str = "default"
    matched_scope: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PerformanceRiskThresholdConfig:
    """Default performance risk thresholds plus optional scoped overrides."""

    defaults: PerformanceRiskThresholdValues = field(default_factory=PerformanceRiskThresholdValues)
    overrides: Sequence[PerformanceRiskThresholdOverride] = field(default_factory=tuple)

    def resolve(self, context: Mapping[str, str]) -> PerformanceRiskThresholdMatch:
        matches = [
            (index, override)
            for index, override in enumerate(self.overrides)
            if override.matches(context)
        ]
        if not matches:
            return PerformanceRiskThresholdMatch(values=self.defaults)
        _, override = max(matches, key=lambda item: (item[1].specificity(), item[0]))
        return PerformanceRiskThresholdMatch(
            values=self.defaults.with_override(override),
            threshold_source=override.source or "override",
            matched_scope=override.matched_scope(),
        )


@dataclass(frozen=True)
class PerformanceTrendComparison:
    """Minimal V2 performance trend comparison result."""

    dimension: str
    left_scope: ComparisonScope
    right_scope: ComparisonScope
    base_filters: Mapping[str, Any] = field(default_factory=dict)
    sample_summary: Mapping[str, Any] = field(default_factory=dict)
    metric_change_summary: Mapping[str, Any] = field(default_factory=dict)
    comparability_notes: Sequence[str] = field(default_factory=tuple)
    performance_risk_items: Sequence[QualityGateRiskItem] = field(default_factory=tuple)
    metrics: Sequence[ComparedMetricTrend] = field(default_factory=tuple)
