from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.app import (
    AggregatedIssueNotFound,
    DeviceRecordNotFound,
    RunRecordNotFound,
    SnapshotRecordNotFound,
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedTaskRecordNotFound,
)
from stability.app.admission_case_contract_payload import admission_case_contract_payload, json_ready
from stability.app.task_service import TaskRecordNotFound
from stability.domain import (
    AggregatedIssue,
    AnalysisSnapshotRecord,
    AnalysisSnapshotSummary,
    ComparedMetricTrend,
    ComparedIssue,
    ComparisonResult,
    IssueEventReference,
    IssueAttribution,
    MetricTrendSummary,
    PerformanceTrendComparison,
    RegressedIssue,
    RegressedMetric,
    RegressionResult,
    SamplingConfig,
    TaskDefinition,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.cli.handlers.web import handle_serve_web as _web_handle_serve_web
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; payloads_admission.py owns this command/payload group.


def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)

def _admission_case_payload(item: object) -> dict[str, object]:
    if isinstance(item, Mapping):
        return json_ready(dict(item))
    return admission_case_contract_payload(item)


def _admission_report_payload_from_bundle(bundle: object, baseline_key: str) -> dict[str, object]:
    service = getattr(bundle, "admission_case_service", None)
    if service is None:
        raise SystemExit("Admission case service is unavailable.")
    for method_name in (
        "export_admission_report_payload",
        "build_admission_report",
        "build_admission_report_payload",
        "get_admission_report_payload",
        "build_report_payload",
        "get_report_payload",
    ):
        method = getattr(service, method_name, None)
        if method is None:
            continue
        try:
            return _normalize_admission_report_payload(method(baseline_key=baseline_key), source="service")
        except TypeError:
            return _normalize_admission_report_payload(method(baseline_key), source="service")
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    if not hasattr(service, "get_case"):
        raise SystemExit("Admission report service method is unavailable.")
    try:
        case = service.get_case(baseline_key)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return _fallback_admission_report_payload(case)


def _normalize_admission_report_payload(item: object, *, source: str) -> dict[str, object]:
    if isinstance(item, Mapping):
        payload = dict(item)
    elif hasattr(item, "__dataclass_fields__"):
        payload = _jsonable_mapping(item)
    else:
        payload = {
            "report_contract_version": str(getattr(item, "report_contract_version", "") or "admission_report.v1"),
            "report_id": str(getattr(item, "report_id", "") or ""),
            "baseline_key": str(getattr(item, "baseline_key", "") or ""),
            "status": str(getattr(item, "status", "") or ""),
            "final_decision": str(getattr(item, "final_decision", "") or ""),
            "risk_level": str(getattr(item, "risk_level", "") or ""),
            "quality_gate_summary": dict(getattr(item, "quality_gate_summary", {}) or {}),
            "top_issue_summary": dict(getattr(item, "top_issue_summary", {}) or {}),
            "performance_risk_summary": dict(getattr(item, "performance_risk_summary", {}) or {}),
            "manual_overrides": dict(getattr(item, "manual_overrides", {}) or {}),
            "collaboration_summary": dict(getattr(item, "collaboration_summary", {}) or {}),
            "external_sync_summary": dict(getattr(item, "external_sync_summary", {}) or {}),
            "evidence_refs": dict(getattr(item, "evidence_refs", {}) or {}),
            "source_refs": dict(getattr(item, "source_refs", {}) or {}),
            "recommended_actions": list(getattr(item, "recommended_actions", ()) or ()),
            "generated_at": _isoformat_or_none(getattr(item, "generated_at", None)),
        }
    if "formal_report" in payload and isinstance(payload["formal_report"], Mapping):
        payload = dict(payload["formal_report"])
    payload["report_contract_version"] = str(payload.get("report_contract_version", "") or "admission_report.v1")
    payload["source"] = str(payload.get("source", "") or source)
    if "recommended_actions" in payload:
        payload["recommended_actions"] = list(payload.get("recommended_actions") or [])
    return payload


