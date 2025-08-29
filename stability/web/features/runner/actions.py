from __future__ import annotations

from typing import Any, Mapping


class RunnerActionsMixin:
    def _handle_unattended_configure(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        service = getattr(self._bundle, "unattended_service", None)
        if service is None or not hasattr(service, "configure_task"):
            raise ValueError("Unattended service is unavailable.")
        primary_device_ids = self._expand_form_values(payload, "devices") or self._expand_form_values(payload, "device")
        backup_device_ids = self._expand_form_values(payload, "backup_devices") or self._expand_form_values(payload, "backup_device")
        record = service.configure_task(
            task_id=self._required_form_value(dict(payload), "task_id"),
            interval_minutes=max(self._form_int(payload, "interval_minutes", default=30), 1),
            desired_device_count=self._form_optional_int(payload, "desired_device_count"),
            primary_device_ids=primary_device_ids,
            backup_device_ids=backup_device_ids,
            failure_threshold=max(self._form_int(payload, "failure_threshold", default=3), 0),
            max_round_history=max(self._form_int(payload, "max_round_history", default=10), 1),
            rotation_strategy=self._form_value(dict(payload), "rotation_strategy") or "round_robin",
            rotation_advance_policy=self._form_value(dict(payload), "rotation_advance_policy") or "every_round",
            max_device_window_history=max(self._form_int(payload, "max_device_window_history", default=10), 1),
            enabled=not self._form_bool(payload, "disabled", default=False),
            start_now=self._form_bool(payload, "start_now", default=False),
        )
        task_payload = self._unattended_task_payload(record)
        return {"storage_mode": "persistent", **task_payload, "unattended_task": task_payload}

    def _handle_unattended_run_round(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        actor = dict(request_context.get("current_actor", {}) or {})
        service = getattr(self._bundle, "unattended_service", None)
        if service is None or not hasattr(service, "run_task_round"):
            raise ValueError("Unattended service is unavailable.")
        result = service.run_task_round(
            task_id=self._required_form_value(dict(payload), "task_id"),
            force=not self._form_bool(payload, "respect_schedule", default=False),
            requested_by=str(actor.get("actor_id", "") or "web"),
            persist_monitoring=not self._form_bool(payload, "no_persist_monitoring", default=False),
            collect_snapshot=not self._form_bool(payload, "skip_monitoring", default=False),
            stop_on_failure=self._form_bool(payload, "stop_on_failure", default=False),
            max_concurrency=max(self._form_int(payload, "max_concurrency", default=1), 1),
            retry_count=max(self._form_int(payload, "retry_count", default=0), 0),
        )
        return {
            "storage_mode": "persistent",
            "monitoring_backend": self._form_value(dict(payload), "monitoring_backend") or getattr(self._bundle, "monitoring_backend", None),
            "task": self._unattended_task_payload(getattr(result, "task", None)),
            "execution": self._unattended_round_execution_payload(result),
        }

    def _handle_unattended_patrol(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        actor = dict(request_context.get("current_actor", {}) or {})
        service = getattr(self._bundle, "unattended_service", None)
        if service is None or not hasattr(service, "run_due_tasks"):
            raise ValueError("Unattended service is unavailable.")
        result = service.run_due_tasks(
            task_id=self._form_value(dict(payload), "task_id"),
            force=self._form_bool(payload, "force", default=False),
            requested_by=str(actor.get("actor_id", "") or "web"),
            persist_monitoring=not self._form_bool(payload, "no_persist_monitoring", default=False),
            collect_snapshot=not self._form_bool(payload, "skip_monitoring", default=False),
            stop_on_failure=self._form_bool(payload, "stop_on_failure", default=False),
            max_concurrency=max(self._form_int(payload, "max_concurrency", default=1), 1),
            retry_count=max(self._form_int(payload, "retry_count", default=0), 0),
        )
        return {
            "storage_mode": "persistent",
            "monitoring_backend": self._form_value(dict(payload), "monitoring_backend") or getattr(self._bundle, "monitoring_backend", None),
            "patrol": self._unattended_patrol_payload(result),
        }

__all__ = ["RunnerActionsMixin"]
