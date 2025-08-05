from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from stability.app.admission_case_store import datetime_or_none
from stability.domain import (
    AdmissionCaseExecutionSummary,
    AdmissionCaseRegressionSummary,
    AdmissionCaseScenarioCoverage,
    AdmissionCaseTopIssue,
)

RUN_FILTER_KEYS = ("task_id", "run_status", "template_type", "package_name", "device_id", "created_from", "created_to")
REGRESSION_FILTER_KEYS = RUN_FILTER_KEYS + ("dimension", "left_value", "right_value")


def execution_summary(service: object | None, filters: Mapping[str, Any]) -> AdmissionCaseExecutionSummary:
    if service is None or not hasattr(service, "list_runs"):
        return AdmissionCaseExecutionSummary()

    payload = service.list_runs(limit=20, **scoped_filters(filters, keys=RUN_FILTER_KEYS))
    runs = [dict(item) for item in list(payload or []) if isinstance(item, Mapping)]
    status_counts = Counter(str(item.get("run_status", "") or "unknown") for item in runs)
    failed_run_count = sum(
        count for status, count in status_counts.items() if status in {"failed", "partial_failed", "timeout"}
    )
    issue_run_count = sum(
        1 for item in runs if bool(item.get("has_issue")) or str(item.get("run_status", "")) in {"failed", "partial_failed"}
    )
    latest = runs[0] if runs else {}
    return AdmissionCaseExecutionSummary(
        total_runs=len(runs),
        status_counts=dict(status_counts),
        failed_run_count=failed_run_count,
        issue_run_count=issue_run_count,
        task_ids=tuple(sorted({str(item.get("task_id", "") or "") for item in runs if str(item.get("task_id", "")).strip()})),
        task_names=tuple(sorted({str(item.get("task_name", "") or "") for item in runs if str(item.get("task_name", "")).strip()})),
        package_names=tuple(
            sorted({str(item.get("package_name", "") or "") for item in runs if str(item.get("package_name", "")).strip()})
        ),
        template_types=tuple(
            sorted({str(item.get("template_type", "") or "") for item in runs if str(item.get("template_type", "")).strip()})
        ),
        device_ids=tuple(
            sorted(
                {
                    str(device_id)
                    for item in runs
                    for device_id in list(item.get("target_device_ids", []) or [])
                    if str(device_id).strip()
                }
            )
        ),
        latest_run_id=str(latest.get("run_id", "") or ""),
        latest_run_status=str(latest.get("run_status", "") or ""),
        latest_run_created_at=datetime_or_none(latest.get("created_at")),
        recent_runs=tuple(runs[:5]),
    )


def top_issues(service: object | None, filters: Mapping[str, Any]) -> tuple[AdmissionCaseTopIssue, ...]:
    if service is None or not hasattr(service, "list_top_issues"):
        return ()
    items = service.list_top_issues(limit=5, **scoped_filters(filters, keys=RUN_FILTER_KEYS))
    result: list[AdmissionCaseTopIssue] = []
    for item in list(items or []):
        result.append(
            AdmissionCaseTopIssue(
                fingerprint=str(getattr(getattr(item, "fingerprint", None), "value", "") or ""),
                title=str(getattr(item, "title", "") or ""),
                issue_type=str(getattr(getattr(item, "issue_type", None), "value", getattr(item, "issue_type", "")) or ""),
                severity=str(getattr(getattr(item, "severity", None), "value", getattr(item, "severity", "")) or ""),
                occurrence_count=int(getattr(item, "occurrence_count", 0) or 0),
                affected_run_count=int(getattr(item, "affected_run_count", 0) or 0),
                affected_device_count=int(getattr(item, "affected_device_count", 0) or 0),
                affected_scenario_count=int(getattr(item, "affected_scenario_count", 0) or 0),
                last_seen_at=datetime_or_none(getattr(item, "last_seen_at", None)),
                affected_scenarios=tuple(getattr(item, "affected_scenarios", ()) or ()),
                affected_versions=tuple(getattr(item, "affected_versions", ()) or ()),
            )
        )
    return tuple(result)


def regression_summary(service: object | None, filters: Mapping[str, Any]) -> AdmissionCaseRegressionSummary:
    if service is None or not hasattr(service, "evaluate_regression"):
        return AdmissionCaseRegressionSummary()
    regression_filters = scoped_filters(filters, keys=REGRESSION_FILTER_KEYS)
    if not regression_filters.get("dimension") or not regression_filters.get("left_value") or not regression_filters.get("right_value"):
        return AdmissionCaseRegressionSummary(
            available=False,
            overall_result="not_configured",
            reasons=("当前报告未绑定 regression comparison scope。",),
            source_filters=regression_filters,
        )
    result = service.evaluate_regression(**regression_filters)
    return AdmissionCaseRegressionSummary(
        available=True,
        dimension=str(getattr(result, "dimension", "") or ""),
        overall_result=str(getattr(result, "overall_result", "insufficient_data") or "insufficient_data"),
        issue_result_summary=dict(getattr(result, "issue_result_summary", {}) or {}),
        metric_result_summary=dict(getattr(result, "metric_result_summary", {}) or {}),
        reasons=tuple(getattr(result, "reasons", ()) or ()),
        comparability_notes=tuple(getattr(result, "comparability_notes", ()) or ()),
        source_filters=regression_filters,
    )


def scenario_coverage(
    *,
    filters: Mapping[str, Any],
    execution_summary: AdmissionCaseExecutionSummary,
    top_issues: Sequence[AdmissionCaseTopIssue],
) -> AdmissionCaseScenarioCoverage:
    scenarios = tuple(execution_summary.template_types)
    issue_scenarios = tuple(
        sorted({str(name) for item in top_issues for name in (item.affected_scenarios or ()) if str(name).strip()})
    )
    notes: list[str] = []
    if not scenarios:
        notes.append("当前 admission case 过滤范围内没有匹配到执行 run。")
        state = "missing"
    else:
        state = "covered"
        notes.append("场景覆盖当前按过滤范围内的任务模板类型估算。")
    if filters.get("template_type"):
        notes.append(f"当前 case 过滤限定在 template_type={filters['template_type']}。")
    if issue_scenarios:
        notes.append(f"Top Issue 当前覆盖到 {len(issue_scenarios)} 个 issue scenario。")
    return AdmissionCaseScenarioCoverage(
        scenario_count=len(scenarios),
        scenarios=scenarios,
        issue_scenario_count=len(issue_scenarios),
        issue_scenarios=issue_scenarios,
        coverage_state=state,
        notes=tuple(notes),
    )


def normalized_filters(filters: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in REGRESSION_FILTER_KEYS:
        value = filters.get(key)
        if value in (None, "", (), [], {}):
            continue
        normalized[key] = value
    return normalized


def scoped_filters(filters: Mapping[str, Any], *, keys: Sequence[str]) -> dict[str, Any]:
    scoped: dict[str, Any] = {}
    for key in keys:
        value = filters.get(key)
        if value in (None, "", (), [], {}):
            continue
        scoped[key] = value
    return scoped
