from __future__ import annotations

from html import escape
from typing import Any, Mapping
from urllib.parse import quote


class PerformanceRecordCardsMixin:
    def _task_table(self, items: list[dict[str, Any]], *, current_actor: Mapping[str, Any] | None = None) -> str:
        if not items:
            return self._notice("当前没有任务定义。")
        cards = []
        for item in items:
            task_id = str(item.get("task_id", "") or "")
            task_name = str(item.get("task_name", "") or "")
            package_name = str(item.get("package_name", "") or "")
            template_cell = self._task_template_cell(str(item.get("template_type", "") or ""))
            archived = bool(item.get("archived") or item.get("hidden"))
            archive_meta = (
                f"<div class='record-list-wide'><b>归档</b>{escape(self._display_datetime(item.get('archived_at', '')) or '已隐藏')} / {escape(str(item.get('archive_reason', '') or '无说明'))}</div>"
                if archived
                else ""
            )
            archive_action = self._task_archive_inline_form(task_id, current_actor=dict(current_actor or {})) if task_id and not archived else ""
            cards.append(
                f"<article class='record-list-card{' archived-record' if archived else ''}'>"
                "<div class='record-list-card-head'>"
                f"<h4 title='{escape(task_name, quote=True)}'>{escape(task_name or task_id or '未命名任务')}</h4>"
                f"<span>{escape('已归档' if archived else str(item.get('planned_device_count', 0)) + ' 台设备')}</span>"
                "</div>"
                "<div class='record-list-meta-grid'>"
                f"<div><b>模板</b>{template_cell}</div>"
                f"<div><b>包名</b><span title='{escape(package_name, quote=True)}'>{escape(package_name or 'n/a')}</span></div>"
                f"<div><b>创建</b>{escape(self._display_datetime(item.get('created_at', '')) or 'n/a')}</div>"
                f"{archive_meta}"
                "</div>"
                "<div class='record-list-actions'>"
                + self._route_link_new_tab("任务详情", f"/tasks/task/{quote(task_id, safe='')}" if task_id else "")
                + (" / " + self._route_link_new_tab("Task JSON", f"/api/tasks/task/{quote(task_id, safe='')}") if task_id else "")
                + archive_action
                + "</div>"
                "</article>"
            )
        return "<div class='record-list-cards'>" + "".join(cards) + "</div>"

    def _task_archive_inline_form(self, task_id: str, *, current_actor: Mapping[str, Any]) -> str:
        return (
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/archive-task', current_actor=current_actor), quote=True)}' class='inline-archive-form'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<input type='hidden' name='reason' value='用户从任务列表归档隐藏。' />"
            "<button type='submit' class='link-button danger-link-button'>归档隐藏</button>"
            "</form>"
        )

    def _run_table(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有执行记录。")
        cards = []
        for item in items:
            monitoring_summary = dict(item.get("monitoring_summary", {}) or {})
            run_id = str(item.get("run_id", "") or "")
            task_name = str(item.get("task_name", "") or "")
            run_status = str(item.get("run_status", "") or "unknown")
            devices = ", ".join(item.get("target_device_ids", []) or []) or "n/a"
            monitor_line = str(monitoring_summary.get("summary_line", "未发现监控快照") or "未发现监控快照")
            short_run_id = run_id[:10] + "..." + run_id[-6:] if len(run_id) > 22 else run_id
            cards.append(
                "<article class='record-list-card'>"
                "<div class='record-list-card-head'>"
                f"<h4 title='{escape(task_name, quote=True)}'>{escape(task_name or '未命名任务')}</h4>"
                f"<span class='pill'>{escape(run_status)}</span>"
                "</div>"
                f"<div class='record-run-id mono' title='{escape(run_id, quote=True)}'>{escape(short_run_id or 'n/a')}</div>"
                "<div class='record-list-meta-grid'>"
                f"<div><b>设备</b><span title='{escape(devices, quote=True)}'>{escape(devices)}</span></div>"
                f"<div><b>创建</b>{escape(self._display_datetime(item.get('created_at', '')) or 'n/a')}</div>"
                f"<div class='record-list-wide'><b>监控</b><span title='{escape(monitor_line, quote=True)}'>{escape(monitor_line)}</span></div>"
                "</div>"
                "<div class='record-list-actions'>"
                + self._route_link_new_tab("Run 详情", item.get("detail_path", ""))
                + (" / " + self._route_link_new_tab("Run JSON", item.get("api_path", "")) if item.get("api_path", "") else "")
                + "</div>"
                "</article>"
            )
        return "<div class='record-list-cards'>" + "".join(cards) + "</div>"

    def _run_instance_monitoring_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前这条 Run 还没有执行实例。")
        cards = []
        for item in items:
            monitoring = dict(item.get("monitoring", {}) or {})
            metrics = dict(monitoring.get("metrics", {}) or {})
            metric_lines = [
                f"{label}={value}"
                for label, value in (
                    ("cpu", metrics.get("cpu_usage")),
                    ("system_cpu", metrics.get("system_cpu_usage")),
                    ("mem_pss", metrics.get("memory_pss")),
                    ("mem_java", metrics.get("memory_java")),
                    ("mem_native", metrics.get("memory_native")),
                    ("mem_graphics", metrics.get("memory_graphics")),
                    ("fps", metrics.get("fps")),
                    ("frame_p99_ms", metrics.get("frame_time_99p")),
                    ("gpu", metrics.get("gpu_usage")),
                    ("gpu_p95_ms", metrics.get("gpu_p95_ms")),
                    ("gpu_p99_ms", metrics.get("gpu_p99_ms")),
                    ("gpu_temp", metrics.get("gpu_temperature")),
                    ("jank", metrics.get("jank_percent")),
                    ("jank_frames", metrics.get("jank_frames")),
                    ("battery", metrics.get("battery_level")),
                    ("battery_temp", metrics.get("battery_temperature")),
                    ("power", metrics.get("power_usage")),
                    ("trace_bytes", metrics.get("perfetto_trace_size_bytes")),
                )
                if value not in ("", None)
            ]
            cards.append(
                "<article class='card stack run-instance-monitoring-card'>"
                f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
                f"<div class='meta'>device={escape(str(item.get('device_id', '') or 'n/a'))} / status={escape(str(item.get('status', '') or 'unknown'))}</div>"
                f"<div>backend={escape(str(monitoring.get('backend', 'unknown') or 'unknown'))} / captured_at={escape(str(monitoring.get('captured_at', 'n/a') or 'n/a'))}</div>"
                + (
                    f"<div>key metrics：{escape(' / '.join(metric_lines))}</div>"
                    if metric_lines
                    else "<div class='meta'>当前快照里还没有稳定可展示的 key metrics。</div>"
                )
                + (
                    f"<div>apps：{escape(', '.join(monitoring.get('app_packages', []) or []) or 'n/a')}</div>"
                    if monitoring.get("app_packages")
                    else ""
                )
                + self._artifact_links(
                    "实例跳转",
                    [
                        ("Snapshot JSON", monitoring.get("snapshot_path", "")),
                        ("Trace", monitoring.get("trace_path", "")),
                        ("Report Markdown", item.get("report_path", "")),
                        ("Report HTML", item.get("html_report_path", "")),
                        ("Execution Log", item.get("execution_log_path", "")),
                    ],
                )
                + "</article>"
            )
        return "<div class='cards run-instance-monitoring-grid'>" + "".join(cards) + "</div>"


__all__ = ["PerformanceRecordCardsMixin"]
