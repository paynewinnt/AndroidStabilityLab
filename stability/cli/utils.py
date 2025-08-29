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
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; utils.py owns this command/payload group.


def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)

def _expand_multi_value(values: Iterable[str]) -> list[str]:
    """Split repeated or comma-separated CLI options into a flat string list."""
    items: list[str] = []
    for raw in values:
        for item in raw.split(","):
            value = item.strip()
            if value:
                items.append(value)
    return items


def _analysis_snapshot_filters(args: argparse.Namespace) -> dict[str, object]:
    filters: dict[str, object] = {
        "task_id": args.task_id.strip(),
        "run_status": args.status.strip(),
        "template_type": args.template_type.strip(),
        "version": args.version.strip(),
        "package_name": args.package_name.strip(),
        "device_id": args.device_id.strip(),
        "issue_type": args.issue_type.strip(),
        "created_from": args.created_from.strip(),
        "created_to": args.created_to.strip(),
        "limit": args.limit,
    }
    if getattr(args, "dimension", "").strip():
        filters["dimension"] = args.dimension.strip()
    if getattr(args, "left_value", "").strip():
        filters["left_value"] = args.left_value.strip()
    if getattr(args, "right_value", "").strip():
        filters["right_value"] = args.right_value.strip()
    if getattr(args, "candidate_path", "").strip():
        filters["candidate_path"] = args.candidate_path.strip()
    if getattr(args, "baseline_path", "").strip():
        filters["baseline_path"] = args.baseline_path.strip()
    if getattr(args, "policy_path", "").strip():
        filters["policy_path"] = args.policy_path.strip()
    if getattr(args, "snapshot_type", "") in {"replay", "review"} and getattr(args, "include_unchanged", False):
        filters["include_unchanged"] = True
    if getattr(args, "snapshot_type", "") == "regression":
        if args.min_side_issue_groups is not None:
            filters["min_side_issue_groups"] = args.min_side_issue_groups
        if args.significant_occurrence_delta is not None:
            filters["significant_occurrence_delta"] = args.significant_occurrence_delta
        if args.significant_affected_run_delta is not None:
            filters["significant_affected_run_delta"] = args.significant_affected_run_delta
        if args.significant_affected_device_delta is not None:
            filters["significant_affected_device_delta"] = args.significant_affected_device_delta
        if args.significant_affected_scenario_delta is not None:
            filters["significant_affected_scenario_delta"] = args.significant_affected_scenario_delta
        if args.min_side_metric_sessions is not None:
            filters["min_side_metric_sessions"] = args.min_side_metric_sessions
        if args.min_side_metric_samples is not None:
            filters["min_side_metric_samples"] = args.min_side_metric_samples
        if args.significant_metric_delta_ratio is not None:
            filters["significant_metric_delta_ratio"] = args.significant_metric_delta_ratio
    return filters


def _require_snapshot_scope_args(args: argparse.Namespace) -> None:
    if not args.dimension.strip() or not args.left_value.strip() or not args.right_value.strip():
        raise SystemExit(
            "--dimension, --left-value and --right-value are required for comparison/regression snapshots."
        )


def _require_snapshot_replay_args(args: argparse.Namespace) -> None:
    if not args.candidate_path.strip():
        raise SystemExit("--candidate-path is required for replay snapshots.")


def _require_snapshot_review_args(args: argparse.Namespace) -> None:
    if not args.candidate_path.strip():
        raise SystemExit("--candidate-path is required for review snapshots.")


def _parse_json_object(raw: str) -> dict[str, object]:
    """Parse a CLI JSON string and enforce that the payload is a JSON object."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--metadata must be valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("--metadata must be a JSON object.")
    return data


def _parse_optional_bool(raw: str) -> bool | None:
    normalized = raw.strip().lower()
    if not normalized:
        return None
    return normalized == "true"


def _split_values(values: Iterable[str]) -> list[str]:
    """Expand repeated comma-separated CLI flags into stable unique strings."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for item in str(raw or "").split(","):
            value = item.strip()
            if value and value not in seen:
                result.append(value)
                seen.add(value)
    return result


