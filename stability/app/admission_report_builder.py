from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from stability.domain import (
    AdmissionCase,
    AdmissionCaseLifecycleEvent,
    AdmissionCaseRoleAuditEntry,
    AdmissionCaseTopIssue,
    AdmissionReportPayload,
    QualityGateRiskItem,
    QualityGateResult,
)
from stability.domain.value_objects import utcnow
from stability.time_utils import format_beijing_datetime


def build_admission_report_payload(
    item: AdmissionCase,
    *,
    generated_at: datetime | None = None,
) -> AdmissionReportPayload:
    """Build an export-ready, auditable report contract for one admission case."""

    gate = getattr(item, "quality_gate", None)
    override = getattr(item, "override", None) or getattr(gate, "override", None)
    generated = generated_at or utcnow()
    return AdmissionReportPayload(
        report_contract_version="admission_report.v1",
        report_id=admission_report_id(item),
        baseline_key=str(getattr(item, "baseline_key", "") or ""),
        status=str(getattr(item, "status", "") or "open"),
        final_decision=str(getattr(item, "final_decision", "") or "unknown"),
        risk_level=report_risk_level(item),
        quality_gate_summary=report_quality_gate_summary(item, gate=gate),
        top_issue_summary=report_top_issue_summary(getattr(item, "top_issues", ()) or ()),
        performance_risk_summary=report_performance_risk_summary(getattr(item, "performance_risk_items", ()) or ()),
        manual_overrides=report_manual_overrides(override),
        collaboration_summary=report_collaboration_summary(item),
        external_sync_summary=report_external_sync_summary(item),
        evidence_refs=report_evidence_refs(item),
        source_refs=dict(getattr(item, "source_refs", {}) or {}),
        recommended_actions=report_recommended_actions(item),
        generated_at=generated,
    )


def admission_report_id(item: AdmissionCase) -> str:
    baseline_key = str(getattr(item, "baseline_key", "") or "unknown")
    source_report_id = str(getattr(item, "report_id", "") or "unknown")
    revision = int(getattr(item, "revision", 1) or 1)
    return f"admission_report:{baseline_key}:{source_report_id}:r{revision}"


def report_quality_gate_summary(
    item: AdmissionCase,
    *,
    gate: QualityGateResult | None,
) -> dict[str, Any]:
    triggered_rules = list(getattr(gate, "triggered_rules", ()) or ())
    risk_items = list(getattr(gate, "risk_items", ()) or ())
    coverage_gaps = list(getattr(gate, "coverage_gaps", ()) or ())
    return {
        "available": gate is not None,
        "automatic_decision": str(getattr(gate, "automatic_decision", "") or ""),
        "final_decision": str(getattr(item, "final_decision", "") or getattr(gate, "final_decision", "") or "unknown"),
        "final_review_opinion": str(
            getattr(item, "final_review_opinion", "") or getattr(gate, "final_review_opinion", "") or ""
        ),
        "error_code": str(getattr(item, "error_code", "") or ""),
        "triggered_rule_count": len(triggered_rules),
        "triggered_rules": [
            {
                "rule_key": str(getattr(rule, "rule_key", "") or ""),
                "decision_on_trigger": str(getattr(rule, "decision_on_trigger", "") or ""),
                "message": str(getattr(rule, "message", "") or ""),
                "source": str(getattr(rule, "source", "") or ""),
                "observed_value": json_ready(getattr(rule, "observed_value", None)),
                "threshold": json_ready(getattr(rule, "threshold", None)),
            }
            for rule in triggered_rules
        ],
        "failure_reasons": list(getattr(gate, "failure_reasons", ()) or ()),
        "risk_item_count": len(risk_items),
        "risk_items": [risk_item_payload(risk) for risk in risk_items],
        "coverage_gap_count": len(coverage_gaps),
        "coverage_gaps": [
            {
                "gap_key": str(getattr(gap, "gap_key", "") or ""),
                "category": str(getattr(gap, "category", "") or ""),
                "severity": str(getattr(gap, "severity", "") or ""),
                "summary": str(getattr(gap, "summary", "") or ""),
                "observed_value": json_ready(getattr(gap, "observed_value", None)),
                "required_value": json_ready(getattr(gap, "required_value", None)),
                "source": str(getattr(gap, "source", "") or ""),
            }
            for gap in coverage_gaps
        ],
    }


def report_top_issue_summary(top_issues: Sequence[AdmissionCaseTopIssue]) -> dict[str, Any]:
    items = list(top_issues or ())
    severity = highest_severity(getattr(item, "severity", "") for item in items)
    return {
        "issue_count": len(items),
        "highest_severity": severity,
        "affected_run_count": sum(int(getattr(item, "affected_run_count", 0) or 0) for item in items),
        "affected_device_count": sum(int(getattr(item, "affected_device_count", 0) or 0) for item in items),
        "issues": [
            {
                "fingerprint": str(getattr(issue, "fingerprint", "") or ""),
                "title": str(getattr(issue, "title", "") or ""),
                "issue_type": str(getattr(issue, "issue_type", "") or ""),
                "severity": str(getattr(issue, "severity", "") or ""),
                "occurrence_count": int(getattr(issue, "occurrence_count", 0) or 0),
                "affected_run_count": int(getattr(issue, "affected_run_count", 0) or 0),
                "affected_device_count": int(getattr(issue, "affected_device_count", 0) or 0),
                "affected_scenario_count": int(getattr(issue, "affected_scenario_count", 0) or 0),
                "last_seen_at": isoformat_or_none(getattr(issue, "last_seen_at", None)),
                "affected_scenarios": list(getattr(issue, "affected_scenarios", ()) or ()),
                "affected_versions": list(getattr(issue, "affected_versions", ()) or ()),
            }
            for issue in items[:5]
        ],
    }


