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
    DeviceRecordNotFound,
    RunRecordNotFound,
    SnapshotRecordNotFound,
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedTaskRecordNotFound,
)
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
from stability.app.admission_report_builder import risk_item_payload as _performance_risk_item_payload
from stability.cli.payloads_analysis import _issue_event_payload
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; payloads_rules.py owns this command/payload group.


def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)

def _rule_diff_payload(item: object) -> dict[str, object]:
    return {
        "path": getattr(item, "path", ""),
        "change_type": getattr(item, "change_type", ""),
        "left_value": getattr(item, "left_value", None),
        "right_value": getattr(item, "right_value", None),
    }


def _rule_replay_payload(item: object) -> dict[str, object]:
    return {
        "baseline": {
            "path": getattr(getattr(item, "baseline", object()), "path", ""),
            "fingerprint_rule_version": getattr(
                getattr(item, "baseline", object()),
                "fingerprint_rule_version",
                "",
            ),
        },
        "candidate": {
            "path": getattr(getattr(item, "candidate", object()), "path", ""),
            "fingerprint_rule_version": getattr(
                getattr(item, "candidate", object()),
                "fingerprint_rule_version",
                "",
            ),
        },
        "filters": dict(getattr(item, "filters", {}) or {}),
        "family_count": int(getattr(item, "family_count", 0) or 0),
        "changed_family_count": int(getattr(item, "changed_family_count", 0) or 0),
        "change_summary": dict(getattr(item, "change_summary", {}) or {}),
        "families": [
            {
                "comparison_key": getattr(family, "comparison_key", ""),
                "issue_type": getattr(family, "issue_type", ""),
                "package_name": getattr(family, "package_name", ""),
                "process_name": getattr(family, "process_name", ""),
                "scenario_name": getattr(family, "scenario_name", ""),
                "title": getattr(family, "title", ""),
                "change_type": getattr(family, "change_type", ""),
                "left_group_count": int(getattr(family, "left_group_count", 0) or 0),
                "right_group_count": int(getattr(family, "right_group_count", 0) or 0),
                "left_occurrence_count": int(getattr(family, "left_occurrence_count", 0) or 0),
                "right_occurrence_count": int(getattr(family, "right_occurrence_count", 0) or 0),
                "left_fingerprints": list(getattr(family, "left_fingerprints", ()) or ()),
                "right_fingerprints": list(getattr(family, "right_fingerprints", ()) or ()),
                "left_sample_event_ids": list(getattr(family, "left_sample_event_ids", ()) or ()),
                "right_sample_event_ids": list(getattr(family, "right_sample_event_ids", ()) or ()),
                "left_sample_events": [
                    _issue_event_payload(event) for event in (getattr(family, "left_sample_events", ()) or ())
                ],
                "right_sample_events": [
                    _issue_event_payload(event) for event in (getattr(family, "right_sample_events", ()) or ())
                ],
                "notes": list(getattr(family, "notes", ()) or ()),
            }
            for family in (getattr(item, "families", ()) or ())
        ],
    }


def _rule_replay_golden_suite_payload(item: object) -> dict[str, object]:
    return {
        "suite_path": getattr(item, "suite_path", ""),
        "suite_version": getattr(item, "suite_version", ""),
        "case_count": int(getattr(item, "case_count", 0) or 0),
        "passed_case_count": int(getattr(item, "passed_case_count", 0) or 0),
        "failed_case_count": int(getattr(item, "failed_case_count", 0) or 0),
        "layer_summaries": {
            str(key): dict(value)
            for key, value in dict(getattr(item, "layer_summaries", {}) or {}).items()
        },
        "passed": int(getattr(item, "failed_case_count", 0) or 0) == 0,
        "cases": [
            {
                "case_id": getattr(case, "case_id", ""),
                "description": getattr(case, "description", ""),
                "layer": getattr(case, "layer", ""),
                "expectation": getattr(case, "expectation", ""),
                "issue_type": getattr(case, "issue_type", ""),
                "passed": bool(getattr(case, "passed", False)),
                "mismatches": list(getattr(case, "mismatches", ()) or ()),
                "replay": (
                    _rule_replay_payload(getattr(case, "replay", object()))
                    if getattr(case, "replay", None) is not None
                    else None
                ),
            }
            for case in (getattr(item, "cases", ()) or ())
        ],
    }


