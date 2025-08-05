from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Sequence

from stability.domain import Device


class TaskDefinitionLike(Protocol):
    task_id: str
    task_name: str
    selected_device_ids: Sequence[str]
    metadata: dict[str, Any]
    updated_at: datetime


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskDefinitionLike]:
        ...

    def list(self) -> Sequence[TaskDefinitionLike]:
        ...

    def save(self, task: TaskDefinitionLike) -> TaskDefinitionLike:
        ...


class DeviceServiceLike(Protocol):
    def list_devices(self) -> list[Device]:
        ...

    def list_quarantined_devices(self) -> list[Device]:
        ...

    def probe_quarantined_devices(
        self,
        *,
        device_ids: Sequence[str] = (),
        actor: str = "system",
        probe_interval_minutes: int = 15,
        occurred_at: datetime | None = None,
    ) -> list[object]:
        ...

    def record_device_failure(
        self,
        device_id: str,
        *,
        reason: str,
        actor: str = "system",
        quarantine_threshold: int | None = None,
        occurred_at: datetime | None = None,
    ) -> Device:
        ...

    def record_device_success(
        self,
        device_id: str,
        *,
        actor: str = "system",
        occurred_at: datetime | None = None,
    ) -> Device:
        ...


class ExecutionServiceLike(Protocol):
    def create_run(
        self,
        task: TaskDefinitionLike,
        requested_devices: Optional[Sequence[str]] = None,
        requested_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        ...


class RunExecutionServiceLike(Protocol):
    def execute_run(
        self,
        run_id: str,
        *,
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ):
        ...


@dataclass(frozen=True)
class UnattendedTaskRecord:
    task_id: str
    task_name: str
    configured: bool
    enabled: bool
    interval_minutes: int
    desired_device_count: int
    failure_threshold: int
    rotation_strategy: str = "round_robin"
    rotation_advance_policy: str = "every_round"
    rotation_cursor: int = 0
    rotation_advance_count: int = 0
    primary_device_ids: tuple[str, ...] = field(default_factory=tuple)
    backup_device_ids: tuple[str, ...] = field(default_factory=tuple)
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_id: str = ""
    due: bool = False
    latest_summary: dict[str, Any] = field(default_factory=dict)
    long_run_summary: dict[str, Any] = field(default_factory=dict)
    recent_device_windows: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    recent_rounds: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UnattendedRoundExecutionResult:
    task: UnattendedTaskRecord
    executed: bool
    reason: str
    round_record: dict[str, Any]


@dataclass(frozen=True)
class UnattendedPatrolSummary:
    generated_at: datetime
    task_count: int
    enabled_task_count: int
    due_task_count: int
    executed_task_count: int
    skipped_task_count: int
    failed_rate: float
    offline_rate: float
    recovery_success_rate: float
    quarantined_device_count: int
    quarantined_device_ids: tuple[str, ...] = field(default_factory=tuple)
    quarantine_probe_attempt_count: int = 0
    quarantine_probe_skipped_count: int = 0
    quarantine_probe_recovered_count: int = 0
    recovered_device_ids: tuple[str, ...] = field(default_factory=tuple)
    quarantine_probe_results: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    task_records: tuple[UnattendedTaskRecord, ...] = field(default_factory=tuple)
    executed_rounds: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnattendedDailyReport:
    report_date: str
    generated_at: datetime
    task_count: int
    active_task_count: int
    round_count: int
    executed_round_count: int
    skipped_round_count: int
    failed_round_count: int
    total_runtime_seconds: int
    total_runtime_hours: float
    device_online_rate: float
    failed_rate: float
    offline_rate: float
    recovery_success_rate: float
    quarantined_device_count: int
    quarantined_device_ids: tuple[str, ...] = field(default_factory=tuple)
    issue_type_distribution: dict[str, int] = field(default_factory=dict)
    top_issue_types: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    interruption_rounds: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    task_summaries: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnattendedWeeklyReport:
    week_key: str
    anchor_date: str
    week_start_date: str
    week_end_date: str
    generated_at: datetime
    task_count: int
    active_task_count: int
    active_day_count: int
    round_count: int
    executed_round_count: int
    skipped_round_count: int
    failed_round_count: int
    total_runtime_seconds: int
    total_runtime_hours: float
    device_online_rate: float
    failed_rate: float
    offline_rate: float
    recovery_success_rate: float
    quarantined_device_count: int
    quarantined_device_ids: tuple[str, ...] = field(default_factory=tuple)
    issue_type_distribution: dict[str, int] = field(default_factory=dict)
    top_issue_types: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    interruption_rounds: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    task_summaries: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    daily_summaries: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LongRunTemplate:
    template_id: str
    name: str
    description: str
    default_template_type: str
    default_interval_minutes: int
    default_max_rounds: int
    recommended_device_count: int
    recommended_rotation_strategy: str
    default_tags: tuple[str, ...] = field(default_factory=tuple)
    risk_notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LongRunPlan:
    template: LongRunTemplate
    configure_kwargs: dict[str, Any]
    runner_kwargs: dict[str, Any]
    task_metadata_suggestions: dict[str, Any]
    overrides: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class _UnattendedConfig:
    configured: bool = False
    enabled: bool = False
    interval_minutes: int = 60
    desired_device_count: int = 1
    failure_threshold: int = 3
    rotation_strategy: str = "round_robin"
    rotation_advance_policy: str = "every_round"
    rotation_cursor: int = 0
    rotation_advance_count: int = 0
    primary_device_ids: list[str] = field(default_factory=list)
    backup_device_ids: list[str] = field(default_factory=list)
    max_round_history: int = 10
    max_device_window_history: int = 10
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_id: str = ""
    latest_summary: dict[str, Any] = field(default_factory=dict)
    long_run_summary: dict[str, Any] = field(default_factory=dict)
    recent_device_windows: list[dict[str, Any]] = field(default_factory=list)
    recent_rounds: list[dict[str, Any]] = field(default_factory=list)


class UnattendedTaskRecordNotFound(LookupError):
    """Raised when one unattended configuration references a missing task."""


class LongRunTemplateNotFound(LookupError):
    """Raised when a long-run template id is unknown."""
