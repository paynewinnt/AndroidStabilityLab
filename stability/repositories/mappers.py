from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from stability.infrastructure.persistence import (
    ArtifactRecordModel,
    DeviceRecord,
    ExecutionInstanceRecord,
    IssueRecordModel,
    TaskDefinitionRecord,
    TaskRunRecord,
)
from stability.domain import (
    ArtifactCaptureStatus,
    ArtifactRecord,
    ArtifactType,
    Device,
    DeviceSnapshot,
    ExecutionInstance,
    ExecutionSummary,
    ExitReason,
    IssueRecord,
    IssueType,
    ResultLevel,
    SamplingConfig,
    SeverityLevel,
    TaskDefinition,
    TaskRun,
    TaskRunStatus,
    TaskRunSummary,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.domain.enums import ExecutionStatus


def task_to_record(
    task: TaskDefinition,
    *,
    record: TaskDefinitionRecord | None = None,
) -> TaskDefinitionRecord:
    record = record or TaskDefinitionRecord()
    record.task_id = task.task_id
    record.task_name = task.task_name
    record.package_name = task.target_app.package_name
    record.app_label = task.target_app.app_label or None
    record.template_type = task.template_type.value
    record.template_params_json = _dump_json(
        {
            "task_params": dict(task.task_params),
            "metadata": dict(task.metadata),
            "target_app": {
                "version_name": task.target_app.version_name,
                "version_code": task.target_app.version_code,
                "launch_activity": task.target_app.launch_activity,
            },
        }
    )
    record.device_selector_json = _dump_json(
        {
            "selected_device_ids": list(task.selected_device_ids),
            "selector": dict(task.device_selector),
        }
    )
    record.sampling_config_json = _dump_json(
        {
            "interval_seconds": task.sampling_config.interval_seconds,
            "enabled_metrics": list(task.sampling_config.enabled_metrics),
            "monitoring_profile": task.sampling_config.monitoring_profile,
            "metadata": dict(task.sampling_config.metadata),
        }
    )
    record.duration_sec = task.duration_seconds or None
    record.sampling_interval_sec = task.sampling_config.interval_seconds or None
    record.timeout_seconds = task.timeout_seconds or None
    record.created_by = task.created_by or None
    record.status = str(task.metadata.get("status", "draft"))
    record.summary = task.notes or None
    record.created_at = task.created_at
    record.updated_at = task.updated_at
    return record


def task_from_record(record: TaskDefinitionRecord) -> TaskDefinition:
    template_payload = _load_json(record.template_params_json)
    selector_payload = _load_json(record.device_selector_json)
    sampling_payload = _load_json(record.sampling_config_json)

    task_params = template_payload.get("task_params")
    if not isinstance(task_params, dict):
        task_params = {k: v for k, v in template_payload.items() if k not in {"metadata", "target_app"}}

    metadata = template_payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.setdefault("status", record.status)

    target_app_payload = template_payload.get("target_app")
    if not isinstance(target_app_payload, dict):
        target_app_payload = {}

    selected_device_ids = selector_payload.get("selected_device_ids")
    if not isinstance(selected_device_ids, list):
        selected_device_ids = []

    device_selector = selector_payload.get("selector")
    if not isinstance(device_selector, dict):
        device_selector = {
            key: value
            for key, value in selector_payload.items()
            if key != "selected_device_ids"
        }

    return TaskDefinition(
        task_id=record.task_id,
        task_name=record.task_name,
        template_type=_task_template_type(record.template_type),
        target_app=TaskTargetApp(
            package_name=record.package_name or "",
            app_label=record.app_label or "",
            version_name=str(target_app_payload.get("version_name", "")),
            version_code=str(target_app_payload.get("version_code", "")),
            launch_activity=str(target_app_payload.get("launch_activity", "")),
        ),
        task_params=dict(task_params),
        selected_device_ids=[str(item) for item in selected_device_ids],
        device_selector=dict(device_selector),
        sampling_config=_sampling_config_from_payload(record, sampling_payload),
        duration_seconds=record.duration_sec or 0,
        timeout_seconds=record.timeout_seconds or 0,
        created_by=record.created_by or "",
        created_at=record.created_at,
        updated_at=record.updated_at,
        notes=record.summary or "",
        metadata=metadata,
    )


def run_to_record(
    run: TaskRun,
    *,
    task_definition_pk: int,
    record: TaskRunRecord | None = None,
) -> TaskRunRecord:
    record = record or TaskRunRecord()
    record.run_id = run.run_id
    record.task_definition_id = task_definition_pk
    record.run_status = run.status.value
    record.planned_device_count = run.planned_device_count
    record.completed_instance_count = (
        run.summary.success_instances
        + run.summary.failed_instances
        + run.summary.cancelled_instances
    )
    record.success_instance_count = run.summary.success_instances
    record.failed_instance_count = run.summary.failed_instances
    record.started_at = run.started_at
    record.finished_at = run.finished_at
    record.created_at = run.created_at
    record.updated_at = run.finished_at or run.started_at or run.created_at
    record.summary = _dump_json(
        {
            "task_name": run.task_name,
            "target_device_ids": list(run.target_device_ids),
            "started_by": run.started_by,
            "metadata": dict(run.metadata),
            "summary": _task_run_summary_payload(run.summary),
        }
    )
    return record


def run_from_record(record: TaskRunRecord) -> TaskRun:
    payload = _load_json(record.summary)
    summary_payload = payload.get("summary")
    if not isinstance(summary_payload, dict):
        summary_payload = {}

    task_name = payload.get("task_name")
    if not isinstance(task_name, str) or not task_name:
        task_name = record.task_definition.task_name if record.task_definition else ""

    target_device_ids = payload.get("target_device_ids")
    if not isinstance(target_device_ids, list):
        target_device_ids = []

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return TaskRun(
        run_id=record.run_id,
        task_definition_id=record.task_definition.task_id if record.task_definition else "",
        task_name=task_name,
        status=_task_run_status(record.run_status),
        planned_device_count=record.planned_device_count,
        target_device_ids=[str(item) for item in target_device_ids],
        started_by=str(payload.get("started_by", "")),
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        summary=_task_run_summary_from_payload(record, summary_payload),
        metadata=metadata,
    )


def instance_to_record(
    instance: ExecutionInstance,
    *,
    task_run_pk: int,
    device_record_pk: int,
    record: ExecutionInstanceRecord | None = None,
) -> ExecutionInstanceRecord:
    record = record or ExecutionInstanceRecord()
    record.instance_id = instance.instance_id
    record.task_run_id = task_run_pk
    record.device_record_id = device_record_pk
    record.status = instance.status.value
    record.result = instance.status.value if instance.status.is_terminal else None
    record.result_level = instance.result_level.value
    record.exit_reason = instance.exit_reason.value
    record.device_snapshot_json = _dump_json(_device_snapshot_payload(instance.device_snapshot))
    record.queued_at = instance.queued_at
    record.started_at = instance.started_at
    record.finished_at = instance.finished_at
    record.timeout_at = None
    record.first_issue_at = instance.summary.first_issue_at
    record.exception_count = instance.summary.issue_count or len(instance.issues)
    record.report_path = _optional_text(instance.metadata.get("report_path"))
    record.log_path = _optional_text(instance.metadata.get("log_path"))
    record.summary = _dump_json(
        {
            "template_type": instance.template_type.value,
            "target_app_package": instance.target_app_package,
            "monitoring_session_id": instance.monitoring_session_id,
            "metadata": dict(instance.metadata),
            "summary": _execution_summary_payload(instance.summary),
        }
    )
    if instance.monitoring_session_id and str(instance.monitoring_session_id).isdigit():
        record.monitoring_session_id = int(str(instance.monitoring_session_id))
    else:
        record.monitoring_session_id = None
    return record


def instance_from_record(record: ExecutionInstanceRecord) -> ExecutionInstance:
    payload = _load_json(record.summary)
    summary_payload = payload.get("summary")
    if not isinstance(summary_payload, dict):
        summary_payload = {}

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    if record.report_path and "report_path" not in metadata:
        metadata["report_path"] = record.report_path
    if record.log_path and "log_path" not in metadata:
        metadata["log_path"] = record.log_path

    template_type_value = payload.get("template_type")
    if not isinstance(template_type_value, str) or not template_type_value:
        template_type_value = (
            record.task_run.task_definition.template_type
            if record.task_run and record.task_run.task_definition
            else TaskTemplateType.CUSTOM.value
        )

    target_app_package = payload.get("target_app_package")
    if not isinstance(target_app_package, str) or not target_app_package:
        target_app_package = (
            record.task_run.task_definition.package_name
            if record.task_run and record.task_run.task_definition
            else ""
        )

    monitoring_session_id = payload.get("monitoring_session_id")
    if monitoring_session_id is None and record.monitoring_session_id is not None:
        monitoring_session_id = str(record.monitoring_session_id)

    return ExecutionInstance(
        instance_id=record.instance_id,
        run_id=record.task_run.run_id if record.task_run else "",
        task_definition_id=(
            record.task_run.task_definition.task_id
            if record.task_run and record.task_run.task_definition
            else ""
        ),
        device_id=record.device.device_id if record.device else "",
        device_snapshot=_device_snapshot_from_record(record),
        template_type=_task_template_type(template_type_value),
        target_app_package=target_app_package,
        status=_execution_status(record.status),
        queued_at=record.queued_at or record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        exit_reason=_exit_reason(record.exit_reason),
        result_level=_result_level(record.result_level),
        monitoring_session_id=str(monitoring_session_id or ""),
        summary=_execution_summary_from_payload(record, summary_payload),
        issues=[issue_from_record(item, record) for item in getattr(record, "issues", [])],
        artifacts=[artifact_from_record(item, record) for item in getattr(record, "artifacts", [])],
        metadata=metadata,
    )


def issue_to_record(
    issue: IssueRecord,
    *,
    execution_instance_pk: int,
    record: IssueRecordModel | None = None,
) -> IssueRecordModel:
    """Map one domain issue record into the SQLAlchemy issue model."""
    record = record or IssueRecordModel()
    record.issue_id = issue.issue_id
    record.execution_instance_id = execution_instance_pk
    record.issue_type = issue.issue_type.value
    record.issue_title = issue.issue_title
    record.severity = issue.severity.value
    record.source = _optional_text(issue.source)
    record.raw_key = _optional_text(issue.raw_key)
    record.summary = _optional_text(issue.summary)
    record.detected_at = issue.detected_at
    record.payload_json = _dump_json(
        {
            "instance_id": issue.instance_id,
            "task_run_id": issue.task_run_id,
            "device_id": issue.device_id,
            "process_name": issue.process_name,
            "package_name": issue.package_name,
            "pid": issue.pid,
            "is_deduplicated": issue.is_deduplicated,
            "metadata": dict(issue.metadata),
        }
    )
    return record


def issue_from_record(record: IssueRecordModel, instance_record: ExecutionInstanceRecord | None = None) -> IssueRecord:
    """Map one SQLAlchemy issue record back into the domain issue model."""
    payload = _load_json(record.payload_json)
    if not isinstance(payload, dict):
        payload = {}
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    instance_ref = instance_record or getattr(record, "execution_instance", None)
    task_run_ref = getattr(instance_ref, "task_run", None) if instance_ref is not None else None
    return IssueRecord(
        issue_id=record.issue_id,
        instance_id=str(payload.get("instance_id", instance_ref.instance_id if instance_ref else "")),
        task_run_id=str(payload.get("task_run_id", task_run_ref.run_id if task_run_ref else "")),
        device_id=str(payload.get("device_id", instance_ref.device.device_id if instance_ref and instance_ref.device else "")),
        issue_type=_issue_type(record.issue_type),
        issue_title=record.issue_title or "",
        severity=_severity_level(record.severity),
        detected_at=record.detected_at,
        source=record.source or "",
        raw_key=record.raw_key or "",
        process_name=str(payload.get("process_name", "")),
        package_name=str(payload.get("package_name", "")),
        pid=payload.get("pid") if isinstance(payload.get("pid"), int) else None,
        summary=record.summary or "",
        is_deduplicated=bool(payload.get("is_deduplicated", False)),
        metadata=metadata,
    )


def artifact_to_record(
    artifact: ArtifactRecord,
    *,
    execution_instance_pk: int,
    issue_record_pk: int | None = None,
    record: ArtifactRecordModel | None = None,
) -> ArtifactRecordModel:
    """Map one domain artifact record into the SQLAlchemy artifact model."""
    record = record or ArtifactRecordModel()
    record.artifact_id = artifact.artifact_id
    record.execution_instance_id = execution_instance_pk
    record.issue_record_id = issue_record_pk
    record.artifact_type = artifact.artifact_type.value
    record.file_path = artifact.file_path
    record.file_name = Path(artifact.file_path).name if artifact.file_path else None
    record.size_bytes = artifact.size_bytes
    record.capture_reason = _optional_text(artifact.capture_reason)
    record.capture_status = artifact.capture_status.value
    record.captured_at = artifact.captured_at
    record.metadata_json = _dump_json(dict(artifact.metadata))
    return record


def artifact_from_record(
    record: ArtifactRecordModel,
    instance_record: ExecutionInstanceRecord | None = None,
) -> ArtifactRecord:
    """Map one SQLAlchemy artifact record back into the domain artifact model."""
    metadata = _load_json(record.metadata_json)
    if not isinstance(metadata, dict):
        metadata = {}
    instance_ref = instance_record or getattr(record, "execution_instance", None)
    task_run_ref = getattr(instance_ref, "task_run", None) if instance_ref is not None else None
    issue_ref = getattr(record, "issue", None)
    artifact = ArtifactRecord(
        artifact_id=record.artifact_id,
        task_run_id=getattr(task_run_ref, "run_id", "") or "",
        instance_id=getattr(instance_ref, "instance_id", "") or "",
        issue_id=getattr(issue_ref, "issue_id", None),
        artifact_type=_artifact_type(record.artifact_type),
        file_path=record.file_path or "",
        captured_at=record.captured_at,
        size_bytes=record.size_bytes,
        capture_status=_artifact_capture_status(record.capture_status),
        capture_reason=record.capture_reason or "",
        metadata=metadata,
    )
    artifact.capture_finished_at = record.captured_at
    return artifact


def device_record_from_snapshot(
    device_id: str,
    snapshot: DeviceSnapshot | None,
    *,
    record: DeviceRecord | None = None,
) -> DeviceRecord:
    record = record or DeviceRecord()
    record.device_id = device_id
    record.serial_no = snapshot.serial if snapshot and snapshot.serial else device_id
    record.brand = snapshot.brand if snapshot else None
    record.model = snapshot.model if snapshot else None
    record.android_version = snapshot.android_version if snapshot else None
    record.rom_version = snapshot.rom_version if snapshot else None
    record.abi = snapshot.abi if snapshot else None
    record.group_name = snapshot.group_name if snapshot and snapshot.group_name else None
    record.tags_json = _dump_json(list(snapshot.tags)) if snapshot else None
    record.last_seen_at = snapshot.captured_at if snapshot else None
    record.last_heartbeat_at = snapshot.captured_at if snapshot else None
    record.online_status = "online"
    record.occupy_status = "idle"
    record.extra_json = _dump_json(dict(snapshot.metadata)) if snapshot else None
    return record


def device_to_record(
    device: Device,
    *,
    record: DeviceRecord | None = None,
) -> DeviceRecord:
    record = record or DeviceRecord()
    record.device_id = device.device_id
    record.serial_no = device.serial or device.device_id
    record.brand = device.brand or None
    record.model = device.model or None
    record.android_version = device.android_version or None
    record.rom_version = device.rom_version or None
    record.abi = device.abi or None
    record.battery_level = device.battery_level
    record.temperature = device.temperature
    record.online_status = device.connection_state.value
    record.occupy_status = device.availability_state.value
    record.group_name = device.group_name or None
    record.tags_json = _dump_json(list(device.tags))
    record.last_seen_at = device.last_heartbeat_at
    record.last_heartbeat_at = device.last_heartbeat_at
    extra_json = dict(device.metadata)
    if device.current_instance_id:
        extra_json["current_instance_id"] = device.current_instance_id
    record.extra_json = _dump_json(extra_json)
    return record


def device_from_record(record: DeviceRecord) -> Device:
    metadata = _load_json(record.extra_json)
    if not isinstance(metadata, dict):
        metadata = {}

    current_instance_id = metadata.pop("current_instance_id", None)
    tags = _load_json(record.tags_json)
    if not isinstance(tags, list):
        tags = []

    return Device(
        device_id=record.device_id,
        serial=record.serial_no or record.device_id,
        brand=record.brand or "",
        model=record.model or "",
        android_version=record.android_version or "",
        rom_version=record.rom_version or "",
        abi=record.abi or "",
        battery_level=record.battery_level,
        temperature=record.temperature,
        connection_state=_device_connection_state(record.online_status),
        availability_state=_device_availability_state(record.occupy_status),
        group_name=record.group_name or "",
        tags=[str(tag) for tag in tags],
        last_heartbeat_at=record.last_heartbeat_at,
        current_instance_id=str(current_instance_id) if current_instance_id else None,
        metadata=metadata,
    )


def _sampling_config_from_payload(
    record: TaskDefinitionRecord,
    payload: dict[str, Any],
) -> SamplingConfig:
    enabled_metrics = payload.get("enabled_metrics")
    if not isinstance(enabled_metrics, list):
        enabled_metrics = []
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    interval = payload.get("interval_seconds")
    if not isinstance(interval, int):
        interval = record.sampling_interval_sec or 5
    return SamplingConfig(
        interval_seconds=interval,
        enabled_metrics=[str(item) for item in enabled_metrics],
        monitoring_profile=str(payload.get("monitoring_profile", "")),
        metadata=metadata,
    )


def _task_run_summary_payload(summary: TaskRunSummary) -> dict[str, Any]:
    return {
        "total_instances": summary.total_instances,
        "pending_instances": summary.pending_instances,
        "active_instances": summary.active_instances,
        "success_instances": summary.success_instances,
        "failed_instances": summary.failed_instances,
        "cancelled_instances": summary.cancelled_instances,
        "total_issues": summary.total_issues,
        "first_issue_at": _format_datetime(summary.first_issue_at),
        "notes": list(summary.notes),
    }


def _task_run_summary_from_payload(
    record: TaskRunRecord,
    payload: dict[str, Any],
) -> TaskRunSummary:
    return TaskRunSummary(
        total_instances=int(payload.get("total_instances", record.planned_device_count or 0)),
        pending_instances=int(payload.get("pending_instances", 0)),
        active_instances=int(payload.get("active_instances", 0)),
        success_instances=int(payload.get("success_instances", record.success_instance_count or 0)),
        failed_instances=int(payload.get("failed_instances", record.failed_instance_count or 0)),
        cancelled_instances=int(payload.get("cancelled_instances", 0)),
        total_issues=int(payload.get("total_issues", 0)),
        first_issue_at=_parse_datetime(payload.get("first_issue_at")),
        notes=[str(item) for item in payload.get("notes", []) if item is not None],
    )


def _execution_summary_payload(summary: ExecutionSummary) -> dict[str, Any]:
    return {
        "issue_count": summary.issue_count,
        "artifact_count": summary.artifact_count,
        "first_issue_at": _format_datetime(summary.first_issue_at),
        "last_heartbeat_at": _format_datetime(summary.last_heartbeat_at),
        "note": summary.note,
        "highlights": list(summary.highlights),
        "metadata": dict(summary.metadata),
    }


def _execution_summary_from_payload(
    record: ExecutionInstanceRecord,
    payload: dict[str, Any],
) -> ExecutionSummary:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return ExecutionSummary(
        issue_count=int(payload.get("issue_count", record.exception_count or 0)),
        artifact_count=int(payload.get("artifact_count", 0)),
        first_issue_at=record.first_issue_at or _parse_datetime(payload.get("first_issue_at")),
        last_heartbeat_at=_parse_datetime(payload.get("last_heartbeat_at")),
        note=str(payload.get("note", "")),
        highlights=[str(item) for item in payload.get("highlights", []) if item is not None],
        metadata=metadata,
    )


def _device_snapshot_payload(snapshot: DeviceSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    payload = asdict(snapshot)
    payload["captured_at"] = _format_datetime(snapshot.captured_at)
    return payload


def _device_snapshot_from_record(record: ExecutionInstanceRecord) -> DeviceSnapshot | None:
    payload = _load_json(record.device_snapshot_json)
    if payload:
        return DeviceSnapshot(
            device_id=str(payload.get("device_id", record.device.device_id if record.device else "")),
            serial=str(payload.get("serial", "")),
            brand=str(payload.get("brand", "")),
            model=str(payload.get("model", "")),
            android_version=str(payload.get("android_version", "")),
            rom_version=str(payload.get("rom_version", "")),
            abi=str(payload.get("abi", "")),
            group_name=str(payload.get("group_name", "")),
            tags=[str(item) for item in payload.get("tags", []) if item is not None],
            captured_at=_parse_datetime(payload.get("captured_at")) or record.created_at,
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {},
        )

    if record.device is None:
        return None

    tags_payload = _load_json(record.device.tags_json)
    tags = tags_payload if isinstance(tags_payload, list) else []
    metadata_payload = _load_json(record.device.extra_json)
    metadata = metadata_payload if isinstance(metadata_payload, dict) else {}

    return DeviceSnapshot(
        device_id=record.device.device_id,
        serial=record.device.serial_no,
        brand=record.device.brand or "",
        model=record.device.model or "",
        android_version=record.device.android_version or "",
        rom_version=record.device.rom_version or "",
        abi=record.device.abi or "",
        group_name=record.device.group_name or "",
        tags=[str(item) for item in tags if item is not None],
        captured_at=record.device.last_seen_at or record.device.created_at,
        metadata=metadata,
    )


def _dump_json(payload: Any) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _load_json(payload: str | None) -> Any:
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _task_template_type(value: str | TaskTemplateType | None) -> TaskTemplateType:
    if isinstance(value, TaskTemplateType):
        return value
    try:
        return TaskTemplateType(value or TaskTemplateType.CUSTOM.value)
    except ValueError:
        return TaskTemplateType.CUSTOM


def _task_run_status(value: str | TaskRunStatus | None) -> TaskRunStatus:
    if isinstance(value, TaskRunStatus):
        return value
    try:
        return TaskRunStatus(value or TaskRunStatus.DRAFT.value)
    except ValueError:
        return TaskRunStatus.DRAFT


def _execution_status(value: str | ExecutionStatus | None) -> ExecutionStatus:
    if isinstance(value, ExecutionStatus):
        return value
    try:
        return ExecutionStatus(value or ExecutionStatus.PENDING.value)
    except ValueError:
        return ExecutionStatus.PENDING


def _exit_reason(value: str | ExitReason | None) -> ExitReason:
    if isinstance(value, ExitReason):
        return value
    try:
        return ExitReason(value or ExitReason.UNKNOWN.value)
    except ValueError:
        return ExitReason.UNKNOWN


def _result_level(value: str | ResultLevel | None) -> ResultLevel:
    if isinstance(value, ResultLevel):
        return value
    try:
        return ResultLevel(value or ResultLevel.UNKNOWN.value)
    except ValueError:
        return ResultLevel.UNKNOWN


def _issue_type(value: str | IssueType | None) -> IssueType:
    if isinstance(value, IssueType):
        return value
    try:
        return IssueType(value or IssueType.CRASH.value)
    except ValueError:
        return IssueType.CRASH


def _severity_level(value: str | SeverityLevel | None) -> SeverityLevel:
    if isinstance(value, SeverityLevel):
        return value
    try:
        return SeverityLevel(value or SeverityLevel.MEDIUM.value)
    except ValueError:
        return SeverityLevel.MEDIUM


def _artifact_type(value: str | ArtifactType | None) -> ArtifactType:
    if isinstance(value, ArtifactType):
        return value
    try:
        return ArtifactType(value or ArtifactType.EXECUTION_LOG.value)
    except ValueError:
        return ArtifactType.EXECUTION_LOG


def _artifact_capture_status(value: str | ArtifactCaptureStatus | None) -> ArtifactCaptureStatus:
    if isinstance(value, ArtifactCaptureStatus):
        return value
    try:
        return ArtifactCaptureStatus(value or ArtifactCaptureStatus.PENDING.value)
    except ValueError:
        return ArtifactCaptureStatus.PENDING


def _device_connection_state(value: str | None):
    from stability.domain import DeviceConnectionState

    if not value:
        return DeviceConnectionState.UNKNOWN
    try:
        return DeviceConnectionState(value)
    except ValueError:
        return DeviceConnectionState.UNKNOWN


def _device_availability_state(value: str | None):
    from stability.domain import DeviceAvailabilityState

    if not value:
        return DeviceAvailabilityState.IDLE
    try:
        return DeviceAvailabilityState(value)
    except ValueError:
        return DeviceAvailabilityState.IDLE
