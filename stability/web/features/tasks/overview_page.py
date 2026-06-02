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

from stability.web.features.tasks.artifacts_page import TasksArtifactsPageMixin


def _generated_at_now() -> str:
    return now_beijing_string()


class TasksPageMixin(TasksArtifactsPageMixin):
    def _render_tasks(self, payload: dict[str, Any]) -> str:
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(
                self._notice(
                    str(flash.get("message", "") or ""),
                    tone=str(flash.get("tone", "ok") or "ok"),
                )
            )
        latest_run = self._latest_workflow_run(payload)
        body.extend(
            [
                self._admin_page_header(
                    "任务大厅",
                    subtitle="任务、Run、执行动作和产物入口统一在列表上下文内完成。",
                    breadcrumbs=[("首页", "/"), ("任务大厅", "")],
                    actions=[self._route_link("JSON API", "/api/tasks")],
                ),
                self._admin_summary_strip(
                    [
                        ("任务数", payload["summary"]["task_count"]),
                        ("最近 Run 数", payload["summary"]["run_count"]),
                        (
                            "失败 Run",
                            payload["summary"]["run_status_counts"].get("failed", 0),
                        ),
                        (
                            "成功 Run",
                            payload["summary"]["run_status_counts"].get("success", 0),
                        ),
                        (
                            "有监控 Run",
                            payload["summary"].get("monitored_run_count", 0),
                        ),
                        ("带 Trace Run", payload["summary"].get("trace_run_count", 0)),
                    ]
                ),
                self._workflow_nav_bar(
                    active="tasks",
                    run_path="/runs",
                    artifact_path="/artifacts",
                    run_hint="Run 列表" if latest_run else "等待 Run",
                    artifact_hint="产物列表",
                ),
                self._task_admin_filter_bar(payload),
                self._task_admin_workspace(payload),
            ]
        )
        if payload.get("device_sync"):
            body.insert(1, self._notice(self._sync_hint(payload["device_sync"])))
        return self._layout(
            "任务大厅",
            "任务定义、执行状态和最近运行记录放在一页里，先把“跑了什么、跑成什么样”可视化。",
            "".join(body),
        )

    @staticmethod
    def _latest_workflow_run(payload: Mapping[str, Any]) -> dict[str, Any]:
        runs = list(payload.get("runs", []) or [])
        if runs:
            return dict(runs[0] or {})
        for task in list(payload.get("tasks", []) or []):
            latest_run = dict((task or {}).get("latest_run", {}) or {})
            if latest_run:
                return latest_run
        return {}

    def _task_admin_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        return self._admin_filter_bar(
            action="/tasks",
            values=filters,
            hidden={
                "show_archived": "1"
                if dict(payload.get("summary", {}) or {}).get("show_archived")
                else ""
            },
            fields=[
                {
                    "name": "keyword",
                    "label": "关键词",
                    "placeholder": "任务名 / 包名 / ID",
                },
                {
                    "name": "status",
                    "label": "状态",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "no_run", "label": "未运行"},
                        {"value": "queued", "label": "queued"},
                        {"value": "running", "label": "running"},
                        {"value": "success", "label": "success"},
                        {"value": "failed", "label": "failed"},
                        {"value": "partial_failed", "label": "partial_failed"},
                        {"value": "cancelled", "label": "cancelled"},
                    ],
                },
                {"name": "package_name", "label": "包名", "placeholder": "com.example"},
                {"name": "device_id", "label": "设备", "placeholder": "device id"},
                {
                    "name": "scenario",
                    "label": "场景",
                    "type": "select",
                    "options": [{"value": "", "label": "全部"}]
                    + [
                        {"value": str(item.value), "label": str(item.plain_label)}
                        for item in list_scenario_definitions()
                    ],
                },
                {
                    "name": "backend",
                    "label": "Backend",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "adb_collector", "label": "adb_collector"},
                        {"value": "solox", "label": "solox"},
                        {"value": "perfetto", "label": "perfetto"},
                        {"value": "solox_perfetto", "label": "solox_perfetto"},
                    ],
                },
                {"name": "created_from", "label": "开始日期", "type": "date"},
                {"name": "created_to", "label": "结束日期", "type": "date"},
            ],
        )

    def _task_admin_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "tasks-admin-table"
        columns = self._task_admin_columns()
        toolbar = self._admin_toolbar(
            title="任务列表",
            description="行内完成 Run 管理、执行、停止、详情和归档。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<button type='button' data-task-modal-target='long-run-task'>新增长稳</button>",
                "<button type='button' class='secondary' data-task-modal-target='standard-task'>新增任务</button>",
                "<button type='button' class='secondary' data-task-modal-target='create-run'>创建 Run</button>",
                "<button type='button' class='secondary' data-task-modal-target='execute-run'>执行 Run</button>",
                "<button type='button' class='secondary' data-task-modal-target='delete-task-run' title='不物理删除，只从默认列表隐藏并记录审计事件。'>归档 / 隐藏</button>",
                "<a class='button secondary' href='/tasks'>刷新</a>",
                (
                    "<a class='button secondary' href='/tasks'>仅看活跃</a>"
                    if dict(payload.get("summary", {}) or {}).get("show_archived")
                    else "<a class='button secondary' href='/tasks?show_archived=1'>查看归档</a>"
                ),
            ],
        )
        table_html, drawers = self._task_admin_table(
            payload, table_id=table_id, columns=columns
        )
        pagination = self._admin_pagination(
            base_path="/tasks",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(
                dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20
            ),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return (
            "<section class='panel admin-list-panel'>"
            + toolbar
            + table_html
            + pagination
            + "</section>"
            + self._task_admin_operation_modals(payload)
            + drawers
        )

    @staticmethod
    def _compact_value_list(values: Sequence[Any], *, limit: int = 3) -> str:
        seen: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.append(text)
        if not seen:
            return "n/a"
        visible = seen[:limit]
        suffix = f" +{len(seen) - limit}" if len(seen) > limit else ""
        return ", ".join(visible) + suffix

    @classmethod
    def _monitoring_backend_label(cls, monitoring_summary: Mapping[str, Any]) -> str:
        summary = dict(monitoring_summary or {})
        backend_counts = dict(summary.get("backend_counts", {}) or {})
        if backend_counts:
            return cls._compact_value_list(sorted(backend_counts.keys()))
        summary_line = str(summary.get("summary_line", "") or "")
        if "backend=" in summary_line:
            return (
                summary_line.split("backend=", 1)[1].split("/", 1)[0].strip() or "n/a"
            )
        return "n/a"

    @classmethod
    def _task_device_label(cls, task: Mapping[str, Any]) -> str:
        values: list[Any] = list(task.get("selected_device_ids", []) or [])
        for run in list(task.get("runs", []) or []):
            values.extend(list(dict(run).get("target_device_ids", []) or []))
        return cls._compact_value_list(values)

    @classmethod
    def _task_backend_label(cls, task: Mapping[str, Any]) -> str:
        values = [
            cls._monitoring_backend_label(dict(run).get("monitoring_summary", {}) or {})
            for run in list(task.get("runs", []) or [])
        ]
        return cls._compact_value_list(value for value in values if value != "n/a")

    @staticmethod
    def _task_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "task", "label": "任务"},
            {"key": "status", "label": "状态"},
            {"key": "package", "label": "包名"},
            {"key": "scenario", "label": "场景"},
            {"key": "devices", "label": "设备"},
            {"key": "backend", "label": "Backend"},
            {"key": "runs", "label": "Run"},
            {"key": "active", "label": "运行中"},
            {"key": "created", "label": "创建时间"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _task_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        tasks = list(payload.get("tasks", []) or [])
        current_actor = dict(payload.get("current_actor", {}) or {})
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for task in tasks:
            item = dict(task or {})
            task_id = str(item.get("task_id", "") or "")
            task_name = str(item.get("task_name", "") or task_id or "未命名任务")
            run_drawer_id = f"admin-task-runs-{self._dom_id_fragment(task_id)}"
            detail_drawer_id = f"admin-task-detail-{self._dom_id_fragment(task_id)}"
            latest_status = str(item.get("latest_run_status", "") or "no_run")
            archived = bool(item.get("archived") or item.get("hidden"))
            archive_action = (
                self._task_archive_inline_form(task_id, current_actor=current_actor)
                if task_id and not archived
                else ""
            )
            devices = self._task_device_label(item)
            backend = self._task_backend_label(item)
            actions = (
                "<div class='admin-table-actions'>"
                + self._admin_drawer_button("Run", run_drawer_id)
                + self._admin_drawer_button("详情", detail_drawer_id)
                + self._route_link_new_tab(
                    "任务页",
                    f"/tasks/task/{quote(task_id, safe='')}" if task_id else "",
                )
                + archive_action
                + (
                    "<span class='admin-status admin-status-muted'>已归档</span>"
                    if archived
                    else ""
                )
                + "</div>"
            )
            rows.append(
                {
                    "select": f"<input type='checkbox' name='task_id' value='{escape(task_id, quote=True)}' />",
                    "task": (
                        f"<strong title='{escape(task_name, quote=True)}'>{escape(task_name)}</strong>"
                        f"<div class='mono' title='{escape(task_id, quote=True)}'>{escape(task_id)}</div>"
                    ),
                    "status": self._admin_status(
                        "已归档" if archived else latest_status,
                        tone="muted" if archived else self._status_tone(latest_status),
                    ),
                    "package": f"<span class='mono'>{escape(str(item.get('package_name', '') or 'n/a'))}</span>",
                    "scenario": self._task_template_cell(
                        str(item.get("template_type", "") or "")
                    ),
                    "devices": f"<span title='{escape(devices, quote=True)}'>{escape(devices)}</span>",
                    "backend": f"<span title='{escape(backend, quote=True)}'>{escape(backend)}</span>",
                    "runs": escape(str(item.get("run_count", 0) or 0)),
                    "active": escape(str(item.get("active_run_count", 0) or 0)),
                    "created": escape(
                        self._display_datetime(item.get("created_at", "")) or "n/a"
                    ),
                    "actions": actions,
                }
            )
            drawers.append(
                self._admin_drawer(
                    run_drawer_id,
                    f"Run 列表 · {task_name}",
                    self._task_run_modal_body(
                        item, payload=payload, current_actor=current_actor
                    ),
                )
            )
            drawers.append(
                self._admin_drawer(
                    detail_drawer_id,
                    f"任务详情 · {task_name}",
                    self._task_admin_detail(item),
                )
            )
        return self._admin_table(
            table_id=table_id,
            columns=columns,
            rows=rows,
            empty_text="当前没有匹配任务。",
        ), "".join(drawers)

    def _task_admin_detail(self, task: Mapping[str, Any]) -> str:
        fields = [
            ("任务 ID", task.get("task_id", "")),
            ("任务名", task.get("task_name", "")),
            ("包名", task.get("package_name", "")),
            ("场景", task.get("template_type", "")),
            ("设备", self._task_device_label(task)),
            ("Backend", self._task_backend_label(task)),
            ("Run 数", task.get("run_count", 0)),
            ("运行中", task.get("active_run_count", 0)),
            ("最新状态", task.get("latest_run_status", "no_run") or "no_run"),
            ("创建时间", self._display_datetime(task.get("created_at", "")) or "n/a"),
        ]
        details = "".join(
            "<div class='admin-detail-item'>"
            f"<small>{escape(str(label))}</small>"
            f"<strong>{escape(str(value or 'n/a'))}</strong>"
            "</div>"
            for label, value in fields
        )
        return (
            "<div class='admin-detail-grid'>" + details + "</div>"
            "<details class='compact-details'><summary>Task JSON</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(dict(task), ensure_ascii=False, indent=2, default=str))
            + "</pre></details>"
        )

    def _task_admin_operation_modals(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            self._task_modal(
                "long-run-task",
                "创建长稳任务",
                self._long_run_task_create_form(payload),
            )
            + self._task_modal(
                "standard-task", "创建任务", self._standard_task_create_form(payload)
            )
            + self._task_modal("create-run", "创建 Run", self._run_create_form(payload))
            + self._task_modal(
                "execute-run", "执行 Run", self._run_execute_form(payload)
            )
            + self._task_modal(
                "delete-task-run",
                "归档 / 隐藏",
                self._task_delete_boundary_card(payload),
            )
            + (
                f"<span hidden data-task-auto-open='{escape(str(dict(payload.get('operation_defaults', {}) or {}).get('auto_open_modal', '') or ''), quote=True)}'></span>"
                if str(
                    dict(payload.get("operation_defaults", {}) or {}).get(
                        "auto_open_modal", ""
                    )
                    or ""
                )
                else ""
            )
        )

    @staticmethod
    def _status_tone(status: str) -> str:
        value = str(status or "").lower()
        if value in {"failed", "partial_failed", "error"}:
            return "danger"
        if value in {
            "queued",
            "pending",
            "running",
            "preparing",
            "collecting",
            "stopping",
            "no_run",
        }:
            return "warning"
        if value in {"cancelled", "archived", "unknown"}:
            return "muted"
        return "ok"

    def _render_runs(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        status_counts = dict(summary.get("run_status_counts", {}) or {})
        body = [
            self._admin_page_header(
                "Run 列表",
                subtitle="按执行批次集中查询、停止、查看详情和进入产物。",
                breadcrumbs=[("首页", "/"), ("任务大厅", "/tasks"), ("Run 列表", "")],
                actions=[self._route_link("JSON API", "/api/runs")],
            ),
            self._admin_summary_strip(
                [
                    ("Run 数", summary.get("run_count", 0)),
                    ("失败 Run", status_counts.get("failed", 0)),
                    ("成功 Run", status_counts.get("success", 0)),
                    ("有监控 Run", summary.get("monitored_run_count", 0)),
                    ("带 Trace Run", summary.get("trace_run_count", 0)),
                ]
            ),
            self._workflow_nav_bar(
                active="run",
                task_path="/tasks",
                run_path="/runs",
                artifact_path="/artifacts",
                run_hint="Run 列表",
                artifact_hint="产物列表",
            ),
            self._run_admin_filter_bar(payload),
            self._run_admin_workspace(payload),
        ]
        return self._layout(
            "Run 列表",
            "按最近执行批次展示 Run，支持进入详情、产物和原始 JSON。",
            "".join(body),
        )

    def _run_admin_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        return self._admin_filter_bar(
            action="/runs",
            values=filters,
            fields=[
                {
                    "name": "keyword",
                    "label": "关键词",
                    "placeholder": "Run / 任务 / 包名 / ID",
                },
                {
                    "name": "status",
                    "label": "状态",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "queued", "label": "queued"},
                        {"value": "running", "label": "running"},
                        {"value": "success", "label": "success"},
                        {"value": "failed", "label": "failed"},
                        {"value": "partial_failed", "label": "partial_failed"},
                        {"value": "cancelled", "label": "cancelled"},
                    ],
                },
                {"name": "package_name", "label": "包名", "placeholder": "com.example"},
                {"name": "device_id", "label": "设备", "placeholder": "device id"},
                {
                    "name": "scenario",
                    "label": "场景",
                    "type": "select",
                    "options": [{"value": "", "label": "全部"}]
                    + [
                        {"value": str(item.value), "label": str(item.plain_label)}
                        for item in list_scenario_definitions()
                    ],
                },
                {
                    "name": "backend",
                    "label": "Backend",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "adb_collector", "label": "adb_collector"},
                        {"value": "solox", "label": "solox"},
                        {"value": "perfetto", "label": "perfetto"},
                        {"value": "solox_perfetto", "label": "solox_perfetto"},
                    ],
                },
                {"name": "created_from", "label": "开始日期", "type": "date"},
                {"name": "created_to", "label": "结束日期", "type": "date"},
            ],
        )

    def _run_admin_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "runs-admin-table"
        columns = self._run_admin_columns()
        toolbar = self._admin_toolbar(
            title="执行批次",
            description="可直接停止活跃 Run，详情和产物都用当前列表上下文承接。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<button type='button' data-task-modal-target='execute-run'>执行 Run</button>",
                "<a class='button secondary' href='/runs'>刷新</a>",
                self._route_link("产物中心", "/artifacts"),
            ],
        )
        table_html, drawers = self._run_admin_table(
            payload, table_id=table_id, columns=columns
        )
        pagination = self._admin_pagination(
            base_path="/runs",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(
                dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20
            ),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return (
            "<section class='panel admin-list-panel'>"
            + toolbar
            + table_html
            + pagination
            + "</section>"
            + self._task_modal(
                "execute-run", "执行 Run", self._run_execute_form(payload)
            )
            + drawers
        )

    @staticmethod
    def _run_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "run", "label": "Run"},
            {"key": "status", "label": "状态"},
            {"key": "task", "label": "任务"},
            {"key": "package", "label": "包名"},
            {"key": "scenario", "label": "场景"},
            {"key": "devices", "label": "设备"},
            {"key": "monitoring", "label": "Backend / 监控"},
            {"key": "created", "label": "创建时间"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _run_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        runs = list(payload.get("runs", []) or [])
        current_actor = dict(payload.get("current_actor", {}) or {})
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for run in runs:
            item = dict(run or {})
            run_id = str(item.get("run_id", "") or "")
            task_id = str(item.get("task_id", "") or "")
            task_name = str(item.get("task_name", "") or run_id or "未命名 Run")
            run_status = str(item.get("run_status", "") or "unknown")
            drawer_id = f"admin-run-detail-{self._dom_id_fragment(run_id)}"
            short_run_id = (
                run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
            )
            devices = ", ".join(item.get("target_device_ids", []) or []) or "n/a"
            monitoring_summary = dict(item.get("monitoring_summary", {}) or {})
            backend = self._monitoring_backend_label(monitoring_summary)
            monitor_line = str(
                monitoring_summary.get("summary_line", "") or "未发现监控快照"
            )
            actions = (
                "<div class='admin-table-actions'>"
                + self._admin_drawer_button("详情", drawer_id)
                + self._route_link_new_tab("查看详情", item.get("detail_path", ""))
                + self._route_link_new_tab(
                    "产物", f"/artifacts/run/{quote(run_id, safe='')}" if run_id else ""
                )
                + self._route_link_new_tab("Run JSON", item.get("api_path", ""))
                + self._task_run_execute_inline_form(item, current_actor=current_actor)
                + self._task_run_stop_inline_form(item, current_actor=current_actor)
                + "</div>"
            )
            rows.append(
                {
                    "select": f"<input type='checkbox' name='run_id' value='{escape(run_id, quote=True)}' />",
                    "run": (
                        f"<strong class='mono' title='{escape(run_id, quote=True)}'>{escape(short_run_id or 'n/a')}</strong>"
                        f"<div class='mono' title='{escape(run_id, quote=True)}'>{escape(run_id)}</div>"
                    ),
                    "status": self._admin_status(
                        run_status, tone=self._status_tone(run_status)
                    ),
                    "task": self._route_link(
                        task_name,
                        f"/tasks/task/{quote(task_id, safe='')}" if task_id else "",
                    ),
                    "package": f"<span class='mono'>{escape(str(item.get('package_name', '') or 'n/a'))}</span>",
                    "scenario": self._task_template_cell(
                        str(item.get("template_type", "") or "")
                    ),
                    "devices": f"<span title='{escape(devices, quote=True)}'>{escape(devices)}</span>",
                    "monitoring": (
                        f"<span class='mono'>{escape(backend)}</span>"
                        f"<div class='meta' title='{escape(monitor_line, quote=True)}'>{escape(monitor_line)}</div>"
                    ),
                    "created": escape(
                        self._display_datetime(item.get("created_at", "")) or "n/a"
                    ),
                    "actions": actions,
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"Run 详情 · {short_run_id or run_id}",
                    self._run_admin_detail(item),
                )
            )
        return self._admin_table(
            table_id=table_id,
            columns=columns,
            rows=rows,
            empty_text="当前没有匹配 Run。",
        ), "".join(drawers)

    def _run_admin_detail(self, run: Mapping[str, Any]) -> str:
        monitoring_summary = dict(run.get("monitoring_summary", {}) or {})
        fields = [
            ("Run ID", run.get("run_id", "")),
            ("任务 ID", run.get("task_id", "")),
            ("任务名", run.get("task_name", "")),
            ("包名", run.get("package_name", "")),
            ("场景", run.get("template_type", "")),
            ("状态", run.get("run_status", "")),
            ("设备", ", ".join(run.get("target_device_ids", []) or [])),
            ("Backend", self._monitoring_backend_label(monitoring_summary)),
            ("创建时间", self._display_datetime(run.get("created_at", "")) or "n/a"),
            ("监控样本", monitoring_summary.get("sample_count", 0)),
            ("Trace", monitoring_summary.get("trace_count", 0)),
        ]
        details = "".join(
            "<div class='admin-detail-item'>"
            f"<small>{escape(str(label))}</small>"
            f"<strong>{escape(str(value or 'n/a'))}</strong>"
            "</div>"
            for label, value in fields
        )
        return (
            "<div class='admin-detail-grid'>" + details + "</div>"
            "<details class='compact-details'><summary>Monitoring Summary</summary><pre class='mono compact-pre'>"
            + escape(
                json.dumps(
                    monitoring_summary, ensure_ascii=False, indent=2, default=str
                )
            )
            + "</pre></details>"
            "<details class='compact-details'><summary>Run JSON</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(dict(run), ensure_ascii=False, indent=2, default=str))
            + "</pre></details>"
        )

    def _run_list(self, runs: Sequence[Mapping[str, Any]]) -> str:
        if not runs:
            return self._notice("当前没有执行记录。", tone="warning")
        cards = []
        for item in runs:
            run = dict(item or {})
            run_id = str(run.get("run_id", "") or "")
            task_id = str(run.get("task_id", "") or "")
            task_path = f"/tasks/task/{quote(task_id, safe='')}" if task_id else ""
            task_name = str(run.get("task_name", "") or run_id or "未命名 Run")
            run_status = str(run.get("run_status", "") or "unknown")
            short_run_id = (
                run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
            )
            devices = ", ".join(run.get("target_device_ids", []) or []) or "n/a"
            monitoring_summary = dict(run.get("monitoring_summary", {}) or {})
            monitor_line = str(
                monitoring_summary.get("summary_line", "") or "未发现监控快照"
            )
            cards.append(
                "<article class='record-list-card run-list-card'>"
                "<div class='record-list-card-head'>"
                f"<h4 title='{escape(task_name, quote=True)}'>{escape(task_name)}</h4>"
                f"<span class='pill'>{escape(run_status)}</span>"
                "</div>"
                f"<div class='record-run-id mono' title='{escape(run_id, quote=True)}'>{escape(short_run_id or 'n/a')}</div>"
                "<div class='record-list-meta-grid'>"
                f"<div><b>设备</b><span title='{escape(devices, quote=True)}'>{escape(devices)}</span></div>"
                f"<div><b>创建</b>{escape(self._display_datetime(run.get('created_at', '')) or 'n/a')}</div>"
                f"<div><b>任务</b>{self._route_link(task_id or 'n/a', task_path)}</div>"
                f"<div class='record-list-wide'><b>监控</b><span title='{escape(monitor_line, quote=True)}'>{escape(monitor_line)}</span></div>"
                "</div>"
                "<div class='record-list-actions'>"
                + self._route_link_new_tab("查看详情", run.get("detail_path", ""))
                + " / "
                + self._route_link_new_tab(
                    "产物", f"/artifacts/run/{quote(run_id, safe='')}" if run_id else ""
                )
                + " / "
                + self._route_link_new_tab("Run JSON", run.get("api_path", ""))
                + "</div>"
                "</article>"
            )
        return "<div class='record-list-cards run-list'>" + "".join(cards) + "</div>"

    def _task_run_board(self, payload: Mapping[str, Any]) -> str:
        tasks = list(payload.get("tasks", []) or [])
        if not tasks:
            return self._notice("当前没有任务定义。")
        current_actor = dict(payload.get("current_actor", {}) or {})
        cards: list[str] = []
        modals: list[str] = []
        for task in tasks:
            task_payload = dict(task or {})
            task_id = str(task_payload.get("task_id", "") or "")
            modal_id = f"task-runs-{self._dom_id_fragment(task_id)}"
            task_name = str(
                task_payload.get("task_name", "") or task_id or "未命名任务"
            )
            cards.append(
                self._task_run_row(
                    task_payload, modal_id=modal_id, current_actor=current_actor
                )
            )
            modals.append(
                self._task_modal(
                    modal_id,
                    f"Run 列表 · {task_name}",
                    self._task_run_modal_body(
                        task_payload, payload=payload, current_actor=current_actor
                    ),
                )
            )
        return (
            "<div class='task-run-board'>"
            "<div class='task-run-board-head'>"
            "<div><h3>任务列表</h3><span>每个任务直接管理自己的 Run：创建、执行、停止、查看详情和归档都在同一行完成。</span></div>"
            "<a class='action-link' href='/tasks?show_archived=1'>查看归档任务</a>"
            "</div>"
            "<div class='task-run-list'>"
            + "".join(cards)
            + "</div></div>"
            + "".join(modals)
        )

    def _task_run_row(
        self,
        task: Mapping[str, Any],
        *,
        modal_id: str,
        current_actor: Mapping[str, Any],
    ) -> str:
        task_id = str(task.get("task_id", "") or "")
        task_name = str(task.get("task_name", "") or task_id or "未命名任务")
        package_name = str(task.get("package_name", "") or "n/a")
        template_cell = self._task_template_cell(
            str(task.get("template_type", "") or "")
        )
        created_at = self._display_datetime(task.get("created_at", "")) or "n/a"
        archived = bool(task.get("archived") or task.get("hidden"))
        latest_status = str(task.get("latest_run_status", "") or "no_run")
        run_count = int(task.get("run_count", 0) or 0)
        active_count = int(task.get("active_run_count", 0) or 0)
        archive_action = (
            self._task_archive_inline_form(task_id, current_actor=dict(current_actor))
            if task_id and not archived
            else ""
        )
        return (
            f"<article class='task-run-row{' archived-record' if archived else ''}'>"
            "<div class='task-run-main'>"
            f"<h3 title='{escape(task_name, quote=True)}'>{escape(task_name)}</h3>"
            "<div class='task-run-subline'>"
            f"<div>{template_cell}</div>"
            f"<span class='mono' title='{escape(package_name, quote=True)}'>{escape(package_name)}</span>"
            f"<span class='mono' title='{escape(task_id, quote=True)}'>id:{escape(task_id)}</span>"
            f"<span>{escape(created_at)}</span>"
            "</div>"
            "</div>"
            "<div class='task-run-metrics'>"
            + self._task_run_metric("Run", run_count)
            + self._task_run_metric("最新", latest_status)
            + self._task_run_metric("运行中", active_count)
            + "</div>"
            "<div class='task-row-actions'>"
            f"<button type='button' class='task-run-primary-button' data-task-modal-target='{escape(modal_id, quote=True)}'>Run</button>"
            + self._route_link_new_tab(
                "任务详情", f"/tasks/task/{quote(task_id, safe='')}" if task_id else ""
            )
            + archive_action
            + ("<span class='pill'>已归档</span>" if archived else "")
            + "</div>"
            "</article>"
        )

    @staticmethod
    def _task_run_metric(label: str, value: object) -> str:
        return (
            "<span class='task-run-metric'>"
            f"<small>{escape(label)}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
        )

    def _task_run_modal_body(
        self,
        task: Mapping[str, Any],
        *,
        payload: Mapping[str, Any],
        current_actor: Mapping[str, Any],
    ) -> str:
        runs = list(task.get("runs", []) or [])
        return (
            "<div class='task-run-modal-stack'>"
            + self._task_run_create_inline_form(
                task, payload=payload, current_actor=current_actor
            )
            + self._task_run_entries(runs, current_actor=current_actor)
            + "</div>"
        )

    def _task_run_create_inline_form(
        self,
        task: Mapping[str, Any],
        *,
        payload: Mapping[str, Any],
        current_actor: Mapping[str, Any],
    ) -> str:
        task_id = str(task.get("task_id", "") or "")
        selected_devices = set(
            str(item) for item in list(task.get("selected_device_ids", []) or [])
        )
        device_select = self._task_run_device_select(
            list(payload.get("schedulable_devices", []) or []),
            selected_devices=selected_devices,
        )
        return (
            "<section class='task-run-modal-section'>"
            "<div class='task-run-modal-section-head'><strong>创建 Run</strong><span>默认优先选中任务已绑定设备，可临时改成设备池里的其他设备。</span></div>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='task-run-create-form'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            f"{device_select}"
            "<label>metadata(JSON)<textarea name='metadata' rows='2' placeholder='例如 {\"source\":\"tasks-page\"}'></textarea></label>"
            "<div class='form-actions'><button type='submit'>创建 Run</button></div>"
            "</form>"
            "</section>"
        )

    @staticmethod
    def _task_run_device_select(
        devices: Sequence[Mapping[str, Any]],
        *,
        selected_devices: set[str],
    ) -> str:
        options = []
        for item in devices:
            device_id = str(item.get("device_id", "") or "")
            if not device_id:
                continue
            label_parts = [
                device_id,
                str(item.get("model", "") or item.get("product", "") or "").strip(),
                str(item.get("connection_state", "") or "").strip(),
            ]
            label = " / ".join(part for part in label_parts if part)
            selected = " selected" if device_id in selected_devices else ""
            options.append(
                f"<option value='{escape(device_id, quote=True)}'{selected}>{escape(label)}</option>"
            )
        if not options:
            return "<div class='notice warning'>当前没有可调度设备，先到设备池刷新或连接设备。</div>"
        return (
            "<label>设备<select name='device' multiple required>"
            + "".join(options)
            + "</select></label>"
        )

    def _task_run_entries(
        self, runs: Sequence[Mapping[str, Any]], *, current_actor: Mapping[str, Any]
    ) -> str:
        if not runs:
            return (
                "<section class='task-run-modal-section'>"
                + self._notice("这个任务还没有 Run，先在上方创建一条。")
                + "</section>"
            )
        entries = "".join(
            self._task_run_entry(dict(run), current_actor=current_actor) for run in runs
        )
        return (
            "<section class='task-run-modal-section'>"
            "<div class='task-run-modal-section-head'><strong>Run 列表</strong><span>只展示最近关联记录；完整细节从 Run 详情继续下钻。</span></div>"
            "<div class='task-run-entry-list'>" + entries + "</div></section>"
        )

    def _task_run_entry(
        self, run: Mapping[str, Any], *, current_actor: Mapping[str, Any]
    ) -> str:
        run_id = str(run.get("run_id", "") or "")
        run_status = str(run.get("run_status", "") or "unknown")
        short_run_id = run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
        devices = ", ".join(run.get("target_device_ids", []) or []) or "n/a"
        monitoring_summary = dict(run.get("monitoring_summary", {}) or {})
        monitor_line = str(
            monitoring_summary.get("summary_line", "未发现监控快照") or "未发现监控快照"
        )
        return (
            "<article class='task-run-entry'>"
            "<div class='task-run-entry-head'>"
            f"<strong class='mono' title='{escape(run_id, quote=True)}'>{escape(short_run_id or 'n/a')}</strong>"
            f"<span class='pill'>{escape(run_status)}</span>"
            "</div>"
            "<div class='task-run-entry-meta'>"
            f"<span><b>设备</b>{escape(devices)}</span>"
            f"<span><b>创建</b>{escape(self._display_datetime(run.get('created_at', '')) or 'n/a')}</span>"
            f"<span class='task-run-entry-wide'><b>监控</b>{escape(monitor_line)}</span>"
            "</div>"
            "<div class='task-run-entry-actions'>"
            + self._route_link_new_tab("Run 详情", run.get("detail_path", ""))
            + self._route_link_new_tab(
                "产物", f"/artifacts/run/{quote(run_id, safe='')}" if run_id else ""
            )
            + self._route_link_new_tab("Run JSON", run.get("api_path", ""))
            + self._task_run_execute_inline_form(run, current_actor=current_actor)
            + self._task_run_stop_inline_form(run, current_actor=current_actor)
            + "</div>"
            "</article>"
        )

    def _task_run_execute_inline_form(
        self, run: Mapping[str, Any], *, current_actor: Mapping[str, Any]
    ) -> str:
        if not self._run_can_execute(run):
            return ""
        run_id = str(run.get("run_id", "") or "")
        return (
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/execute-run', current_actor=current_actor), quote=True)}' class='task-run-action-form task-run-execute-form'>"
            f"<input type='hidden' name='run_id' value='{escape(run_id, quote=True)}' />"
            "<label>Backend<select name='monitoring_backend'><option value='default'>default</option><option value='solox'>solox</option><option value='perfetto'>perfetto</option><option value='solox_perfetto'>solox_perfetto</option></select></label>"
            "<label>并发<input type='number' name='max_concurrency' value='1' min='1' /></label>"
            "<label>重试<input type='number' name='retry_count' value='0' min='0' /></label>"
            "<button type='submit'>执行</button>"
            "</form>"
        )

    def _task_run_stop_inline_form(
        self, run: Mapping[str, Any], *, current_actor: Mapping[str, Any]
    ) -> str:
        if not self._run_can_stop(run):
            return ""
        run_id = str(run.get("run_id", "") or "")
        return (
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/stop-run', current_actor=current_actor), quote=True)}' class='task-run-action-form task-run-stop-form'>"
            f"<input type='hidden' name='run_id' value='{escape(run_id, quote=True)}' />"
            "<input type='hidden' name='reason' value='user_stopped' />"
            "<button type='submit' class='danger-inline-button'>停止</button>"
            "</form>"
        )

    @staticmethod
    def _run_can_execute(run: Mapping[str, Any]) -> bool:
        status = str(run.get("run_status", "") or "").lower()
        if status in {"success", "failed", "cancelled", "partial_failed", "running"}:
            return False
        counts = dict(run.get("instance_status_counts", {}) or {})
        return not any(
            str(key) in {"running", "preparing", "stopping", "collecting"}
            and int(value or 0) > 0
            for key, value in counts.items()
        )

    @staticmethod
    def _run_can_stop(run: Mapping[str, Any]) -> bool:
        status = str(run.get("run_status", "") or "").lower()
        if status in {"success", "failed", "cancelled", "partial_failed"}:
            return False
        counts = dict(run.get("instance_status_counts", {}) or {})
        active_states = {"pending", "preparing", "running", "stopping", "collecting"}
        return status in {"queued", "pending", "running"} or any(
            str(key) in active_states and int(value or 0) > 0
            for key, value in counts.items()
        )

    @staticmethod
    def _dom_id_fragment(value: str) -> str:
        safe = "".join(
            ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "")
        )
        return safe or "unknown"

    def _render_run_detail(self, payload: dict[str, Any]) -> str:
        run = dict(payload.get("run", {}) or {})
        task = dict(run.get("task", {}) or {})
        monitoring_summary = dict(run.get("monitoring_summary", {}) or {})
        task_id = str(run.get("task_id", "") or "")
        run_id = str(run.get("run_id", "") or "")
        body = [
            self._task_page_return_strip(
                current="Run 详情",
                links=[
                    ("返回 Run 列表", "/runs"),
                    ("返回任务大厅", "/tasks"),
                    (
                        "返回任务详情",
                        f"/tasks/task/{quote(task_id, safe='')}" if task_id else "",
                    ),
                    (
                        "查看 Run 产物",
                        f"/artifacts/run/{quote(run_id, safe='')}" if run_id else "",
                    ),
                ],
            ),
            self._run_detail_compact_summary(run, task, monitoring_summary),
            self._workflow_nav_bar(
                active="run",
                task_path=f"/tasks/task/{quote(task_id, safe='')}"
                if task_id
                else "/tasks",
                run_path="/runs",
                artifact_path="/artifacts",
                run_hint="Run 列表",
                artifact_items=self._run_detail_artifact_items(run),
                artifact_hint="产物列表",
            ),
            self._section(
                "Run 概览",
                [
                    "<details class='compact-details run-detail-json-drawer'>"
                    "<summary>查看 Run 原始概览 JSON</summary>"
                    "<pre class='mono compact-pre'>"
                    + escape(
                        json.dumps(
                            {
                                "run_id": run.get("run_id", ""),
                                "task_id": run.get("task_id", ""),
                                "task_name": run.get("task_name", ""),
                                "run_status": run.get("run_status", ""),
                                "target_device_ids": run.get("target_device_ids", []),
                                "created_at": run.get("created_at", ""),
                                "started_at": run.get("started_at", ""),
                                "finished_at": run.get("finished_at", ""),
                                "summary": run.get("summary", {}),
                                "monitoring_summary": monitoring_summary,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    + "</pre></details>"
                ],
            ),
            self._section(
                "Monitoring Overview",
                [
                    f"<p>{self._route_link_new_tab('Run JSON', run.get('api_path', ''))}</p>",
                    self._notice(
                        str(
                            monitoring_summary.get("summary_line", "")
                            or "当前这条 Run 还没有可展示的监控快照。"
                        ),
                        tone="ok"
                        if monitoring_summary.get("sample_count", 0)
                        else "warning",
                    ),
                ],
            ),
            self._section(
                "Execution Instances",
                [
                    self._run_instance_monitoring_cards(
                        list(run.get("instances", []) or [])
                    )
                ],
            ),
        ]
        return self._layout(
            "Run 详情",
            "展示单条 Run 的执行实例、监控 backend、关键指标和 trace 入口。",
            "".join(body),
        )

    def _workflow_nav_bar(
        self,
        *,
        active: str,
        task_path: str = "/tasks",
        run_path: str = "/runs",
        performance_path: str = "/performance",
        artifact_path: str = "",
        artifact_items: Sequence[tuple[str, Any]] | None = None,
        task_hint: str = "定义目标、模板和设备",
        run_hint: str = "创建批次并执行",
        performance_hint: str = "查看采样和趋势",
        artifact_hint: str | None = None,
    ) -> str:
        fallback_label, fallback_path = self._first_workflow_artifact(
            artifact_items or []
        )
        resolved_artifact_path = str(artifact_path or fallback_path or "").strip()
        artifact_label = "统一产物页" if artifact_path else fallback_label
        resolved_artifact_hint = (
            artifact_hint
            if artifact_hint is not None
            else artifact_label or "报告 / Trace / JSON"
        )
        steps = [
            ("tasks", "任务", task_path, task_hint),
            ("run", "Run", run_path, run_hint),
            ("performance", "性能", performance_path, performance_hint),
            ("artifact", "产物", resolved_artifact_path or "#", resolved_artifact_hint),
        ]
        rendered = []
        for key, label, path, hint in steps:
            class_name = "workflow-step"
            if key == active:
                class_name += " active"
            if key == "artifact" and not resolved_artifact_path:
                class_name += " muted"
            disabled = (
                " aria-disabled='true'"
                if key == "artifact" and not resolved_artifact_path
                else ""
            )
            rendered.append(
                f"<a class='{class_name}' href='{escape(str(path or '#'), quote=True)}'{disabled}>"
                f"<strong>{escape(label)}</strong>"
                f"<span>{escape(str(hint))}</span>"
                "</a>"
            )
        return (
            "<nav class='workflow-nav-bar' aria-label='任务到产物操作链路'>"
            "<div class='workflow-nav-title'>任务 -> Run -> 性能 -> 产物</div>"
            "<div class='workflow-nav-steps'>" + "".join(rendered) + "</div>"
            "</nav>"
        )

    @staticmethod
    def _task_page_return_strip(
        *, current: str, links: Sequence[tuple[str, Any]]
    ) -> str:
        rendered_links = []
        for label, path in links:
            label_text = str(label or "").strip()
            raw_path = str(path or "").strip()
            if not label_text or not raw_path:
                continue
            rendered_links.append(
                f"<a class='action-link' href='{escape(raw_path, quote=True)}'>{escape(label_text)}</a>"
            )
        if not rendered_links:
            return ""
        return (
            "<div class='page-return-strip'>"
            f"<div class='page-return-meta'>{escape(str(current or '当前位置'))}</div>"
            "<div class='page-return-actions'>"
            + "".join(rendered_links)
            + "</div></div>"
        )

    @staticmethod
    def _first_workflow_artifact(items: Sequence[tuple[str, Any]]) -> tuple[str, str]:
        for label, path in items:
            value = str(path or "").strip()
            if value:
                return str(label or "产物"), value
        return "", ""

    @staticmethod
    def _run_detail_artifact_items(run: Mapping[str, Any]) -> list[tuple[str, Any]]:
        items: list[tuple[str, Any]] = [("Run JSON", run.get("api_path", ""))]
        for instance in list(run.get("instances", []) or []):
            monitoring = dict((instance or {}).get("monitoring", {}) or {})
            items.extend(
                [
                    ("Snapshot JSON", monitoring.get("snapshot_path", "")),
                    ("Trace", monitoring.get("trace_path", "")),
                    ("Report Markdown", (instance or {}).get("report_path", "")),
                    ("Report HTML", (instance or {}).get("html_report_path", "")),
                    ("Execution Log", (instance or {}).get("execution_log_path", "")),
                ]
            )
        return items

    def _run_artifacts_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        run = dict(payload.get("run", {}) or {})
        instances = list(run.get("instances", []) or [])
        reports: list[dict[str, Any]] = []
        monitoring: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        for instance in instances:
            item = dict(instance or {})
            instance_id = str(item.get("instance_id", "") or "")
            device_id = str(item.get("device_id", "") or "")
            reports.append(
                {
                    "instance_id": instance_id,
                    "device_id": device_id,
                    "markdown_path": str(item.get("report_path", "") or ""),
                    "html_path": str(item.get("html_report_path", "") or ""),
                    "execution_log_path": str(item.get("execution_log_path", "") or ""),
                }
            )
            monitor = dict(item.get("monitoring", {}) or {})
            monitoring.append(
                {
                    "instance_id": instance_id,
                    "device_id": device_id,
                    "backend": str(monitor.get("backend", "") or "unknown"),
                    "snapshot_path": str(monitor.get("snapshot_path", "") or ""),
                    "samples_path": str(monitor.get("samples_path", "") or ""),
                    "sample_count": int(monitor.get("sample_count", 0) or 0),
                    "metrics": dict(monitor.get("metrics", {}) or {}),
                    "captured_at": str(monitor.get("captured_at", "") or ""),
                }
            )
            trace_path = str(
                monitor.get("trace_path", "")
                or item.get("monitoring_trace_path", "")
                or ""
            )
            if trace_path:
                traces.append(
                    {
                        "instance_id": instance_id,
                        "device_id": device_id,
                        "trace_path": trace_path,
                    }
                )
            issue_count = int(item.get("issue_count", 0) or 0)
            if issue_count or item.get("exit_reason") or item.get("highlights"):
                issues.append(
                    {
                        "instance_id": instance_id,
                        "device_id": device_id,
                        "status": str(item.get("status", "") or ""),
                        "issue_count": issue_count,
                        "exit_reason": str(item.get("exit_reason", "") or ""),
                        "result_level": str(item.get("result_level", "") or ""),
                        "highlights": list(item.get("highlights", []) or []),
                        "note": str(item.get("note", "") or ""),
                    }
                )
        return {
            "page": "run_artifacts",
            "title": f"Run 产物 · {run.get('run_id', '')}",
            "generated_at": payload.get("generated_at", ""),
            "run": run,
            "summary": {
                "report_count": sum(
                    1
                    for item in reports
                    if item.get("markdown_path") or item.get("html_path")
                ),
                "trace_count": len(traces),
                "monitoring_snapshot_count": sum(
                    1 for item in monitoring if item.get("snapshot_path")
                ),
                "issue_count": int(
                    dict(run.get("summary", {}) or {}).get("total_issues", 0)
                    or sum(int(item.get("issue_count", 0) or 0) for item in issues)
                ),
            },
            "reports": reports,
            "traces": traces,
            "monitoring": monitoring,
            "issues": issues,
        }

    def _render_run_artifacts(self, payload: dict[str, Any]) -> str:
        artifacts = self._run_artifacts_payload(payload)
        run = dict(artifacts.get("run", {}) or {})
        task = dict(run.get("task", {}) or {})
        run_id = str(run.get("run_id", "") or "")
        task_id = str(run.get("task_id", "") or "")
        body = [
            self._task_page_return_strip(
                current="Run 产物",
                links=[
                    ("返回产物列表", "/artifacts"),
                    ("返回 Run 列表", "/runs"),
                    ("返回任务大厅", "/tasks"),
                    (
                        "返回 Run 详情",
                        f"/runs/{quote(run_id, safe='')}" if run_id else "",
                    ),
                    (
                        "返回任务详情",
                        f"/tasks/task/{quote(task_id, safe='')}" if task_id else "",
                    ),
                ],
            ),
            self._run_artifact_summary(artifacts),
            self._workflow_nav_bar(
                active="artifact",
                task_path=f"/tasks/task/{quote(task_id, safe='')}"
                if task_id
                else "/tasks",
                run_path="/runs",
                artifact_path="/artifacts",
                run_hint="Run 列表",
                artifact_hint="产物列表",
            ),
            self._section(
                "Report",
                [
                    self._run_artifact_report_cards(
                        list(artifacts.get("reports", []) or [])
                    )
                ],
            ),
            self._section(
                "Trace",
                [
                    self._run_artifact_trace_cards(
                        list(artifacts.get("traces", []) or [])
                    )
                ],
            ),
            self._section(
                "Monitoring Snapshot",
                [
                    self._run_artifact_monitoring_cards(
                        list(artifacts.get("monitoring", []) or [])
                    )
                ],
            ),
            self._section(
                "Issue Summary",
                [
                    self._run_artifact_issue_cards(
                        list(artifacts.get("issues", []) or []), run
                    )
                ],
            ),
        ]
        return self._layout(
            "Run 产物",
            f"{escape(str(task.get('task_name', '') or run.get('task_name', '') or run_id))} 的报告、Trace、监控快照和异常摘要统一入口。",
            "".join(body),
        )

    @staticmethod
    def _run_artifact_summary(artifacts: Mapping[str, Any]) -> str:
        summary = dict(artifacts.get("summary", {}) or {})
        run = dict(artifacts.get("run", {}) or {})
        chips = "".join(
            "<span class='runner-summary-chip run-artifact-summary-chip'>"
            f"<small>{escape(label)}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
            for label, value in (
                ("Run", run.get("run_id", "n/a") or "n/a"),
                ("报告", summary.get("report_count", 0)),
                ("Trace", summary.get("trace_count", 0)),
                ("监控快照", summary.get("monitoring_snapshot_count", 0)),
                ("Issue", summary.get("issue_count", 0)),
            )
        )
        return (
            "<section class='card runner-summary-compact run-artifact-summary-compact'>"
            "<div class='runner-summary-row run-artifact-summary-row'>"
            + chips
            + "</div>"
            "</section>"
        )

    def _run_artifact_report_cards(self, reports: Sequence[Mapping[str, Any]]) -> str:
        cards = []
        for item in reports:
            links = self._artifact_links(
                "文件",
                [
                    ("Markdown", item.get("markdown_path", "")),
                    ("HTML", item.get("html_path", "")),
                    ("执行日志", item.get("execution_log_path", "")),
                ],
            )
            if not links:
                links = self._notice(
                    "当前实例没有落盘 report 或执行日志。", tone="warning"
                )
            cards.append(
                "<article class='card stack run-artifact-card'>"
                f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
                f"<div class='meta'>device={escape(str(item.get('device_id', '') or 'n/a'))}</div>"
                + links
                + "</article>"
            )
        return (
            "<div class='cards run-artifact-grid'>" + "".join(cards) + "</div>"
            if cards
            else self._notice("当前 Run 没有 report 产物。", tone="warning")
        )

    def _run_artifact_trace_cards(self, traces: Sequence[Mapping[str, Any]]) -> str:
        if not traces:
            return self._notice(
                "当前 Run 没有 trace 产物。default/SoloX 后端通常没有 Perfetto trace；需要 trace 时使用 perfetto backend。",
                tone="warning",
            )
        return (
            "<div class='cards run-artifact-grid'>"
            + "".join(
                "<article class='card stack run-artifact-card'>"
                f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
                f"<div class='meta'>device={escape(str(item.get('device_id', '') or 'n/a'))}</div>"
                + self._artifact_links(
                    "Trace 文件", [("Perfetto Trace", item.get("trace_path", ""))]
                )
                + "</article>"
                for item in traces
            )
            + "</div>"
        )

    def _run_artifact_monitoring_cards(
        self, monitoring_items: Sequence[Mapping[str, Any]]
    ) -> str:
        cards = []
        for item in monitoring_items:
            metrics = dict(item.get("metrics", {}) or {})
            metric_line = (
                ", ".join(f"{key}={value}" for key, value in metrics.items())
                or "暂无关键指标"
            )
            cards.append(
                "<article class='card stack run-artifact-card'>"
                f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
                f"<div class='meta'>backend={escape(str(item.get('backend', '') or 'unknown'))} / samples={escape(str(item.get('sample_count', 0)))}</div>"
                f"<p class='mono compact-line'>{escape(metric_line)}</p>"
                + self._artifact_links(
                    "采样文件",
                    [
                        ("Snapshot JSON", item.get("snapshot_path", "")),
                        ("Samples JSON", item.get("samples_path", "")),
                    ],
                )
                + "</article>"
            )
        return (
            "<div class='cards run-artifact-grid'>" + "".join(cards) + "</div>"
            if cards
            else self._notice("当前 Run 没有 monitoring snapshot。", tone="warning")
        )

    @staticmethod
    def _run_artifact_issue_cards(
        issues: Sequence[Mapping[str, Any]], run: Mapping[str, Any]
    ) -> str:
        if not issues:
            total = int(dict(run.get("summary", {}) or {}).get("total_issues", 0) or 0)
            if total <= 0:
                return "<div class='notice ok'>当前 Run 未记录 issue。</div>"
        cards = []
        for item in issues:
            highlights = (
                ", ".join(
                    str(value) for value in list(item.get("highlights", []) or [])
                )
                or "无高亮信号"
            )
            cards.append(
                "<article class='card stack run-artifact-card'>"
                f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
                f"<div class='meta'>device={escape(str(item.get('device_id', '') or 'n/a'))} / status={escape(str(item.get('status', '') or 'unknown'))}</div>"
                "<ul>"
                f"<li>issue_count：{escape(str(item.get('issue_count', 0)))}</li>"
                f"<li>exit_reason：{escape(str(item.get('exit_reason', '') or 'n/a'))}</li>"
                f"<li>result_level：{escape(str(item.get('result_level', '') or 'n/a'))}</li>"
                f"<li>highlights：{escape(highlights)}</li>"
                "</ul>"
                + (
                    f"<p>{escape(str(item.get('note', '') or ''))}</p>"
                    if item.get("note")
                    else ""
                )
                + "</article>"
            )
        return (
            "<div class='cards run-artifact-grid'>" + "".join(cards) + "</div>"
            if cards
            else "<div class='notice ok'>当前 Run 未记录 issue。</div>"
        )

    @staticmethod
    def _run_detail_compact_summary(
        run: Mapping[str, Any],
        task: Mapping[str, Any],
        monitoring_summary: Mapping[str, Any],
    ) -> str:
        chips = "".join(
            "<span class='runner-summary-chip run-detail-summary-chip'>"
            f"<small>{escape(label)}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
            for label, value in (
                ("Run 状态", run.get("run_status", "unknown")),
                ("实例数", run.get("instance_count", 0)),
                ("监控样本", monitoring_summary.get("sample_count", 0)),
                ("Trace 数", monitoring_summary.get("trace_count", 0)),
                ("任务", run.get("task_name", "n/a") or "n/a"),
                ("模板", task.get("template_type", "n/a") or "n/a"),
            )
        )
        return (
            "<section class='card runner-summary-compact run-detail-summary-compact'>"
            "<div class='runner-summary-row run-detail-summary-row'>" + chips + "</div>"
            "</section>"
        )
