from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from stability.scenario.registry import list_scenario_definitions


class TasksArtifactsPageMixin:
    def _render_artifacts(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        body = [
            self._admin_page_header(
                "产物中心",
                subtitle="按 Run 汇总报告、Trace、监控快照和异常摘要；详情用抽屉承接，文件再进入单独产物页。",
                breadcrumbs=[("首页", "/"), ("任务大厅", "/tasks"), ("产物中心", "")],
                actions=[self._route_link("JSON API", "/api/artifacts")],
            ),
            self._admin_summary_strip(
                [
                    ("Run 数", summary.get("run_count", 0)),
                    ("报告", summary.get("report_count", 0)),
                    ("Trace", summary.get("trace_count", 0)),
                    ("监控快照", summary.get("monitoring_snapshot_count", 0)),
                    ("Issue", summary.get("issue_count", 0)),
                ]
            ),
            self._workflow_nav_bar(
                active="artifact",
                task_path="/tasks",
                run_path="/runs",
                artifact_path="/artifacts",
                run_hint="Run 列表",
                artifact_hint="产物列表",
            ),
            self._artifact_admin_filter_bar(payload),
            self._artifact_admin_workspace(payload),
        ]
        return self._layout(
            "产物中心",
            "按 Run 汇总报告、Trace、监控快照和异常摘要。",
            "".join(body),
        )

    def _artifact_admin_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        return self._admin_filter_bar(
            action="/artifacts",
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

    def _artifact_admin_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "artifacts-admin-table"
        columns = self._artifact_admin_columns()
        toolbar = self._admin_toolbar(
            title="Run 产物列表",
            description="报告、Trace、监控快照和 Issue 按 Run 聚合；先看列表，再用详情抽屉或产物页下钻。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/artifacts'>刷新</a>",
                self._route_link("Run 列表", "/runs"),
            ],
        )
        table_html, drawers = self._artifact_admin_table(
            payload, table_id=table_id, columns=columns
        )
        pagination = self._admin_pagination(
            base_path="/artifacts",
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
            + drawers
        )

    @staticmethod
    def _artifact_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "run", "label": "Run"},
            {"key": "status", "label": "状态"},
            {"key": "task", "label": "任务"},
            {"key": "package", "label": "包名"},
            {"key": "scenario", "label": "场景"},
            {"key": "devices", "label": "设备"},
            {"key": "artifacts", "label": "产物"},
            {"key": "monitoring", "label": "Backend / 监控"},
            {"key": "created", "label": "创建时间"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _artifact_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        items = list(payload.get("items", []) or [])
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for raw_item in items:
            item = dict(raw_item or {})
            run_id = str(item.get("run_id", "") or "")
            task_id = str(item.get("task_id", "") or "")
            task_name = str(item.get("task_name", "") or run_id or "未命名 Run")
            run_status = str(item.get("run_status", "") or "unknown")
            drawer_id = f"admin-artifact-detail-{self._dom_id_fragment(run_id)}"
            short_run_id = (
                run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
            )
            monitoring_summary = dict(item.get("monitoring_summary", {}) or {})
            artifact_summary = dict(item.get("artifact_summary", {}) or {})
            devices = ", ".join(item.get("target_device_ids", []) or []) or "n/a"
            backend = self._monitoring_backend_label(monitoring_summary)
            monitor_line = str(
                monitoring_summary.get("summary_line", "") or "未发现监控快照"
            )
            artifact_line = " / ".join(
                f"{label}:{artifact_summary.get(key, 0)}"
                for label, key in (
                    ("报告", "report_count"),
                    ("Trace", "trace_count"),
                    ("监控", "monitoring_snapshot_count"),
                    ("Issue", "issue_count"),
                )
            )
            actions = (
                "<div class='admin-table-actions'>"
                + self._admin_drawer_button("详情", drawer_id)
                + self._route_link_new_tab("查看详情", item.get("artifact_path", ""))
                + self._route_link_new_tab("Run 详情", item.get("detail_path", ""))
                + self._route_link_new_tab("Run JSON", item.get("api_path", ""))
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
                    "artifacts": f"<span title='{escape(artifact_line, quote=True)}'>{escape(artifact_line)}</span>",
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
                    f"Run 产物 · {short_run_id or run_id}",
                    self._artifact_admin_detail(item),
                )
            )
        return self._admin_table(
            table_id=table_id,
            columns=columns,
            rows=rows,
            empty_text="当前没有匹配 Run 产物。",
        ), "".join(drawers)

    def _artifact_admin_detail(self, item: Mapping[str, Any]) -> str:
        monitoring_summary = dict(item.get("monitoring_summary", {}) or {})
        artifact_summary = dict(item.get("artifact_summary", {}) or {})
        fields = [
            ("Run ID", item.get("run_id", "")),
            ("任务 ID", item.get("task_id", "")),
            ("任务名", item.get("task_name", "")),
            ("包名", item.get("package_name", "")),
            ("场景", item.get("template_type", "")),
            ("状态", item.get("run_status", "")),
            ("设备", ", ".join(item.get("target_device_ids", []) or [])),
            ("Backend", self._monitoring_backend_label(monitoring_summary)),
            ("创建时间", self._display_datetime(item.get("created_at", "")) or "n/a"),
        ]
        detail_grid = "".join(
            "<div class='admin-detail-item'>"
            f"<small>{escape(str(label))}</small>"
            f"<strong>{escape(str(value or 'n/a'))}</strong>"
            "</div>"
            for label, value in fields
        )
        return (
            "<div class='admin-detail-grid'>"
            + detail_grid
            + "</div>"
            + self._artifact_count_chips(artifact_summary)
            + self._artifact_links(
                "跳转",
                [
                    ("查看详情", item.get("artifact_path", "")),
                    ("Run 详情", item.get("detail_path", "")),
                    ("Run JSON", item.get("api_path", "")),
                    ("Artifacts API", item.get("artifacts_api_path", "")),
                ],
            )
            + "<details class='compact-details'><summary>Monitoring Summary</summary><pre class='mono compact-pre'>"
            + escape(
                json.dumps(
                    monitoring_summary, ensure_ascii=False, indent=2, default=str
                )
            )
            + "</pre></details>"
            "<details class='compact-details'><summary>Artifact Summary</summary><pre class='mono compact-pre'>"
            + escape(
                json.dumps(artifact_summary, ensure_ascii=False, indent=2, default=str)
            )
            + "</pre></details>"
        )

    def _artifact_run_list(self, items: Sequence[Mapping[str, Any]]) -> str:
        if not items:
            return self._notice("当前还没有可展示的 Run 产物。", tone="warning")
        cards = []
        for item in items:
            run_id = str(item.get("run_id", "") or "")
            short_run_id = (
                run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
            )
            task_name = str(item.get("task_name", "") or run_id or "未命名 Run")
            run_status = str(item.get("run_status", "") or "unknown")
            devices = ", ".join(item.get("target_device_ids", []) or []) or "n/a"
            monitoring_summary = dict(item.get("monitoring_summary", {}) or {})
            artifact_summary = dict(item.get("artifact_summary", {}) or {})
            monitor_line = str(
                monitoring_summary.get("summary_line", "") or "未发现监控快照"
            )
            cards.append(
                "<article class='record-list-card artifact-run-card'>"
                "<div class='record-list-card-head'>"
                f"<h4 title='{escape(task_name, quote=True)}'>{escape(task_name)}</h4>"
                f"<span class='pill'>{escape(run_status)}</span>"
                "</div>"
                f"<div class='record-run-id mono' title='{escape(run_id, quote=True)}'>{escape(short_run_id or 'n/a')}</div>"
                "<div class='record-list-meta-grid'>"
                f"<div><b>设备</b><span title='{escape(devices, quote=True)}'>{escape(devices)}</span></div>"
                f"<div><b>创建</b>{escape(self._display_datetime(item.get('created_at', '')) or 'n/a')}</div>"
                f"<div><b>完成</b>{escape(self._display_datetime(item.get('finished_at', '')) or 'n/a')}</div>"
                f"<div class='record-list-wide'><b>监控</b><span title='{escape(monitor_line, quote=True)}'>{escape(monitor_line)}</span></div>"
                "</div>"
                + self._artifact_count_chips(artifact_summary)
                + "<div class='record-list-actions'>"
                + self._route_link_new_tab("查看详情", item.get("artifact_path", ""))
                + " / "
                + self._route_link_new_tab("Run 详情", item.get("detail_path", ""))
                + " / "
                + self._route_link_new_tab("Run JSON", item.get("api_path", ""))
                + "</div>"
                "</article>"
            )
        return (
            "<div class='record-list-cards artifact-run-list'>"
            + "".join(cards)
            + "</div>"
        )

    @staticmethod
    def _artifact_count_chips(summary: Mapping[str, Any]) -> str:
        chips = "".join(
            "<span class='runner-summary-chip artifact-count-chip'>"
            f"<small>{escape(label)}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
            for label, value in (
                ("报告", summary.get("report_count", 0)),
                ("Trace", summary.get("trace_count", 0)),
                ("监控快照", summary.get("monitoring_snapshot_count", 0)),
                ("Issue", summary.get("issue_count", 0)),
            )
        )
        return "<div class='runner-summary-row artifact-count-row'>" + chips + "</div>"
