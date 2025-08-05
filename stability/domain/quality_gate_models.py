from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class QualityGateRule:
    """First-class quality gate rule definition used by V3 admission."""

    rule_key: str
    name: str
    rule_version: str
    scope: str
    metric_key: str
    comparator: str
    threshold: Any = None
    decision_on_trigger: str = ""
    description: str = ""
    applies_to: Mapping[str, Any] = field(default_factory=dict)
    created_by: str = ""
    updated_by: str = ""


@dataclass(frozen=True)
class QualityGateTriggeredRule:
    """Evaluation result for one gate rule against one admission case."""

    rule_key: str
    rule_name: str
    rule_version: str
    decision_on_trigger: str
    observed_value: Any = None
    threshold: Any = None
    message: str = ""
    source: str = ""


@dataclass(frozen=True)
class QualityGateRiskItem:
    """One non-blocking or blocking risk item surfaced by admission."""

    risk_key: str
    category: str
    severity: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)
    source: str = ""
    blocks_admission: bool = False


@dataclass(frozen=True)
class QualityGateCoverageGap:
    """Coverage insufficiency that should be visible in the admission result."""

    gap_key: str
    category: str
    severity: str
    summary: str
    observed_value: Any = None
    required_value: Any = None
    source: str = ""


@dataclass(frozen=True)
class QualityGateOverrideRecord:
    """Manual override record kept separately from automatic gate evaluation."""

    override_id: str
    baseline_key: str
    automatic_decision: str
    final_decision: str
    reason: str
    created_at: datetime
    created_by: str
    session_source: str = ""
    audit_source: Mapping[str, Any] = field(default_factory=dict)
    comment: str = ""
    evidence_paths: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class QualityGateResult:
    """Admission result for one reusable baseline key."""

    baseline_key: str
    report_id: str
    report_name: str
    evaluated_at: datetime
    automatic_decision: str
    final_decision: str
    final_review_opinion: str
    rules: Sequence[QualityGateRule] = field(default_factory=tuple)
    triggered_rules: Sequence[QualityGateTriggeredRule] = field(default_factory=tuple)
    failure_reasons: Sequence[str] = field(default_factory=tuple)
    risk_items: Sequence[QualityGateRiskItem] = field(default_factory=tuple)
    performance_risk_items: Sequence[QualityGateRiskItem] = field(default_factory=tuple)
    coverage_gaps: Sequence[QualityGateCoverageGap] = field(default_factory=tuple)
    override: QualityGateOverrideRecord | None = None
    policy_versions: Sequence[str] = field(default_factory=tuple)
    candidate_paths: Sequence[str] = field(default_factory=tuple)
    baseline_paths: Sequence[str] = field(default_factory=tuple)
    report_created_at: str = ""
    updated_at: datetime | None = None
    updated_by: str = ""
    latest_audit_summary: Mapping[str, Any] = field(default_factory=dict)
    current_report_golden_suite: Mapping[str, Any] = field(default_factory=dict)
    report_summary: Mapping[str, Any] = field(default_factory=dict)
    source_links: Mapping[str, Any] = field(default_factory=dict)
