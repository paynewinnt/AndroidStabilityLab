from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RuleReplayGoldenCaseSummary:
    """Lightweight view of one golden sample case."""

    case_id: str
    description: str
    issue_type: str
    layer: str
    expectation: str
    include_unchanged: bool = False
    issue_count: int = 0
    package_name: str = ""
    template_type: str = ""
    source_run_id: str = ""


@dataclass(frozen=True)
class RuleReplayGoldenSuiteListing:
    """Filtered golden-suite listing plus aggregate counters."""

    suite_path: str
    suite_version: str
    case_count: int
    filters: Mapping[str, Any] = field(default_factory=dict)
    layer_counts: Mapping[str, int] = field(default_factory=dict)
    issue_type_counts: Mapping[str, int] = field(default_factory=dict)
    expectation_counts: Mapping[str, int] = field(default_factory=dict)
    cases: Sequence[RuleReplayGoldenCaseSummary] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuleReplayGoldenCaseDetail:
    """Full payload for one golden sample case."""

    suite_path: str
    suite_version: str
    summary: RuleReplayGoldenCaseSummary
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleReplayGoldenDiffEntry:
    """One case-level difference between two golden suites."""

    case_id: str
    change_type: str
    changed_fields: Sequence[str] = field(default_factory=tuple)
    left_case: Mapping[str, Any] = field(default_factory=dict)
    right_case: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleReplayGoldenDiffResult:
    """Structured difference between two golden suites."""

    left_path: str
    right_path: str
    left_suite_version: str
    right_suite_version: str
    diff_count: int
    change_counts: Mapping[str, int] = field(default_factory=dict)
    entries: Sequence[RuleReplayGoldenDiffEntry] = field(default_factory=tuple)
