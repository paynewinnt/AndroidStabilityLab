from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping, Sequence

from stability.app.task_service import TaskRecordNotFound
from stability.domain import SamplingConfig, TaskDefinition, TaskTargetApp, TaskTemplateType
from stability.time_utils import format_beijing_datetime_or_original


@dataclass(frozen=True)
class CreateTaskCommand:
    task_name: str
    template_type: str
    package_name: str
    app_label: str = ""
    version_name: str = ""
    version_code: str = ""
    launch_activity: str = ""
    task_params: Mapping[str, Any] | None = None
    selected_device_ids: Sequence[str] = ()
    sampling_interval: int = 5
    enabled_metrics: Sequence[str] = ()
    duration_seconds: int = 0
    timeout_seconds: int = 0
    created_by: str = ""
    notes: str = ""
    metadata: Mapping[str, Any] | None = None
    storage_mode: str = "persistent"
    sync_devices: bool = False


@dataclass(frozen=True)
class CreateRunCommand:
    task_id: str
    requested_device_ids: Sequence[str] = ()
    requested_by: str = ""
    metadata: Mapping[str, Any] | None = None
    sync_devices: bool = False


@dataclass(frozen=True)
class ExecuteRunCommand:
    run_id: str
    persist_monitoring: bool = True
    collect_snapshot: bool = True
    stop_on_failure: bool = False
    max_concurrency: int = 1
    retry_count: int = 0
    monitoring_backend: str = ""
    requested_monitoring_backend: str = ""


def resolve_monitoring_backend_override(value: str) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate in {"", "default"}:
        return None
    return candidate


def create_task(bundle: object, command: CreateTaskCommand) -> dict[str, Any]:
    task_service = getattr(bundle, "task_service", None)
    if task_service is None or not hasattr(task_service, "create_task"):
        raise ValueError("Task service is unavailable.")
    sync_payload = _sync_devices_if_requested(bundle, enabled=command.sync_devices)
    try:
        template_type = TaskTemplateType(str(command.template_type).strip())
    except ValueError as exc:
        raise ValueError(f"Unsupported template_type: {command.template_type}") from exc

    task = TaskDefinition(
        task_name=str(command.task_name).strip(),
        template_type=template_type,
        target_app=TaskTargetApp(
            package_name=str(command.package_name).strip(),
            app_label=str(command.app_label or "").strip(),
            version_name=str(command.version_name or "").strip(),
            version_code=str(command.version_code or "").strip(),
            launch_activity=str(command.launch_activity or "").strip(),
        ),
        task_params=dict(command.task_params or {}),
        selected_device_ids=[str(item).strip() for item in command.selected_device_ids if str(item).strip()],
        sampling_config=SamplingConfig(
            interval_seconds=int(command.sampling_interval or 0),
            enabled_metrics=[str(item).strip() for item in command.enabled_metrics if str(item).strip()],
        ),
        duration_seconds=int(command.duration_seconds or 0),
        timeout_seconds=int(command.timeout_seconds or 0),
        created_by=str(command.created_by or "").strip(),
        notes=str(command.notes or ""),
        metadata=dict(command.metadata or {}),
    )

    result = task_service.create_task(task)
    created_task = getattr(result, "task", task)
    payload = _task_create_payload(
        result=result,
        task=created_task,
        storage_mode=command.storage_mode,
    )
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    return payload


def create_run(bundle: object, command: CreateRunCommand) -> dict[str, Any]:
    task_service = getattr(bundle, "task_service", None)
    execution_service = getattr(bundle, "execution_service", None)
    if task_service is None or execution_service is None:
        raise ValueError("Execution services are unavailable.")
    sync_payload = _sync_devices_if_requested(bundle, enabled=command.sync_devices)
    try:
        task = task_service.get_task(str(command.task_id).strip())
    except TaskRecordNotFound:
        raise

    requested_device_ids = [str(item).strip() for item in command.requested_device_ids if str(item).strip()]
    metadata = dict(command.metadata or {})
    plan = execution_service.plan_run(task, requested_devices=requested_device_ids, metadata=metadata)
    if not list(getattr(plan, "dispatches", ()) or ()):
        selection_scope = requested_device_ids or list(getattr(task, "selected_device_ids", []) or [])
        selection_message = f"requested devices {selection_scope}" if selection_scope else "the current device inventory"
        raise ValueError(f"No schedulable devices matched {selection_message}; run was not created.")

    result = execution_service.create_run(
        task,
        requested_devices=requested_device_ids,
        requested_by=str(command.requested_by or "").strip(),
        metadata=metadata,
    )
    payload = _run_create_payload(task=task, result=result, plan=plan)
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    return payload


def execute_run(run_execution_service: object, command: ExecuteRunCommand) -> dict[str, Any]:
    if run_execution_service is None or not hasattr(run_execution_service, "execute_run"):
        raise ValueError("Run execution service is unavailable.")
    result = run_execution_service.execute_run(
        str(command.run_id).strip(),
        persist_monitoring=bool(command.persist_monitoring),
        collect_snapshot=bool(command.collect_snapshot),
        stop_on_failure=bool(command.stop_on_failure),
        max_concurrency=max(int(command.max_concurrency or 1), 1),
        retry_count=max(int(command.retry_count or 0), 0),
    )
    return _run_execute_payload(
        result=result,
        monitoring_backend=str(command.monitoring_backend or ""),
        requested_monitoring_backend=str(command.requested_monitoring_backend or ""),
        max_concurrency=max(int(command.max_concurrency or 1), 1),
        retry_count=max(int(command.retry_count or 0), 0),
    )


