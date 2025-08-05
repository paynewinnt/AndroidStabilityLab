from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from .quality_gate_models import QualityGateOverrideRecord, QualityGateResult, QualityGateRiskItem


ADMISSION_CASE_CONTRACT_VERSION = "admission_case.v1"
ADMISSION_CASE_STATE_MACHINE_VERSION = "admission_case.lifecycle.v1"


@dataclass(frozen=True)
class AdmissionCaseTopIssue:
    """Top-issue summary attached to one admission case."""

    fingerprint: str
    title: str
    issue_type: str
    severity: str
    occurrence_count: int
    affected_run_count: int
    affected_device_count: int
    affected_scenario_count: int
    last_seen_at: datetime | None = None
    affected_scenarios: Sequence[str] = field(default_factory=tuple)
    affected_versions: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdmissionCaseExecutionSummary:
    """Run-level execution summary scoped to one admission case."""

    total_runs: int = 0
    status_counts: Mapping[str, int] = field(default_factory=dict)
    failed_run_count: int = 0
    issue_run_count: int = 0
    task_ids: Sequence[str] = field(default_factory=tuple)
    task_names: Sequence[str] = field(default_factory=tuple)
    package_names: Sequence[str] = field(default_factory=tuple)
    template_types: Sequence[str] = field(default_factory=tuple)
    device_ids: Sequence[str] = field(default_factory=tuple)
    latest_run_id: str = ""
    latest_run_status: str = ""
    latest_run_created_at: datetime | None = None
    recent_runs: Sequence[Mapping[str, Any]] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdmissionCaseScenarioCoverage:
    """Minimal scenario-coverage view for one admission case."""

    scenario_count: int = 0
    scenarios: Sequence[str] = field(default_factory=tuple)
    issue_scenario_count: int = 0
    issue_scenarios: Sequence[str] = field(default_factory=tuple)
    coverage_state: str = "missing"
    notes: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdmissionCaseRegressionSummary:
    """Regression summary attached to one admission case."""

    available: bool = False
    dimension: str = ""
    overall_result: str = "insufficient_data"
    issue_result_summary: Mapping[str, int] = field(default_factory=dict)
    metric_result_summary: Mapping[str, Any] = field(default_factory=dict)
    reasons: Sequence[str] = field(default_factory=tuple)
    comparability_notes: Sequence[str] = field(default_factory=tuple)
    source_filters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdmissionCaseLifecycleEvent:
    """One workflow transition recorded on the admission case itself."""

    entry_id: str
    action: str
    from_status: str
    to_status: str
    changed_at: datetime
    changed_by: str
    reason: str = ""
    audit_event_id: str = ""
    permission_check_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class AdmissionCaseRoleAuditEntry:
    """One assignee/reviewer change recorded on the admission case itself."""

    entry_id: str
    role_name: str
    changed_at: datetime
    changed_by: str
    from_actor_id: str = ""
    from_actor_display_name: str = ""
    to_actor_id: str = ""
    to_actor_display_name: str = ""
    reason: str = ""
    audit_event_id: str = ""
    permission_check_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class AdmissionCase:
    """One first-class admission review object."""

    case_id: str
    baseline_key: str
    report_id: str
    report_name: str
    contract_version: str = ADMISSION_CASE_CONTRACT_VERSION
    state_machine_version: str = ADMISSION_CASE_STATE_MACHINE_VERSION
    status: str = "open"
    revision: int = 1
    assignee_id: str = ""
    assignee_display_name: str = ""
    final_reviewer_id: str = ""
    final_reviewer_display_name: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    updated_by: str = ""
    filters: Mapping[str, Any] = field(default_factory=dict)
    execution_summary: AdmissionCaseExecutionSummary = field(default_factory=AdmissionCaseExecutionSummary)
    top_issues: Sequence[AdmissionCaseTopIssue] = field(default_factory=tuple)
    regression_summary: AdmissionCaseRegressionSummary = field(default_factory=AdmissionCaseRegressionSummary)
    scenario_coverage: AdmissionCaseScenarioCoverage = field(default_factory=AdmissionCaseScenarioCoverage)
    performance_risk_items: Sequence[QualityGateRiskItem] = field(default_factory=tuple)
    quality_gate: QualityGateResult | None = None
    override: QualityGateOverrideRecord | None = None
    final_review_opinion: str = ""
    final_decision: str = ""
    error_code: str = ""
    lifecycle_events: Sequence[AdmissionCaseLifecycleEvent] = field(default_factory=tuple)
    role_audit_entries: Sequence[AdmissionCaseRoleAuditEntry] = field(default_factory=tuple)
    case_trace: Mapping[str, Any] = field(default_factory=dict)
    report_summary: Mapping[str, Any] = field(default_factory=dict)
    latest_audit_summary: Mapping[str, Any] = field(default_factory=dict)
    source_links: Mapping[str, Any] = field(default_factory=dict)
    source_refs: Mapping[str, Any] = field(default_factory=dict)
    ci_contract: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdmissionReportPayload:
    """Auditable, export-ready report contract for one admission case."""

    report_contract_version: str
    report_id: str
    baseline_key: str
    status: str
    final_decision: str
    risk_level: str
    quality_gate_summary: Mapping[str, Any] = field(default_factory=dict)
    top_issue_summary: Mapping[str, Any] = field(default_factory=dict)
    performance_risk_summary: Mapping[str, Any] = field(default_factory=dict)
    manual_overrides: Mapping[str, Any] = field(default_factory=dict)
    collaboration_summary: Mapping[str, Any] = field(default_factory=dict)
    external_sync_summary: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: Mapping[str, Any] = field(default_factory=dict)
    source_refs: Mapping[str, Any] = field(default_factory=dict)
    recommended_actions: Sequence[str] = field(default_factory=tuple)
    generated_at: datetime | None = None