def report_performance_risk_summary(risk_items: Sequence[QualityGateRiskItem]) -> dict[str, Any]:
    risks = list(risk_items or ())
    return {
        "risk_count": len(risks),
        "blocking_risk_count": sum(1 for risk in risks if bool(getattr(risk, "blocks_admission", False))),
        "highest_severity": highest_severity(getattr(risk, "severity", "") for risk in risks),
        "risks": [risk_item_payload(risk) for risk in risks],
    }


def risk_item_payload(risk: object) -> dict[str, Any]:
    return {
        "risk_key": str(getattr(risk, "risk_key", "") or ""),
        "category": str(getattr(risk, "category", "") or ""),
        "severity": str(getattr(risk, "severity", "") or ""),
        "summary": str(getattr(risk, "summary", "") or ""),
        "details": json_ready(dict(getattr(risk, "details", {}) or {})),
        "source": str(getattr(risk, "source", "") or ""),
        "blocks_admission": bool(getattr(risk, "blocks_admission", False)),
    }


def report_manual_overrides(override: object | None) -> dict[str, Any]:
    if override is None:
        return {"has_override": False}
    return {
        "has_override": True,
        "override_id": str(getattr(override, "override_id", "") or ""),
        "automatic_decision": str(getattr(override, "automatic_decision", "") or ""),
        "final_decision": str(getattr(override, "final_decision", "") or ""),
        "reason": str(getattr(override, "reason", "") or ""),
        "created_at": isoformat_or_none(getattr(override, "created_at", None)),
        "created_by": str(getattr(override, "created_by", "") or ""),
        "session_source": str(getattr(override, "session_source", "") or ""),
        "audit_source": json_ready(dict(getattr(override, "audit_source", {}) or {})),
        "comment": str(getattr(override, "comment", "") or ""),
        "evidence_paths": list(getattr(override, "evidence_paths", ()) or ()),
    }


def report_collaboration_summary(item: AdmissionCase) -> dict[str, Any]:
    lifecycle_events = list(getattr(item, "lifecycle_events", ()) or ())
    role_audit_entries = list(getattr(item, "role_audit_entries", ()) or ())
    return {
        "status": str(getattr(item, "status", "") or "open"),
        "case_revision": int(getattr(item, "revision", 1) or 1),
        "assignee": {
            "actor_id": str(getattr(item, "assignee_id", "") or ""),
            "display_name": str(getattr(item, "assignee_display_name", "") or ""),
        },
        "final_reviewer": {
            "actor_id": str(getattr(item, "final_reviewer_id", "") or ""),
            "display_name": str(getattr(item, "final_reviewer_display_name", "") or ""),
        },
        "updated_by": str(getattr(item, "updated_by", "") or ""),
        "lifecycle_event_count": len(lifecycle_events),
        "role_audit_entry_count": len(role_audit_entries),
        "latest_lifecycle_event": lifecycle_event_payload(lifecycle_events[-1]) if lifecycle_events else None,
        "latest_role_audit_entry": role_audit_payload(role_audit_entries[-1]) if role_audit_entries else None,
    }


def lifecycle_event_payload(event: AdmissionCaseLifecycleEvent) -> dict[str, Any]:
    return {
        "entry_id": str(getattr(event, "entry_id", "") or ""),
        "action": str(getattr(event, "action", "") or ""),
        "from_status": str(getattr(event, "from_status", "") or ""),
        "to_status": str(getattr(event, "to_status", "") or ""),
        "changed_at": isoformat_or_none(getattr(event, "changed_at", None)),
        "changed_by": str(getattr(event, "changed_by", "") or ""),
        "reason": str(getattr(event, "reason", "") or ""),
        "audit_event_id": str(getattr(event, "audit_event_id", "") or ""),
        "permission_check_id": str(getattr(event, "permission_check_id", "") or ""),
        "session_id": str(getattr(event, "session_id", "") or ""),
    }


def role_audit_payload(entry: AdmissionCaseRoleAuditEntry) -> dict[str, Any]:
    return {
        "entry_id": str(getattr(entry, "entry_id", "") or ""),
        "role_name": str(getattr(entry, "role_name", "") or ""),
        "changed_at": isoformat_or_none(getattr(entry, "changed_at", None)),
        "changed_by": str(getattr(entry, "changed_by", "") or ""),
        "from_actor_id": str(getattr(entry, "from_actor_id", "") or ""),
        "to_actor_id": str(getattr(entry, "to_actor_id", "") or ""),
        "reason": str(getattr(entry, "reason", "") or ""),
        "audit_event_id": str(getattr(entry, "audit_event_id", "") or ""),
        "permission_check_id": str(getattr(entry, "permission_check_id", "") or ""),
        "session_id": str(getattr(entry, "session_id", "") or ""),
    }


