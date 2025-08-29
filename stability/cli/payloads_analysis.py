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
from stability.cli.payloads_longrun import _jsonable_mapping
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; payloads_analysis.py owns this command/payload group.


def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)

def _aggregated_issue_payload(item: AggregatedIssue, *, include_samples: bool) -> dict[str, object]:
    metadata = dict(getattr(item, "metadata", {}) or {})
    payload = {
        "fingerprint": item.fingerprint.value,
        "rule_version": item.fingerprint.rule_version,
        "fingerprint_components": dict(item.fingerprint.components),
        "issue_type": item.issue_type.value,
        "title": item.title,
        "severity": item.severity.value,
        "first_seen_at": _isoformat_or_none(item.first_seen_at),
        "last_seen_at": _isoformat_or_none(item.last_seen_at),
        "occurrence_count": item.occurrence_count,
        "affected_run_count": item.affected_run_count,
        "affected_device_count": item.affected_device_count,
        "affected_scenario_count": item.affected_scenario_count,
        "affected_version_count": item.affected_version_count,
        "affected_packages": list(item.affected_packages),
        "affected_devices": list(item.affected_devices),
        "affected_scenarios": list(item.affected_scenarios),
        "affected_versions": list(item.affected_versions),
        "sample_event_ids": list(item.sample_event_ids),
        "score": item.score,
        "score_breakdown": dict(item.score_breakdown),
        "metadata": metadata,
    }
    _append_advanced_issue_evidence(payload, item=item, metadata=metadata)
    if include_samples:
        payload["sample_events"] = [_issue_event_payload(sample) for sample in item.sample_events]
    return payload


def _issue_event_payload(item: IssueEventReference) -> dict[str, object]:
    metadata = dict(getattr(item, "metadata", {}) or {})
    payload = {
        "event_id": item.event_id,
        "run_id": item.run_id,
        "task_id": item.task_id,
        "task_name": item.task_name,
        "instance_id": item.instance_id,
        "device_id": item.device_id,
        "package_name": item.package_name,
        "scenario_name": item.scenario_name,
        "issue_type": item.issue_type.value,
        "severity": item.severity.value,
        "detected_at": _isoformat_or_none(item.detected_at),
        "summary": item.summary,
        "report_path": item.report_path,
        "execution_log_path": item.execution_log_path,
        "artifact_paths": list(item.artifact_paths),
        "metadata": metadata,
    }
    _append_advanced_issue_evidence(payload, item=item, metadata=metadata)
    return payload


def _append_advanced_issue_evidence(
    payload: dict[str, object],
    *,
    item: object,
    metadata: Mapping[str, object],
) -> None:
    evidence_signals = getattr(item, "evidence_signals", None)
    if evidence_signals is None:
        evidence_signals = metadata.get("evidence_signals")
    if evidence_signals:
        payload["evidence_signals"] = list(evidence_signals) if isinstance(evidence_signals, (list, tuple)) else evidence_signals
    confirmation_level = str(getattr(item, "confirmation_level", "") or metadata.get("confirmation_level", "") or "")
    if confirmation_level:
        payload["confirmation_level"] = confirmation_level


def _issue_attribution_payload(item: IssueAttribution) -> dict[str, object]:
    payload: dict[str, object] = {
        "fingerprint": item.fingerprint,
        "issue_type": getattr(item.issue_type, "value", item.issue_type),
        "title": item.title,
        "direction": item.direction,
        "direction_label": item.direction_label,
        "confidence": item.confidence,
        "summary": item.summary,
        "rule_version": item.rule_version,
        "matched_rule_id": item.matched_rule_id,
        "matched_rule_name": item.matched_rule_name,
        "score": item.score,
        "sample_event_ids": list(item.sample_event_ids),
        "hits": [
            {
                "field": hit.field,
                "keyword": hit.keyword,
                "evidence": hit.evidence,
                "score": hit.score,
            }
            for hit in item.hits
        ],
        "notes": list(item.notes),
    }
    for field in (
        "confidence_score",
        "matched_rule_ids",
        "evidence_summary",
        "recommended_next_steps",
        "review_notes",
    ):
        if not hasattr(item, field):
            continue
        value = getattr(item, field)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            payload[field] = list(value)
        else:
            payload[field] = value
    return payload


