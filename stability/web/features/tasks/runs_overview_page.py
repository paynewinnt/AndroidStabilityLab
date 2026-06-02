from __future__ import annotations

import json
from html import escape
from urllib.parse import quote

from stability.scenario.registry import list_scenario_definitions
from typing import Any, Mapping, Sequence


class RunsOverviewPageMixin:
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