def _device_pools_payload(
    device_service: object,
    *,
    group: str = "",
    team: str = "",
    tags: Sequence[str] = (),
) -> dict[str, object]:
    """Build a device-pool governance view, preferring the formal service API when present."""
    if hasattr(device_service, "summarize_device_pools") and hasattr(device_service, "suggest_device_candidates"):
        return _formal_device_pools_payload(
            device_service,
            group=group,
            team=team,
            tags=tags,
        )
    if hasattr(device_service, "list_device_pools"):
        payload = _call_device_pool_service_method(
            device_service.list_device_pools,
            group=group,
            team=team,
            tags=tags,
        )
        return _normalize_device_pools_payload(payload)
    if hasattr(device_service, "describe_device_pools"):
        payload = _call_device_pool_service_method(
            device_service.describe_device_pools,
            group=group,
            team=team,
            tags=tags,
        )
        return _normalize_device_pools_payload(payload)

    devices = [dict(item) for item in device_service.list_device_summaries()]
    group_filter = str(group or "").strip()
    team_filter = str(team or "").strip()
    tag_filters = tuple(str(item).strip() for item in tags if str(item).strip())
    if group_filter:
        devices = [item for item in devices if str(item.get("group_name", "") or "ungrouped") == group_filter]
    if team_filter:
        devices = [item for item in devices if _device_team(item) == team_filter]
    if tag_filters:
        required_tags = set(tag_filters)
        devices = [item for item in devices if required_tags.issubset(set(_device_tags(item)))]

    pools_by_key: dict[str, dict[str, object]] = {}
    group_counts: dict[str, int] = {}
    team_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for device in devices:
        group_name = str(device.get("group_name", "") or "ungrouped")
        owning_team = _device_team(device)
        pool_key = f"group:{group_name}|team:{owning_team}"
        pool = pools_by_key.setdefault(
            pool_key,
            {
                "pool_key": pool_key,
                "group_name": group_name,
                "team": owning_team,
                "device_count": 0,
                "online_device_count": 0,
                "schedulable_device_count": 0,
                "unschedulable_device_count": 0,
                "schedulable_devices": [],
                "unschedulable_devices": [],
                "tags": [],
                "tag_counts": {},
                "unschedulable_reason_counts": {},
            },
        )
        device_tags = _device_tags(device)
        reasons = _unschedulable_reasons(device)
        is_schedulable = not reasons
        pool["device_count"] = int(pool["device_count"]) + 1
        if bool(device.get("is_online", False)):
            pool["online_device_count"] = int(pool["online_device_count"]) + 1
        if is_schedulable:
            pool["schedulable_device_count"] = int(pool["schedulable_device_count"]) + 1
            schedulable_devices = list(pool["schedulable_devices"])
            schedulable_devices.append(device)
            pool["schedulable_devices"] = schedulable_devices
        else:
            pool["unschedulable_device_count"] = int(pool["unschedulable_device_count"]) + 1
            unschedulable_devices = list(pool["unschedulable_devices"])
            unschedulable_devices.append({**device, "unschedulable_reasons": reasons})
            pool["unschedulable_devices"] = unschedulable_devices
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
                pool_reason_counts = dict(pool["unschedulable_reason_counts"])
                pool_reason_counts[reason] = pool_reason_counts.get(reason, 0) + 1
                pool["unschedulable_reason_counts"] = pool_reason_counts
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
        team_counts[owning_team] = team_counts.get(owning_team, 0) + 1
        for tag in device_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            pool_tag_counts = dict(pool["tag_counts"])
            pool_tag_counts[tag] = pool_tag_counts.get(tag, 0) + 1
            pool["tag_counts"] = pool_tag_counts
            pool["tags"] = sorted(pool_tag_counts)

    pools = sorted(
        pools_by_key.values(),
        key=lambda item: (str(item.get("group_name", "")), str(item.get("team", ""))),
    )
    return {
        "storage_mode": "persistent",
        "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
        "summary": {
            "pool_count": len(pools),
            "device_count": len(devices),
            "online_device_count": sum(1 for item in devices if bool(item.get("is_online", False))),
            "schedulable_device_count": sum(1 for item in devices if not _unschedulable_reasons(item)),
            "unschedulable_device_count": sum(1 for item in devices if _unschedulable_reasons(item)),
            "group_counts": dict(sorted(group_counts.items())),
            "team_counts": dict(sorted(team_counts.items())),
            "tag_counts": dict(sorted(tag_counts.items())),
            "unschedulable_reason_counts": dict(sorted(reason_counts.items())),
        },
        "pools": pools,
    }