def _sync_devices_if_requested(bundle: object, *, enabled: bool) -> dict[str, Any] | None:
    service = getattr(bundle, "device_service", None)
    if not enabled or service is None or not hasattr(service, "sync_devices"):
        return None
    result = service.sync_devices(include_unavailable=True, mark_missing_offline=True)
    return {
        "scanned_count": int(getattr(result, "scanned_count", 0) or 0),
        "created_count": len(getattr(result, "created", ()) or ()),
        "updated_count": len(getattr(result, "updated", ()) or ()),
        "refreshed_count": len(getattr(result, "refreshed", ()) or ()),
        "marked_offline_count": len(getattr(result, "marked_offline", ()) or ()),
    }


def _task_create_payload(*, result: object, task: object, storage_mode: str) -> dict[str, Any]:
    return {
        "storage_mode": storage_mode,
        "task_id": str(getattr(task, "task_id", "") or ""),
        "task_name": str(getattr(task, "task_name", "") or ""),
        "template_type": _enum_value(getattr(task, "template_type", "")),
        "package_name": str(getattr(getattr(task, "target_app", None), "package_name", "") or ""),
        "device_count": int(getattr(task, "planned_device_count", lambda: 0)() or 0),
        "selected_device_ids": list(getattr(task, "selected_device_ids", ()) or ()),
        "task_params": dict(getattr(task, "task_params", {}) or {}),
        "sampling_interval": int(getattr(getattr(task, "sampling_config", None), "interval_seconds", 0) or 0),
        "enabled_metrics": list(getattr(getattr(task, "sampling_config", None), "enabled_metrics", ()) or ()),
        "created_by": str(getattr(task, "created_by", "") or ""),
        "created_at": _format_time(getattr(result, "created_at", None)),
        "target_app": _dataclass_payload(getattr(task, "target_app", None)),
    }


def _run_create_payload(*, task: object, result: object, plan: object) -> dict[str, Any]:
    run = getattr(result, "run", None)
    instances = list(getattr(result, "instances", ()) or ())
    return {
        "storage_mode": "persistent",
        "task_id": str(getattr(task, "task_id", "") or ""),
        "task_name": str(getattr(task, "task_name", "") or ""),
        "run_id": str(getattr(run, "run_id", "") or ""),
        "run_status": str(getattr(run, "run_status", "") or ""),
        "requested_device_ids": list(getattr(plan, "requested_devices", ()) or ()),
        "target_device_ids": list(getattr(run, "target_device_ids", ()) or ()),
        "planned_device_count": int(getattr(getattr(result, "plan", None), "planned_device_count", 0) or 0),
        "instance_count": len(instances),
        "instance_status_counts": _count_instance_statuses(instances),
        "started_by": str(getattr(run, "started_by", "") or ""),
        "created_at": _format_time(getattr(result, "created_at", None)),
        "summary": _json_safe_dict(getattr(run, "summary", {})),
        "instances": [_instance_payload(instance) for instance in instances],
    }


def _run_execute_payload(
    *,
    result: object,
    monitoring_backend: str,
    requested_monitoring_backend: str,
    max_concurrency: int,
    retry_count: int,
) -> dict[str, Any]:
    run = getattr(result, "run", None)
    instances = list(getattr(result, "instances", ()) or ())
    payload = {
        "storage_mode": "persistent",
        "task_id": str(getattr(getattr(result, "task", None), "task_id", "") or ""),
        "task_name": str(getattr(getattr(result, "task", None), "task_name", "") or ""),
        "run_id": str(getattr(run, "run_id", "") or ""),
        "run_status": str(getattr(run, "run_status", "") or ""),
        "instance_count": len(instances),
        "instance_status_counts": _count_instance_statuses(instances),
        "executed_at": _format_time(getattr(result, "executed_at", None)),
        "monitoring_backend": monitoring_backend,
        "max_concurrency": max_concurrency,
        "retry_count": retry_count,
        "report_paths": _json_safe_dict(getattr(result, "report_paths", {})),
        "instances": [_instance_payload(instance) for instance in instances],
        "executed_instance_count": int(getattr(result, "executed_instance_count", len(instances)) or 0),
        "skipped_instance_count": int(getattr(result, "skipped_instance_count", 0) or 0),
        "skipped_reason": str(getattr(result, "skipped_reason", "") or ""),
    }
    if requested_monitoring_backend:
        payload["requested_monitoring_backend"] = requested_monitoring_backend
    return payload


def _instance_payload(instance: object) -> dict[str, Any]:
    payload = {
        "instance_id": str(getattr(instance, "instance_id", "") or ""),
        "device_id": str(getattr(instance, "device_id", "") or ""),
        "status": str(getattr(instance, "instance_status", getattr(instance, "status", "")) or ""),
    }
    metadata = dict(getattr(instance, "metadata", {}) or {})
    for key in ("monitoring_backend", "monitoring_trace_path", "monitoring_snapshot_path"):
        value = str(metadata.get(key, "") or getattr(instance, key, "") or "").strip()
        if value:
            payload[key] = value
    return payload


def _count_instance_statuses(instances: Sequence[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for instance in instances:
        status = str(getattr(instance, "instance_status", getattr(instance, "status", "unknown")) or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _json_safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {
            str(key): item
            for key, item in dict(getattr(value, "__dict__", {}) or {}).items()
            if not str(key).startswith("_")
        }
    return {}


def _dataclass_payload(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    return _json_safe_dict(value)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _format_time(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)
