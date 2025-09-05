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
        filters = self._admin_list_filters(query, default_page_size=20)
        active_tasks = self._task_summaries(limit=0)
        all_tasks = self._task_summaries(limit=0, include_archived=True)
        archived_tasks = [item for item in all_tasks if bool(item.get("archived") or item.get("hidden"))]
        runs = self._decorate_runs_with_monitoring(self._run_summaries(limit=200))
        runs_by_task_id = self._runs_by_task_id(runs)
        source_tasks = all_tasks if show_archived else active_tasks
        enriched_tasks = [
            self._task_with_runs(item, runs_by_task_id.get(str(item.get("task_id", "") or ""), ()))
            for item in source_tasks
        ]
        filtered_tasks = [item for item in enriched_tasks if self._task_matches_admin_filters(item, filters)]
        total_task_count = len(filtered_tasks)
        tasks = self._page_slice(filtered_tasks, page=int(filters["page"]), page_size=int(filters["page_size"]))
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
                "task_count": total_task_count,
                "active_task_count": len(active_tasks),
                "archived_task_count": len(archived_tasks),
                "show_archived": show_archived,
                "run_count": len(runs),
                "run_status_counts": status_counts,
                "monitored_run_count": monitored_run_count,
                "trace_run_count": trace_run_count,
            },
            "filters": filters,
            "pagination": {
                "page": int(filters["page"]),
                "page_size": int(filters["page_size"]),
                "total": total_task_count,
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
        filters = self._admin_list_filters(query, default_page_size=20)
        limit = min(max(self._int_query(query, "limit", default=200), 1), 500)
        tasks_by_id = {
            str(item.get("task_id", "") or ""): dict(item)
            for item in self._task_summaries(limit=0, include_archived=True)
            if str(item.get("task_id", "") or "")
        }
        all_runs = [
            self._run_with_task_metadata(run, tasks_by_id=tasks_by_id)
            for run in self._decorate_runs_with_monitoring(self._run_summaries(limit=limit))
        ]
        filtered_runs = [item for item in all_runs if self._run_matches_admin_filters(item, filters)]
        total_run_count = len(filtered_runs)
        runs = self._page_slice(filtered_runs, page=int(filters["page"]), page_size=int(filters["page_size"]))
        status_counts: dict[str, int] = {}
        for item in filtered_runs:
            status = str(item.get("run_status", "") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        monitored_run_count = sum(1 for item in filtered_runs if dict(item.get("monitoring_summary", {}) or {}).get("sample_count", 0))
        trace_run_count = sum(1 for item in filtered_runs if dict(item.get("monitoring_summary", {}) or {}).get("trace_count", 0))
        return {
            "page": "runs",
            "title": "Run 列表",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "filters": {**filters, "limit": limit},
            "pagination": {
                "page": int(filters["page"]),
                "page_size": int(filters["page_size"]),
                "total": total_run_count,
            },
            "summary": {
                "run_count": total_run_count,
                "run_status_counts": status_counts,
                "monitored_run_count": monitored_run_count,
                "trace_run_count": trace_run_count,
            },
            "runs": runs,
        }

    @staticmethod
    def _run_with_task_metadata(run: Mapping[str, Any], *, tasks_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        payload = dict(run)
        task = dict(tasks_by_id.get(str(payload.get("task_id", "") or ""), {}) or {})
        if task:
            payload.setdefault("task_name", task.get("task_name", ""))
            payload.setdefault("package_name", task.get("package_name", ""))
            payload.setdefault("template_type", task.get("template_type", ""))
        return payload

    def _admin_list_filters(self, query: dict[str, list[str]], *, default_page_size: int) -> dict[str, Any]:
        return {
            "keyword": self._str_query(query, "keyword"),
            "status": self._str_query(query, "status"),
            "device_id": self._str_query(query, "device_id"),
            "package_name": self._str_query(query, "package_name"),
            "scenario": self._str_query(query, "scenario") or self._str_query(query, "template_type"),
            "backend": self._str_query(query, "backend") or self._str_query(query, "monitoring_backend"),
            "created_from": self._str_query(query, "created_from"),
            "created_to": self._str_query(query, "created_to"),
            "page": max(self._int_query(query, "page", default=1), 1),
            "page_size": min(max(self._int_query(query, "page_size", default=default_page_size), 1), 100),
        }

    @staticmethod
    def _page_slice(items: list[dict[str, Any]], *, page: int, page_size: int) -> list[dict[str, Any]]:
        start = max(page - 1, 0) * max(page_size, 1)
        return items[start:start + max(page_size, 1)]

    @classmethod
    def _task_matches_admin_filters(cls, task: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        keyword = str(filters.get("keyword", "") or "").lower()
        if keyword:
            haystack = " ".join(
                str(value or "")
                for value in (
                    task.get("task_id", ""),
                    task.get("task_name", ""),
                    task.get("package_name", ""),
                    task.get("template_type", ""),
                    task.get("latest_run_status", ""),
                )
            ).lower()
            if keyword not in haystack:
                return False
        status = str(filters.get("status", "") or "").lower()
        if status and status != str(task.get("latest_run_status", "") or "no_run").lower():
            return False
        package_name = str(filters.get("package_name", "") or "").lower()
        if package_name and package_name not in str(task.get("package_name", "") or "").lower():
            return False
        scenario = str(filters.get("scenario", "") or "").lower()
        if scenario and scenario != str(task.get("template_type", "") or "").lower():
            return False
        device_id = str(filters.get("device_id", "") or "").lower()
        if device_id:
            device_values = [str(value or "").lower() for value in list(task.get("selected_device_ids", []) or [])]
            for run in list(task.get("runs", []) or []):
                device_values.extend(str(value or "").lower() for value in list(dict(run).get("target_device_ids", []) or []))
            if not any(device_id in value for value in device_values):
                return False
        backend = str(filters.get("backend", "") or "").lower()
        if backend and not any(cls._run_monitoring_backend_matches(dict(run), backend) for run in list(task.get("runs", []) or [])):
            return False
        return cls._created_at_in_range(str(task.get("created_at", "") or ""), filters)

    @classmethod
    def _run_matches_admin_filters(cls, run: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        keyword = str(filters.get("keyword", "") or "").lower()
        if keyword:
            haystack = " ".join(
                str(value or "")
                for value in (
                    run.get("run_id", ""),
                    run.get("task_id", ""),
                    run.get("task_name", ""),
                    run.get("package_name", ""),
                    run.get("template_type", ""),
                    run.get("run_status", ""),
                )
            ).lower()
            if keyword not in haystack:
                return False
        status = str(filters.get("status", "") or "").lower()
        if status and status != str(run.get("run_status", "") or "").lower():
            return False
        package_name = str(filters.get("package_name", "") or "").lower()
        if package_name and package_name not in str(run.get("package_name", "") or "").lower():
            return False
        scenario = str(filters.get("scenario", "") or "").lower()
        if scenario and scenario != str(run.get("template_type", "") or "").lower():
            return False
        device_id = str(filters.get("device_id", "") or "").lower()
        if device_id and not any(device_id in str(value or "").lower() for value in list(run.get("target_device_ids", []) or [])):
            return False
        backend = str(filters.get("backend", "") or "").lower()
        if backend and not cls._run_monitoring_backend_matches(run, backend):
            return False
        return cls._created_at_in_range(str(run.get("created_at", "") or ""), filters)

    @staticmethod
    def _run_monitoring_backend_matches(run: Mapping[str, Any], backend: str) -> bool:
        monitoring = dict(run.get("monitoring_summary", {}) or {})
        backend_counts = dict(monitoring.get("backend_counts", {}) or {})
        summary_line = str(monitoring.get("summary_line", "") or "")
        return backend in summary_line.lower() or any(backend == str(key or "").lower() for key in backend_counts)

    @staticmethod
    def _created_at_in_range(value: str, filters: Mapping[str, Any]) -> bool:
        date_text = str(value or "")[:10]
        created_from = str(filters.get("created_from", "") or "")[:10]
        created_to = str(filters.get("created_to", "") or "")[:10]
        if created_from and date_text and date_text < created_from:
            return False
        if created_to and date_text and date_text > created_to:
            return False
        return True

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
        filters = self._admin_list_filters(query, default_page_size=20)
        limit = min(max(self._int_query(query, "limit", default=200), 1), 500)
        service = getattr(self._bundle, "run_history_service", None)
        runs = list(service.list_runs(limit=limit)) if service is not None and hasattr(service, "list_runs") else []
        items = [self._artifact_list_item(dict(run or {}), service=service) for run in runs]
        filtered_items = [item for item in items if self._run_matches_admin_filters(item, filters)]
        paged_items = self._page_slice(filtered_items, page=int(filters["page"]), page_size=int(filters["page_size"]))
        return {
            "page": "artifacts",
            "title": "产物中心",
            "generated_at": _generated_at_now(),
            "filters": {**filters, "limit": limit},
            "pagination": {
                "page": int(filters["page"]),
                "page_size": int(filters["page_size"]),
                "total": len(filtered_items),
            },
            "summary": self._artifact_list_summary(filtered_items),
            "items": paged_items,
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
        package_name = str(detail.get("package_name", task.get("package_name", run.get("package_name", ""))) or "")
        template_type = str(detail.get("template_type", task.get("template_type", run.get("template_type", ""))) or "")
        return {
            "run_id": run_id,
            "task_id": task_id,
            "task_name": task_name,
            "package_name": package_name,
            "template_type": template_type,
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