def _formal_device_pools_payload(
    device_service: object,
    *,
    group: str = "",
    team: str = "",
    tags: Sequence[str] = (),
) -> dict[str, object]:
    summaries = {
        dimension: [
            _object_payload(item)
            for item in device_service.summarize_device_pools(group_by=dimension)  # type: ignore[attr-defined]
        ]
        for dimension in ("group", "team", "tag")
    }
    plan = _object_payload(
        device_service.suggest_device_candidates(  # type: ignore[attr-defined]
            group_name=str(group or "").strip(),
            team_name=str(team or "").strip(),
            tags=tuple(str(item).strip() for item in tags if str(item).strip()),
            requested_count=0,
        )
    )
    candidates = [
        _candidate_device_payload(item, schedulable=True)
        for item in list(plan.get("candidates", []) or [])
    ]
    rejected = [
        _candidate_device_payload(item, schedulable=False)
        for item in list(plan.get("rejected_candidates", []) or [])
    ]
    return _device_pools_payload_from_candidates(
        candidates=candidates,
        rejected=rejected,
        summaries=summaries,
        group=group,
        team=team,
        tags=tags,
    )


def _device_pools_payload_from_candidates(
    *,
    candidates: Sequence[Mapping[str, object]],
    rejected: Sequence[Mapping[str, object]],
    summaries: Mapping[str, Sequence[Mapping[str, object]]],
    group: str = "",
    team: str = "",
    tags: Sequence[str] = (),
) -> dict[str, object]:
    group_filter = str(group or "").strip()
    team_filter = str(team or "").strip()
    tag_filters = tuple(str(item).strip() for item in tags if str(item).strip())
    devices = [dict(item) for item in candidates] + [dict(item) for item in rejected]
    pools_by_key: dict[str, dict[str, object]] = {}
    reason_counts: dict[str, int] = {}
    for device in devices:
        group_name = str(device.get("group_name", "") or "ungrouped")
        owning_team = _device_team(device)
        pool_key = f"group:{group_name}|team:{owning_team}"
        pool = pools_by_key.setdefault(
            pool_key,
            {
                "pool_key": pool_key,
                "group_name": group_name,
                "team": owning_team,
                "device_count": 0,
                "online_device_count": 0,
                "schedulable_device_count": 0,
                "unschedulable_device_count": 0,
                "schedulable_devices": [],
                "unschedulable_devices": [],
                "tags": [],
                "tag_counts": {},
                "unschedulable_reason_counts": {},
            },
        )
        pool["device_count"] = int(pool["device_count"]) + 1
        if bool(device.get("is_online", False)):
            pool["online_device_count"] = int(pool["online_device_count"]) + 1
        if bool(device.get("is_schedulable", False)):
            pool["schedulable_device_count"] = int(pool["schedulable_device_count"]) + 1
            schedulable_devices = list(pool["schedulable_devices"])
            schedulable_devices.append(device)
            pool["schedulable_devices"] = schedulable_devices
        else:
            reasons = list(device.get("unschedulable_reasons", []) or ["not_schedulable"])
            pool["unschedulable_device_count"] = int(pool["unschedulable_device_count"]) + 1
            unschedulable_devices = list(pool["unschedulable_devices"])
            unschedulable_devices.append({**device, "unschedulable_reasons": reasons})
            pool["unschedulable_devices"] = unschedulable_devices
            for reason in reasons:
                reason_key = str(reason)
                reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1
                pool_reason_counts = dict(pool["unschedulable_reason_counts"])
                pool_reason_counts[reason_key] = pool_reason_counts.get(reason_key, 0) + 1
                pool["unschedulable_reason_counts"] = pool_reason_counts
        for tag in _device_tags(device):
            pool_tag_counts = dict(pool["tag_counts"])
            pool_tag_counts[tag] = pool_tag_counts.get(tag, 0) + 1
            pool["tag_counts"] = pool_tag_counts
            pool["tags"] = sorted(pool_tag_counts)

    pools = sorted(
        pools_by_key.values(),
        key=lambda item: (str(item.get("group_name", "")), str(item.get("team", ""))),
    )
    return {
        "storage_mode": "persistent",
        "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
        "service_summary": {
            "groups": list(summaries.get("group", []) or []),
            "teams": list(summaries.get("team", []) or []),
            "tags": list(summaries.get("tag", []) or []),
        },
        "summary": {
            "pool_count": len(pools),
            "device_count": len(devices),
            "online_device_count": sum(int(item.get("online_count", 0) or 0) for item in summaries.get("group", []) or []) if not any([group_filter, team_filter, tag_filters]) else sum(1 for item in devices if bool(item.get("is_online", False))),
            "schedulable_device_count": len(candidates),
            "unschedulable_device_count": len(rejected),
            "group_counts": _summary_counts(summaries.get("group", []) or []),
            "team_counts": _summary_counts(summaries.get("team", []) or []),
            "tag_counts": _summary_counts(summaries.get("tag", []) or []),
            "unschedulable_reason_counts": dict(sorted(reason_counts.items())),
        },
        "pools": pools,
    }


