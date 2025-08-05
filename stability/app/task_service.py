from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

from stability.scenario.registry import get_scenario_definition, validate_scenario_task_contract
from stability.domain.value_objects import new_id, utcnow
from stability.time_utils import format_beijing_datetime


class TaskDefinitionLike(Protocol):
    """Protocol for V1 task definitions created by the domain layer."""

    task_id: Optional[str]
    task_name: str


class TaskRepository(Protocol):
    """Persistence contract for task definitions."""

    def add(self, task: TaskDefinitionLike) -> TaskDefinitionLike:
        ...

    def get(self, task_id: str) -> Optional[TaskDefinitionLike]:
        ...

    def list(self) -> Sequence[TaskDefinitionLike]:
        ...

    def save(self, task: TaskDefinitionLike) -> TaskDefinitionLike:
        ...


class TaskAuditEventSink(Protocol):
    """Optional event sink for task lifecycle audit events."""

    def publish_event(
        self,
        *,
        event_type: str,
        target_type: str,
        target_id: str,
        created_by: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        ...


TaskValidator = Callable[[TaskDefinitionLike], None]


class TaskRecordNotFound(LookupError):
    """Raised when a requested task definition does not exist."""


@dataclass(frozen=True)
class TaskCreateResult:
    """Return object for task creation requests."""

    task: TaskDefinitionLike
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class TaskArchiveResult:
    """Return object for soft deletion / archive requests."""

    task: TaskDefinitionLike
    archived_at: datetime
    audit_event: Mapping[str, Any]


class TaskService:
    """Thin application service for task-definition orchestration."""

    def __init__(
        self,
        repository: TaskRepository,
        validators: Optional[Iterable[TaskValidator]] = None,
        audit_event_sink: TaskAuditEventSink | None = None,
    ) -> None:
        self._repository = repository
        self._validators = list(validators or [])
        self._audit_event_sink = audit_event_sink

    def create_task(self, task: TaskDefinitionLike) -> TaskCreateResult:
        """Validate and persist a task definition."""
        self._validate(task)
        self._ensure_default_name(task)
        created = self._repository.add(task)
        return TaskCreateResult(task=created)

    def get_task(self, task_id: str) -> TaskDefinitionLike:
        task = self._repository.get(task_id)
        if task is None:
            raise TaskRecordNotFound(f"Task '{task_id}' was not found.")
        return task

    def list_tasks(self, *, include_archived: bool = False) -> List[TaskDefinitionLike]:
        tasks = list(self._repository.list())
        if include_archived:
            return tasks
        return [task for task in tasks if not self._is_archived(task)]

    def save_task(self, task: TaskDefinitionLike) -> TaskDefinitionLike:
        self._validate(task)
        self._ensure_default_name(task)
        return self._repository.save(task)

    def update_task_fields(self, task_id: str, **updates: Any) -> TaskDefinitionLike:
        task = self.get_task(task_id)
        for field_name, value in updates.items():
            setattr(task, field_name, value)
        self._validate(task)
        return self._repository.save(task)

    def archive_task(
        self,
        task_id: str,
        *,
        actor_id: str,
        reason: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> TaskArchiveResult:
        """Soft-delete a task by hiding it from default lists and recording audit evidence."""
        task = self.get_task(task_id)
        now = utcnow()
        metadata = dict(getattr(task, "metadata", {}) or {})
        lifecycle = dict(metadata.get("lifecycle", {}) or {})
        previous_state = str(lifecycle.get("state", metadata.get("status", "active")) or "active")
        audit_payload = dict(audit_source or {})
        audit_event = {
            "audit_event_id": str(audit_payload.get("audit_event_id", "") or new_id("audit_event")),
            "action": "task.archived",
            "target_type": "task",
            "target_id": task_id,
            "actor_id": actor_id.strip() or str(audit_payload.get("resolved_actor_id", "") or "system"),
            "identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
            "session_id": str(audit_payload.get("resolved_session_id", "") or ""),
            "auth_mechanism": str(audit_payload.get("auth_mechanism", "") or ""),
            "request_id": str(audit_payload.get("request_id", "") or ""),
            "reason": reason.strip(),
            "previous_state": previous_state,
            "new_state": "archived",
            "created_at": now.isoformat(),
        }
        lifecycle.update(
            {
                "state": "archived",
                "archived": True,
                "hidden": True,
                "archived_at": now.isoformat(),
                "archived_by": audit_event["actor_id"],
                "archive_reason": reason.strip(),
            }
        )
        audit_events = list(metadata.get("audit_events", []) or [])
        audit_events.append(audit_event)
        metadata.update(
            {
                "status": "archived",
                "archived": True,
                "hidden": True,
                "archived_at": now.isoformat(),
                "archived_by": audit_event["actor_id"],
                "archive_reason": reason.strip(),
                "lifecycle": lifecycle,
                "audit_events": audit_events,
            }
        )
        setattr(task, "metadata", metadata)
        if hasattr(task, "updated_at"):
            setattr(task, "updated_at", now)
        archived = self._repository.save(task)
        if self._audit_event_sink is not None:
            self._audit_event_sink.publish_event(
                event_type="task.archived",
                target_type="task",
                target_id=task_id,
                created_by=audit_event["actor_id"],
                session_source=str(audit_payload.get("actor_session_source", "") or ""),
                audit_source=audit_payload,
                payload={
                    "task_id": task_id,
                    "previous_state": previous_state,
                    "new_state": "archived",
                    "hidden": True,
                    "reason": reason.strip(),
                    "audit_event": audit_event,
                },
            )
        return TaskArchiveResult(task=archived, archived_at=now, audit_event=audit_event)

    def describe_task(self, task: TaskDefinitionLike, *, include_metadata: bool = True) -> Dict[str, Any]:
        """Return a lightweight summary safe for GUI or CLI callers."""
        target_app = getattr(task, "target_app", None)
        package_name = getattr(task, "package_name", None)
        if not package_name and target_app is not None:
            package_name = getattr(target_app, "package_name", None)
        template_type = getattr(task, "template_type", None)
        sampling_config = getattr(task, "sampling_config", None)
        payload = {
            "task_id": getattr(task, "task_id", None),
            "task_name": getattr(task, "task_name", None),
            "template_type": getattr(template_type, "value", template_type),
            "package_name": package_name,
            "target_app": asdict(target_app) if target_app is not None else None,
            "selected_device_ids": list(getattr(task, "selected_device_ids", ()) or ()),
            "planned_device_count": getattr(task, "planned_device_count", lambda: 0)(),
            "task_params": dict(getattr(task, "task_params", {}) or {}),
            "sampling_config": asdict(sampling_config) if sampling_config is not None else {},
            "duration_seconds": getattr(task, "duration_seconds", 0),
            "timeout_seconds": getattr(task, "timeout_seconds", 0),
            "created_by": getattr(task, "created_by", None),
            "created_at": self._isoformat_or_none(getattr(task, "created_at", None)),
            "updated_at": self._isoformat_or_none(getattr(task, "updated_at", None)),
            "notes": getattr(task, "notes", ""),
            "status": getattr(task, "status", None),
            "archived": self._is_archived(task),
            "hidden": self._is_hidden(task),
            "archived_at": self._isoformat_or_none(self._metadata_datetime(task, "archived_at")),
            "archived_by": str(dict(getattr(task, "metadata", {}) or {}).get("archived_by", "") or ""),
            "archive_reason": str(dict(getattr(task, "metadata", {}) or {}).get("archive_reason", "") or ""),
        }
        if payload["template_type"]:
            try:
                definition = get_scenario_definition(str(payload["template_type"]))
                payload["template"] = {
                    "template_type": definition.value,
                    "chinese_name": definition.chinese_name,
                    "description": definition.description,
                    "risk_level": definition.risk_level,
                    "requires_device": definition.requires_device,
                    "requires_apk": definition.requires_apk,
                    "changes_device_state": definition.changes_device_state,
                    "risk_note": definition.risk_note,
                    "supported_metrics": list(definition.supported_metrics),
                    "default_metrics": list(definition.default_metrics),
                }
            except KeyError:
                payload["template"] = {"template_type": str(payload["template_type"]), "unknown": True}
        if include_metadata:
            payload["metadata"] = dict(getattr(task, "metadata", {}) or {})
        return payload

    def list_task_summaries(self, *, include_archived: bool = False) -> List[Dict[str, Any]]:
        return [
            self.describe_task(task, include_metadata=False)
            for task in sorted(
                self.list_tasks(include_archived=include_archived),
                key=lambda item: (
                    self._sortable_datetime(getattr(item, "created_at", None)),
                    getattr(item, "task_id", "") or "",
                ),
                reverse=True,
            )
        ]

    @staticmethod
    def _isoformat_or_none(value: Any) -> str | None:
        return format_beijing_datetime(value)

    @staticmethod
    def _sortable_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.min

    @classmethod
    def _is_archived(cls, task: TaskDefinitionLike) -> bool:
        metadata = dict(getattr(task, "metadata", {}) or {})
        lifecycle = dict(metadata.get("lifecycle", {}) or {})
        return bool(
            metadata.get("archived")
            or str(metadata.get("status", "") or "").lower() == "archived"
            or lifecycle.get("archived")
            or lifecycle.get("state") == "archived"
        )

    @classmethod
    def _is_hidden(cls, task: TaskDefinitionLike) -> bool:
        metadata = dict(getattr(task, "metadata", {}) or {})
        lifecycle = dict(metadata.get("lifecycle", {}) or {})
        return bool(metadata.get("hidden") or lifecycle.get("hidden") or cls._is_archived(task))

    @staticmethod
    def _metadata_datetime(task: TaskDefinitionLike, key: str) -> Any:
        value = dict(getattr(task, "metadata", {}) or {}).get(key)
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value.strip())
            except ValueError:
                return value
        return None

    def _validate(self, task: TaskDefinitionLike) -> None:
        sampling_config = getattr(task, "sampling_config", None)
        validate_scenario_task_contract(
            template_type=getattr(task, "template_type", ""),
            task_params=dict(getattr(task, "task_params", {}) or {}),
            enabled_metrics=list(getattr(sampling_config, "enabled_metrics", ()) or ()),
        )
        for validator in self._validators:
            validator(task)

    @staticmethod
    def _ensure_default_name(task: TaskDefinitionLike) -> None:
        if getattr(task, "task_name", None):
            return
        task_id = getattr(task, "task_id", None) or "draft"
        setattr(task, "task_name", f"task-{task_id}")