def _compared_issue_payload(item: ComparedIssue) -> dict[str, object]:
    return {
        "comparison_key": item.comparison_key,
        "title": item.title,
        "issue_type": item.issue_type,
        "severity": item.severity,
        "change_type": item.change_type,
        "occurrence_delta": item.occurrence_delta,
        "left_fingerprint": item.left_fingerprint,
        "right_fingerprint": item.right_fingerprint,
        "left_occurrence_count": item.left_occurrence_count,
        "right_occurrence_count": item.right_occurrence_count,
        "left_affected_run_count": item.left_affected_run_count,
        "right_affected_run_count": item.right_affected_run_count,
        "left_affected_device_count": item.left_affected_device_count,
        "right_affected_device_count": item.right_affected_device_count,
        "left_affected_scenario_count": item.left_affected_scenario_count,
        "right_affected_scenario_count": item.right_affected_scenario_count,
        "left_sample_event_ids": list(item.left_sample_event_ids),
        "right_sample_event_ids": list(item.right_sample_event_ids),
        "left_sample_events": [_issue_event_payload(event) for event in item.left_sample_events],
        "right_sample_events": [_issue_event_payload(event) for event in item.right_sample_events],
    }


def _comparison_result_payload(item: ComparisonResult) -> dict[str, object]:
    return {
        "dimension": item.dimension,
        "left_scope": {
            "dimension": item.left_scope.dimension,
            "value": item.left_scope.value,
            "label": item.left_scope.label,
            "filters": dict(item.left_scope.filters),
        },
        "right_scope": {
            "dimension": item.right_scope.dimension,
            "value": item.right_scope.value,
            "label": item.right_scope.label,
            "filters": dict(item.right_scope.filters),
        },
        "base_filters": dict(item.base_filters),
        "sample_summary": dict(item.sample_summary),
        "issue_change_summary": dict(item.issue_change_summary),
        "metric_change_summary": dict(item.metric_change_summary),
        "comparability_notes": list(item.comparability_notes),
        "issue_count": len(item.issues),
        "issues": [_compared_issue_payload(issue) for issue in item.issues],
    }


def _metric_trend_summary_payload(item: MetricTrendSummary) -> dict[str, object]:
    return {
        "metric_key": item.metric_key,
        "label": item.label,
        "unit": item.unit,
        "sample_count": item.sample_count,
        "session_count": item.session_count,
        "average": item.average,
        "peak": item.peak,
        "p95": item.p95,
        "latest": item.latest,
    }


def _compared_metric_trend_payload(item: ComparedMetricTrend) -> dict[str, object]:
    return {
        "metric_key": item.metric_key,
        "label": item.label,
        "unit": item.unit,
        "higher_is_worse": item.higher_is_worse,
        "left_summary": _metric_trend_summary_payload(item.left_summary),
        "right_summary": _metric_trend_summary_payload(item.right_summary),
        "average_delta": item.average_delta,
        "peak_delta": item.peak_delta,
        "p95_delta": item.p95_delta,
        "latest_delta": item.latest_delta,
        "change_type": item.change_type,
    }


def _performance_trend_payload(item: PerformanceTrendComparison) -> dict[str, object]:
    return {
        "dimension": item.dimension,
        "left_scope": {
            "dimension": item.left_scope.dimension,
            "value": item.left_scope.value,
            "label": item.left_scope.label,
            "filters": dict(item.left_scope.filters),
        },
        "right_scope": {
            "dimension": item.right_scope.dimension,
            "value": item.right_scope.value,
            "label": item.right_scope.label,
            "filters": dict(item.right_scope.filters),
        },
        "base_filters": dict(item.base_filters),
        "sample_summary": dict(item.sample_summary),
        "metric_change_summary": dict(item.metric_change_summary),
        "comparability_notes": list(item.comparability_notes),
        "metric_count": len(item.metrics),
        "metrics": [_compared_metric_trend_payload(metric) for metric in item.metrics],
    }


