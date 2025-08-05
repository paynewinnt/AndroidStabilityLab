from __future__ import annotations

from stability.time_utils import now_beijing_string

from ...application_common import *
from ...application_payload_monitoring import ApplicationPayloadMonitoringMixin


def _generated_at_now() -> str:
    return now_beijing_string()


class TasksPayloadMixin(ApplicationPayloadMonitoringMixin):
    def _tasks_payload(self, query: dict[str, list[str]], *, request_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        device_sync = self._maybe_sync_devices(query)
        show_archived = self._str_query(query, "show_archived") in {"1", "true", "yes"}
        active_tasks = self._task_summaries(limit=0)
        all_tasks = self._task_summaries(limit=0, include_archived=True)
        archived_tasks = [item for item in all_tasks if bool(item.get("archived") or item.get("hidden"))]
        tasks = all_tasks[:50] if show_archived else active_tasks[:50]
        runs = self._decorate_runs_with_monitoring(self._run_summaries(limit=50))
        devices = self._device_summaries()
        schedulable_devices = [dict(item) for item in devices if bool(dict(item).get("is_schedulable", False))]
        status_counts: dict[str, int] = {}
        for item in runs:
            status = str(item.get("run_status", "") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        monitored_run_count = sum(1 for item in runs if dict(item.get("monitoring_summary", {}) or {}).get("sample_count", 0))
        trace_run_count = sum(1 for item in runs if dict(item.get("monitoring_summary", {}) or {}).get("trace_count", 0))
        return {
            "page": "tasks",
            "title": "任务大厅",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "device_sync": device_sync,
            "summary": {
                "task_count": len(tasks),
                "active_task_count": len(active_tasks),
                "archived_task_count": len(archived_tasks),
                "show_archived": show_archived,
                "run_count": len(runs),
                "run_status_counts": status_counts,
                "monitored_run_count": monitored_run_count,
                "trace_run_count": trace_run_count,
            },
            "tasks": tasks,
            "runs": runs,
            "devices": devices,
            "schedulable_devices": schedulable_devices,
            "managed_apks": self._managed_apks_payload(),
            "operation_defaults": {
                "template_type": self._str_query(query, "template_type") or "cold_start_loop",
                "monitoring_backend": self._str_query(query, "monitoring_backend") or "default",
            },
        }

    def _run_detail_payload(self, run_id: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
        service = getattr(self._bundle, "run_history_service", None)
        if service is None or not hasattr(service, "get_run_detail"):
            raise ValueError("Run history service is unavailable.")
        detail = dict(service.get_run_detail(run_id))
        task = dict(detail.get("task", {}) or {})
        instances = self._decorate_run_detail_instances(list(detail.get("instances", []) or ()))
        monitoring_summary = self._run_monitoring_summary(instances)
        return {
            "page": "run_detail",
            "title": f"Run 详情 · {run_id}",
            "generated_at": _generated_at_now(),
            "query": dict(query or {}),
            "run": {
                **detail,
                "task": task,
                "instances": instances,
                "detail_path": f"/runs/{quote(run_id, safe='')}",
                "api_path": f"/api/runs/{quote(run_id, safe='')}",
                "monitoring_summary": monitoring_summary,
            },
        }


__all__ = ["TasksPayloadMixin"]