def _rule_replay_golden_draft_payload(item: object) -> dict[str, object]:
    return {
        "output_path": getattr(item, "output_path", ""),
        "suite_version": getattr(item, "suite_version", ""),
        "appended": bool(getattr(item, "appended", False)),
        "case_id": getattr(item, "case_id", ""),
        "issue_type": getattr(item, "issue_type", ""),
        "layer": getattr(item, "layer", ""),
        "expectation": getattr(item, "expectation", ""),
        "issue_count": int(getattr(item, "issue_count", 0) or 0),
        "source_run_id": getattr(item, "source_run_id", ""),
        "selected_issue_ids": list(getattr(item, "selected_issue_ids", ()) or ()),
        "selected_instance_ids": list(getattr(item, "selected_instance_ids", ()) or ()),
        "baseline_path": getattr(item, "baseline_path", ""),
        "candidate_path": getattr(item, "candidate_path", ""),
        "expected": dict(getattr(item, "expected", {}) or {}),
        "replay_preview": (
            _rule_replay_payload(getattr(item, "replay_preview", object()))
            if getattr(item, "replay_preview", None) is not None
            else None
        ),
    }


def _rule_replay_golden_case_summary_payload(item: object) -> dict[str, object]:
    return {
        "case_id": getattr(item, "case_id", ""),
        "description": getattr(item, "description", ""),
        "issue_type": getattr(item, "issue_type", ""),
        "layer": getattr(item, "layer", ""),
        "expectation": getattr(item, "expectation", ""),
        "include_unchanged": bool(getattr(item, "include_unchanged", False)),
        "issue_count": int(getattr(item, "issue_count", 0) or 0),
        "package_name": getattr(item, "package_name", ""),
        "template_type": getattr(item, "template_type", ""),
        "source_run_id": getattr(item, "source_run_id", ""),
    }


def _rule_replay_golden_suite_listing_payload(item: object) -> dict[str, object]:
    return {
        "suite_path": getattr(item, "suite_path", ""),
        "suite_version": getattr(item, "suite_version", ""),
        "case_count": int(getattr(item, "case_count", 0) or 0),
        "filters": dict(getattr(item, "filters", {}) or {}),
        "layer_counts": dict(getattr(item, "layer_counts", {}) or {}),
        "issue_type_counts": dict(getattr(item, "issue_type_counts", {}) or {}),
        "expectation_counts": dict(getattr(item, "expectation_counts", {}) or {}),
        "cases": [
            _rule_replay_golden_case_summary_payload(case)
            for case in (getattr(item, "cases", ()) or ())
        ],
    }


def _rule_replay_golden_case_detail_payload(item: object) -> dict[str, object]:
    return {
        "suite_path": getattr(item, "suite_path", ""),
        "suite_version": getattr(item, "suite_version", ""),
        "summary": _rule_replay_golden_case_summary_payload(getattr(item, "summary", object())),
        "payload": dict(getattr(item, "payload", {}) or {}),
    }


def _rule_replay_golden_diff_payload(item: object) -> dict[str, object]:
    return {
        "left_path": getattr(item, "left_path", ""),
        "right_path": getattr(item, "right_path", ""),
        "left_suite_version": getattr(item, "left_suite_version", ""),
        "right_suite_version": getattr(item, "right_suite_version", ""),
        "diff_count": int(getattr(item, "diff_count", 0) or 0),
        "change_counts": dict(getattr(item, "change_counts", {}) or {}),
        "entries": [
            {
                "case_id": getattr(entry, "case_id", ""),
                "change_type": getattr(entry, "change_type", ""),
                "changed_fields": list(getattr(entry, "changed_fields", ()) or ()),
                "left_case": dict(getattr(entry, "left_case", {}) or {}),
                "right_case": dict(getattr(entry, "right_case", {}) or {}),
            }
            for entry in (getattr(item, "entries", ()) or ())
        ],
    }


