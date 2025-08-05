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
from stability.web import serve_web_portal

# Split from stability.cli.task_create; analysis.py owns this command/payload group.

# Split from stability/cli/handlers/analysis.py.

def _handle_list_top_issues(args: argparse.Namespace) -> int:
    """List aggregated issues ordered by Top Issue score."""
    bundle = create_v1_persistent_bootstrap()
    items = bundle.analysis_service.list_top_issues(
        task_id=args.task_id.strip(),
        run_status=args.status.strip(),
        template_type=args.template_type.strip(),
        version=args.version.strip(),
        package_name=args.package_name.strip(),
        device_id=args.device_id.strip(),
        issue_type=args.issue_type.strip(),
        created_from=args.created_from.strip(),
        created_to=args.created_to.strip(),
        limit=args.limit,
    )
    payload = {
        "storage_mode": "persistent",
        "filters": {
            "task_id": args.task_id.strip(),
            "run_status": args.status.strip(),
            "template_type": args.template_type.strip(),
            "version": args.version.strip(),
            "package_name": args.package_name.strip(),
            "device_id": args.device_id.strip(),
            "issue_type": args.issue_type.strip(),
            "created_from": args.created_from.strip(),
            "created_to": args.created_to.strip(),
        },
        "top_issue_count": len(items),
        "issues": [_aggregated_issue_payload(item, include_samples=False) for item in items],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_issue_group(args: argparse.Namespace) -> int:
    """Show one aggregated issue group with sample events."""
    bundle = create_v1_persistent_bootstrap()
    try:
        item = bundle.analysis_service.get_issue_group(
            args.fingerprint.strip(),
            task_id=args.task_id.strip(),
            run_status=args.status.strip(),
            template_type=args.template_type.strip(),
            version=args.version.strip(),
            package_name=args.package_name.strip(),
            device_id=args.device_id.strip(),
            issue_type=args.issue_type.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
        )
    except AggregatedIssueNotFound as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        "fingerprint": args.fingerprint.strip(),
        "issue_group": _aggregated_issue_payload(item, include_samples=True),
    }
    if getattr(bundle, "attribution_service", None) is not None:
        payload["attribution"] = _issue_attribution_payload(
            bundle.attribution_service.attribute_issue_group(item)
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_compare_issues(args: argparse.Namespace) -> int:
    """Compare aggregated issue groups across two scopes."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.comparison_service.compare_issues(
            dimension=args.dimension.strip(),
            left_value=args.left_value.strip(),
            right_value=args.right_value.strip(),
            task_id=args.task_id.strip(),
            run_status=args.status.strip(),
            template_type=args.template_type.strip(),
            version=args.version.strip(),
            package_name=args.package_name.strip(),
            issue_type=args.issue_type.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
            limit=args.limit,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        "comparison": _comparison_result_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_compare_performance_trends(args: argparse.Namespace) -> int:
    """Compare persisted monitoring trends across two scopes."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.performance_trend_service.compare_performance_trends(
            dimension=args.dimension.strip(),
            left_value=args.left_value.strip(),
            right_value=args.right_value.strip(),
            task_id=args.task_id.strip(),
            run_status=args.status.strip(),
            template_type=args.template_type.strip(),
            version=args.version.strip(),
            package_name=args.package_name.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        "comparison": _performance_trend_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_judge_regression(args: argparse.Namespace) -> int:
    """Judge one comparison result with the current minimal regression rules."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.regression_service.evaluate_regression(
            dimension=args.dimension.strip(),
            left_value=args.left_value.strip(),
            right_value=args.right_value.strip(),
            task_id=args.task_id.strip(),
            run_status=args.status.strip(),
            template_type=args.template_type.strip(),
            version=args.version.strip(),
            package_name=args.package_name.strip(),
            issue_type=args.issue_type.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
            limit=args.limit,
            min_side_issue_groups=args.min_side_issue_groups,
            significant_occurrence_delta=args.significant_occurrence_delta,
            significant_affected_run_delta=args.significant_affected_run_delta,
            significant_affected_device_delta=args.significant_affected_device_delta,
            significant_affected_scenario_delta=args.significant_affected_scenario_delta,
            min_side_metric_sessions=args.min_side_metric_sessions,
            min_side_metric_samples=args.min_side_metric_samples,
            significant_metric_delta_ratio=args.significant_metric_delta_ratio,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        "regression": _regression_result_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_create_analysis_snapshot(args: argparse.Namespace) -> int:
    """Persist one analysis result into a reusable snapshot file bundle."""
    bundle = create_v1_persistent_bootstrap()
    filters = _analysis_snapshot_filters(args)
    tags = _expand_multi_value(args.tags)
    snapshot_type = args.snapshot_type.strip()
    if snapshot_type == "top_issues":
        record = bundle.snapshot_service.create_top_issues_snapshot(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            tags=tags,
            **filters,
        )
    elif snapshot_type == "comparison":
        _require_snapshot_scope_args(args)
        record = bundle.snapshot_service.create_comparison_snapshot(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            tags=tags,
            **filters,
        )
    elif snapshot_type == "replay":
        _require_snapshot_replay_args(args)
        record = bundle.snapshot_service.create_rule_replay_snapshot(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            tags=tags,
            **filters,
        )
    elif snapshot_type == "review":
        _require_snapshot_review_args(args)
        record = bundle.snapshot_service.create_rule_review_snapshot(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            tags=tags,
            **filters,
        )
    else:
        _require_snapshot_scope_args(args)
        record = bundle.snapshot_service.create_regression_snapshot(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            tags=tags,
            **filters,
        )

    payload = {
        "storage_mode": "persistent",
        "snapshot": _analysis_snapshot_record_payload(record),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_analysis_snapshots(args: argparse.Namespace) -> int:
    """List persisted analysis snapshots from the file-backed snapshot store."""
    bundle = create_v1_persistent_bootstrap()
    items = bundle.snapshot_service.list_snapshots(
        snapshot_type=args.snapshot_type.strip(),
        created_by=args.created_by.strip(),
        limit=args.limit,
    )
    payload = {
        "storage_mode": "persistent",
        "snapshot_count": len(items),
        "snapshots": [_analysis_snapshot_summary_payload(item) for item in items],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_analysis_snapshot(args: argparse.Namespace) -> int:
    """Show one persisted analysis snapshot payload."""
    bundle = create_v1_persistent_bootstrap()
    try:
        record = bundle.snapshot_service.get_snapshot(args.snapshot_id.strip())
    except SnapshotRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "snapshot": _analysis_snapshot_record_payload(record),
        "integrity": bundle.snapshot_service.inspect_snapshot_integrity(record),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_delete_analysis_snapshot(args: argparse.Namespace) -> int:
    """Delete one persisted analysis snapshot bundle."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.snapshot_service.delete_snapshot(args.snapshot_id.strip())
    except SnapshotRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "delete_result": result,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
