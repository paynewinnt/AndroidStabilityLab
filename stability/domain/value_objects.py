from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from stability.time_utils import utcnow


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(slots=True)
class DeviceSnapshot:
    device_id: str
    serial: str
    brand: str = ""
    model: str = ""
    android_version: str = ""
    rom_version: str = ""
    abi: str = ""
    group_name: str = ""
    tags: list[str] = field(default_factory=list)
    captured_at: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.model or self.serial or self.device_id


@dataclass(slots=True)
class TaskTargetApp:
    package_name: str
    app_label: str = ""
    version_name: str = ""
    version_code: str = ""
    launch_activity: str = ""

    @property
    def display_name(self) -> str:
        return self.app_label or self.package_name


@dataclass(slots=True)
class SamplingConfig:
    interval_seconds: int = 5
    enabled_metrics: list[str] = field(default_factory=list)
    monitoring_profile: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_enabled(self) -> bool:
        return self.interval_seconds > 0


@dataclass(slots=True)
class TaskRunSummary:
    total_instances: int = 0
    pending_instances: int = 0
    active_instances: int = 0
    success_instances: int = 0
    failed_instances: int = 0
    cancelled_instances: int = 0
    total_issues: int = 0
    first_issue_at: datetime | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionSummary:
    issue_count: int = 0
    artifact_count: int = 0
    first_issue_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    note: str = ""
    highlights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def record_issue(self, detected_at: datetime | None) -> None:
        self.issue_count += 1
        if detected_at and self.first_issue_at is None:
            self.first_issue_at = detected_at

    def record_artifact(self) -> None:
        self.artifact_count += 1
