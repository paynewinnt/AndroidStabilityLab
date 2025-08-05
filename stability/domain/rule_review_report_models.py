from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from .quality_gate_models import QualityGateRiskItem


@dataclass(frozen=True)
class RuleReviewReportEntry:
    """One included review snapshot in the aggregated review report."""

    snapshot_id: str
    name: str
    created_at: datetime
    created_by: str
    decision: str
    policy_version: str
    baseline_path: str
    candidate_path: str
    changed_family_count: int
    finding_count: int
    change_summary: Mapping[str, int] = field(default_factory=dict)
    reasons: Sequence[str] = field(default_factory=tuple)
    golden_suite_passed: bool | None = None
    golden_suite_case_count: int = 0
    golden_suite_passed_case_count: int = 0
    golden_suite_failed_case_count: int = 0
    golden_suite_version: str = ""
    golden_suite_suite_path: str = ""
    golden_suite_layer_summaries: Mapping[str, Any] = field(default_factory=dict)
    performance_summary: Mapping[str, Any] = field(default_factory=dict)
    performance_risk_items: Sequence[QualityGateRiskItem] = field(default_factory=tuple)
    detail_path: str = ""
    markdown_path: str = ""


@dataclass(frozen=True)
class RuleReviewFamilySummary:
    """Aggregated changed-family summary across multiple review snapshots."""

    family_key: str
    issue_type: str
    package_name: str
    scenario_name: str
    title: str
    change_type: str
    snapshot_count: int
    total_occurrence_count: int
    highest_decision: str
    sample_snapshot_ids: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuleReviewReportRecord:
    """Persisted rule review summary report bundle."""

    report_id: str
    name: str
    created_at: datetime
    created_by: str
    filters: Mapping[str, Any] = field(default_factory=dict)
    summary: Mapping[str, Any] = field(default_factory=dict)
    entries: Sequence[RuleReviewReportEntry] = field(default_factory=tuple)
    high_risk_families: Sequence[RuleReviewFamilySummary] = field(default_factory=tuple)
    detail_path: str = ""
    markdown_path: str = ""
    html_path: str = ""


@dataclass(frozen=True)
class RuleReviewReportComparisonFamily:
    """One high-risk family delta across two review reports."""

    family_key: str
    issue_type: str
    package_name: str
    scenario_name: str
    title: str
    change_type: str
    delta_status: str
    left_snapshot_count: int
    right_snapshot_count: int
    left_total_occurrence_count: int
    right_total_occurrence_count: int
    left_highest_decision: str
    right_highest_decision: str


@dataclass(frozen=True)
class RuleReviewReportComparisonRecord:
    """Persisted comparison bundle across two rule review summary reports."""

    comparison_id: str
    name: str
    created_at: datetime
    created_by: str
    left_report_id: str
    right_report_id: str
    left_report_name: str
    right_report_name: str
    left_detail_path: str = ""
    right_detail_path: str = ""
    summary: Mapping[str, Any] = field(default_factory=dict)
    family_diffs: Sequence[RuleReviewReportComparisonFamily] = field(default_factory=tuple)
    detail_path: str = ""
    markdown_path: str = ""
    html_path: str = ""


@dataclass(frozen=True)
class RuleReviewReportBaselineRecord:
    """Named baseline pointer for one reusable rule review report."""

    baseline_key: str
    report_id: str
    report_name: str
    policy_versions: Sequence[str] = field(default_factory=tuple)
    candidate_paths: Sequence[str] = field(default_factory=tuple)
    baseline_paths: Sequence[str] = field(default_factory=tuple)
    report_created_at: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    updated_by: str = ""
    latest_audit_id: str = ""
    latest_audit_detail_path: str = ""
    latest_audit_markdown_path: str = ""
    latest_audit_html_path: str = ""
    latest_audit_index_path: str = ""
    latest_audit_version_count: int = 0