def _call_device_pool_service_method(method: object, *, group: str, team: str, tags: Sequence[str]) -> object:
    try:
        return method(group=group, team=team, tags=tuple(tags))  # type: ignore[misc]
    except TypeError:
        return method()  # type: ignore[misc]


def _normalize_device_pools_payload(payload: object) -> dict[str, object]:
    if isinstance(payload, Mapping):
        result = dict(payload)
    else:
        result = {"pools": list(payload or [])}
    result.setdefault("storage_mode", "persistent")
    result.setdefault("summary", {})
    result.setdefault("pools", [])
    return result


def _object_payload(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())  # type: ignore[no-any-return, attr-defined]
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _candidate_device_payload(value: object, *, schedulable: bool) -> dict[str, object]:
    payload = _object_payload(value)
    profile = _object_payload(payload.get("profile", {}) or {})
    tags = profile.get("tags", ()) or ()
    reasons = list(payload.get("reasons", []) or [])
    return {
        "device_id": str(payload.get("device_id", "") or ""),
        "serial": str(payload.get("serial", "") or ""),
        "display_name": str(payload.get("display_name", "") or ""),
        "group_name": str(profile.get("group_name", "") or "ungrouped"),
        "team": str(profile.get("team_name", "") or "unassigned"),
        "tags": sorted({str(item).strip() for item in tags if str(item).strip()}),
        "is_online": "offline" not in reasons,
        "is_schedulable": bool(payload.get("schedulable", schedulable)),
        "score": int(payload.get("score", 0) or 0),
        "unschedulable_reasons": reasons,
        "profile": profile,
    }


def _summary_counts(items: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("key", "") or "").strip()
        if key:
            counts[key] = int(item.get("total_count", item.get("device_count", 0)) or 0)
    return dict(sorted(counts.items()))


def _device_team(device: Mapping[str, object]) -> str:
    metadata = dict(device.get("metadata", {}) or {})
    return str(
        device.get("team")
        or device.get("team_id")
        or device.get("team_name")
        or device.get("owner_team")
        or metadata.get("team")
        or metadata.get("team_id")
        or metadata.get("team_name")
        or metadata.get("owner_team")
        or "unassigned"
    )


def _device_tags(device: Mapping[str, object]) -> list[str]:
    raw_tags = device.get("tags", ()) or ()
    return sorted({str(item).strip() for item in raw_tags if str(item).strip()})


def _unschedulable_reasons(device: Mapping[str, object]) -> list[str]:
    if bool(device.get("is_schedulable", False)):
        return []
    reasons: list[str] = []
    if not bool(device.get("is_online", False)):
        reasons.append("offline")
    availability = str(device.get("availability_state", "") or "").strip()
    if availability and availability not in {"idle", "available"}:
        reasons.append(f"availability:{availability}")
    connection = str(device.get("connection_state", "") or "").strip()
    if connection and connection not in {"connected", "online"}:
        reasons.append(f"connection:{connection}")
    if str(device.get("current_instance_id", "") or "").strip():
        reasons.append("busy")
    if not reasons:
        reasons.append("not_schedulable")
    return sorted(set(reasons))


