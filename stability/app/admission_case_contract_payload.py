from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from stability.domain import AdmissionCase
from stability.domain.admission_case_models import (
    ADMISSION_CASE_CONTRACT_VERSION,
    ADMISSION_CASE_STATE_MACHINE_VERSION,
)


ADMISSION_CASE_LIST_CONTRACT_VERSION = "admission_case_list.v1"


def admission_case_contract_payload(item: AdmissionCase) -> dict[str, Any]:
    """Return the stable JSON-ready application contract for one AdmissionCase."""

    decision_trace = dict(getattr(item, "case_trace", {}) or {}).get("decision", {})
    decision = dict(decision_trace) if isinstance(decision_trace, Mapping) else {}
    final_decision = str(getattr(item, "final_decision", "") or decision.get("final_decision", "") or "")
    error_code = str(getattr(item, "error_code", "") or decision.get("error_code", "") or "")
    final_review_opinion = str(
        getattr(item, "final_review_opinion", "") or decision.get("final_review_opinion", "") or ""
    )

    return json_ready(
        {
            "contract_version": str(getattr(item, "contract_version", "") or ADMISSION_CASE_CONTRACT_VERSION),
            "case_id": str(getattr(item, "case_id", "") or ""),
            "baseline_key": str(getattr(item, "baseline_key", "") or ""),
            "report_id": str(getattr(item, "report_id", "") or ""),
            "report_name": str(getattr(item, "report_name", "") or ""),
            "status": str(getattr(item, "status", "") or "open"),
            "revision": int(getattr(item, "revision", 1) or 1),
            "state_machine_version": str(
                getattr(item, "state_machine_version", "") or ADMISSION_CASE_STATE_MACHINE_VERSION
            ),
            "created_at": getattr(item, "created_at", None),
            "updated_at": getattr(item, "updated_at", None),
            "updated_by": str(getattr(item, "updated_by", "") or ""),
            "assignee": {
                "actor_id": str(getattr(item, "assignee_id", "") or ""),
                "display_name": str(getattr(item, "assignee_display_name", "") or ""),
            },
            "final_reviewer": {
                "actor_id": str(getattr(item, "final_reviewer_id", "") or ""),
                "display_name": str(getattr(item, "final_reviewer_display_name", "") or ""),
            },
            "decision": {
                "automatic_decision": str(decision.get("automatic_decision", "") or ""),
                "final_decision": final_decision,
                "final_review_opinion": final_review_opinion,
                "error_code": error_code,
            },
            "final_decision": final_decision,
            "final_review_opinion": final_review_opinion,
            "error_code": error_code,
            "evidence_blocks": {
                "execution_summary": getattr(item, "execution_summary", None),
                "top_issues": tuple(getattr(item, "top_issues", ()) or ()),
                "regression_summary": getattr(item, "regression_summary", None),
                "scenario_coverage": getattr(item, "scenario_coverage", None),
                "performance_risk_items": tuple(getattr(item, "performance_risk_items", ()) or ()),
                "report_summary": dict(getattr(item, "report_summary", {}) or {}),
                "latest_audit_summary": dict(getattr(item, "latest_audit_summary", {}) or {}),
            },
            "case_trace": dict(getattr(item, "case_trace", {}) or {}),
            "source_refs": dict(getattr(item, "source_refs", {}) or {}),
            "source_links": dict(getattr(item, "source_links", {}) or {}),
            "ci_contract": dict(getattr(item, "ci_contract", {}) or {}),
            "lifecycle": {
                "state_machine_version": str(
                    getattr(item, "state_machine_version", "") or ADMISSION_CASE_STATE_MACHINE_VERSION
                ),
                "events": tuple(getattr(item, "lifecycle_events", ()) or ()),
            },
            "role_audit": {
                "entries": tuple(getattr(item, "role_audit_entries", ()) or ()),
            },
            "filters": dict(getattr(item, "filters", {}) or {}),
        }
    )


def admission_case_list_contract_payload(items: Sequence[AdmissionCase]) -> dict[str, Any]:
    """Return a stable JSON-ready list contract for AdmissionCase collections."""

    entries = [admission_case_contract_payload(item) for item in items]
    return {
        "contract_version": ADMISSION_CASE_LIST_CONTRACT_VERSION,
        "count": len(entries),
        "entries": entries,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if is_dataclass(value):
        return json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in dict(value).items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if hasattr(value, "__dict__"):
        return json_ready(vars(value))
    return value
