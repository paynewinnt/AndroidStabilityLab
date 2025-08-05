from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Sequence

from stability.time_utils import format_beijing_datetime

from .run_execution_service import RunRecordNotFound


class TaskDefinitionLike(Protocol):
    task_id: str
    task_name: str
    template_type: object
    target_app: object


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskDefinitionLike]:
        ...


class TaskRunLike(Protocol):
    run_id: str
    task_definition_id: str
    task_name: str
    run_status: str
    planned_device_count: int
    target_device_ids: Sequence[str]
    started_by: str
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    summary: object
    metadata: dict[str, Any]


class RunRepository(Protocol):
    def get(self, run_id: str) -> Optional[TaskRunLike]:
        ...

    def list(self) -> Sequence[TaskRunLike]:
        ...


class ExecutionInstanceLike(Protocol):
    instance_id: str
    device_id: str
    instance_status: str
    exit_reason: object
    result_level: object
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    summary: object
    metadata: dict[str, Any]
    issues: Sequence[object]
    artifacts: Sequence[object]

    def duration_seconds(self) -> float | None:
        ...


class InstanceRepository(Protocol):
    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstanceLike]:
        ...


class RunHistoryService:
    """Query-oriented service for persisted task runs and their execution instances."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
    ) -> None:
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository

    def list_runs(
        self,
        *,
        task_id: str | None = None,
        run_status: str | None = None,
        template_type: str | None = None,
        package_name: str | None = None,
        device_id: str | None = None,
        has_issue: bool | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int | None = 20,
    ) -> List[Dict[str, Any]]:
        """Return lightweight run summaries ordered by newest first."""
        runs = list(self._run_repository.list())
        task_cache: Dict[str, TaskDefinitionLike | None] = {}
        created_from_dt = self._parse_iso_datetime(created_from)
        created_to_dt = self._parse_iso_datetime(created_to)
        if task_id:
            runs = [run for run in runs if getattr(run, "task_definition_id", "") == task_id]
        if run_status:
            runs = [run for run in runs if getattr(run, "run_status", "") == run_status]
        if template_type:
            runs = [
                run
                for run in runs
                if self._task_field(run, task_cache, "template_type") == template_type
            ]
        if package_name:
            runs = [
                run
                for run in runs
                if self._task_field(run, task_cache, "package_name") == package_name
            ]
        if device_id:
            runs = [
                run
                for run in runs
                if device_id in set(getattr(run, "target_device_ids", ()) or ())
                or any(
                    getattr(instance, "device_id", "") == device_id
                    for instance in self._instance_repository.list_by_run(getattr(run, "run_id", "") or "")
                )
            ]
        if has_issue is not None:
            runs = [
                run
                for run in runs
                if self._run_has_issue(run) is has_issue
            ]
        if created_from_dt is not None:
            runs = [
                run
                for run in runs
                if (getattr(run, "created_at", None) or datetime.min) >= created_from_dt
            ]
        if created_to_dt is not None:
            runs = [
                run
                for run in runs
                if (getattr(run, "created_at", None) or datetime.min) <= created_to_dt
            ]
        runs.sort(
            key=lambda item: getattr(item, "created_at", None) or datetime.min,
            reverse=True,
        )
        normalized_limit = self._normalize_limit(limit)
        if normalized_limit is not None:
            runs = runs[:normalized_limit]
        return [self._run_summary_payload(run) for run in runs]

    def get_run_detail(self, run_id: str) -> Dict[str, Any]:
        """Return one run plus its instances, task hints, and artifact/report paths."""
        run = self._run_repository.get(run_id)
        if run is None:
            raise RunRecordNotFound(f"Run '{run_id}' was not found.")

        instances = list(self._instance_repository.list_by_run(run_id))
        task = self._task_repository.get(getattr(run, "task_definition_id", "") or "")
        payload = self._run_summary_payload(run)
        payload.update(
            {
                "task": self._task_payload(task),
                "report_paths": {
                    getattr(instance, "instance_id", ""): str(getattr(instance, "metadata", {}).get("report_path", ""))
                    for instance in instances
                    if getattr(instance, "metadata", {}).get("report_path")
                },
                "html_report_paths": {
                    getattr(instance, "instance_id", ""): str(
                        getattr(instance, "metadata", {}).get("html_report_path", "")
                    )
                    for instance in instances
                    if getattr(instance, "metadata", {}).get("html_report_path")
                },
                "instances": [self._instance_payload(instance) for instance in instances],
            }
        )
        return payload

    @staticmethod
    def _normalize_limit(limit: int | None) -> int | None:
        if limit is None:
            return None
        return max(0, int(limit))

    @staticmethod
    def _task_payload(task: TaskDefinitionLike | None) -> Dict[str, Any]:
        if task is None:
            return {}
        target_app = getattr(task, "target_app", None)
        template_type = getattr(task, "template_type", None)
        return {
            "task_id": getattr(task, "task_id", None),
            "task_name": getattr(task, "task_name", None),
            "template_type": getattr(template_type, "value", template_type),
            "package_name": getattr(target_app, "package_name", None) if target_app is not None else None,
            "launch_activity": getattr(target_app, "launch_activity", None) if target_app is not None else None,
        }

    @classmethod
    def _run_summary_payload(cls, run: TaskRunLike) -> Dict[str, Any]:
        summary = getattr(run, "summary", None)
        return {
            "run_id": getattr(run, "run_id", None),
            "task_id": getattr(run, "task_definition_id", None),
            "task_name": getattr(run, "task_name", None),
            "run_status": getattr(run, "run_status", None),
            "planned_device_count": getattr(run, "planned_device_count", 0),
            "target_device_ids": list(getattr(run, "target_device_ids", ()) or ()),
            "started_by": getattr(run, "started_by", None),
            "created_at": cls._isoformat_or_none(getattr(run, "created_at", None)),
            "started_at": cls._isoformat_or_none(getattr(run, "started_at", None)),
            "finished_at": cls._isoformat_or_none(getattr(run, "finished_at", None)),
            "summary": cls._json_safe(asdict(summary)) if summary is not None else {},
            "instance_count": getattr(summary, "total_instances", 0) if summary is not None else 0,
            "instance_status_counts": cls._instance_status_counts_from_run(summary),
            "metadata": cls._json_safe(dict(getattr(run, "metadata", {}) or {})),
        }

    @classmethod
    def _instance_payload(cls, instance: ExecutionInstanceLike) -> Dict[str, Any]:
        summary = getattr(instance, "summary", None)
        metadata = dict(getattr(instance, "metadata", {}) or {})
        exit_reason = getattr(instance, "exit_reason", None)
        result_level = getattr(instance, "result_level", None)
        return {
            "instance_id": getattr(instance, "instance_id", None),
            "device_id": getattr(instance, "device_id", None),
            "status": getattr(instance, "instance_status", None),
            "exit_reason": getattr(exit_reason, "value", exit_reason),
            "result_level": getattr(result_level, "value", result_level),
            "queued_at": cls._isoformat_or_none(getattr(instance, "queued_at", None)),
            "started_at": cls._isoformat_or_none(getattr(instance, "started_at", None)),
            "finished_at": cls._isoformat_or_none(getattr(instance, "finished_at", None)),
            "duration_seconds": instance.duration_seconds(),
            "issue_count": len(getattr(instance, "issues", ()) or ()),
            "artifact_count": len(getattr(instance, "artifacts", ()) or ()),
            "note": getattr(summary, "note", ""),
            "highlights": list(getattr(summary, "highlights", ()) or ()),
            "report_path": metadata.get("report_path"),
            "html_report_path": metadata.get("html_report_path"),
            "execution_log_path": metadata.get("execution_log_path"),
            "monitoring_backend": metadata.get("monitoring_backend"),
            "monitoring_profile": metadata.get("monitoring_profile"),
            "monitoring_snapshot_path": metadata.get("monitoring_snapshot_path"),
            "monitoring_trace_path": metadata.get("monitoring_trace_path"),
            "monitoring_session_id": metadata.get("monitoring_session_id"),
        }

    @staticmethod
    def _instance_status_counts_from_run(summary: object | None) -> Dict[str, int]:
        if summary is None:
            return {}
        counts = {
            "pending": int(getattr(summary, "pending_instances", 0) or 0),
            "running": int(getattr(summary, "active_instances", 0) or 0),
            "success": int(getattr(summary, "success_instances", 0) or 0),
            "failed": int(getattr(summary, "failed_instances", 0) or 0),
            "cancelled": int(getattr(summary, "cancelled_instances", 0) or 0),
        }
        return {key: value for key, value in counts.items() if value > 0}

    @staticmethod
    def _isoformat_or_none(value: datetime | None) -> str | None:
        return format_beijing_datetime(value)

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [cls._json_safe(item) for item in value]
        return value

    def _task_field(
        self,
        run: TaskRunLike,
        cache: Dict[str, TaskDefinitionLike | None],
        field_name: str,
    ) -> str | None:
        task_id = getattr(run, "task_definition_id", "") or ""
        if task_id not in cache:
            cache[task_id] = self._task_repository.get(task_id)
        task = cache[task_id]
        payload = self._task_payload(task)
        value = payload.get(field_name)
        return str(value) if value not in (None, "") else None

    def _run_has_issue(self, run: TaskRunLike) -> bool:
        return any(
            len(getattr(instance, "issues", ()) or ()) > 0
            for instance in self._instance_repository.list_by_run(getattr(run, "run_id", "") or "")
        )

    @staticmethod
    def _parse_iso_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        normalized = raw.strip()
        if not normalized:
            return None
        try:
            return datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Invalid ISO datetime value: {raw}") from exc
