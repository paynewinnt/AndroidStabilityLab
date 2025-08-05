from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .analysis_models import IssueEventReference


@dataclass(frozen=True)
class RuleReplaySide:
    """Describe one side of a rule replay comparison."""

    path: str
    fingerprint_rule_version: str


@dataclass(frozen=True)
class ReplayedIssueFamily:
    """One issue-family comparison row across two rule configurations."""

    comparison_key: str
    issue_type: str
    package_name: str
    process_name: str
    scenario_name: str
    title: str
    change_type: str
    left_group_count: int
    right_group_count: int
    left_occurrence_count: int
    right_occurrence_count: int
    left_fingerprints: Sequence[str] = field(default_factory=tuple)
    right_fingerprints: Sequence[str] = field(default_factory=tuple)
    left_sample_event_ids: Sequence[str] = field(default_factory=tuple)
    right_sample_event_ids: Sequence[str] = field(default_factory=tuple)
    left_sample_events: Sequence[IssueEventReference] = field(default_factory=tuple)
    right_sample_events: Sequence[IssueEventReference] = field(default_factory=tuple)
    notes: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuleReplayResult:
    """Structured replay result for one pair of rule configurations."""

    baseline: RuleReplaySide
    candidate: RuleReplaySide
    filters: Mapping[str, object]
    family_count: int
    changed_family_count: int
    change_summary: Mapping[str, int]
    families: Sequence[ReplayedIssueFamily] = field(default_factory=tuple)