def _regressed_issue_payload(item: RegressedIssue) -> dict[str, object]:
    return {
        "comparison_key": item.comparison_key,
        "title": item.title,
        "issue_type": item.issue_type,
        "severity": item.severity,
        "regression_result": item.regression_result,
        "change_type": item.change_type,
        "reason": item.reason,
        "occurrence_delta": item.occurrence_delta,
        "left_fingerprint": item.left_fingerprint,
        "right_fingerprint": item.right_fingerprint,
        "left_occurrence_count": item.left_occurrence_count,
        "right_occurrence_count": item.right_occurrence_count,
        "left_affected_run_count": item.left_affected_run_count,
        "right_affected_run_count": item.right_affected_run_count,
        "left_affected_device_count": item.left_affected_device_count,
        "right_affected_device_count": item.right_affected_device_count,
        "left_affected_scenario_count": item.left_affected_scenario_count,
        "right_affected_scenario_count": item.right_affected_scenario_count,
    }


def _regressed_metric_payload(item: RegressedMetric) -> dict[str, object]:
    return {
        "metric_key": item.metric_key,
        "label": item.label,
        "unit": item.unit,
        "higher_is_worse": item.higher_is_worse,
        "regression_result": item.regression_result,
        "change_type": item.change_type,
        "reason": item.reason,
        "left_summary": _metric_trend_summary_payload(item.left_summary),
        "right_summary": _metric_trend_summary_payload(item.right_summary),
        "average_delta": item.average_delta,
        "peak_delta": item.peak_delta,
        "p95_delta": item.p95_delta,
        "latest_delta": item.latest_delta,
    }


def _regression_result_payload(item: RegressionResult) -> dict[str, object]:
    return {
        "dimension": item.dimension,
        "left_scope": {
            "dimension": item.left_scope.dimension,
            "value": item.left_scope.value,
            "label": item.left_scope.label,
            "filters": dict(item.left_scope.filters),
        },
        "right_scope": {
            "dimension": item.right_scope.dimension,
            "value": item.right_scope.value,
            "label": item.right_scope.label,
            "filters": dict(item.right_scope.filters),
        },
        "base_filters": dict(item.base_filters),
        "rule_set": item.rule_set.as_dict(),
        "overall_result": item.overall_result,
        "issue_result_summary": dict(item.issue_result_summary),
        "metric_result_summary": dict(item.metric_result_summary),
        "summary": dict(item.summary),
        "reasons": list(item.reasons),
        "comparability_notes": list(item.comparability_notes),
        "issue_count": len(item.issues),
        "metric_count": len(item.metrics),
        "issues": [_regressed_issue_payload(issue) for issue in item.issues],
        "metrics": [_regressed_metric_payload(metric) for metric in item.metrics],
    }


def _analysis_snapshot_summary_payload(item: AnalysisSnapshotSummary) -> dict[str, object]:
    return {
        "snapshot_id": item.snapshot_id,
        "snapshot_type": item.snapshot_type,
        "name": item.name,
        "created_at": _isoformat_or_none(item.created_at),
        "created_by": item.created_by,
        "detail_path": item.detail_path,
        "markdown_path": item.markdown_path,
        "summary": dict(item.summary),
        "filters": dict(item.filters),
        "rule_versions": dict(item.rule_versions),
        "source_summary": dict(getattr(item, "source_summary", {}) or {}),
    }


def _analysis_snapshot_record_payload(item: AnalysisSnapshotRecord) -> dict[str, object]:
    return {
        "snapshot_id": item.snapshot_id,
        "snapshot_type": item.snapshot_type,
        "name": item.name,
        "created_at": _isoformat_or_none(item.created_at),
        "created_by": item.created_by,
        "scope": dict(item.scope),
        "filters": dict(item.filters),
        "data_range": dict(item.data_range),
        "rule_versions": dict(item.rule_versions),
        "summary": dict(item.summary),
        "source_refs": dict(getattr(item, "source_refs", {}) or {}),
        "detail_path": item.detail_path,
        "markdown_path": item.markdown_path,
        "payload": dict(item.payload),
        "tags": list(item.tags),
    }


def _rule_validation_payload(item: object) -> dict[str, object]:
    return {
        "path": getattr(item, "path", ""),
        "source_exists": bool(getattr(item, "source_exists", False)),
        "valid": bool(getattr(item, "valid", False)),
        "error_count": len(getattr(item, "errors", ()) or ()),
        "warning_count": len(getattr(item, "warnings", ()) or ()),
        "errors": list(getattr(item, "errors", ()) or ()),
        "warnings": list(getattr(item, "warnings", ()) or ()),
    }