def _maybe_sync_devices(
    bundle: object,
    *,
    enabled: bool,
    target_device_id: str = "",
) -> dict[str, object] | None:
    if (not enabled and not target_device_id) or getattr(bundle, "device_service", None) is None:
        return None
    if target_device_id:
        synced_device = bundle.device_service.sync_device(target_device_id)
        return {
            "mode": "target_device",
            "target_device_id": target_device_id,
            "found": synced_device is not None,
            "updated_device_id": getattr(synced_device, "device_id", None),
        }

    sync_result = bundle.device_service.sync_devices(include_unavailable=True, mark_missing_offline=True)
    return {
        "mode": "full_registry",
        "scanned_count": sync_result.scanned_count,
        "created_count": len(sync_result.created),
        "updated_count": len(sync_result.updated),
        "refreshed_count": len(sync_result.refreshed),
        "marked_offline_count": len(sync_result.marked_offline),
    }


def _count_instance_statuses(instances: Sequence[object]) -> dict[str, int]:
    """Count instance statuses for compact CLI summaries."""
    counts: dict[str, int] = {}
    for instance in instances:
        status = str(getattr(instance, "instance_status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _instance_payload(instance: object) -> dict[str, object]:
    """Serialize one execution instance into a small JSON-friendly summary."""
    payload = {
        "instance_id": getattr(instance, "instance_id", None),
        "device_id": getattr(instance, "device_id", None),
        "status": getattr(instance, "instance_status", None),
        "queued_at": _isoformat_or_none(getattr(instance, "queued_at", None)),
    }
    monitoring_session_id = getattr(instance, "monitoring_session_id", None)
    if monitoring_session_id:
        payload["monitoring_session_id"] = monitoring_session_id
    metadata = dict(getattr(instance, "metadata", {}) or {})
    monitoring_backend = str(metadata.get("monitoring_backend", "") or "").strip()
    if monitoring_backend:
        payload["monitoring_backend"] = monitoring_backend
    monitoring_trace_path = str(metadata.get("monitoring_trace_path", "") or "").strip()
    if monitoring_trace_path:
        payload["monitoring_trace_path"] = monitoring_trace_path
    monitoring_snapshot_path = str(metadata.get("monitoring_snapshot_path", "") or "").strip()
    if monitoring_snapshot_path:
        payload["monitoring_snapshot_path"] = monitoring_snapshot_path
    return payload


def _unattended_task_payload(item: object) -> dict[str, object]:
    return {
        "task_id": getattr(item, "task_id", ""),
        "task_name": getattr(item, "task_name", ""),
        "configured": bool(getattr(item, "configured", False)),
        "enabled": bool(getattr(item, "enabled", False)),
        "interval_minutes": int(getattr(item, "interval_minutes", 0) or 0),
        "desired_device_count": int(getattr(item, "desired_device_count", 0) or 0),
        "failure_threshold": int(getattr(item, "failure_threshold", 0) or 0),
        "rotation_strategy": str(getattr(item, "rotation_strategy", "") or ""),
        "rotation_advance_policy": str(getattr(item, "rotation_advance_policy", "") or ""),
        "rotation_cursor": int(getattr(item, "rotation_cursor", 0) or 0),
        "rotation_advance_count": int(getattr(item, "rotation_advance_count", 0) or 0),
        "primary_device_ids": list(getattr(item, "primary_device_ids", ()) or ()),
        "backup_device_ids": list(getattr(item, "backup_device_ids", ()) or ()),
        "next_run_at": _isoformat_or_none(getattr(item, "next_run_at", None)),
        "last_run_at": _isoformat_or_none(getattr(item, "last_run_at", None)),
        "last_run_id": getattr(item, "last_run_id", ""),
        "due": bool(getattr(item, "due", False)),
        "latest_summary": dict(getattr(item, "latest_summary", {}) or {}),
        "long_run_summary": dict(getattr(item, "long_run_summary", {}) or {}),
        "recent_device_windows": [dict(entry) for entry in (getattr(item, "recent_device_windows", ()) or ())],
        "recent_rounds": [dict(entry) for entry in (getattr(item, "recent_rounds", ()) or ())],
    }


def _unattended_round_execution_payload(item: object) -> dict[str, object]:
    return {
        "executed": bool(getattr(item, "executed", False)),
        "reason": getattr(item, "reason", ""),
        "round": dict(getattr(item, "round_record", {}) or {}),
    }


def _unattended_patrol_payload(item: object) -> dict[str, object]:
    return {
        "generated_at": _isoformat_or_none(getattr(item, "generated_at", None)),
        "task_count": int(getattr(item, "task_count", 0) or 0),
        "enabled_task_count": int(getattr(item, "enabled_task_count", 0) or 0),
        "due_task_count": int(getattr(item, "due_task_count", 0) or 0),
        "executed_task_count": int(getattr(item, "executed_task_count", 0) or 0),
        "skipped_task_count": int(getattr(item, "skipped_task_count", 0) or 0),
        "failed_rate": float(getattr(item, "failed_rate", 0.0) or 0.0),
        "offline_rate": float(getattr(item, "offline_rate", 0.0) or 0.0),
        "recovery_success_rate": float(getattr(item, "recovery_success_rate", 0.0) or 0.0),
        "quarantined_device_count": int(getattr(item, "quarantined_device_count", 0) or 0),
        "quarantined_device_ids": list(getattr(item, "quarantined_device_ids", ()) or ()),
        "quarantine_probe_attempt_count": int(getattr(item, "quarantine_probe_attempt_count", 0) or 0),
        "quarantine_probe_skipped_count": int(getattr(item, "quarantine_probe_skipped_count", 0) or 0),
        "quarantine_probe_recovered_count": int(getattr(item, "quarantine_probe_recovered_count", 0) or 0),
        "recovered_device_ids": list(getattr(item, "recovered_device_ids", ()) or ()),
        "metrics": dict(getattr(item, "metrics", {}) or {}),
        "quarantine_probe_results": [
            dict(entry) for entry in (getattr(item, "quarantine_probe_results", ()) or ())
        ],
        "executed_rounds": [dict(entry) for entry in (getattr(item, "executed_rounds", ()) or ())],
        "tasks": [_unattended_task_payload(record) for record in (getattr(item, "task_records", ()) or ())],
    }


def _unattended_runner_payload(item: object) -> dict[str, object]:
    paths = getattr(item, "paths", None)
    patrols = []
    for cycle in (getattr(item, "patrols", ()) or ()):
        patrols.append(
            {
                "cycle_index": int(getattr(cycle, "cycle_index", 0) or 0),
                "started_at": _isoformat_or_none(getattr(cycle, "started_at", None)),
                "finished_at": _isoformat_or_none(getattr(cycle, "finished_at", None)),
                "patrol": _unattended_patrol_payload(getattr(cycle, "patrol", None)),
            }
        )
    return {
        "started_at": _isoformat_or_none(getattr(item, "started_at", None)),
        "finished_at": _isoformat_or_none(getattr(item, "finished_at", None)),
        "interval_seconds": int(getattr(item, "interval_seconds", 0) or 0),
        "max_iterations": int(getattr(item, "max_iterations", 0) or 0),
        "cycle_count": int(getattr(item, "cycle_count", 0) or 0),
        "stopped_reason": str(getattr(item, "stopped_reason", "") or ""),
        "task_id": str(getattr(item, "task_id", "") or ""),
        "force": bool(getattr(item, "force", False)),
        "paths": {
            "root_dir": str(getattr(paths, "root_dir", "") or ""),
            "lock_path": str(getattr(paths, "lock_path", "") or ""),
            "heartbeat_path": str(getattr(paths, "heartbeat_path", "") or ""),
            "daily_reports_dir": str(getattr(paths, "daily_reports_dir", "") or ""),
            "weekly_reports_dir": str(getattr(paths, "weekly_reports_dir", "") or ""),
        },
        "latest_daily_report": dict(getattr(item, "latest_daily_report", {}) or {}),
        "daily_report_paths": dict(getattr(item, "daily_report_paths", {}) or {}),
        "latest_weekly_report": dict(getattr(item, "latest_weekly_report", {}) or {}),
        "weekly_report_paths": dict(getattr(item, "weekly_report_paths", {}) or {}),
        "patrols": patrols,
    }


def _unattended_daily_report_payload(item: object) -> dict[str, object]:
    return {
        "report_date": str(getattr(item, "report_date", "") or ""),
        "generated_at": _isoformat_or_none(getattr(item, "generated_at", None)),
        "task_count": int(getattr(item, "task_count", 0) or 0),
        "active_task_count": int(getattr(item, "active_task_count", 0) or 0),
        "round_count": int(getattr(item, "round_count", 0) or 0),
        "executed_round_count": int(getattr(item, "executed_round_count", 0) or 0),
        "skipped_round_count": int(getattr(item, "skipped_round_count", 0) or 0),
        "failed_round_count": int(getattr(item, "failed_round_count", 0) or 0),
        "total_runtime_seconds": int(getattr(item, "total_runtime_seconds", 0) or 0),
        "total_runtime_hours": float(getattr(item, "total_runtime_hours", 0.0) or 0.0),
        "device_online_rate": float(getattr(item, "device_online_rate", 0.0) or 0.0),
        "failed_rate": float(getattr(item, "failed_rate", 0.0) or 0.0),
        "offline_rate": float(getattr(item, "offline_rate", 0.0) or 0.0),
        "recovery_success_rate": float(getattr(item, "recovery_success_rate", 0.0) or 0.0),
        "quarantined_device_count": int(getattr(item, "quarantined_device_count", 0) or 0),
        "quarantined_device_ids": list(getattr(item, "quarantined_device_ids", ()) or ()),
        "issue_type_distribution": dict(getattr(item, "issue_type_distribution", {}) or {}),
        "top_issue_types": [dict(entry) for entry in (getattr(item, "top_issue_types", ()) or ())],
        "interruption_rounds": [dict(entry) for entry in (getattr(item, "interruption_rounds", ()) or ())],
        "task_summaries": [dict(entry) for entry in (getattr(item, "task_summaries", ()) or ())],
        "metrics": dict(getattr(item, "metrics", {}) or {}),
    }


def _unattended_weekly_report_payload(item: object) -> dict[str, object]:
    return {
        "week_key": str(getattr(item, "week_key", "") or ""),
        "anchor_date": str(getattr(item, "anchor_date", "") or ""),
        "week_start_date": str(getattr(item, "week_start_date", "") or ""),
        "week_end_date": str(getattr(item, "week_end_date", "") or ""),
        "generated_at": _isoformat_or_none(getattr(item, "generated_at", None)),
        "task_count": int(getattr(item, "task_count", 0) or 0),
        "active_task_count": int(getattr(item, "active_task_count", 0) or 0),
        "active_day_count": int(getattr(item, "active_day_count", 0) or 0),
        "round_count": int(getattr(item, "round_count", 0) or 0),
        "executed_round_count": int(getattr(item, "executed_round_count", 0) or 0),
        "skipped_round_count": int(getattr(item, "skipped_round_count", 0) or 0),
        "failed_round_count": int(getattr(item, "failed_round_count", 0) or 0),
        "total_runtime_seconds": int(getattr(item, "total_runtime_seconds", 0) or 0),
        "total_runtime_hours": float(getattr(item, "total_runtime_hours", 0.0) or 0.0),
        "device_online_rate": float(getattr(item, "device_online_rate", 0.0) or 0.0),
        "failed_rate": float(getattr(item, "failed_rate", 0.0) or 0.0),
        "offline_rate": float(getattr(item, "offline_rate", 0.0) or 0.0),
        "recovery_success_rate": float(getattr(item, "recovery_success_rate", 0.0) or 0.0),
        "quarantined_device_count": int(getattr(item, "quarantined_device_count", 0) or 0),
        "quarantined_device_ids": list(getattr(item, "quarantined_device_ids", ()) or ()),
        "issue_type_distribution": dict(getattr(item, "issue_type_distribution", {}) or {}),
        "top_issue_types": [dict(entry) for entry in (getattr(item, "top_issue_types", ()) or ())],
        "interruption_rounds": [dict(entry) for entry in (getattr(item, "interruption_rounds", ()) or ())],
        "task_summaries": [dict(entry) for entry in (getattr(item, "task_summaries", ()) or ())],
        "daily_summaries": [dict(entry) for entry in (getattr(item, "daily_summaries", ()) or ())],
        "metrics": dict(getattr(item, "metrics", {}) or {}),
    }
