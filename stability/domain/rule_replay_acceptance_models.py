from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .rule_replay_models import RuleReplayResult


@dataclass(frozen=True)
class RuleReplayGoldenCaseResult:
    """Validation result for one replay golden sample."""

    case_id: str
    description: str
    passed: bool
    layer: str = ""
    expectation: str = ""
    issue_type: str = ""
    mismatches: Sequence[str] = field(default_factory=tuple)
    replay: RuleReplayResult | None = None


@dataclass(frozen=True)
class RuleReplayGoldenSuiteResult:
    """Validation summary across one replay golden-sample suite."""

    suite_path: str
    suite_version: str
    case_count: int
    passed_case_count: int
    failed_case_count: int
    layer_summaries: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    cases: Sequence[RuleReplayGoldenCaseResult] = field(default_factory=tuple)