def _rule_inspection_payload(item: object) -> dict[str, object]:
    return {
        "path": getattr(item, "path", ""),
        "source_exists": bool(getattr(item, "source_exists", False)),
        "validation": _rule_validation_payload(getattr(item, "validation", object())),
        "source_rules": dict(getattr(item, "source_rules", {}) or {}),
        "default_rules": dict(getattr(item, "default_rules", {}) or {}),
        "effective_rules": dict(getattr(item, "effective_rules", {}) or {}),
    }


def _describe_rule_entrypoint_payload(
    service: object,
    *,
    path_override: str | None = None,
) -> dict[str, object]:
    describe_method = getattr(service, "describe_rule_entrypoint", None)
    if callable(describe_method):
        result = _call_rule_service_method(
            describe_method,
            (
                ((), {"path": path_override}),
                ((path_override,), {}),
                ((), {}),
            ),
        )
        if result is not None:
            payload = _jsonable_mapping(result)
        payload.setdefault("source", "service")
        payload.setdefault("write_policy", "governed_candidate_publish")
        return payload

    inspection = service.inspect_rules(path_override) if hasattr(service, "inspect_rules") else object()
    validation = getattr(inspection, "validation", object())
    source_path = str(getattr(inspection, "path", "") or path_override or "")
    effective_rules = dict(getattr(inspection, "effective_rules", {}) or {})
    source_rules = dict(getattr(inspection, "source_rules", {}) or {})
    return {
        "source": "fallback",
        "contract_version": "asl.rule_entrypoint.v1",
        "config_path": source_path,
        "current_version": str(
            effective_rules.get("version")
            or source_rules.get("version")
            or effective_rules.get("rule_version")
            or ""
        ),
        "source_exists": bool(getattr(inspection, "source_exists", False)),
        "validation": _rule_validation_payload(validation),
        "editable_fields": [
            "version",
            "fingerprint_rules",
            "issue_group_rules",
            "performance_thresholds",
            "risk_policies",
        ],
        "risk_prompts": [
            "规则变更会影响 issue 聚合、准入门禁和历史对比口径。",
            "请先运行 preview-analysis-rule-update、diff-analysis-rules、review-analysis-rules 和 golden replay，再由审计流程落库。",
        ],
        "recommended_flow": [
            "describe-rule-entrypoint",
            "preview-analysis-rule-update --set <field>=<value>",
            "diff-analysis-rules",
            "review-analysis-rules",
            "verify-rule-replay-goldens",
            "promote-rule-review-report-baseline",
        ],
        "related_policy_files": [
            source_path,
            "config/stability_rules.json",
            "config/stability_rules.base.json",
            "config/rule_replay_golden_samples.json",
        ],
        "write_policy": "preview_only_no_config_write",
    }


