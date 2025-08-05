from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .quality_gate_models import QualityGateRiskItem
from .rule_replay_acceptance_models import RuleReplayGoldenSuiteResult
from .rule_replay_models import ReplayedIssueFamily


@dataclass(frozen=True)
class RuleReviewFinding:
    """One policy finding produced while reviewing a rule change."""

    level: str
    scope: str
    issue_type: str
    change_type: str
    observed_count: int
    threshold: int
    message: str


@dataclass(frozen=True)
class RuleReviewResult:
    """Structured decision for one candidate rule change."""

    decision: str
    policy_version: str
    policy_path: str
    baseline_path: str
    candidate_path: str
    baseline_rule_version: str
    candidate_rule_version: str
    filters: Mapping[str, object]
    family_count: int
    changed_family_count: int
    change_summary: Mapping[str, int] = field(default_factory=dict)
    issue_type_change_summary: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    findings: Sequence[RuleReviewFinding] = field(default_factory=tuple)
    reasons: Sequence[str] = field(default_factory=tuple)
    baseline_valid: bool = True
    candidate_valid: bool = True
    baseline_errors: Sequence[str] = field(default_factory=tuple)
    candidate_errors: Sequence[str] = field(default_factory=tuple)
    golden_suite: RuleReplayGoldenSuiteResult | None = None
    performance_summary: Mapping[str, Any] = field(default_factory=dict)
    performance_risk_items: Sequence[QualityGateRiskItem] = field(default_factory=tuple)
    families: Sequence[ReplayedIssueFamily] = field(default_factory=tuple)
