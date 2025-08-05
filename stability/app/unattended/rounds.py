from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from stability.domain.value_objects import new_id, utcnow

from .models import TaskDefinitionLike, UnattendedRoundExecutionResult, _UnattendedConfig


class UnattendedRoundExecutionMixin:
    def run_task_round(
        self,
        task_id: str,
        *,
        force: bool = True,
        requested_by: str = "automation",
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ) -> UnattendedRoundExecutionResult:
        task = self._require_task(task_id)
        config = self._load_config(task)
        record = self._build_task_record(task, config)
        now = utcnow()
        if not config.enabled:
            round_record = self._build_skipped_round(
                task=task,
                config=config,
                reason="task_disabled",
                scheduled_at=config.next_run_at,
                triggered_at=now,
            )
            return UnattendedRoundExecutionResult(task=record, executed=False, reason="task_disabled", round_record=round_record)
        if not force and not record.due:
            round_record = self._build_skipped_round(
                task=task,
                config=config,
                reason="not_due",
                scheduled_at=config.next_run_at,
                triggered_at=now,
            )
            return UnattendedRoundExecutionResult(task=record, executed=False, reason="not_due", round_record=round_record)

        selection = self._select_devices(task, config, occurred_at=now)
        if not selection["assigned_device_ids"]:
            round_record = self._build_skipped_round(
                task=task,
                config=config,
                reason="no_schedulable_devices",
                scheduled_at=config.next_run_at,
                triggered_at=now,
                selection=selection,
            )
            self._update_device_health((), selection["unavailable_device_ids"], config.failure_threshold, occurred_at=now)
            self._update_state_after_round(task, config, round_record, occurred_at=now)
            return UnattendedRoundExecutionResult(
                task=self._build_task_record(task, config),
                executed=False,
                reason="no_schedulable_devices",
                round_record=round_record,
            )

        round_id = new_id("round")
        run_metadata = {
            "automation": {
                "source": "unattended",
                "round_id": round_id,
                "scheduled_at": self._isoformat(config.next_run_at),
                "triggered_at": now.isoformat(),
                "preferred_device_ids": list(selection["preferred_device_ids"]),
                "assigned_device_ids": list(selection["assigned_device_ids"]),
                "unavailable_device_ids": list(selection["unavailable_device_ids"]),
                "replacement_events": list(selection["replacement_events"]),
            }
        }
        batch = self._execution_service.create_run(
            task,
            requested_devices=tuple(selection["assigned_device_ids"]),
            requested_by=requested_by,
            metadata=run_metadata,
        )
        executed = self._run_execution_service.execute_run(
            getattr(batch.run, "run_id", ""),
            persist_monitoring=persist_monitoring,
            collect_snapshot=collect_snapshot,
            stop_on_failure=stop_on_failure,
            max_concurrency=max_concurrency,
            retry_count=retry_count,
        )
        round_record = self._build_completed_round(
            task=task,
            config=config,
            executed=executed,
            round_id=round_id,
            scheduled_at=config.next_run_at,
            triggered_at=now,
            selection=selection,
        )
        self._update_device_health(executed.instances, selection["unavailable_device_ids"], config.failure_threshold, occurred_at=now)
        self._update_state_after_round(task, config, round_record, occurred_at=now, run_id=getattr(executed.run, "run_id", ""))
        return UnattendedRoundExecutionResult(
            task=self._build_task_record(task, config),
            executed=True,
            reason="executed",
            round_record=round_record,
        )

    def _update_device_health(
        self,
        instances: Sequence[object],
        unavailable_device_ids: Sequence[str],
        failure_threshold: int,
        *,
        occurred_at: datetime,
    ) -> None:
        for device_id in unavailable_device_ids:
            if device_id:
                self._record_device_failure_safe(
                    device_id,
                    reason="dispatch_unavailable",
                    failure_threshold=failure_threshold,
                    occurred_at=occurred_at,
                )

        for instance in instances:
            device_id = str(getattr(instance, "device_id", "") or "")
            if not device_id:
                continue
            if getattr(instance, "instance_status", "") == "success":
                self._device_service.record_device_success(device_id, actor="unattended", occurred_at=occurred_at)
                continue
            exit_reason = getattr(getattr(instance, "exit_reason", None), "value", getattr(instance, "exit_reason", ""))
            self._record_device_failure_safe(
                device_id,
                reason=str(exit_reason or "instance_failed"),
                failure_threshold=failure_threshold,
                occurred_at=occurred_at,
            )

    def _record_device_failure_safe(
        self,
        device_id: str,
        *,
        reason: str,
        failure_threshold: int,
        occurred_at: datetime,
    ) -> None:
        try:
            self._device_service.record_device_failure(
                device_id,
                reason=reason,
                actor="unattended",
                quarantine_threshold=failure_threshold,
                occurred_at=occurred_at,
            )
        except LookupError:
            return

    def _build_completed_round(
        self,
        *,
        task: TaskDefinitionLike,
        config: _UnattendedConfig,
        executed,
        round_id: str,
        scheduled_at: datetime | None,
        triggered_at: datetime,
        selection: dict[str, Any],
    ) -> dict[str, Any]:
        instances = list(getattr(executed, "instances", ()) or ())
        instance_status_counts = self._count_instance_statuses(instances)
        instance_count = len(instances)
        failed_instance_count = sum(
            count for status, count in instance_status_counts.items() if status in {"failed", "precheck_failed"}
        )
        offline_event_count = len(selection["unavailable_device_ids"]) + sum(
            1 for instance in instances if self._instance_has_offline_event(instance)
        )
        recovery_attempt_count = len(selection["replacement_events"])
        recovery_success_count = len(selection["replacement_events"])
        for instance in instances:
            attempted, succeeded = self._instance_recovery_outcome(instance)
            if attempted:
                recovery_attempt_count += 1
            if succeeded:
                recovery_success_count += 1
        run = getattr(executed, "run", None)
        return {
            "round_id": round_id,
            "task_id": task.task_id,
            "task_name": task.task_name,
            "run_id": getattr(run, "run_id", ""),
            "run_status": getattr(run, "run_status", ""),
            "status": getattr(run, "run_status", "") or ("success" if failed_instance_count == 0 else "failed"),
            "scheduled_at": self._isoformat(scheduled_at),
            "triggered_at": triggered_at.isoformat(),
            "finished_at": self._isoformat(getattr(run, "finished_at", None)),
            "preferred_device_ids": list(selection["preferred_device_ids"]),
            "assigned_device_ids": list(selection["assigned_device_ids"]),
            "unavailable_device_ids": list(selection["unavailable_device_ids"]),
            "replacement_events": list(selection["replacement_events"]),
            "rotation": dict(selection.get("rotation", {}) or {}),
            "instance_count": instance_count,
            "instance_status_counts": instance_status_counts,
            "failed_instance_count": failed_instance_count,
            "offline_event_count": offline_event_count,
            "recovery_attempt_count": recovery_attempt_count,
            "recovery_success_count": recovery_success_count,
            "issue_type_counts": self._count_issue_types(instances),
            "summary": {
                "desired_device_count": config.desired_device_count,
                "assigned_device_count": len(selection["assigned_device_ids"]),
            },
        }

    def _build_skipped_round(
        self,
        *,
        task: TaskDefinitionLike,
        config: _UnattendedConfig,
        reason: str,
        scheduled_at: datetime | None,
        triggered_at: datetime,
        selection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selection = selection or {
            "preferred_device_ids": list(config.primary_device_ids or task.selected_device_ids),
            "assigned_device_ids": [],
            "unavailable_device_ids": [],
            "replacement_events": [],
        }
        return {
            "round_id": new_id("round"),
            "task_id": task.task_id,
            "task_name": task.task_name,
            "run_id": "",
            "run_status": "",
            "status": reason,
            "scheduled_at": self._isoformat(scheduled_at),
            "triggered_at": triggered_at.isoformat(),
            "finished_at": triggered_at.isoformat(),
            "preferred_device_ids": list(selection["preferred_device_ids"]),
            "assigned_device_ids": list(selection["assigned_device_ids"]),
            "unavailable_device_ids": list(selection["unavailable_device_ids"]),
            "replacement_events": list(selection["replacement_events"]),
            "rotation": dict(selection.get("rotation", {}) or {}),
            "instance_count": 0,
            "instance_status_counts": {},
            "failed_instance_count": 0,
            "offline_event_count": len(selection["unavailable_device_ids"]),
            "recovery_attempt_count": len(selection["replacement_events"]),
            "recovery_success_count": 0,
            "issue_type_counts": {},
            "summary": {"reason": reason, "desired_device_count": config.desired_device_count},
        }

    @staticmethod
    def _count_instance_statuses(instances: Sequence[object]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for instance in instances:
            status = str(getattr(instance, "instance_status", "") or "")
            if not status:
                continue
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _count_issue_types(instances: Sequence[object]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for instance in instances:
            for issue in list(getattr(instance, "issues", ()) or ()):
                issue_type = getattr(getattr(issue, "issue_type", None), "value", getattr(issue, "issue_type", ""))
                issue_key = str(issue_type or "").strip()
                if not issue_key:
                    continue
                counts[issue_key] = counts.get(issue_key, 0) + 1
        return counts

    @staticmethod
    def _instance_has_offline_event(instance: object) -> bool:
        exit_reason = getattr(getattr(instance, "exit_reason", None), "value", getattr(instance, "exit_reason", ""))
        if exit_reason == "device_offline":
            return True
        issues = getattr(instance, "issues", ()) or ()
        for issue in issues:
            issue_type = getattr(getattr(issue, "issue_type", None), "value", getattr(issue, "issue_type", ""))
            if issue_type == "device_offline":
                return True
        return False

    @staticmethod
    def _instance_recovery_outcome(instance: object) -> tuple[bool, bool]:
        summary = getattr(instance, "summary", None)
        metadata = dict(getattr(summary, "metadata", {}) or {})
        execution_attempts = list(metadata.get("execution_attempts", []) or [])
        scenario_result = dict(metadata.get("scenario_result", {}) or {})
        attempted = False
        succeeded = False
        if scenario_result.get("recovered_after_disconnect") is True:
            attempted = True
            succeeded = getattr(instance, "instance_status", "") == "success"
        if any(bool(item.get("retryable")) for item in execution_attempts if isinstance(item, dict)):
            attempted = True
            if getattr(instance, "instance_status", "") == "success":
                succeeded = True
        return attempted, succeeded