def _rule_replay_golden_promotion_payload(item: object) -> dict[str, object]:
    return {
        "source_path": getattr(item, "source_path", ""),
        "target_path": getattr(item, "target_path", ""),
        "selected_case_ids": list(getattr(item, "selected_case_ids", ()) or ()),
        "promoted_case_ids": list(getattr(item, "promoted_case_ids", ()) or ()),
        "replaced_case_ids": list(getattr(item, "replaced_case_ids", ()) or ()),
        "skipped_case_ids": list(getattr(item, "skipped_case_ids", ()) or ()),
        "target_suite_version": getattr(item, "target_suite_version", ""),
        "source_suite_version": getattr(item, "source_suite_version", ""),
        "promoted_case_count": int(getattr(item, "promoted_case_count", 0) or 0),
        "replace_existing": bool(getattr(item, "replace_existing", False)),
        "acceptance": (
            _rule_replay_golden_suite_payload(getattr(item, "acceptance"))
            if getattr(item, "acceptance", None) is not None
            else None
        ),
    }


def _rule_review_payload(item: object) -> dict[str, object]:
    return {
        "decision": getattr(item, "decision", ""),
        "policy_version": getattr(item, "policy_version", ""),
        "policy_path": getattr(item, "policy_path", ""),
        "baseline_path": getattr(item, "baseline_path", ""),
        "candidate_path": getattr(item, "candidate_path", ""),
        "baseline_rule_version": getattr(item, "baseline_rule_version", ""),
        "candidate_rule_version": getattr(item, "candidate_rule_version", ""),
        "filters": dict(getattr(item, "filters", {}) or {}),
        "family_count": int(getattr(item, "family_count", 0) or 0),
        "changed_family_count": int(getattr(item, "changed_family_count", 0) or 0),
        "change_summary": dict(getattr(item, "change_summary", {}) or {}),
        "issue_type_change_summary": {
            str(key): dict(value)
            for key, value in dict(getattr(item, "issue_type_change_summary", {}) or {}).items()
        },
        "findings": [
            {
                "level": getattr(finding, "level", ""),
                "scope": getattr(finding, "scope", ""),
                "issue_type": getattr(finding, "issue_type", ""),
                "change_type": getattr(finding, "change_type", ""),
                "observed_count": int(getattr(finding, "observed_count", 0) or 0),
                "threshold": int(getattr(finding, "threshold", 0) or 0),
                "message": getattr(finding, "message", ""),
            }
            for finding in (getattr(item, "findings", ()) or ())
        ],
        "reasons": list(getattr(item, "reasons", ()) or ()),
        "baseline_valid": bool(getattr(item, "baseline_valid", False)),
        "candidate_valid": bool(getattr(item, "candidate_valid", False)),
        "baseline_errors": list(getattr(item, "baseline_errors", ()) or ()),
        "candidate_errors": list(getattr(item, "candidate_errors", ()) or ()),
        "golden_suite": (
            _rule_replay_golden_suite_payload(getattr(item, "golden_suite"))
            if getattr(item, "golden_suite", None) is not None
            else None
        ),
        "performance_summary": dict(getattr(item, "performance_summary", {}) or {}),
        "performance_risk_items": [
            _performance_risk_item_payload(entry)
            for entry in (getattr(item, "performance_risk_items", ()) or ())
        ],
        "families": [
            {
                "comparison_key": getattr(family, "comparison_key", ""),
                "issue_type": getattr(family, "issue_type", ""),
                "package_name": getattr(family, "package_name", ""),
                "process_name": getattr(family, "process_name", ""),
                "scenario_name": getattr(family, "scenario_name", ""),
                "title": getattr(family, "title", ""),
                "change_type": getattr(family, "change_type", ""),
                "left_group_count": int(getattr(family, "left_group_count", 0) or 0),
                "right_group_count": int(getattr(family, "right_group_count", 0) or 0),
                "left_occurrence_count": int(getattr(family, "left_occurrence_count", 0) or 0),
                "right_occurrence_count": int(getattr(family, "right_occurrence_count", 0) or 0),
                "left_fingerprints": list(getattr(family, "left_fingerprints", ()) or ()),
                "right_fingerprints": list(getattr(family, "right_fingerprints", ()) or ()),
                "left_sample_event_ids": list(getattr(family, "left_sample_event_ids", ()) or ()),
                "right_sample_event_ids": list(getattr(family, "right_sample_event_ids", ()) or ()),
                "left_sample_events": [
                    _issue_event_payload(event) for event in (getattr(family, "left_sample_events", ()) or ())
                ],
                "right_sample_events": [
                    _issue_event_payload(event) for event in (getattr(family, "right_sample_events", ()) or ())
                ],
                "notes": list(getattr(family, "notes", ()) or ()),
            }
            for family in (getattr(item, "families", ()) or ())
        ],
    }


