from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from stability.app.admission_case_store import isoformat_or_none
from stability.domain import (
    AdmissionCaseExecutionSummary,
    AdmissionCaseRegressionSummary,
    AdmissionCaseScenarioCoverage,
    AdmissionCaseTopIssue,
    QualityGateResult,
)


def error_code(*, final_decision: str, quality_gate: QualityGateResult | None = None) -> str:
    normalized = str(final_decision or "").strip().lower()
    if normalized in {"pass", "approved", "ok"}:
        return "PASS"
    if normalized in {"conditional_pass", "warn", "conditional"}:
        return "CONDITIONAL_PASS"
    if normalized in {"fail", "rejected", "reject"}:
        return "FAIL"
    if normalized == "unknown":
        return "NO_QUALITY_GATE" if quality_gate is None else "UNKNOWN_DECISION"
    if not normalized:
        if quality_gate is None:
            return "NO_QUALITY_GATE"
        if getattr(quality_gate, "failure_reasons", ()):
            return "REQUIRES_REVIEW"
        return "UNKNOWN_DECISION"
    return "UNKNOWN_DECISION"


def case_trace_payload(
    *,
    baseline_key: str,
    report: object,
    quality_gate: QualityGateResult | None,
    execution_summary: AdmissionCaseExecutionSummary,
    top_issues: Sequence[AdmissionCaseTopIssue],
    regression_summary: AdmissionCaseRegressionSummary,
    scenario_coverage: AdmissionCaseScenarioCoverage,
    latest_audit: object | None,
    final_decision: str,
    error_code: str,
    final_review_opinion: str,
    report_id: str,
    report_name: str,
    baseline_updated_at: datetime | None,
) -> dict[str, Any]:
    return {
        "case_id": f"admission_case:{baseline_key}:{report_id or 'unknown'}",
        "contract_version": "admission_case.v1",
        "baseline_key": baseline_key,
        "report": {
            "report_id": report_id,
            "report_name": report_name,
            "created_at": isoformat_or_none(getattr(report, "created_at", None)),
            "updated_at": isoformat_or_none(baseline_updated_at),
            "created_by": str(getattr(report, "created_by", "") or ""),
        },
        "decision": {
            "automatic_decision": str(getattr(quality_gate, "automatic_decision", "") or ""),
            "final_decision": final_decision,
            "final_review_opinion": final_review_opinion,
            "error_code": error_code,
        },
        "evidence": {
            "top_issues": [as_text(item.fingerprint) for item in list(top_issues)[:5]],
            "top_issue_count": len(top_issues),
            "triggered_rules": [
                str(getattr(item, "rule_key", "")) for item in list(getattr(quality_gate, "triggered_rules", ()) or [])
            ],
            "performance_risk_count": len(list(getattr(quality_gate, "performance_risk_items", ()) or ())),
            "regression": {
                "available": bool(regression_summary.available),
                "dimension": str(getattr(regression_summary, "dimension", "") or ""),
                "overall_result": str(getattr(regression_summary, "overall_result", "insufficient_data") or "insufficient_data"),
            },
            "execution": {
                "total_runs": int(getattr(execution_summary, "total_runs", 0) or 0),
                "failed_run_count": int(getattr(execution_summary, "failed_run_count", 0) or 0),
                "latest_run_id": str(getattr(execution_summary, "latest_run_id", "") or ""),
                "latest_run_status": str(getattr(execution_summary, "latest_run_status", "") or ""),
            },
            "scenario_coverage": {
                "state": str(getattr(scenario_coverage, "coverage_state", "") or ""),
                "scenario_count": int(getattr(scenario_coverage, "scenario_count", 0) or 0),
            },
        },
        "artifacts": {
            "report_summary": dict(getattr(report, "summary", {}) or {}),
            "latest_audit_summary": dict(getattr(latest_audit, "summary", {}) or {}),
            "override": (
                {
                    "override_id": str(getattr(getattr(quality_gate, "override", None), "override_id", "")),
                    "baseline_key": str(getattr(getattr(quality_gate, "override", None), "baseline_key", "") or ""),
                    "final_decision": str(getattr(getattr(quality_gate, "override", None), "final_decision", "") or ""),
                    "reason": str(getattr(getattr(quality_gate, "override", None), "reason", "") or ""),
                }
                if getattr(quality_gate, "override", None) is not None
                else None
            ),
        },
        "updated_at": isoformat_or_none(baseline_updated_at),
    }


def source_refs(
    *,
    report: object,
    latest_audit: object | None,
    quality_gate: QualityGateResult | None,
    source_links: Mapping[str, Any],
    filters: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "report": {
            "report_id": str(getattr(report, "report_id", "") or ""),
            "detail_path": str(source_links.get("report_detail_path", "") or ""),
            "markdown_path": str(source_links.get("report_markdown_path", "") or ""),
            "html_path": str(source_links.get("report_html_path", "") or ""),
        },
        "latest_audit": {
            "detail_path": str(source_links.get("latest_audit_detail_path", "") or ""),
            "markdown_path": str(source_links.get("latest_audit_markdown_path", "") or ""),
            "html_path": str(source_links.get("latest_audit_html_path", "") or ""),
            "index_path": str(source_links.get("latest_audit_index_path", "") or ""),
            "available": latest_audit is not None,
        },
        "quality_gate": {
            "available": quality_gate is not None,
            "baseline_key": str(getattr(quality_gate, "baseline_key", "") or ""),
            "automatic_decision": str(getattr(quality_gate, "automatic_decision", "") or ""),
        },
        "filters": dict(filters),
    }


def ci_contract(
    *,
    case_id: str,
    baseline_key: str,
    report_id: str,
    final_decision: str,
    error_code: str,
    final_review_opinion: str,
    status: str,
    revision: int,
    assignee_id: str,
    assignee_display_name: str,
    final_reviewer_id: str,
    final_reviewer_display_name: str,
    source_refs: Mapping[str, Any],
    case_trace: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = dict(case_trace.get("evidence", {}) or {})
    return {
        "contract_version": "admission_case.v1",
        "case_id": case_id,
        "baseline_key": baseline_key,
        "report_id": report_id,
        "case_revision": int(revision),
        "status": status,
        "assignee": {
            "actor_id": assignee_id,
            "display_name": assignee_display_name,
        },
        "final_reviewer": {
            "actor_id": final_reviewer_id,
            "display_name": final_reviewer_display_name,
        },
        "final_decision": final_decision,
        "error_code": error_code,
        "final_review_opinion": final_review_opinion,
        "sync_event_type": "admission_case.updated",
        "decision_source": "admission_case",
        "case_trace_summary": {
            "triggered_rule_keys": list(evidence.get("triggered_rules", []) or []),
            "top_issue_count": int(evidence.get("top_issue_count", 0) or 0),
            "performance_risk_count": int(evidence.get("performance_risk_count", 0) or 0),
        },
        "source_refs": dict(source_refs),
    }


def as_text(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "")
