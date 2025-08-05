from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .comparison_models import ComparisonScope
from .performance_trend_models import MetricTrendSummary


@dataclass(frozen=True)
class RegressionRuleSet:
    """Rule thresholds used by the minimal V2 regression judge."""

    version: str = "v1"
    min_side_issue_groups: int = 1
    significant_occurrence_delta: int = 1
    significant_affected_run_delta: int = 1
    significant_affected_device_delta: int = 1
    significant_affected_scenario_delta: int = 1
    min_side_metric_sessions: int = 1
    min_side_metric_samples: int = 1
    significant_metric_delta_ratio: float = 0.1

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "min_side_issue_groups": self.min_side_issue_groups,
            "significant_occurrence_delta": self.significant_occurrence_delta,
            "significant_affected_run_delta": self.significant_affected_run_delta,
            "significant_affected_device_delta": self.significant_affected_device_delta,
            "significant_affected_scenario_delta": self.significant_affected_scenario_delta,
            "min_side_metric_sessions": self.min_side_metric_sessions,
            "min_side_metric_samples": self.min_side_metric_samples,
            "significant_metric_delta_ratio": self.significant_metric_delta_ratio,
        }


@dataclass(frozen=True)
class RegressedIssue:
    """Issue-level regression judgment."""

    comparison_key: str
    title: str
    issue_type: str
    severity: str
    regression_result: str
    change_type: str
    reason: str
    occurrence_delta: int
    left_fingerprint: str = ""
    right_fingerprint: str = ""
    left_occurrence_count: int = 0
    right_occurrence_count: int = 0
    left_affected_run_count: int = 0
    right_affected_run_count: int = 0
    left_affected_device_count: int = 0
    right_affected_device_count: int = 0
    left_affected_scenario_count: int = 0
    right_affected_scenario_count: int = 0


@dataclass(frozen=True)
class RegressedMetric:
    """Metric-level regression judgment."""

    metric_key: str
    label: str
    unit: str
    higher_is_worse: bool
    regression_result: str
    change_type: str
    reason: str
    left_summary: MetricTrendSummary
    right_summary: MetricTrendSummary
    average_delta: float | None = None
    peak_delta: float | None = None
    p95_delta: float | None = None
    latest_delta: float | None = None


@dataclass(frozen=True)
class RegressionResult:
    """Minimal regression result built on top of one comparison result."""

    dimension: str
    left_scope: ComparisonScope
    right_scope: ComparisonScope
    base_filters: Mapping[str, Any] = field(default_factory=dict)
    rule_set: RegressionRuleSet = field(default_factory=RegressionRuleSet)
    overall_result: str = "insufficient_data"
    issue_result_summary: Mapping[str, int] = field(default_factory=dict)
    metric_result_summary: Mapping[str, Any] = field(default_factory=dict)
    summary: Mapping[str, Any] = field(default_factory=dict)
    reasons: Sequence[str] = field(default_factory=tuple)
    comparability_notes: Sequence[str] = field(default_factory=tuple)
    issues: Sequence[RegressedIssue] = field(default_factory=tuple)
    metrics: Sequence[RegressedMetric] = field(default_factory=tuple)