def _preview_analysis_rule_update_payload(
    service: object,
    *,
    path_override: str | None,
    updates: Mapping[str, object],
) -> dict[str, object]:
    edit_request = _rule_update_edit_request(updates)
    preview_rule_update_method = getattr(service, "preview_rule_update", None)
    if callable(preview_rule_update_method):
        result = _call_rule_service_method(
            preview_rule_update_method,
            (
                ((edit_request["patch"],), {"path": path_override}),
                ((), {"patch": edit_request["patch"], "path": path_override}),
                ((edit_request["patch"],), {}),
            ),
        )
        if result is not None:
            payload = _rule_update_service_preview_payload(result, path_override=path_override)
            return payload

    build_edit_plan_method = getattr(service, "build_rule_edit_plan", None)
    if callable(build_edit_plan_method):
        attempts: list[tuple[tuple[object, ...], dict[str, object]]] = []
        single_edit = edit_request.get("single_edit")
        if isinstance(single_edit, Mapping):
            attempts.append(
                (
                    (),
                    {
                        "section": single_edit.get("section"),
                        "key": single_edit.get("key"),
                        "value": single_edit.get("value"),
                        "path": path_override,
                    },
                )
            )
        attempts.extend(
            (
                ((), {"patch": edit_request["patch"], "path": path_override}),
                ((), {"patch": edit_request["patch"]}),
            )
        )
        result = _call_rule_service_method(build_edit_plan_method, tuple(attempts))
        if result is not None:
            payload = _rule_update_service_preview_payload(result, path_override=path_override)
            return payload

    preview_method = getattr(service, "preview_analysis_rule_update", None)
    if callable(preview_method):
        result = _call_rule_service_method(
            preview_method,
            (
                ((), {"path": path_override, "updates": dict(updates)}),
                ((dict(updates),), {"path": path_override}),
                ((path_override, dict(updates)), {}),
                ((), {"updates": dict(updates)}),
            ),
        )
        if result is not None:
            payload = _jsonable_mapping(result)
            payload.setdefault("source", "service")
            payload.setdefault("write_policy", "preview_only_no_config_write")
            return payload

    entrypoint = _describe_rule_entrypoint_payload(service, path_override=path_override)
    editable_fields = {str(item) for item in list(entrypoint.get("editable_fields", []) or [])}
    requested_fields = [str(key) for key in updates.keys()]
    unknown_fields = [field for field in requested_fields if editable_fields and field not in editable_fields]
    return {
        "source": "fallback",
        "contract_version": "asl.rule_update_preview.v1",
        "config_path": str(entrypoint.get("config_path", "") or path_override or ""),
        "current_version": str(entrypoint.get("current_version", "") or ""),
        "updates": dict(updates),
        "changed_field_count": len(updates),
        "unknown_fields": unknown_fields,
        "validation": dict(entrypoint.get("validation", {}) or {}),
        "risk_prompts": list(entrypoint.get("risk_prompts", []) or []),
        "recommended_flow": list(entrypoint.get("recommended_flow", []) or []),
        "related_policy_files": list(entrypoint.get("related_policy_files", []) or []),
        "write_policy": "preview_only_no_config_write",
    }


def _rule_update_service_preview_payload(
    result: Mapping[str, object],
    *,
    path_override: str | None,
) -> dict[str, object]:
    payload = dict(result)
    payload.setdefault("source", "service")
    payload.setdefault("write_policy", "preview_only_no_config_write")
    if "config_path" not in payload and payload.get("rule_path"):
        payload["config_path"] = payload["rule_path"]
    if "config_path" not in payload and path_override:
        payload["config_path"] = path_override
    if "changed_field_count" not in payload:
        patch = payload.get("patch", {})
        payload["changed_field_count"] = _rule_patch_field_count(patch if isinstance(patch, Mapping) else {})
    return payload


def _rule_update_edit_request(updates: Mapping[str, object]) -> dict[str, object]:
    patch: dict[str, object] = {}
    parsed_edits: list[dict[str, object]] = []
    for raw_key, value in updates.items():
        section, key = _rule_update_section_key(str(raw_key))
        if section and key:
            section_patch = patch.setdefault(section, {})
            if isinstance(section_patch, dict):
                section_patch[key] = value
            parsed_edits.append({"section": section, "key": key, "value": value})
        else:
            patch[str(raw_key)] = value
    return {
        "patch": patch,
        "single_edit": parsed_edits[0] if len(parsed_edits) == 1 and len(updates) == 1 else None,
    }


def _rule_update_section_key(raw_key: str) -> tuple[str | None, str | None]:
    key = raw_key.strip()
    if "." in key:
        section, field = key.split(".", 1)
        section = section.strip()
        field = field.strip()
        if section and field:
            return section, field
    if key == "version":
        return "fingerprint", "version"
    return None, None


def _rule_patch_field_count(patch: Mapping[str, object]) -> int:
    count = 0
    for value in patch.values():
        if isinstance(value, Mapping):
            count += len(value)
        else:
            count += 1
    return count


def _call_rule_service_method(
    method: object,
    attempts: Sequence[tuple[tuple[object, ...], dict[str, object]]],
) -> dict[str, object] | None:
    for args, kwargs in attempts:
        clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
        try:
            result = method(*args, **clean_kwargs)  # type: ignore[misc]
        except TypeError:
            continue
        except Exception:
            return None
        return _jsonable_mapping(result)
    return None