def _rule_review_report_payload(item: object) -> dict[str, object]:
    return {
        "report_id": getattr(item, "report_id", ""),
        "name": getattr(item, "name", ""),
        "created_at": _isoformat_or_none(getattr(item, "created_at", None)),
        "created_by": getattr(item, "created_by", ""),
        "filters": dict(getattr(item, "filters", {}) or {}),
        "summary": dict(getattr(item, "summary", {}) or {}),
        "entries": [
            {
                "snapshot_id": getattr(entry, "snapshot_id", ""),
                "name": getattr(entry, "name", ""),
                "created_at": _isoformat_or_none(getattr(entry, "created_at", None)),
                "created_by": getattr(entry, "created_by", ""),
                "decision": getattr(entry, "decision", ""),
                "policy_version": getattr(entry, "policy_version", ""),
                "baseline_path": getattr(entry, "baseline_path", ""),
                "candidate_path": getattr(entry, "candidate_path", ""),
                "changed_family_count": int(getattr(entry, "changed_family_count", 0) or 0),
                "finding_count": int(getattr(entry, "finding_count", 0) or 0),
                "change_summary": dict(getattr(entry, "change_summary", {}) or {}),
                "reasons": list(getattr(entry, "reasons", ()) or ()),
                "golden_suite_passed": getattr(entry, "golden_suite_passed", None),
                "golden_suite_case_count": int(getattr(entry, "golden_suite_case_count", 0) or 0),
                "golden_suite_passed_case_count": int(
                    getattr(entry, "golden_suite_passed_case_count", 0) or 0
                ),
                "golden_suite_failed_case_count": int(
                    getattr(entry, "golden_suite_failed_case_count", 0) or 0
                ),
                "golden_suite_version": getattr(entry, "golden_suite_version", ""),
                "golden_suite_suite_path": getattr(entry, "golden_suite_suite_path", ""),
                "performance_summary": dict(getattr(entry, "performance_summary", {}) or {}),
                "performance_risk_items": [
                    _performance_risk_item_payload(risk)
                    for risk in (getattr(entry, "performance_risk_items", ()) or ())
                ],
                "detail_path": getattr(entry, "detail_path", ""),
                "markdown_path": getattr(entry, "markdown_path", ""),
            }
            for entry in (getattr(item, "entries", ()) or ())
        ],
        "high_risk_families": [
            {
                "family_key": getattr(entry, "family_key", ""),
                "issue_type": getattr(entry, "issue_type", ""),
                "package_name": getattr(entry, "package_name", ""),
                "scenario_name": getattr(entry, "scenario_name", ""),
                "title": getattr(entry, "title", ""),
                "change_type": getattr(entry, "change_type", ""),
                "snapshot_count": int(getattr(entry, "snapshot_count", 0) or 0),
                "total_occurrence_count": int(getattr(entry, "total_occurrence_count", 0) or 0),
                "highest_decision": getattr(entry, "highest_decision", ""),
                "sample_snapshot_ids": list(getattr(entry, "sample_snapshot_ids", ()) or ()),
            }
            for entry in (getattr(item, "high_risk_families", ()) or ())
        ],
        "detail_path": getattr(item, "detail_path", ""),
        "markdown_path": getattr(item, "markdown_path", ""),
        "html_path": getattr(item, "html_path", ""),
    }