@dataclass(frozen=True)
class RuleReviewReportBaselineHistoryEntry:
    """One immutable baseline assignment event kept for audit and rollback."""

    revision_id: str
    report_id: str
    report_name: str
    policy_versions: Sequence[str] = field(default_factory=tuple)
    candidate_paths: Sequence[str] = field(default_factory=tuple)
    baseline_paths: Sequence[str] = field(default_factory=tuple)
    report_created_at: str = ""
    changed_at: datetime | None = None
    changed_by: str = ""
    action: str = ""
    reasons: Sequence[str] = field(default_factory=tuple)
    comparison_id: str = ""
    comparison_detail_path: str = ""
    policy_version: str = ""


@dataclass(frozen=True)
class RuleReviewReportBaselinePromotionResult:
    """Decision record for one baseline promotion attempt."""

    baseline_key: str
    target_report_id: str
    target_report_name: str
    baseline_report_id: str
    baseline_report_name: str
    policy_version: str
    approved: bool
    promoted: bool
    reasons: Sequence[str] = field(default_factory=tuple)
    comparison_id: str = ""
    comparison_detail_path: str = ""
    target_golden_suite: Mapping[str, Any] = field(default_factory=dict)
    baseline_golden_suite: Mapping[str, Any] = field(default_factory=dict)
    updated_baseline: RuleReviewReportBaselineRecord | None = None


@dataclass(frozen=True)
class RuleReviewReportBaselineRollbackResult:
    """Outcome of one baseline rollback operation."""

    baseline_key: str
    from_report_id: str
    from_report_name: str
    to_report_id: str
    to_report_name: str
    rolled_back: bool
    reasons: Sequence[str] = field(default_factory=tuple)
    updated_baseline: RuleReviewReportBaselineRecord | None = None


@dataclass(frozen=True)
class RuleReviewReportBaselineAuditEvent:
    """One readable baseline transition derived from immutable history revisions."""

    revision_id: str
    action: str
    changed_at: datetime | None = None
    changed_by: str = ""
    from_report_id: str = ""
    from_report_name: str = ""
    to_report_id: str = ""
    to_report_name: str = ""
    reason_summary: str = ""
    reasons: Sequence[str] = field(default_factory=tuple)
    comparison_id: str = ""
    comparison_detail_path: str = ""
    policy_version: str = ""


@dataclass(frozen=True)
class RuleReviewReportBaselineAuditRecord:
    """Persisted audit bundle across one baseline's full revision history."""

    audit_id: str
    name: str
    created_at: datetime
    created_by: str
    baseline_key: str
    current_report_id: str
    current_report_name: str
    summary: Mapping[str, Any] = field(default_factory=dict)
    events: Sequence[RuleReviewReportBaselineAuditEvent] = field(default_factory=tuple)
    detail_path: str = ""
    markdown_path: str = ""
    html_path: str = ""


@dataclass(frozen=True)
class RuleReviewReportBaselineAuditVersionRecord:
    """One lightweight indexed latest-audit version entry."""

    revision_id: str
    action: str
    changed_at: datetime | None = None
    changed_by: str = ""
    report_id: str = ""
    report_name: str = ""
    audit_id: str = ""
    summary: Mapping[str, Any] = field(default_factory=dict)
    detail_path: str = ""
    markdown_path: str = ""
    html_path: str = ""


@dataclass(frozen=True)
class RuleReviewReportBaselineAuditView:
    """Readable latest-audit view for one baseline key."""

    baseline: RuleReviewReportBaselineRecord
    audit_id: str
    audit_name: str
    created_at: datetime | None = None
    created_by: str = ""
    summary: Mapping[str, Any] = field(default_factory=dict)
    retention: Mapping[str, Any] = field(default_factory=dict)
    version_count: int = 0
    versions: Sequence[RuleReviewReportBaselineAuditVersionRecord] = field(default_factory=tuple)
    detail_path: str = ""
    markdown_path: str = ""
    html_path: str = ""
    index_path: str = ""