def report_external_sync_summary(item: AdmissionCase) -> dict[str, Any]:
    ci_contract = dict(getattr(item, "ci_contract", {}) or {})
    return {
        "ci_contract_available": bool(ci_contract),
        "ci_contract": ci_contract,
        "sync_event_type": str(ci_contract.get("sync_event_type", "") or ""),
        "decision_source": str(ci_contract.get("decision_source", "") or ""),
        "error_code": str(ci_contract.get("error_code", getattr(item, "error_code", "")) or ""),
    }


def report_evidence_refs(item: AdmissionCase) -> dict[str, Any]:
    source_refs = dict(getattr(item, "source_refs", {}) or {})
    report_refs = dict(source_refs.get("report", {}) or {})
    latest_audit_refs = dict(source_refs.get("latest_audit", {}) or {})
    return {
        "report_detail_path": str(report_refs.get("detail_path", "") or ""),
        "report_markdown_path": str(report_refs.get("markdown_path", "") or ""),
        "report_html_path": str(report_refs.get("html_path", "") or ""),
        "latest_audit_detail_path": str(latest_audit_refs.get("detail_path", "") or ""),
        "latest_audit_markdown_path": str(latest_audit_refs.get("markdown_path", "") or ""),
        "latest_audit_html_path": str(latest_audit_refs.get("html_path", "") or ""),
        "latest_audit_index_path": str(latest_audit_refs.get("index_path", "") or ""),
        "case_trace": dict(getattr(item, "case_trace", {}) or {}),
        "top_issue_fingerprints": [
            str(getattr(issue, "fingerprint", "") or "") for issue in list(getattr(item, "top_issues", ()) or ())[:5]
        ],
        "performance_risk_sources": [
            str(getattr(risk, "source", "") or "")
            for risk in list(getattr(item, "performance_risk_items", ()) or ())
            if str(getattr(risk, "source", "") or "").strip()
        ],
    }


def report_recommended_actions(item: AdmissionCase) -> tuple[str, ...]:
    actions: list[str] = []
    gate = getattr(item, "quality_gate", None)
    final_decision = str(getattr(item, "final_decision", "") or "").strip().lower()
    if gate is None:
        actions.append("Run quality gate evaluation before sharing this admission report externally.")
    if final_decision == "fail":
        actions.append("Block admission until failing quality gate rules and top issues are resolved.")
    elif final_decision == "conditional_pass":
        actions.append("Collect final reviewer confirmation for conditional pass before release handoff.")
    if getattr(item, "override", None) is not None:
        actions.append("Keep manual override evidence attached to the release or client handoff record.")
    if list(getattr(item, "performance_risk_items", ()) or ()):
        actions.append("Review performance risk items and link accepted risks to tracking tickets.")
    if list(getattr(item, "top_issues", ()) or ()):
        actions.append("Confirm Top Issue ownership and mitigation status before closing the case.")
    coverage_state = str(getattr(getattr(item, "scenario_coverage", None), "coverage_state", "") or "")
    if coverage_state == "missing":
        actions.append("Add execution evidence because scenario coverage is currently missing.")
    if not actions:
        actions.append("No immediate action is required; retain this payload with release evidence.")
    return tuple(actions)


def report_risk_level(item: AdmissionCase) -> str:
    final_decision = str(getattr(item, "final_decision", "") or "").strip().lower()
    if final_decision == "fail":
        return "high"
    if final_decision in {"unknown", ""}:
        return "unknown"
    severity = highest_severity(
        [
            *(getattr(issue, "severity", "") for issue in list(getattr(item, "top_issues", ()) or ())),
            *(getattr(risk, "severity", "") for risk in list(getattr(item, "performance_risk_items", ()) or ())),
        ]
    )
    if any(bool(getattr(risk, "blocks_admission", False)) for risk in list(getattr(item, "performance_risk_items", ()) or ())):
        return "high"
    if final_decision == "conditional_pass":
        return "medium" if severity not in {"high", "critical"} else "high"
    if severity in {"critical", "high"}:
        return "high"
    if severity == "medium":
        return "medium"
    return "low"


def highest_severity(values: Sequence[str] | Any) -> str:
    rank = {"": 0, "info": 1, "low": 2, "minor": 2, "medium": 3, "warning": 3, "high": 4, "critical": 5}
    best = ""
    for value in values:
        normalized = str(value or "").strip().lower()
        if rank.get(normalized, 0) > rank.get(best, 0):
            best = normalized
    return best or "none"


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return format_beijing_datetime(value)
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in dict(value).items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if hasattr(value, "__dict__"):
        return json_ready(vars(value))
    return value


def isoformat_or_none(value: Any) -> str | None:
    parsed = datetime_or_none(value)
    if parsed is None:
        return None
    return format_beijing_datetime(parsed)


def datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        return parse_datetime(value)
    return None


def parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
