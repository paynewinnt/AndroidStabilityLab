from __future__ import annotations

from stability.time_utils import now_beijing_string

from typing import Any, Mapping
from urllib.parse import quote
from .monitoring_payload import MonitoringPayloadMixin


def _generated_at_now() -> str:
    return now_beijing_string()


class TasksPayloadMixin(MonitoringPayloadMixin):
    def _tasks_payload(self, query: dict[str, list[str]], *, request_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        device_sync = self._maybe_sync_devices(query)
        show_archived = self._str_query(query, "show_archived") in {"1", "true", "yes"}
        active_tasks = self._task_summaries(limit=0)
        all_tasks = self._task_summaries(limit=0, include_archived=True)
        archived_tasks = [item for item in all_tasks if bool(item.get("archived") or item.get("hidden"))]
        tasks = all_tasks[:50] if show_archived else active_tasks[:50]
        runs = self._decorate_runs_with_monitoring(self._run_summaries(limit=200))
        runs_by_task_id = self._runs_by_task_id(runs)
        tasks = [self._task_with_runs(item, runs_by_task_id.get(str(item.get("task_id", "") or ""), ())) for item in tasks]
        devices = self._device_summaries()
        schedulable_devices = [dict(item) for item in devices if bool(dict(item).get("is_schedulable", False))]
        status_counts: dict[str, int] = {}
        for item in runs:
            status = str(item.get("run_status", "") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        monitored_run_count = sum(1 for item in runs if dict(item.get("monitoring_summary", {}) or {}).get("sample_count", 0))
        trace_run_count = sum(1 for item in runs if dict(item.get("monitoring_summary", {}) or {}).get("trace_count", 0))
        operation_defaults: dict[str, Any] = {
            "template_type": self._str_query(query, "template_type") or "cold_start_loop",
            "monitoring_backend": self._str_query(query, "monitoring_backend") or "default",
        }
        long_run_defaults = self._long_run_task_operation_defaults(query, request_context=request_context)
        if long_run_defaults:
            operation_defaults.update(long_run_defaults)
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
            "runs_by_task_id": runs_by_task_id,
            "devices": devices,
            "schedulable_devices": schedulable_devices,
            "managed_apks": self._managed_apks_payload(),
            "operation_defaults": operation_defaults,
        }

    def _long_run_task_operation_defaults(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        template_key = (
            self._str_query(query, "long_run_template")
            or self._str_query(query, "long_run_template_key")
            or ""
        ).strip()
        if not template_key:
            return {}
        template_query = {key: list(values) for key, values in query.items()}
        template_query["template_key"] = [template_key]
        template_payload = self._long_run_templates_payload(template_query, request_context=request_context)
        template = dict(template_payload.get("template", {}) or {})
        plan = dict(template_payload.get("plan", {}) or {})
        configure_kwargs = dict(plan.get("configure_kwargs", {}) or {})
        runner_kwargs = dict(plan.get("runner_kwargs", {}) or {})
        metadata_suggestions = dict(plan.get("task_metadata_suggestions", {}) or {})
        defaults = dict(template.get("defaults", {}) or {})
        overrides = dict(template_payload.get("overrides", {}) or {})
        interval_minutes = self._coerce_positive_int(
            configure_kwargs.get("interval_minutes", defaults.get("interval_minutes", overrides.get("interval_minutes"))),
            default=60,
        )
        raw_max_rounds = runner_kwargs.get("max_iterations", defaults.get("max_rounds", overrides.get("max_rounds")))
        if raw_max_rounds in (None, ""):
            duration_seconds = self._coerce_non_negative_int(defaults.get("duration_seconds"), default=0)
            max_rounds = max(1, (duration_seconds + interval_minutes * 60 - 1) // (interval_minutes * 60)) if duration_seconds else 12
        else:
            max_rounds = self._coerce_positive_int(raw_max_rounds, default=12)
        runtime_hours = max(1, (interval_minutes * max_rounds + 59) // 60)
        template_name = str(template.get("name", "") or metadata_suggestions.get("long_run_template_name", "") or template_key)
        tags = list(metadata_suggestions.get("tags", template.get("default_tags", defaults.get("tags", []))) or [])
        metadata_default = {
            "source": "web_long_run_template",
            "long_run_template_id": template_key,
            "long_run_template_name": template_name,
            "tags": [str(item) for item in tags if str(item or "").strip()],
        }
        task_name = str(overrides.get("task_name", "") or self._str_query(query, "task_name") or "")
        if not task_name and template_name:
            task_name = f"{template_name} 长稳"
        package_name = str(overrides.get("package_name", "") or self._str_query(query, "package_name") or "")
        monitoring_backend = str(overrides.get("monitoring_backend", "") or self._str_query(query, "monitoring_backend") or "default")
        return {
            "auto_open_modal": "long-run-task",
            "long_run_template_key": template_key,
            "long_run_template_name": template_name,
            "long_run_template_payload": template_payload,
            "template_type": str(
                defaults.get("template_type", "")
                or template.get("template_type", "")
                or template.get("default_template_type", "")
                or "monkey"
            ),
            "task_name": task_name,
            "package_name": package_name,
            "runtime_hours": runtime_hours,
            "interval_minutes": interval_minutes,
            "desired_device_count": self._coerce_positive_int(
                configure_kwargs.get("desired_device_count", defaults.get("desired_device_count")),
                default=1,
            ),
            "failure_threshold": self._coerce_positive_int(configure_kwargs.get("failure_threshold"), default=3),
            "rotation_strategy": str(configure_kwargs.get("rotation_strategy", defaults.get("rotation_strategy", "round_robin")) or "round_robin"),
            "rotation_advance_policy": str(configure_kwargs.get("rotation_advance_policy", "every_round") or "every_round"),
            "start_now": "1" if bool(configure_kwargs.get("start_now", overrides.get("start_now", False))) else "0",
            "primary_device_ids": list(configure_kwargs.get("primary_device_ids", []) or []),
            "backup_device_ids": list(configure_kwargs.get("backup_device_ids", []) or []),
            "monitoring_backend": monitoring_backend,
            "metadata": metadata_default,
            "template_summary": str(template.get("chinese_purpose", "") or template.get("chinese_explanation", "") or template.get("description", "") or ""),
        }

    @staticmethod
    def _coerce_positive_int(value: Any, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(default)
        return max(1, parsed)

    @staticmethod
    def _coerce_non_negative_int(value: Any, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(default)
        return max(0, parsed)

    @staticmethod
    def _runs_by_task_id(runs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in runs:
            task_id = str(item.get("task_id", "") or "")
            if not task_id:
                continue
            grouped.setdefault(task_id, []).append(item)
        return grouped

    @staticmethod
    def _task_with_runs(task: Mapping[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
        task_payload = dict(task)
        related_runs = [dict(item) for item in runs]
        status_counts: dict[str, int] = {}
        active_statuses = {"queued", "running"}
        active_count = 0
        for run in related_runs:
            status = str(run.get("run_status", "") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            if status in active_statuses or any(
                str(key) in {"pending", "preparing", "running", "stopping", "collecting"} and int(value or 0) > 0
                for key, value in dict(run.get("instance_status_counts", {}) or {}).items()
            ):
                active_count += 1
        latest_run = related_runs[0] if related_runs else {}
        task_payload.update(
            {
                "runs": related_runs,
                "run_count": len(related_runs),
                "active_run_count": active_count,
                "run_status_counts": status_counts,
                "latest_run": latest_run,
                "latest_run_status": str(latest_run.get("run_status", "") or ""),
            }
        )
        return task_payload

    def _runs_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del request_context
        limit = min(max(self._int_query(query, "limit", default=100), 1), 300)
        runs = self._decorate_runs_with_monitoring(self._run_summaries(limit=limit))
        status_counts: dict[str, int] = {}
        for item in runs:
            status = str(item.get("run_status", "") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        monitored_run_count = sum(1 for item in runs if dict(item.get("monitoring_summary", {}) or {}).get("sample_count", 0))
        trace_run_count = sum(1 for item in runs if dict(item.get("monitoring_summary", {}) or {}).get("trace_count", 0))
        return {
            "page": "runs",
            "title": "Run 列表",
            "generated_at": _generated_at_now(),
            "filters": {"limit": limit},
            "summary": {
                "run_count": len(runs),
                "run_status_counts": status_counts,
                "monitored_run_count": monitored_run_count,
                "trace_run_count": trace_run_count,
            },
            "runs": runs,
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

    def _artifacts_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del request_context
        limit = min(max(self._int_query(query, "limit", default=50), 1), 200)
        service = getattr(self._bundle, "run_history_service", None)
        runs = list(service.list_runs(limit=limit)) if service is not None and hasattr(service, "list_runs") else []
        items = [self._artifact_list_item(dict(run or {}), service=service) for run in runs]
        return {
            "page": "artifacts",
            "title": "产物中心",
            "generated_at": _generated_at_now(),
            "filters": {"limit": limit},
            "summary": self._artifact_list_summary(items),
            "items": items,
        }

    def _artifact_list_item(self, run: dict[str, Any], *, service: Any) -> dict[str, Any]:
        run_id = str(run.get("run_id", "") or "").strip()
        detail: dict[str, Any] = {}
        instances: list[dict[str, Any]] = []
        if run_id and service is not None and hasattr(service, "get_run_detail"):
            try:
                detail = dict(service.get_run_detail(run_id))
                instances = self._decorate_run_detail_instances(list(detail.get("instances", []) or ()))
            except Exception:
                detail = {}
                instances = []
        task = dict(detail.get("task", {}) or {})
        monitoring_summary = self._run_monitoring_summary(instances) if instances else self._empty_monitoring_summary()
        artifact_summary = self._artifact_summary_for_run(detail=detail, run=run, instances=instances)
        task_id = str(detail.get("task_id", run.get("task_id", "")) or "")
        task_name = str(detail.get("task_name", task.get("task_name", run.get("task_name", ""))) or "")
        return {
            "run_id": run_id,
            "task_id": task_id,
            "task_name": task_name,
            "run_status": str(detail.get("run_status", run.get("run_status", "")) or "unknown"),
            "target_device_ids": list(detail.get("target_device_ids", run.get("target_device_ids", [])) or []),
            "created_at": str(detail.get("created_at", run.get("created_at", "")) or ""),
            "started_at": str(detail.get("started_at", run.get("started_at", "")) or ""),
            "finished_at": str(detail.get("finished_at", run.get("finished_at", "")) or ""),
            "detail_path": f"/runs/{quote(run_id, safe='')}" if run_id else "",
            "artifact_path": f"/artifacts/run/{quote(run_id, safe='')}" if run_id else "",
            "api_path": f"/api/runs/{quote(run_id, safe='')}" if run_id else "",
            "artifacts_api_path": f"/api/artifacts/run/{quote(run_id, safe='')}" if run_id else "",
            "monitoring_summary": monitoring_summary,
            "artifact_summary": artifact_summary,
        }

    @staticmethod
    def _artifact_list_summary(items: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "run_count": len(items),
            "report_count": sum(int(dict(item.get("artifact_summary", {}) or {}).get("report_count", 0) or 0) for item in items),
            "trace_count": sum(int(dict(item.get("artifact_summary", {}) or {}).get("trace_count", 0) or 0) for item in items),
            "monitoring_snapshot_count": sum(
                int(dict(item.get("artifact_summary", {}) or {}).get("monitoring_snapshot_count", 0) or 0) for item in items
            ),
            "issue_count": sum(int(dict(item.get("artifact_summary", {}) or {}).get("issue_count", 0) or 0) for item in items),
        }

    @staticmethod
    def _empty_monitoring_summary() -> dict[str, Any]:
        return {
            "sample_count": 0,
            "trace_count": 0,
            "backend_counts": {},
            "latest_sample_at": "",
            "summary_line": "未发现监控快照",
        }

    @staticmethod
    def _artifact_summary_for_run(
        *,
        detail: Mapping[str, Any],
        run: Mapping[str, Any],
        instances: list[dict[str, Any]],
    ) -> dict[str, int]:
        summary = dict(detail.get("summary", run.get("summary", {})) or {})
        report_count = sum(1 for item in instances if item.get("report_path") or item.get("html_report_path"))
        trace_count = sum(1 for item in instances if dict(item.get("monitoring", {}) or {}).get("trace_path") or item.get("monitoring_trace_path"))
        snapshot_count = sum(
            1 for item in instances if dict(item.get("monitoring", {}) or {}).get("snapshot_path") or item.get("monitoring_snapshot_path")
        )
        issue_count = int(summary.get("total_issues", 0) or sum(int(item.get("issue_count", 0) or 0) for item in instances))
        return {
            "report_count": report_count,
            "trace_count": trace_count,
            "monitoring_snapshot_count": snapshot_count,
            "issue_count": issue_count,
        }


__all__ = ["TasksPayloadMixin"]
