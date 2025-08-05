from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from .enums import IssueType, SeverityLevel


@dataclass(frozen=True)
class IssueFingerprint:
    """Stable identifier used to aggregate similar issue events."""

    value: str
    rule_version: str = "v1"
    components: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IssueEventReference:
    """One concrete issue event that belongs to an aggregated issue group."""

    event_id: str
    run_id: str
    task_id: str
    task_name: str
    instance_id: str
    device_id: str
    package_name: str
    scenario_name: str
    issue_type: IssueType
    severity: SeverityLevel
    detected_at: datetime | None = None
    summary: str = ""
    report_path: str = ""
    execution_log_path: str = ""
    artifact_paths: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedIssue:
    """Grouped issue view used by V2 Top Issue and drilldown queries."""

    fingerprint: IssueFingerprint
    issue_type: IssueType
    title: str
    severity: SeverityLevel
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    occurrence_count: int
    affected_run_count: int
    affected_device_count: int
    affected_scenario_count: int
    affected_version_count: int
    affected_packages: Sequence[str] = field(default_factory=tuple)
    affected_devices: Sequence[str] = field(default_factory=tuple)
    affected_scenarios: Sequence[str] = field(default_factory=tuple)
    affected_versions: Sequence[str] = field(default_factory=tuple)
    sample_event_ids: Sequence[str] = field(default_factory=tuple)
    sample_events: Sequence[IssueEventReference] = field(default_factory=tuple)
    score: float = 0.0
    score_breakdown: Mapping[str, float] = field(default_factory=dict)