def _fallback_admission_report_payload(item: object) -> dict[str, object]:
    case = _admission_case_payload(item)
    quality_gate = getattr(item, "quality_gate", None)
    quality_gate_payload = _quality_gate_like_payload(quality_gate) if quality_gate is not None else {}
    quality_gate_summary = {
        "automatic_decision": quality_gate_payload.get("automatic_decision", ""),
        "final_decision": case.get("final_decision", ""),
        "error_code": case.get("error_code", ""),
        "triggered_rule_count": quality_gate_payload.get("triggered_rule_count", 0),
        "risk_count": quality_gate_payload.get("risk_count", 0),
        "performance_risk_count": len(list(case.get("performance_risk_items", []) or [])),
        "coverage_gap_count": quality_gate_payload.get("coverage_gap_count", 0),
    }
    top_issues = list(case.get("top_issues", []) or [])
    performance_risks = list(case.get("performance_risk_items", []) or [])
    override = quality_gate_payload.get("override") or case.get("override") or {}
    return {
        "report_contract_version": "admission_report.v1",
        "source": "fallback",
        "report_id": str(case.get("report_id", "") or ""),
        "baseline_key": str(case.get("baseline_key", "") or ""),
        "status": str(case.get("status", "") or ""),
        "final_decision": str(case.get("final_decision", "") or ""),
        "risk_level": _derive_admission_report_risk_level(
            final_decision=str(case.get("final_decision", "") or ""),
            top_issue_count=len(top_issues),
            performance_risk_count=len(performance_risks),
            quality_gate_summary=quality_gate_summary,
        ),
        "quality_gate_summary": quality_gate_summary,
        "top_issue_summary": {
            "count": len(top_issues),
            "items": top_issues[:5],
        },
        "performance_risk_summary": {
            "count": len(performance_risks),
            "items": performance_risks[:5],
        },
        "manual_overrides": {
            "has_override": bool(override),
            "override": dict(override) if isinstance(override, Mapping) else {},
            "final_review_opinion": str(case.get("final_review_opinion", "") or ""),
        },
        "collaboration_summary": {
            "assignee_id": str(case.get("assignee_id", "") or ""),
            "assignee_display_name": str(case.get("assignee_display_name", "") or ""),
            "final_reviewer_id": str(case.get("final_reviewer_id", "") or ""),
            "final_reviewer_display_name": str(case.get("final_reviewer_display_name", "") or ""),
            "status": str(case.get("status", "") or ""),
            "revision": int(case.get("revision", 1) or 1),
        },
        "external_sync_summary": {
            "ci_contract": dict(case.get("ci_contract", {}) or {}),
            "source_links": dict(case.get("source_links", {}) or {}),
        },
        "evidence_refs": dict(case.get("source_refs", {}) or {}),
        "source_refs": dict(case.get("source_refs", {}) or {}),
        "recommended_actions": _admission_report_recommended_actions(
            final_decision=str(case.get("final_decision", "") or ""),
            top_issue_count=len(top_issues),
            performance_risk_count=len(performance_risks),
            has_override=bool(override),
        ),
        "generated_at": None,
    }


def _quality_gate_like_payload(item: object) -> dict[str, object]:
    if isinstance(item, Mapping):
        getter = item.get
    else:
        getter = lambda key, default=None: getattr(item, key, default)
    return {
        "automatic_decision": str(getter("automatic_decision", "") or ""),
        "triggered_rule_count": len(list(getter("triggered_rules", ()) or ())),
        "risk_count": len(list(getter("risk_items", ()) or ())),
        "performance_risk_count": len(list(getter("performance_risk_items", ()) or ())),
        "coverage_gap_count": len(list(getter("coverage_gaps", ()) or ())),
        "override": getter("override", None),
    }


def _derive_admission_report_risk_level(
    *,
    final_decision: str,
    top_issue_count: int,
    performance_risk_count: int,
    quality_gate_summary: Mapping[str, object],
) -> str:
    decision = final_decision.strip().lower()
    if decision in {"fail", "reject", "rejected", "block"}:
        return "critical"
    if top_issue_count > 0 or int(quality_gate_summary.get("risk_count", 0) or 0) > 0:
        return "high"
    if performance_risk_count > 0 or int(quality_gate_summary.get("coverage_gap_count", 0) or 0) > 0:
        return "medium"
    if decision in {"pass", "approved"}:
        return "low"
    return "unknown"


def _admission_report_recommended_actions(
    *,
    final_decision: str,
    top_issue_count: int,
    performance_risk_count: int,
    has_override: bool,
) -> list[str]:
    actions: list[str] = []
    decision = final_decision.strip().lower()
    if decision in {"fail", "reject", "rejected", "block"}:
        actions.append("Block release and resolve failing admission evidence before retry.")
    if top_issue_count > 0:
        actions.append("Review top issues and confirm owner, scenario coverage, and fix plan.")
    if performance_risk_count > 0:
        actions.append("Review performance risks against scoped thresholds before final sign-off.")
    if has_override:
        actions.append("Audit manual override reason and evidence before external write-back.")
    if not actions:
        actions.append("No blocking evidence found; proceed with standard release sign-off.")
    return actions
