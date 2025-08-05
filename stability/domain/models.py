from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from .enums import (
    ArtifactCaptureStatus,
    ArtifactType,
    DeviceAvailabilityState,
    DeviceConnectionState,
    ExecutionStatus,
    ExitReason,
    IssueType,
    MetricType,
    ResultLevel,
    SeverityLevel,
    TaskRunStatus,
    TaskTemplateType,
)
from .value_objects import (
    DeviceSnapshot,
    ExecutionSummary,
    SamplingConfig,
    TaskRunSummary,
    TaskTargetApp,
    new_id,
    utcnow,
)


@dataclass(slots=True)
class Device:
    device_id: str = field(default_factory=lambda: new_id("device"))
    serial: str = ""
    brand: str = ""
    model: str = ""
    android_version: str = ""
    rom_version: str = ""
    abi: str = ""
    battery_level: float | None = None
    temperature: float | None = None
    connection_state: DeviceConnectionState = DeviceConnectionState.UNKNOWN
    availability_state: DeviceAvailabilityState = DeviceAvailabilityState.IDLE
    group_name: str = ""
    tags: list[str] = field(default_factory=list)
    last_heartbeat_at: datetime | None = None
    current_instance_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.model or self.serial or self.device_id

    def is_online(self) -> bool:
        return self.connection_state == DeviceConnectionState.ONLINE

    def is_schedulable(self) -> bool:
        return self.is_online() and self.availability_state == DeviceAvailabilityState.IDLE and not self.is_under_maintenance()

    @property
    def team_name(self) -> str:
        return str(self.metadata.get("team") or self.metadata.get("team_name") or "").strip()

    @property
    def owner(self) -> str:
        return str(self.metadata.get("owner") or "").strip()

    @property
    def priority(self) -> int:
        try:
            return int(self.metadata.get("priority", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def capabilities(self) -> list[str]:
        payload = self.metadata.get("capabilities", [])
        if isinstance(payload, str):
            payload = [item.strip() for item in payload.split(",")]
        if not isinstance(payload, list):
            return []
        return sorted({str(item).strip() for item in payload if str(item).strip()})

    def is_under_maintenance(self) -> bool:
        return bool(self.metadata.get("maintenance") or self.metadata.get("maintenance_mode"))

    @property
    def maintenance_reason(self) -> str:
        return str(self.metadata.get("maintenance_reason") or "").strip()

    def touch_heartbeat(self, seen_at: datetime | None = None) -> None:
        self.last_heartbeat_at = seen_at or utcnow()

    def reserve_for(self, instance_id: str) -> None:
        self.current_instance_id = instance_id
        self.availability_state = DeviceAvailabilityState.RESERVED
        self.touch_heartbeat()

    def mark_running(self, instance_id: str | None = None) -> None:
        if instance_id:
            self.current_instance_id = instance_id
        self.availability_state = DeviceAvailabilityState.RUNNING
        self.touch_heartbeat()

    def release(self) -> None:
        self.current_instance_id = None
        self.availability_state = DeviceAvailabilityState.IDLE
        self.touch_heartbeat()

    def mark_quarantined(self, *, reason: str = "", quarantined_at: datetime | None = None) -> None:
        self.current_instance_id = None
        self.availability_state = DeviceAvailabilityState.QUARANTINED
        if reason:
            self.metadata["quarantine_reason"] = reason
        self.touch_heartbeat(quarantined_at)

    def clear_quarantine(self, *, released_at: datetime | None = None) -> None:
        self.current_instance_id = None
        if self.is_online():
            self.availability_state = DeviceAvailabilityState.IDLE
        else:
            self.availability_state = DeviceAvailabilityState.ERROR
        self.touch_heartbeat(released_at)

    def snapshot(self, captured_at: datetime | None = None) -> DeviceSnapshot:
        return DeviceSnapshot(
            device_id=self.device_id,
            serial=self.serial,
            brand=self.brand,
            model=self.model,
            android_version=self.android_version,
            rom_version=self.rom_version,
            abi=self.abi,
            group_name=self.group_name,
            tags=list(self.tags),
            captured_at=captured_at or utcnow(),
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class TaskDefinition:
    task_id: str = field(default_factory=lambda: new_id("task"))
    task_name: str = ""
    template_type: TaskTemplateType = TaskTemplateType.CUSTOM
    target_app: TaskTargetApp = field(default_factory=lambda: TaskTargetApp(package_name=""))
    task_params: dict[str, Any] = field(default_factory=dict)
    selected_device_ids: list[str] = field(default_factory=list)
    device_selector: dict[str, Any] = field(default_factory=dict)
    sampling_config: SamplingConfig = field(default_factory=SamplingConfig)
    duration_seconds: int = 0
    timeout_seconds: int = 0
    created_by: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def planned_device_count(self) -> int:
        return len(self.selected_device_ids)

    def uses_device(self, device_id: str) -> bool:
        return device_id in self.selected_device_ids

    def sampling_enabled(self) -> bool:
        return self.sampling_config.is_enabled()


@dataclass(slots=True)
class TaskRun:
    run_id: str = field(default_factory=lambda: new_id("run"))
    task_definition_id: str = ""
    task_name: str = ""
    status: TaskRunStatus = TaskRunStatus.DRAFT
    planned_device_count: int = 0
    target_device_ids: list[str] = field(default_factory=list)
    started_by: str = ""
    created_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: TaskRunSummary = field(default_factory=TaskRunSummary)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def run_status(self) -> str:
        return self.status.value

    @run_status.setter
    def run_status(self, value: str | TaskRunStatus) -> None:
        self.status = value if isinstance(value, TaskRunStatus) else TaskRunStatus(value)

    def mark_queued(self) -> None:
        self.status = TaskRunStatus.QUEUED

    def mark_started(self, started_at: datetime | None = None) -> None:
        self.status = TaskRunStatus.RUNNING
        self.started_at = started_at or self.started_at or utcnow()

    def mark_finished(self, status: TaskRunStatus, finished_at: datetime | None = None) -> None:
        self.status = status
        self.finished_at = finished_at or utcnow()

    def apply_summary_payload(self, payload: dict[str, Any]) -> None:
        if not payload:
            return
        note = payload.get("note")
        if note:
            self.summary.notes.append(str(note))
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            self.metadata.update(metadata)

    def sync_from_instances(self, instances: Iterable[ExecutionInstance]) -> None:
        items = list(instances)
        if not items:
            self.summary = TaskRunSummary()
            return

        active_count = 0
        success_count = 0
        failed_count = 0
        cancelled_count = 0
        pending_count = 0
        issue_count = 0
        first_issue_at: datetime | None = None

        for item in items:
            issue_count += len(item.issues)
            if item.summary.first_issue_at and first_issue_at is None:
                first_issue_at = item.summary.first_issue_at
            if item.status.is_active:
                active_count += 1
            elif item.status == ExecutionStatus.SUCCESS:
                success_count += 1
            elif item.status in {ExecutionStatus.FAILED, ExecutionStatus.PRECHECK_FAILED}:
                failed_count += 1
            elif item.status == ExecutionStatus.CANCELLED:
                cancelled_count += 1
            else:
                pending_count += 1

        self.summary = TaskRunSummary(
            total_instances=len(items),
            pending_instances=pending_count,
            active_instances=active_count,
            success_instances=success_count,
            failed_instances=failed_count,
            cancelled_instances=cancelled_count,
            total_issues=issue_count,
            first_issue_at=first_issue_at,
        )

        if active_count > 0:
            self.mark_started()
            return

        if pending_count == len(items):
            self.status = TaskRunStatus.QUEUED
            return

        terminal_count = success_count + failed_count + cancelled_count
        if terminal_count != len(items):
            self.status = TaskRunStatus.RUNNING
            return

        if success_count == len(items):
            self.mark_finished(TaskRunStatus.SUCCESS)
        elif failed_count == len(items):
            self.mark_finished(TaskRunStatus.FAILED)
        elif cancelled_count == len(items):
            self.mark_finished(TaskRunStatus.CANCELLED)
        else:
            self.mark_finished(TaskRunStatus.PARTIAL_FAILED)


@dataclass(slots=True)
class IssueRecord:
    issue_id: str = field(default_factory=lambda: new_id("issue"))
    instance_id: str = ""
    task_run_id: str = ""
    device_id: str = ""
    issue_type: IssueType = IssueType.CRASH
    issue_title: str = ""
    severity: SeverityLevel = SeverityLevel.MEDIUM
    detected_at: datetime = field(default_factory=utcnow)
    source: str = ""
    raw_key: str = ""
    process_name: str = ""
    package_name: str = ""
    pid: int | None = None
    summary: str = ""
    is_deduplicated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_blocking(self) -> bool:
        return self.severity in {SeverityLevel.HIGH, SeverityLevel.CRITICAL}

    def deduplication_key(self) -> str:
        return self.raw_key or "|".join(
            [
                self.issue_type.value,
                self.package_name,
                self.process_name,
                self.issue_title,
            ]
        )


@dataclass(slots=True)
class ArtifactRecord:
    artifact_id: str = field(default_factory=lambda: new_id("artifact"))
    task_run_id: str = ""
    instance_id: str = ""
    issue_id: str | None = None
    artifact_type: ArtifactType = ArtifactType.LOGCAT
    file_path: str = ""
    captured_at: datetime = field(default_factory=utcnow)
    capture_started_at: datetime | None = None
    capture_finished_at: datetime | None = None
    size_bytes: int | None = None
    capture_status: ArtifactCaptureStatus = ArtifactCaptureStatus.PENDING
    capture_reason: str = ""
    capture_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        return self.capture_status == ArtifactCaptureStatus.SUCCESS and bool(self.file_path)

    def mark_captured(self, captured_at: datetime | None = None, size_bytes: int | None = None) -> None:
        now = captured_at or utcnow()
        self.captured_at = now
        self.capture_finished_at = now
        self.size_bytes = size_bytes if size_bytes is not None else self.size_bytes
        self.capture_status = ArtifactCaptureStatus.SUCCESS

    def mark_failed(self, message: str) -> None:
        self.capture_status = ArtifactCaptureStatus.FAILED
        self.capture_message = message
        self.capture_finished_at = utcnow()


@dataclass(slots=True)
class PerformanceSummary:
    metric_id: str = field(default_factory=lambda: new_id("metric"))
    instance_id: str = ""
    metric_type: MetricType = MetricType.CUSTOM
    sampling_start_at: datetime | None = None
    sampling_end_at: datetime | None = None
    summary_payload: dict[str, Any] = field(default_factory=dict)
    chart_path: str = ""
    sample_count: int = 0
    average_value: float | None = None
    peak_value: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def sampling_duration_seconds(self) -> float | None:
        if not self.sampling_start_at or not self.sampling_end_at:
            return None
        return (self.sampling_end_at - self.sampling_start_at).total_seconds()

    def has_chart(self) -> bool:
        return bool(self.chart_path)


@dataclass(slots=True)
class ExecutionInstance:
    instance_id: str = field(default_factory=lambda: new_id("instance"))
    run_id: str = ""
    task_definition_id: str = ""
    device_id: str = ""
    device_snapshot: DeviceSnapshot | None = None
    template_type: TaskTemplateType = TaskTemplateType.CUSTOM
    target_app_package: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    queued_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_reason: ExitReason = ExitReason.UNKNOWN
    result_level: ResultLevel = ResultLevel.UNKNOWN
    monitoring_session_id: str | None = None
    summary: ExecutionSummary = field(default_factory=ExecutionSummary)
    issues: list[IssueRecord] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    performance_summaries: list[PerformanceSummary] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def instance_status(self) -> str:
        return self.status.value

    @instance_status.setter
    def instance_status(self, value: str | ExecutionStatus) -> None:
        if isinstance(value, ExecutionStatus):
            self.status = value
            return
        aliases = {
            "completed": ExecutionStatus.SUCCESS,
        }
        self.status = aliases.get(value, ExecutionStatus(value))

    def mark_preparing(self, started_at: datetime | None = None) -> None:
        self.status = ExecutionStatus.PREPARING
        self.started_at = started_at or self.started_at or utcnow()

    def mark_running(self, started_at: datetime | None = None) -> None:
        self.status = ExecutionStatus.RUNNING
        self.started_at = started_at or self.started_at or utcnow()

    def mark_stopping(self) -> None:
        self.status = ExecutionStatus.STOPPING

    def mark_collecting(self) -> None:
        self.status = ExecutionStatus.COLLECTING

    def mark_finished(
        self,
        status: ExecutionStatus,
        *,
        exit_reason: ExitReason,
        result_level: ResultLevel,
        note: str = "",
        finished_at: datetime | None = None,
    ) -> None:
        self.status = status
        self.exit_reason = exit_reason
        self.result_level = result_level
        self.finished_at = finished_at or utcnow()
        if note:
            self.summary.note = note

    def add_issue(self, issue: IssueRecord) -> None:
        self.issues.append(issue)
        self.summary.record_issue(issue.detected_at)

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        self.artifacts.append(artifact)
        self.summary.record_artifact()

    def add_performance_summary(self, metric: PerformanceSummary) -> None:
        self.performance_summaries.append(metric)

    def first_issue_at(self) -> datetime | None:
        return self.summary.first_issue_at

    def duration_seconds(self) -> float | None:
        if not self.started_at or not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def apply_summary_payload(self, payload: dict[str, Any]) -> None:
        if not payload:
            return
        note = payload.get("note")
        if note:
            self.summary.note = str(note)
        highlights = payload.get("highlights")
        if isinstance(highlights, list):
            self.summary.highlights.extend(str(item) for item in highlights)
        first_issue_at = payload.get("first_issue_at")
        if isinstance(first_issue_at, datetime):
            self.summary.first_issue_at = first_issue_at
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            self.summary.metadata.update(metadata)