def _rule_review_report_comparison_payload(item: object) -> dict[str, object]:
    return {
        "comparison_id": getattr(item, "comparison_id", ""),
        "name": getattr(item, "name", ""),
        "created_at": _isoformat_or_none(getattr(item, "created_at", None)),
        "created_by": getattr(item, "created_by", ""),
        "left_report_id": getattr(item, "left_report_id", ""),
        "right_report_id": getattr(item, "right_report_id", ""),
        "left_report_name": getattr(item, "left_report_name", ""),
        "right_report_name": getattr(item, "right_report_name", ""),
        "left_detail_path": getattr(item, "left_detail_path", ""),
        "right_detail_path": getattr(item, "right_detail_path", ""),
        "summary": dict(getattr(item, "summary", {}) or {}),
        "family_diffs": [
            {
                "family_key": getattr(entry, "family_key", ""),
                "issue_type": getattr(entry, "issue_type", ""),
                "package_name": getattr(entry, "package_name", ""),
                "scenario_name": getattr(entry, "scenario_name", ""),
                "title": getattr(entry, "title", ""),
                "change_type": getattr(entry, "change_type", ""),
                "delta_status": getattr(entry, "delta_status", ""),
                "left_snapshot_count": int(getattr(entry, "left_snapshot_count", 0) or 0),
                "right_snapshot_count": int(getattr(entry, "right_snapshot_count", 0) or 0),
                "left_total_occurrence_count": int(getattr(entry, "left_total_occurrence_count", 0) or 0),
                "right_total_occurrence_count": int(getattr(entry, "right_total_occurrence_count", 0) or 0),
                "left_highest_decision": getattr(entry, "left_highest_decision", ""),
                "right_highest_decision": getattr(entry, "right_highest_decision", ""),
            }
            for entry in (getattr(item, "family_diffs", ()) or ())
        ],
        "detail_path": getattr(item, "detail_path", ""),
        "markdown_path": getattr(item, "markdown_path", ""),
        "html_path": getattr(item, "html_path", ""),
    }


def _rule_review_report_baseline_payload(item: object) -> dict[str, object]:
    return {
        "baseline_key": getattr(item, "baseline_key", ""),
        "report_id": getattr(item, "report_id", ""),
        "report_name": getattr(item, "report_name", ""),
        "policy_versions": list(getattr(item, "policy_versions", ()) or ()),
        "candidate_paths": list(getattr(item, "candidate_paths", ()) or ()),
        "baseline_paths": list(getattr(item, "baseline_paths", ()) or ()),
        "report_created_at": _isoformat_or_none(getattr(item, "report_created_at", "")),
        "created_at": _isoformat_or_none(getattr(item, "created_at", None)),
        "updated_at": _isoformat_or_none(getattr(item, "updated_at", None)),
        "updated_by": getattr(item, "updated_by", ""),
        "latest_audit_id": getattr(item, "latest_audit_id", ""),
        "latest_audit_detail_path": getattr(item, "latest_audit_detail_path", ""),
        "latest_audit_markdown_path": getattr(item, "latest_audit_markdown_path", ""),
        "latest_audit_html_path": getattr(item, "latest_audit_html_path", ""),
        "latest_audit_index_path": getattr(item, "latest_audit_index_path", ""),
        "latest_audit_version_count": int(getattr(item, "latest_audit_version_count", 0) or 0),
    }


def _rule_review_report_baseline_promotion_payload(item: object) -> dict[str, object]:
    return {
        "baseline_key": getattr(item, "baseline_key", ""),
        "target_report_id": getattr(item, "target_report_id", ""),
        "target_report_name": getattr(item, "target_report_name", ""),
        "baseline_report_id": getattr(item, "baseline_report_id", ""),
        "baseline_report_name": getattr(item, "baseline_report_name", ""),
        "policy_version": getattr(item, "policy_version", ""),
        "approved": bool(getattr(item, "approved", False)),
        "promoted": bool(getattr(item, "promoted", False)),
        "reasons": list(getattr(item, "reasons", ()) or ()),
        "comparison_id": getattr(item, "comparison_id", ""),
        "comparison_detail_path": getattr(item, "comparison_detail_path", ""),
        "target_golden_suite": dict(getattr(item, "target_golden_suite", {}) or {}),
        "baseline_golden_suite": dict(getattr(item, "baseline_golden_suite", {}) or {}),
        "updated_baseline": (
            _rule_review_report_baseline_payload(getattr(item, "updated_baseline"))
            if getattr(item, "updated_baseline", None) is not None
            else None
        ),
    }


def _rule_review_report_baseline_history_payload(item: object) -> dict[str, object]:
    return {
        "revision_id": getattr(item, "revision_id", ""),
        "report_id": getattr(item, "report_id", ""),
        "report_name": getattr(item, "report_name", ""),
        "policy_versions": list(getattr(item, "policy_versions", ()) or ()),
        "candidate_paths": list(getattr(item, "candidate_paths", ()) or ()),
        "baseline_paths": list(getattr(item, "baseline_paths", ()) or ()),
        "report_created_at": _isoformat_or_none(getattr(item, "report_created_at", "")),
        "changed_at": _isoformat_or_none(getattr(item, "changed_at", None)),
        "changed_by": getattr(item, "changed_by", ""),
        "action": getattr(item, "action", ""),
        "reasons": list(getattr(item, "reasons", ()) or ()),
        "comparison_id": getattr(item, "comparison_id", ""),
        "comparison_detail_path": getattr(item, "comparison_detail_path", ""),
        "policy_version": getattr(item, "policy_version", ""),
    }


