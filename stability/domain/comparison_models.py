from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .analysis_models import AggregatedIssue, IssueEventReference


@dataclass(frozen=True)
class ComparisonScope:
    """One side of a comparison query."""

    dimension: str
    value: str
    label: str
    filters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComparedIssue:
    """Issue-level delta between two comparison scopes."""

    comparison_key: str
    title: str
    issue_type: str
    severity: str
    change_type: str
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
    left_sample_event_ids: Sequence[str] = field(default_factory=tuple)
    right_sample_event_ids: Sequence[str] = field(default_factory=tuple)
    left_sample_events: Sequence[IssueEventReference] = field(default_factory=tuple)
    right_sample_events: Sequence[IssueEventReference] = field(default_factory=tuple)
    left_issue: AggregatedIssue | None = None
    right_issue: AggregatedIssue | None = None


@dataclass(frozen=True)
class ComparisonResult:
    """Minimal multi-scope issue comparison result."""

    dimension: str
    left_scope: ComparisonScope
    right_scope: ComparisonScope
    base_filters: Mapping[str, Any] = field(default_factory=dict)
    sample_summary: Mapping[str, Any] = field(default_factory=dict)
    issue_change_summary: Mapping[str, int] = field(default_factory=dict)
    metric_change_summary: Mapping[str, Any] = field(default_factory=dict)
    comparability_notes: Sequence[str] = field(default_factory=tuple)
    issues: Sequence[ComparedIssue] = field(default_factory=tuple)
