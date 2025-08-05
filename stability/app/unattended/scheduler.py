from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

from stability.domain.value_objects import utcnow

from .models import (
    UnattendedPatrolSummary,
    UnattendedTaskRecord,
    UnattendedTaskRecordNotFound,
)


class UnattendedSchedulerMixin:
    def configure_task(
        self,
        task_id: str,
        *,
        interval_minutes: int,
        desired_device_count: int | None = None,
        primary_device_ids: Sequence[str] = (),
        backup_device_ids: Sequence[str] = (),
        failure_threshold: int = 3,
        max_round_history: int = 10,
        rotation_strategy: str = "round_robin",
        rotation_advance_policy: str = "every_round",
        max_device_window_history: int = 10,
        enabled: bool = True,
        start_now: bool = False,
    ) -> UnattendedTaskRecord:
        task = self._require_task(task_id)
        config = self._load_config(task)
        config.enabled = enabled
        config.interval_minutes = max(1, int(interval_minutes or 60))
        config.desired_device_count = max(
            1,
            int(desired_device_count or len(primary_device_ids or task.selected_device_ids) or 1),
        )
        config.failure_threshold = max(1, int(failure_threshold or 3))
        config.max_round_history = max(1, int(max_round_history or 10))
        config.rotation_strategy = self._normalize_rotation_strategy(rotation_strategy)
        config.rotation_advance_policy = self._normalize_rotation_advance_policy(rotation_advance_policy)
        config.max_device_window_history = max(1, int(max_device_window_history or 10))
        config.primary_device_ids = list(primary_device_ids or task.selected_device_ids)
        config.backup_device_ids = list(backup_device_ids)
        now = utcnow()
        config.next_run_at = now if start_now else now + timedelta(minutes=config.interval_minutes)
        config.rotation_cursor = self._normalize_rotation_cursor(
            config.rotation_cursor,
            config.primary_device_ids,
            config.rotation_strategy,
        )
        config.long_run_summary = self._build_long_run_summary(config)
        self._save_config(task, config)
        return self.get_task_record(task_id)

    def list_task_records(
        self,
        *,
        configured_only: bool = True,
        enabled_only: bool = False,
        due_only: bool = False,
        limit: int | None = None,
    ) -> list[UnattendedTaskRecord]:
        items: list[UnattendedTaskRecord] = []
        for task in self._task_repository.list():
            config = self._load_config(task)
            if configured_only and not config.configured:
                continue
            if not config.enabled and enabled_only:
                continue
            record = self._build_task_record(task, config)
            if due_only and not record.due:
                continue
            items.append(record)
        items.sort(
            key=lambda item: (
                item.next_run_at or datetime.max,
                item.task_id,
            )
        )
        if limit is not None:
            items = items[: max(0, int(limit))]
        return items

    def get_task_record(self, task_id: str) -> UnattendedTaskRecord:
        task = self._require_task(task_id)
        return self._build_task_record(task, self._load_config(task))

    def run_due_tasks(
        self,
        *,
        task_id: str = "",
        force: bool = False,
        requested_by: str = "automation",
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ) -> UnattendedPatrolSummary:
        task_records = (
            [self.get_task_record(task_id.strip())]
            if task_id.strip()
            else self.list_task_records()
        )
        probe_results = self._probe_quarantined_devices(
            task_records=task_records,
            scoped=bool(task_id.strip()),
        )
        executed_rounds: list[dict[str, Any]] = []
        skipped_count = 0
        executed_count = 0
        for record in task_records:
            if not force and not record.due:
                skipped_count += 1
                continue
            result = self.run_task_round(
                record.task_id,
                force=force,
                requested_by=requested_by,
                persist_monitoring=persist_monitoring,
                collect_snapshot=collect_snapshot,
                stop_on_failure=stop_on_failure,
                max_concurrency=max_concurrency,
                retry_count=retry_count,
            )
            if result.executed:
                executed_count += 1
            else:
                skipped_count += 1
            executed_rounds.append(dict(result.round_record))
        refreshed_records = (
            [self.get_task_record(task_id.strip())]
            if task_id.strip()
            else self.list_task_records()
        )
        return self._build_patrol_summary(
            task_records=refreshed_records,
            explicit_task_ids=[task_id.strip()] if task_id.strip() else [],
            executed_rounds=executed_rounds,
            executed_task_count=executed_count,
            skipped_task_count=skipped_count,
            quarantine_probe_results=probe_results,
        )

    def build_patrol_summary(self, *, task_id: str = "") -> UnattendedPatrolSummary:
        task_records = (
            [self.get_task_record(task_id.strip())]
            if task_id.strip()
            else self.list_task_records()
        )
        return self._build_patrol_summary(
            task_records=task_records,
            explicit_task_ids=[task_id.strip()] if task_id.strip() else [],
            executed_rounds=[],
            executed_task_count=0,
            skipped_task_count=0,
            quarantine_probe_results=[],
        )

    def _build_patrol_summary(
        self,
        *,
        task_records: Sequence[UnattendedTaskRecord],
        explicit_task_ids: Sequence[str],
        executed_rounds: Sequence[dict[str, Any]],
        executed_task_count: int,
        skipped_task_count: int,
        quarantine_probe_results: Sequence[dict[str, Any]],
    ) -> UnattendedPatrolSummary:
        if explicit_task_ids:
            records = list(task_records)
        else:
            records = self.list_task_records()
        total_instances = 0
        failed_instances = 0
        offline_events = 0
        recovery_attempts = 0
        recovery_successes = 0
        for record in records:
            for round_record in record.recent_rounds:
                total_instances += int(round_record.get("instance_count", 0) or 0)
                failed_instances += int(round_record.get("failed_instance_count", 0) or 0)
                offline_events += int(round_record.get("offline_event_count", 0) or 0)
                recovery_attempts += int(round_record.get("recovery_attempt_count", 0) or 0)
                recovery_successes += int(round_record.get("recovery_success_count", 0) or 0)
        quarantined_devices = self._device_service.list_quarantined_devices()
        probe_attempts = sum(1 for item in quarantine_probe_results if bool(item.get("attempted", False)))
        probe_skipped = sum(1 for item in quarantine_probe_results if bool(item.get("skipped", False)))
        probe_recovered = [
            str(item.get("device_id", "") or "")
            for item in quarantine_probe_results
            if bool(item.get("recovered", False))
        ]
        failure_rate = failed_instances / total_instances if total_instances > 0 else 0.0
        offline_rate = offline_events / total_instances if total_instances > 0 else 0.0
        recovery_success_rate = recovery_successes / recovery_attempts if recovery_attempts > 0 else 0.0
        return UnattendedPatrolSummary(
            generated_at=utcnow(),
            task_count=len(records),
            enabled_task_count=sum(1 for item in records if item.enabled),
            due_task_count=sum(1 for item in records if item.due),
            executed_task_count=executed_task_count,
            skipped_task_count=skipped_task_count,
            failed_rate=failure_rate,
            offline_rate=offline_rate,
            recovery_success_rate=recovery_success_rate,
            quarantined_device_count=len(quarantined_devices),
            quarantined_device_ids=tuple(device.device_id for device in quarantined_devices),
            quarantine_probe_attempt_count=probe_attempts,
            quarantine_probe_skipped_count=probe_skipped,
            quarantine_probe_recovered_count=len(probe_recovered),
            recovered_device_ids=tuple(item for item in probe_recovered if item),
            quarantine_probe_results=tuple(dict(item) for item in quarantine_probe_results),
            task_records=tuple(records),
            executed_rounds=tuple(dict(item) for item in executed_rounds),
            metrics={
                "instance_count": total_instances,
                "failed_instance_count": failed_instances,
                "offline_event_count": offline_events,
                "recovery_attempt_count": recovery_attempts,
                "recovery_success_count": recovery_successes,
                "quarantine_probe_attempt_count": probe_attempts,
                "quarantine_probe_skipped_count": probe_skipped,
                "quarantine_probe_recovered_count": len(probe_recovered),
            },
        )

    def _probe_quarantined_devices(
        self,
        *,
        task_records: Sequence[UnattendedTaskRecord],
        scoped: bool,
    ) -> list[dict[str, Any]]:
        device_ids: tuple[str, ...] = ()
        if scoped:
            scoped_ids: set[str] = set()
            for record in task_records:
                scoped_ids.update(str(item).strip() for item in record.primary_device_ids if str(item).strip())
                scoped_ids.update(str(item).strip() for item in record.backup_device_ids if str(item).strip())
            device_ids = tuple(sorted(scoped_ids))
        results = self._device_service.probe_quarantined_devices(
            device_ids=device_ids,
            actor="unattended",
            occurred_at=utcnow(),
        )
        return [
            {
                "device_id": str(getattr(item, "device_id", "") or ""),
                "serial": str(getattr(item, "serial", "") or ""),
                "attempted": bool(getattr(item, "attempted", False)),
                "recovered": bool(getattr(item, "recovered", False)),
                "skipped": bool(getattr(item, "skipped", False)),
                "reason": str(getattr(item, "reason", "") or ""),
                "probed_at": self._isoformat(getattr(item, "probed_at", None)),
                "next_probe_at": self._isoformat(getattr(item, "next_probe_at", None)),
            }
            for item in results
        ]

    def _require_task(self, task_id: str):
        task = self._task_repository.get(task_id)
        if task is None:
            raise UnattendedTaskRecordNotFound(f"Task '{task_id}' was not found.")
        return task
