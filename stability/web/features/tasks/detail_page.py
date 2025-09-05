from __future__ import annotations

from stability.scenario.registry import (
    METRIC_REGISTRY,
    default_metric_template_scopes,
    get_param_sections_for_web,
    get_scenario_definition,
    get_template_form_schema,
    list_scenario_definitions,
    metric_template_scopes,
)
from stability.time_utils import now_beijing_string

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote


def _generated_at_now() -> str:
    return now_beijing_string()


from .forms import TaskFormsMixin

class TaskDetailPageMixin(TaskFormsMixin):
    def _task_detail_payload(
        self,
        task_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_service = getattr(self._bundle, "task_service", None)
        if task_service is None or not hasattr(task_service, "get_task"):
            raise ValueError("Task service is unavailable.")
        task = task_service.get_task(task_id)
        task_payload = self._describe_task_payload(task)
        run_history_service = getattr(self._bundle, "run_history_service", None)
        runs: list[dict[str, Any]] = []
        if run_history_service is not None and hasattr(run_history_service, "list_runs"):
            runs = self._decorate_runs_with_monitoring(list(run_history_service.list_runs(task_id=task_id, limit=30)))
        return {
            "page": "task_detail",
            "title": f"任务详情 · {task_payload.get('task_name', task_id) or task_id}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "query": dict(query or {}),
            "task": {
                **task_payload,
                "detail_path": f"/tasks/task/{quote(task_id, safe='')}",
                "api_path": f"/api/tasks/task/{quote(task_id, safe='')}",
            },
            "runs": runs,
        }

    def _render_task_detail(self, payload: dict[str, Any]) -> str:
        task = dict(payload.get("task", {}) or {})
        runs = list(payload.get("runs", []) or [])
        task_id = str(task.get("task_id", "") or "")
        task_name = str(task.get("task_name", "") or task_id or "任务详情")
        body = [
            self._task_page_return_strip(
                current=f"任务详情 · {task_name}",
                links=[("返回任务大厅", "/tasks")],
            ),
            self._metric_grid(
                [
                    ("任务", task.get("task_name", "n/a") or "n/a"),
                    ("模板", task.get("template_type", "n/a") or "n/a"),
                    ("设备数", task.get("planned_device_count", 0)),
                    ("最近 Run", len(runs)),
                    ("采样间隔", dict(task.get("sampling_config", {}) or {}).get("interval_seconds", 0)),
                    ("创建人", task.get("created_by", "n/a") or "n/a"),
                ]
            ),
            self._section(
                "任务定义",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(task, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
            ),
            self._section("创建 Run", [self._task_detail_create_run_form(task, current_actor=dict(payload.get("current_actor", {}) or {}))]),
            self._section("关联 Runs", [self._run_table(runs)]),
        ]
        return self._layout(
            "任务详情",
            "展示任务定义、关联 Run 和创建 Run 入口。",
            "".join(body),
        )

    def _unattended_detail_payload(
        self,
        task_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        unattended_service = getattr(self._bundle, "unattended_service", None)
        if unattended_service is None or not hasattr(unattended_service, "get_task_record"):
            raise ValueError("Unattended service is unavailable.")
        record = unattended_service.get_task_record(task_id)
        daily_report = {}
        weekly_report = {}
        if hasattr(unattended_service, "build_daily_report"):
            try:
                daily_report = self._unattended_daily_report_payload(unattended_service.build_daily_report(task_id=task_id))
            except Exception:
                daily_report = {}
        if hasattr(unattended_service, "build_weekly_report"):
            try:
                weekly_report = self._unattended_weekly_report_payload(unattended_service.build_weekly_report(task_id=task_id))
            except Exception:
                weekly_report = {}
        return {
            "page": "unattended_detail",
            "title": f"无人值守详情 · {task_id}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "query": dict(query or {}),
            "task": self._unattended_task_payload(record),
            "daily_report": daily_report,
            "weekly_report": weekly_report,
        }

    def _render_unattended_detail(self, payload: dict[str, Any]) -> str:
        task = dict(payload.get("task", {}) or {})
        daily_report = dict(payload.get("daily_report", {}) or {})
        weekly_report = dict(payload.get("weekly_report", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("Task ID", task.get("task_id", "n/a") or "n/a"),
                    ("启用", "yes" if task.get("enabled") else "no"),
                    ("间隔(分钟)", task.get("interval_minutes", 0)),
                    ("主设备", len(task.get("primary_device_ids", []) or [])),
                    ("备设备", len(task.get("backup_device_ids", []) or [])),
                    ("Due", "yes" if task.get("due") else "no"),
                ]
            ),
            self._section(
                "无人值守配置",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(task, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
            ),
            self._section("执行动作", [self._unattended_detail_actions_form(task, current_actor=dict(payload.get("current_actor", {}) or {}))]),
            self._section(
                "Latest Daily Report",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(daily_report, ensure_ascii=False, indent=2))
                    + "</pre>"
                    if daily_report
                    else self._notice("当前还没有可展示的日报。")
                ],
            ),
            self._section(
                "Latest Weekly Report",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(weekly_report, ensure_ascii=False, indent=2))
                    + "</pre>"
                    if weekly_report
                    else self._notice("当前还没有可展示的周报。")
                ],
            ),
        ]
        return self._layout(
            "无人值守详情",
            "展示无人值守配置、日报周报和手动执行入口。",
            "".join(body),
        )

    def _task_detail_create_run_form(self, task: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        task_id = str(task.get("task_id", "") or "")
        device_selector = self._task_device_selector(
            [item for item in self._device_summaries() if bool(dict(item).get("is_schedulable", False))],
            allow_empty=False,
            label="目标设备",
        )
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>基于当前任务创建 Run</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            f"{device_selector}"
            "<label>metadata(JSON)<textarea name='metadata' rows='3' placeholder='例如 {\"source\":\"web\"}'></textarea></label>"
            "<div><button type='submit'>创建 Run</button></div>"
            "</form>"
            "</article></div>"
        )

    def _unattended_detail_actions_form(self, task: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        task_id = str(task.get("task_id", "") or "")
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>手动跑一轮</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/run-unattended-round', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            "<option value='default'>default</option>"
            "<option value='solox'>solox</option>"
            "<option value='perfetto'>perfetto</option>"
            "</select></label>"
            "<div><button type='submit'>执行轮次</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>触发 Patrol</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/patrol-unattended', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            "<option value='default'>default</option>"
            "<option value='solox'>solox</option>"
            "<option value='perfetto'>perfetto</option>"
            "</select></label>"
            "<div><button type='submit'>执行 Patrol</button></div>"
            "</form>"
            "</article>"
            "</div>"
        )
