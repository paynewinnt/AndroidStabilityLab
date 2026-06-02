from __future__ import annotations

from stability.scenario.registry import list_scenario_definitions
from stability.time_utils import now_beijing_string

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from stability.web.features.tasks.artifacts_page import TasksArtifactsPageMixin
from stability.web.features.tasks.run_detail_page import TasksRunDetailPageMixin
from stability.web.features.tasks.runs_overview_page import RunsOverviewPageMixin
from stability.web.features.tasks.task_run_board_page import TaskRunBoardPageMixin


def _generated_at_now() -> str:
    return now_beijing_string()


class TasksPageMixin(
    TaskRunBoardPageMixin,
    RunsOverviewPageMixin,
    TasksRunDetailPageMixin,
    TasksArtifactsPageMixin,
):
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
