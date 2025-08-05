from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.application import (
    CreateRunCommand,
    CreateTaskCommand,
    ExecuteRunCommand,
    create_run as run_create_use_case,
    create_task as task_create_use_case,
    execute_run as run_execute_use_case,
    DevicePoolQuery,
    list_device_pools as list_device_pools_use_case,
    resolve_monitoring_backend_override,
)
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
from stability.scenario.registry import get_template_form_schema
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; task_lifecycle.py owns this command/payload group.

def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)


def _resolve_monitoring_backend_override(value: str) -> str | None:
    return resolve_monitoring_backend_override(value)


def _handle_create_task(args: argparse.Namespace) -> int:
    """Create one task definition and print a JSON summary for scripting or inspection."""
    metadata = _parse_json_object(args.metadata)
    task_params = _parse_json_object(args.task_params)
    selected_device_ids = _expand_multi_value(args.devices)
    enabled_metrics = _expand_multi_value(args.metrics)

    bundle = create_v1_bootstrap() if args.in_memory else create_v1_persistent_bootstrap()
    payload = task_create_use_case(
        bundle,
        CreateTaskCommand(
            task_name=args.task_name.strip(),
            template_type=args.template_type,
            package_name=args.package_name.strip(),
            app_label=args.app_label.strip(),
            version_name=args.version_name.strip(),
            version_code=args.version_code.strip(),
            launch_activity=args.launch_activity.strip(),
            task_params=task_params,
            selected_device_ids=selected_device_ids,
            sampling_interval=args.sampling_interval,
            enabled_metrics=enabled_metrics,
            duration_seconds=args.duration_seconds,
            timeout_seconds=args.timeout_seconds,
            created_by=args.created_by.strip(),
            notes=args.note,
            metadata=metadata,
            storage_mode="memory" if args.in_memory else "persistent",
            sync_devices=not args.in_memory and not args.skip_device_sync,
        ),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_task_template_schema(args: argparse.Namespace) -> int:
    """Print the shared template form schema used by Web and CLI."""
    payload = get_template_form_schema(args.template_type)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_create_run(args: argparse.Namespace) -> int:
    """Create one persisted task run plus its initial pending execution instances."""
    metadata = _parse_json_object(args.metadata)
    requested_device_ids = _expand_multi_value(args.devices)

    bundle = create_v1_persistent_bootstrap()
    try:
        payload = run_create_use_case(
            bundle,
            CreateRunCommand(
                task_id=args.task_id.strip(),
                requested_device_ids=requested_device_ids,
                requested_by=args.requested_by.strip(),
                metadata=metadata,
                sync_devices=not args.skip_device_sync,
            ),
        )
    except (TaskRecordNotFound, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_execute_run(args: argparse.Namespace) -> int:
    """Execute one existing run through the minimal local runner and print the outcome."""
    bundle = create_v1_persistent_bootstrap(
        monitoring_backend=_resolve_monitoring_backend_override(args.monitoring_backend),
    )
    if bundle.run_execution_service is None:
        raise SystemExit("Run execution service is not available in the current bootstrap.")

    try:
        payload = run_execute_use_case(
            bundle.run_execution_service,
            ExecuteRunCommand(
                run_id=args.run_id.strip(),
                persist_monitoring=not args.no_persist_monitoring,
                collect_snapshot=not args.skip_monitoring,
                stop_on_failure=args.stop_on_failure,
                max_concurrency=args.max_concurrency,
                retry_count=args.retry_count,
                monitoring_backend=str(getattr(bundle, "monitoring_backend", "") or ""),
            ),
        )
    except (RunRecordNotFound, TaskRecordNotFound, LookupError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_devices(args: argparse.Namespace) -> int:
    """List device summaries from the persistent registry."""
    bundle = create_v1_persistent_bootstrap()
    if bundle.device_service is None:
        raise SystemExit("Device service is not available in the current bootstrap.")
    sync_payload = _maybe_sync_devices(
        bundle,
        enabled=args.sync,
        target_device_id=args.sync_device.strip(),
    )
    payload = {
        "storage_mode": "persistent",
        "device_count": len(bundle.device_service.list_devices()),
        "devices": bundle.device_service.list_device_summaries(),
    }
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_device(args: argparse.Namespace) -> int:
    """Show one persisted device with detail fields."""
    bundle = create_v1_persistent_bootstrap()
    if bundle.device_service is None:
        raise SystemExit("Device service is not available in the current bootstrap.")
    sync_payload = _maybe_sync_devices(
        bundle,
        enabled=args.sync,
        target_device_id=args.device_id.strip() if args.sync_target_only else "",
    )
    try:
        device = bundle.device_service.require_device(args.device_id.strip())
    except DeviceRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        "device": bundle.device_service.describe_device(device, include_metadata=True),
    }
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_device_pools(args: argparse.Namespace) -> int:
    """List device pool summaries from the persistent registry."""
    bundle = create_v1_persistent_bootstrap()
    if bundle.device_service is None:
        raise SystemExit("Device service is not available in the current bootstrap.")
    sync_payload = _maybe_sync_devices(bundle, enabled=args.sync, target_device_id="")
    payload = list_device_pools_use_case(
        bundle.device_service,
        DevicePoolQuery(group=args.group, team=args.team, tags=_split_values(args.tags)),
    )
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_inspect_device_pool(args: argparse.Namespace) -> int:
    """Inspect a filtered device pool from the persistent registry."""
    if not any([str(args.group or "").strip(), str(args.team or "").strip(), _split_values(args.tags)]):
        raise SystemExit("At least one of --group, --team, or --tag is required.")
    bundle = create_v1_persistent_bootstrap()
    if bundle.device_service is None:
        raise SystemExit("Device service is not available in the current bootstrap.")
    sync_payload = _maybe_sync_devices(bundle, enabled=args.sync, target_device_id="")
    payload = list_device_pools_use_case(
        bundle.device_service,
        DevicePoolQuery(group=args.group, team=args.team, tags=_split_values(args.tags)),
    )
    payload["pool"] = payload["pools"][0] if len(payload["pools"]) == 1 else None
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_tasks(args: argparse.Namespace) -> int:
    """List persisted task definitions with summary fields."""
    bundle = create_v1_persistent_bootstrap()
    payload = {
        "storage_mode": "persistent",
        "task_count": len(bundle.task_service.list_tasks()),
        "tasks": bundle.task_service.list_task_summaries(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_task(args: argparse.Namespace) -> int:
    """Show one persisted task definition with detail fields."""
    bundle = create_v1_persistent_bootstrap()
    try:
        task = bundle.task_service.get_task(args.task_id.strip())
    except TaskRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        "task": bundle.task_service.describe_task(task, include_metadata=True),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_long_run_templates(args: argparse.Namespace) -> int:
    """List long-run unattended template defaults for operators."""
    bundle = create_v1_persistent_bootstrap()
    payload = _long_run_templates_payload(getattr(bundle, "unattended_service", None))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_long_run_template(args: argparse.Namespace) -> int:
    """Show one long-run unattended template."""
    bundle = create_v1_persistent_bootstrap()
    template_key = args.template_key.strip()
    payload = _long_run_templates_payload(
        getattr(bundle, "unattended_service", None),
        template_key=template_key,
    )
    if payload.get("template") is None:
        raise SystemExit(f"Long-run template '{template_key}' was not found.")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_plan_long_run_template(args: argparse.Namespace) -> int:
    """Preview one long-run unattended template after applying overrides."""
    bundle = create_v1_persistent_bootstrap()
    template_key = args.template_key.strip()
    payload = _long_run_templates_payload(
        getattr(bundle, "unattended_service", None),
        template_key=template_key,
        overrides=_parse_key_value_overrides(args.overrides),
        include_plan=True,
    )
    if payload.get("template") is None:
        raise SystemExit(f"Long-run template '{template_key}' was not found.")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_configure_unattended_task(args: argparse.Namespace) -> int:
    """Persist one unattended configuration on top of an existing task definition."""
    bundle = create_v1_persistent_bootstrap()
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    try:
        record = bundle.unattended_service.configure_task(
            args.task_id.strip(),
            interval_minutes=args.interval_minutes,
            desired_device_count=args.desired_device_count or None,
            primary_device_ids=_expand_multi_value(args.devices),
            backup_device_ids=_expand_multi_value(args.backup_devices),
            failure_threshold=args.failure_threshold,
            max_round_history=args.max_round_history,
            rotation_strategy=args.rotation_strategy,
            rotation_advance_policy=args.rotation_advance_policy,
            max_device_window_history=args.max_device_window_history,
            enabled=not args.disabled,
            start_now=bool(args.start_now),
        )
    except UnattendedTaskRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "unattended_task": _unattended_task_payload(record),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_unattended_tasks(args: argparse.Namespace) -> int:
    """List unattended task definitions with current due state and recent summary."""
    bundle = create_v1_persistent_bootstrap()
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    records = bundle.unattended_service.list_task_records(
        enabled_only=bool(args.enabled_only),
        due_only=bool(args.due_only),
        limit=args.limit,
    )
    payload = {
        "storage_mode": "persistent",
        "task_count": len(records),
        "tasks": [_unattended_task_payload(item) for item in records],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_unattended_task(args: argparse.Namespace) -> int:
    """Show one unattended task config with recent round history."""
    bundle = create_v1_persistent_bootstrap()
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    try:
        record = bundle.unattended_service.get_task_record(args.task_id.strip())
    except UnattendedTaskRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "unattended_task": _unattended_task_payload(record),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_unattended_round(args: argparse.Namespace) -> int:
    """Trigger one unattended round for one configured task."""
    bundle = create_v1_persistent_bootstrap(
        monitoring_backend=_resolve_monitoring_backend_override(args.monitoring_backend),
    )
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    try:
        result = bundle.unattended_service.run_task_round(
            args.task_id.strip(),
            force=not args.respect_schedule,
            requested_by=args.requested_by.strip(),
            persist_monitoring=not args.no_persist_monitoring,
            collect_snapshot=not args.skip_monitoring,
            stop_on_failure=bool(args.stop_on_failure),
            max_concurrency=args.max_concurrency,
            retry_count=args.retry_count,
        )
    except UnattendedTaskRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "monitoring_backend": getattr(bundle, "monitoring_backend", None),
        "task": _unattended_task_payload(result.task),
        "execution": _unattended_round_execution_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_patrol_unattended_tasks(args: argparse.Namespace) -> int:
    """Execute due unattended tasks and print the patrol summary."""
    bundle = create_v1_persistent_bootstrap(
        monitoring_backend=_resolve_monitoring_backend_override(args.monitoring_backend),
    )
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    try:
        result = bundle.unattended_service.run_due_tasks(
            task_id=args.task_id.strip(),
            force=bool(args.force),
            requested_by=args.requested_by.strip(),
            persist_monitoring=not args.no_persist_monitoring,
            collect_snapshot=not args.skip_monitoring,
            stop_on_failure=bool(args.stop_on_failure),
            max_concurrency=args.max_concurrency,
            retry_count=args.retry_count,
        )
    except UnattendedTaskRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "monitoring_backend": getattr(bundle, "monitoring_backend", None),
        "patrol": _unattended_patrol_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_run_unattended_patrol_runner(args: argparse.Namespace) -> int:
    """Run one minimal timed patrol loop and print the final runner summary."""
    bundle = create_v1_persistent_bootstrap(
        monitoring_backend=_resolve_monitoring_backend_override(args.monitoring_backend),
    )
    if getattr(bundle, "unattended_runner_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended patrol runner service.")
    try:
        result = bundle.unattended_runner_service.run(
            interval_seconds=args.interval_seconds,
            max_iterations=args.max_iterations,
            task_id=args.task_id.strip(),
            force=bool(args.force),
            requested_by=args.requested_by.strip(),
            persist_monitoring=not args.no_persist_monitoring,
            collect_snapshot=not args.skip_monitoring,
            stop_on_failure=bool(args.stop_on_failure),
            max_concurrency=args.max_concurrency,
            retry_count=args.retry_count,
        )
    except UnattendedPatrolRunnerAlreadyRunning as exc:
        raise SystemExit(str(exc)) from exc
    except UnattendedTaskRecordNotFound as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "monitoring_backend": getattr(bundle, "monitoring_backend", None),
        "runner": _unattended_runner_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_build_unattended_daily_report(args: argparse.Namespace) -> int:
    """Build one unattended daily report from retained unattended round history."""
    bundle = create_v1_persistent_bootstrap()
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    try:
        report = bundle.unattended_service.build_daily_report(
            task_id=args.task_id.strip(),
            report_date=args.report_date.strip(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "daily_report": _unattended_daily_report_payload(report),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_build_unattended_weekly_report(args: argparse.Namespace) -> int:
    """Build one unattended weekly report from retained unattended round history."""
    bundle = create_v1_persistent_bootstrap()
    if getattr(bundle, "unattended_service", None) is None:
        raise SystemExit("Persistent bootstrap does not expose unattended service.")
    try:
        report = bundle.unattended_service.build_weekly_report(
            task_id=args.task_id.strip(),
            report_date=args.report_date.strip(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "weekly_report": _unattended_weekly_report_payload(report),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_runs(args: argparse.Namespace) -> int:
    """List run history entries with minimal task/run summary fields."""
    bundle = create_v1_persistent_bootstrap()
    has_issue = _parse_optional_bool(args.has_issue)
    try:
        entries = bundle.run_history_service.list_runs(
            task_id=args.task_id.strip() or None,
            run_status=args.status.strip() or None,
            template_type=args.template_type.strip() or None,
            package_name=args.package_name.strip() or None,
            device_id=args.device_id.strip() or None,
            has_issue=has_issue,
            created_from=args.created_from.strip() or None,
            created_to=args.created_to.strip() or None,
            limit=args.limit,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "run_count": len(entries),
        "filters": {
            "task_id": args.task_id.strip() or None,
            "run_status": args.status.strip() or None,
            "template_type": args.template_type.strip() or None,
            "package_name": args.package_name.strip() or None,
            "device_id": args.device_id.strip() or None,
            "has_issue": has_issue,
            "created_from": args.created_from.strip() or None,
            "created_to": args.created_to.strip() or None,
            "limit": args.limit,
        },
        "runs": entries,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_run(args: argparse.Namespace) -> int:
    """Show one persisted run plus all execution-instance history details."""
    bundle = create_v1_persistent_bootstrap()
    try:
        payload = bundle.run_history_service.get_run_detail(args.run_id.strip())
    except (RunRecordNotFound, TaskRecordNotFound, LookupError) as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "storage_mode": "persistent",
        **payload,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
