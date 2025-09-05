from __future__ import annotations

from stability.scenario.registry import list_scenario_definitions

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote


class PerformancePageMixin:
    def _render_performance(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        entries = list(payload.get("entries", []) or [])
        all_entries = list(payload.get("all_entries", entries) or [])
        help_buttons, help_sections = self._page_help_sections("性能采样", summary=summary)
        body = [
            self._admin_page_header(
                "性能采样",
                subtitle="按样本列表查询 backend、设备、包名和关键指标；趋势图保留完整 run 窗口，最大 24h。",
                breadcrumbs=[("首页", "/"), ("任务大厅", "/tasks"), ("性能采样", "")],
                actions=[self._route_link("返回任务大厅", "/tasks"), self._route_link("JSON API", "/api/performance")],
            ),
            self._admin_summary_strip(
                [
                    ("样本数", summary.get("sample_count", 0)),
                    ("有监控 Run", summary.get("monitored_run_count", 0)),
                    ("Trace 数", summary.get("trace_count", 0)),
                    ("最新采样", summary.get("latest_sample_at", "n/a") or "n/a"),
                ]
            ),
            self._workflow_nav_bar(
                active="performance",
                run_path="/runs",
                artifact_path="/artifacts",
                artifact_items=self._performance_artifact_items(all_entries[0] if all_entries else {}),
                run_hint="Run 列表",
                artifact_hint="产物列表",
            ),
            self._performance_admin_filter_bar(filters),
            self._performance_admin_workspace(payload),
            self._section("任务性能趋势", [self._performance_task_panels(all_entries)]),
            self._section("Backend 分布图", [self._performance_backend_chart(summary)]),
            "<details class='compact-details performance-risk-drawer'><summary>性能风险解释字段</summary>"
            + self._performance_risk_contract_card(list(payload.get("risk_detail_fields", []) or []))
            + "</details>",
            "<details class='compact-details performance-onboarding-drawer'><summary>采样说明</summary>"
            + self._performance_compact_header(
                summary=summary,
                filters=filters,
                risk_detail_fields=list(payload.get("risk_detail_fields", []) or []),
            )
            + "</details>",
        ]
        return self._layout(
            "性能采样",
            "这页不是实时仪表盘，而是把最近执行实例已经落盘的 monitoring snapshot 收口起来，方便先判断有没有采到、采到了什么、值不值得继续下钻。",
            "".join(body),
            help_buttons=help_buttons,
            help_modal_sections=help_sections,
        )

    def _performance_admin_filter_bar(self, filters: Mapping[str, Any]) -> str:
        return self._admin_filter_bar(
            action="/performance",
            values=filters,
            fields=[
                {"name": "keyword", "label": "关键词", "placeholder": "Run / 任务 / 包名 / 设备"},
                {
                    "name": "status",
                    "label": "状态",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
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
                    + [{"value": str(item.value), "label": str(item.plain_label)} for item in list_scenario_definitions()],
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
                {"name": "window_hours", "label": "窗口(h)", "type": "number", "placeholder": "1-24"},
                {"name": "page_size", "label": "每页", "type": "number"},
            ],
        )

    def _performance_admin_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "performance-admin-table"
        columns = self._performance_admin_columns()
        toolbar = self._admin_toolbar(
            title="最近监控快照",
            description="样本列表用于快速定位异常；详情、Snapshot JSON 和 Run 入口都不离开当前上下文。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/performance'>刷新</a>",
                self._route_link("Run 列表", "/runs"),
                self._route_link("产物中心", "/artifacts"),
            ],
        )
        table_html, drawers = self._performance_admin_table(payload, table_id=table_id, columns=columns)
        pagination = self._admin_pagination(
            base_path="/performance",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20),
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
    def _performance_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "sample", "label": "样本"},
            {"key": "status", "label": "状态"},
            {"key": "task", "label": "任务"},
            {"key": "package", "label": "包名"},
            {"key": "device", "label": "设备"},
            {"key": "backend", "label": "Backend"},
            {"key": "metrics", "label": "指标"},
            {"key": "captured", "label": "采样时间"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _performance_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        entries = list(payload.get("entries", []) or [])
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for index, raw_entry in enumerate(entries):
            item = dict(raw_entry or {})
            run_id = str(item.get("run_id", "") or "")
            task_id = str(item.get("task_id", "") or "")
            task_name = str(item.get("task_name", "") or run_id or "unknown task")
            sample_id = f"{run_id}-{item.get('instance_id', '')}-{item.get('sample_index', index)}"
            drawer_id = f"admin-performance-sample-{self._dom_id_fragment(sample_id)}"
            run_status = str(item.get("run_status", "") or item.get("instance_status", "") or "unknown")
            metrics = dict(item.get("metrics", {}) or {})
            metric_line = self._performance_metric_summary_line(metrics)
            actions = (
                "<div class='admin-table-actions'>"
                + self._admin_drawer_button("详情", drawer_id)
                + self._route_link_new_tab("Run 详情", item.get("run_detail_path", ""))
                + self._route_link_new_tab("Run JSON", item.get("run_api_path", ""))
                + self._route_link_new_tab("Snapshot JSON", item.get("snapshot_path", ""))
                + self._route_link_new_tab("Trace", item.get("trace_path", ""))
                + "</div>"
            )
            rows.append(
                {
                    "select": f"<input type='checkbox' name='sample' value='{escape(sample_id, quote=True)}' />",
                    "sample": (
                        f"<strong class='mono'>{escape(str(item.get('instance_id', '') or 'n/a'))}</strong>"
                        f"<div class='mono'>sample={escape(str(item.get('sample_index', 0) or 0))}</div>"
                    ),
                    "status": self._admin_status(run_status, tone=self._status_tone(run_status)),
                    "task": self._route_link(task_name, f"/tasks/task/{quote(task_id, safe='')}" if task_id else ""),
                    "package": f"<span class='mono'>{escape(str(item.get('package_name', '') or 'n/a'))}</span>",
                    "device": f"<span class='mono'>{escape(str(item.get('device_id', '') or 'n/a'))}</span>",
                    "backend": escape(str(item.get("backend", "") or "unknown")),
                    "metrics": f"<span title='{escape(metric_line, quote=True)}'>{escape(metric_line)}</span>",
                    "captured": escape(str(item.get("captured_at", "") or item.get("run_created_at", "") or "n/a")),
                    "actions": actions,
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"性能样本 · {task_name}",
                    self._performance_admin_detail(item),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前没有匹配性能样本。"), "".join(drawers)

    @staticmethod
    def _performance_metric_summary_line(metrics: Mapping[str, Any]) -> str:
        pairs = [
            ("CPU", metrics.get("cpu_usage")),
            ("Memory PSS", metrics.get("memory_pss")),
            ("FPS", metrics.get("fps")),
            ("Jank", metrics.get("jank_percent")),
            ("GPU", metrics.get("gpu_usage")),
            ("GPU P95", metrics.get("gpu_p95_ms")),
            ("Frame P99", metrics.get("frame_time_99p")),
        ]
        bits = [f"{label}={value}" for label, value in pairs if value not in ("", None)]
        return " / ".join(bits) if bits else "暂无关键指标"

    def _performance_admin_detail(self, entry: Mapping[str, Any]) -> str:
        metrics = dict(entry.get("metrics", {}) or {})
        fields = [
            ("Run ID", entry.get("run_id", "")),
            ("任务 ID", entry.get("task_id", "")),
            ("任务名", entry.get("task_name", "")),
            ("包名", entry.get("package_name", "")),
            ("设备", entry.get("device_id", "")),
            ("Backend", entry.get("backend", "")),
            ("Run 状态", entry.get("run_status", "")),
            ("实例状态", entry.get("instance_status", "")),
            ("采样时间", entry.get("captured_at", "")),
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
            + self._performance_metric_bars(metrics)
            + self._artifact_links(
                "样本跳转",
                [
                    ("Snapshot JSON", entry.get("snapshot_path", "")),
                    ("Trace", entry.get("trace_path", "")),
                    ("Run 详情", entry.get("run_detail_path", "")),
                    ("Run JSON", entry.get("run_api_path", "")),
                ],
            )
            + "<details class='compact-details'><summary>原始样本 JSON</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(dict(entry), ensure_ascii=False, indent=2, default=str))
            + "</pre></details>"
        )

    def _render_not_found(self, route: str) -> str:
        return self._layout(
            "页面不存在",
            "这个路径目前还没有接进 Web 主入口。",
            self._notice(f"未找到页面：{escape(route)}"),
        )

    @staticmethod
    def _performance_artifact_items(entry: Mapping[str, Any]) -> list[tuple[str, Any]]:
        instance = dict(entry.get("instance", {}) or {})
        return [
            ("Run 详情", entry.get("run_detail_path", "")),
            ("统一产物页", entry.get("artifact_path", "")),
            ("Trace", entry.get("trace_path", "")),
            ("Monitoring Snapshot", entry.get("snapshot_path", "")),
            ("Report Markdown", instance.get("report_path", "")),
            ("Report HTML", instance.get("html_report_path", "")),
        ]

    def _performance_compact_header(
        self,
        *,
        summary: Mapping[str, Any],
        filters: Mapping[str, Any],
        risk_detail_fields: Sequence[str],
    ) -> str:
        chips = "".join(
            "<span class='runner-summary-chip performance-summary-chip'>"
            f"<small>{escape(label)}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
            for label, value in (
                ("样本数", summary.get("sample_count", 0)),
                ("有监控 Run", summary.get("monitored_run_count", 0)),
                ("Trace 数", summary.get("trace_count", 0)),
                ("最新采样", summary.get("latest_sample_at", "n/a") or "n/a"),
            )
        )
        return (
            "<section class='card performance-compact-header'>"
            "<div class='runner-summary-row performance-summary-row'>"
            + chips
            + "</div>"
            "<div class='performance-compact-body'>"
            + self._performance_onboarding_notice(summary)
            + self._performance_scope_notice(summary=summary, filters=filters)
            + "<details class='compact-details performance-risk-drawer'>"
            "<summary>性能风险解释字段</summary>"
            + self._performance_risk_contract_card(list(risk_detail_fields))
            + "</details>"
            "</div>"
            "</section>"
        )


__all__ = ["PerformancePageMixin"]