def _rule_review_report_baseline_rollback_payload(item: object) -> dict[str, object]:
    return {
        "baseline_key": getattr(item, "baseline_key", ""),
        "from_report_id": getattr(item, "from_report_id", ""),
        "from_report_name": getattr(item, "from_report_name", ""),
        "to_report_id": getattr(item, "to_report_id", ""),
        "to_report_name": getattr(item, "to_report_name", ""),
        "rolled_back": bool(getattr(item, "rolled_back", False)),
        "reasons": list(getattr(item, "reasons", ()) or ()),
        "updated_baseline": (
            _rule_review_report_baseline_payload(getattr(item, "updated_baseline"))
            if getattr(item, "updated_baseline", None) is not None
            else None
        ),
    }


def _rule_review_report_baseline_audit_payload(item: object) -> dict[str, object]:
    return {
        "audit_id": getattr(item, "audit_id", ""),
        "name": getattr(item, "name", ""),
        "created_at": _isoformat_or_none(getattr(item, "created_at", None)),
        "created_by": getattr(item, "created_by", ""),
        "baseline_key": getattr(item, "baseline_key", ""),
        "current_report_id": getattr(item, "current_report_id", ""),
        "current_report_name": getattr(item, "current_report_name", ""),
        "summary": dict(getattr(item, "summary", {}) or {}),
        "events": [
            {
                "revision_id": getattr(entry, "revision_id", ""),
                "action": getattr(entry, "action", ""),
                "changed_at": _isoformat_or_none(getattr(entry, "changed_at", None)),
                "changed_by": getattr(entry, "changed_by", ""),
                "from_report_id": getattr(entry, "from_report_id", ""),
                "from_report_name": getattr(entry, "from_report_name", ""),
                "to_report_id": getattr(entry, "to_report_id", ""),
                "to_report_name": getattr(entry, "to_report_name", ""),
                "reason_summary": getattr(entry, "reason_summary", ""),
                "reasons": list(getattr(entry, "reasons", ()) or ()),
                "comparison_id": getattr(entry, "comparison_id", ""),
                "comparison_detail_path": getattr(entry, "comparison_detail_path", ""),
                "policy_version": getattr(entry, "policy_version", ""),
            }
            for entry in (getattr(item, "events", ()) or ())
        ],
        "detail_path": getattr(item, "detail_path", ""),
        "markdown_path": getattr(item, "markdown_path", ""),
        "html_path": getattr(item, "html_path", ""),
    }


def _rule_review_report_baseline_audit_view_payload(item: object) -> dict[str, object]:
    return {
        "baseline": _rule_review_report_baseline_payload(getattr(item, "baseline")),
        "audit_id": getattr(item, "audit_id", ""),
        "audit_name": getattr(item, "audit_name", ""),
        "created_at": _isoformat_or_none(getattr(item, "created_at", None)),
        "created_by": getattr(item, "created_by", ""),
        "summary": dict(getattr(item, "summary", {}) or {}),
        "retention": dict(getattr(item, "retention", {}) or {}),
        "version_count": int(getattr(item, "version_count", 0) or 0),
        "versions": [
            {
                "revision_id": getattr(entry, "revision_id", ""),
                "action": getattr(entry, "action", ""),
                "changed_at": _isoformat_or_none(getattr(entry, "changed_at", None)),
                "changed_by": getattr(entry, "changed_by", ""),
                "report_id": getattr(entry, "report_id", ""),
                "report_name": getattr(entry, "report_name", ""),
                "audit_id": getattr(entry, "audit_id", ""),
                "summary": dict(getattr(entry, "summary", {}) or {}),
                "detail_path": getattr(entry, "detail_path", ""),
                "markdown_path": getattr(entry, "markdown_path", ""),
                "html_path": getattr(entry, "html_path", ""),
            }
            for entry in (getattr(item, "versions", ()) or ())
        ],
        "detail_path": getattr(item, "detail_path", ""),
        "markdown_path": getattr(item, "markdown_path", ""),
        "html_path": getattr(item, "html_path", ""),
        "index_path": getattr(item, "index_path", ""),
    }
