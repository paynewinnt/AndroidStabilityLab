from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence


class PerformancePageMixin:
    def _render_performance(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        entries = list(payload.get("entries", []) or [])
        help_buttons, help_sections = self._page_help_sections("性能采样", summary=summary)
        body = [
            self._task_page_return_strip(
                current="性能采样",
                links=[("返回任务大厅", "/tasks")],
            ),
            self._workflow_nav_bar(
                active="performance",
                run_path="/runs",
                artifact_path="/artifacts",
                artifact_items=self._performance_artifact_items(entries[0] if entries else {}),
                run_hint="Run 列表",
                artifact_hint="产物列表",
            ),
            self._performance_compact_header(
                summary=summary,
                filters=filters,
                risk_detail_fields=list(payload.get("risk_detail_fields", []) or []),
            ),
            self._section("任务性能趋势", [self._performance_task_panels(entries)]),
            self._section("最近监控快照", [self._performance_entry_cards(entries[:12])]),
            self._section("Backend 分布图", [self._performance_backend_chart(summary)]),
        ]
        return self._layout(
            "性能采样",
            "这页不是实时仪表盘，而是把最近执行实例已经落盘的 monitoring snapshot 收口起来，方便先判断有没有采到、采到了什么、值不值得继续下钻。",
            "".join(body),
            help_buttons=help_buttons,
            help_modal_sections=help_sections,
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
