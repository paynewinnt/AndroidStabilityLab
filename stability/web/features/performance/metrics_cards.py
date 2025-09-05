from __future__ import annotations

from html import escape
from typing import Any, Mapping


class PerformanceMetricsCardsMixin:
    def _performance_backend_cards(self, summary: Mapping[str, Any]) -> str:
        backend_counts = dict(summary.get("backend_counts", {}) or {})
        if not backend_counts:
            return self._notice("当前还没有可统计的 backend 分布。")
        cards = []
        for backend, count in sorted(backend_counts.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
            description = {
                "adb_collector": "兼容采样链路，适合快速确认基础 CPU / memory / network 指标是否有落盘。",
                "solox": "一站式应用层采样，适合无 Root 场景下看 CPU / memory / network / battery / FPS / GPU。",
                "perfetto": "系统级 trace 侧车，适合继续做深入 tracing 和 timeline 分析。",
            }.get(str(backend), "当前 backend 没有额外说明。")
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(backend))}</h3>"
                f"<div>样本数：{escape(str(count))}</div>"
                f"<div class='meta'>{escape(description)}</div>"
                "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _performance_backend_chart(self, summary: Mapping[str, Any]) -> str:
        backend_counts = dict(summary.get("backend_counts", {}) or {})
        if not backend_counts:
            return self._notice("当前还没有可统计的 backend 分布。")
        max_count = max(int(value or 0) for value in backend_counts.values()) or 1
        rows = []
        for backend, count in sorted(backend_counts.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
            value = int(count or 0)
            width = max(4, int(value / max_count * 100))
            rows.append(
                "<div class='performance-bar-row'>"
                f"<div class='performance-bar-label'>{escape(str(backend))}</div>"
                "<div class='performance-bar-track'>"
                f"<div class='performance-bar-fill' style='width:{width}%'></div>"
                "</div>"
                f"<div class='performance-bar-value'>{escape(str(value))}</div>"
                "</div>"
            )
        return "<div class='performance-chart-card'>" + "".join(rows) + "</div>"

    def _performance_chart_panel(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("最近没有可绘制的 monitoring snapshot。")
        metric_specs = [
            ("cpu_usage", "CPU", "%", "#0f766e"),
            ("memory_pss", "Memory PSS", "MB", "#d97706"),
            ("fps", "FPS", "", "#2563eb"),
            ("jank_frames", "Jank Frames", "", "#b91c1c"),
            ("jank_percent", "Jank", "%", "#dc2626"),
            ("frame_time_99p", "Frame P99", "ms", "#ea580c"),
            ("gpu_usage", "GPU", "%", "#0e7490"),
            ("gpu_p95_ms", "GPU P95", "ms", "#0891b2"),
            ("gpu_p99_ms", "GPU P99", "ms", "#155e75"),
            ("battery_level", "Battery", "%", "#7c3aed"),
            ("battery_temperature", "Battery Temp", "°C", "#9333ea"),
        ]
        charts = []
        for metric_key, label, unit, color in metric_specs:
            series = self._performance_metric_series(items, metric_key)
            if not series:
                continue
            charts.append(
                "<article class='performance-chart-card'>"
                f"<div class='performance-chart-head'><strong>{escape(label)}</strong><span>{escape(str(series[-1]['value']))}{escape(unit)}</span></div>"
                + self._performance_line_svg(series, color=color)
                + "<div class='performance-chart-axis'>"
                f"<span>{escape(str(series[0]['label']))}</span>"
                f"<span>{escape(str(series[-1]['label']))}</span>"
                "</div>"
                "</article>"
            )
        if not charts:
            return self._notice("最近样本里还没有 CPU / Memory / FPS / Battery 这类可绘制指标。")
        return "<div class='performance-chart-grid'>" + "".join(charts) + "</div>"

    def _performance_task_panels(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("最近没有可聚合的 monitoring snapshot。")
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            run_key = str(item.get("run_id", "") or "").strip()
            task_key = str(item.get("task_id", "") or item.get("task_name", "") or "unknown-task")
            key = f"{task_key}:{run_key}" if run_key else task_key
            groups.setdefault(key, []).append(item)
        panels = []
        for group_items in sorted(
            groups.values(),
            key=lambda values: str(values[0].get("captured_at", "") or values[0].get("run_created_at", "")),
            reverse=True,
        ):
            latest = group_items[0]
            task_name = str(latest.get("task_name", "") or "unknown task")
            task_id = str(latest.get("task_id", "") or "")
            run_id = str(latest.get("run_id", "") or "")
            package_name = str(latest.get("package_name", "") or "n/a")
            run_ids = {str(item.get("run_id", "") or "") for item in group_items if str(item.get("run_id", "") or "")}
            ordered_group_items = self._performance_entries_chronological(group_items)
            latest_metrics = self._performance_latest_non_empty_metrics(ordered_group_items)
            first_sample = str(ordered_group_items[0].get("captured_at", "") or "n/a") if ordered_group_items else "n/a"
            latest_sample = str(ordered_group_items[-1].get("captured_at", "") or "n/a") if ordered_group_items else "n/a"
            drawer_items = list(reversed(ordered_group_items))[:50]
            panels.append(
                "<details class='performance-task-panel performance-task-panel-compact'>"
                "<summary>"
                "<span>"
                f"<strong>{escape(task_name)}</strong>"
                f"<em>{escape(package_name)} / samples={len(group_items)} / run={escape(run_id or 'n/a')}</em>"
                "</span>"
                f"<b>{escape(str(latest.get('captured_at', 'n/a') or 'n/a'))}</b>"
                "</summary>"
                "<div class='performance-task-body performance-task-body-compact'>"
                f"<div class='meta'>task_id={escape(task_id or 'n/a')} / run_count={len(run_ids)} / window={escape(first_sample)} ~ {escape(latest_sample)} / max=24h / latest backend={escape(str(latest.get('backend', 'unknown') or 'unknown'))}</div>"
                + self._performance_metric_bars(latest_metrics)
                + "<h3>任务性能趋势图</h3>"
                + self._performance_chart_panel(group_items)
                + "<details class='performance-sample-drawer'>"
                f"<summary>查看具体性能数据（最近 {len(drawer_items)} 条，完整样本见 samples.json）</summary>"
                + self._performance_entry_cards(drawer_items)
                + "</details>"
                "</div>"
                "</details>"
            )
        return "<div class='performance-task-list'>" + "".join(panels) + "</div>"

    @classmethod
    def _performance_metric_series(cls, items: list[dict[str, Any]], metric_key: str) -> list[dict[str, Any]]:
        series: list[dict[str, Any]] = []
        for item in cls._performance_entries_chronological(items):
            metrics = dict(item.get("metrics", {}) or {})
            value = metrics.get(metric_key)
            if value in ("", None):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            label = str(item.get("captured_at", "") or item.get("run_created_at", "") or "sample")
            series.append({"value": round(number, 2), "label": label[-15:] if len(label) > 15 else label})
        return series

    @staticmethod
    def _performance_entries_chronological(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            items,
            key=lambda item: (
                str(item.get("captured_at", "") or item.get("run_created_at", "") or ""),
                int(item.get("sample_index", 0) or 0),
            ),
        )

    @classmethod
    def _performance_latest_non_empty_metrics(cls, items: list[dict[str, Any]]) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        for item in cls._performance_entries_chronological(items):
            for key, value in dict(item.get("metrics", {}) or {}).items():
                if value in ("", None):
                    continue
                metrics[str(key)] = value
        return metrics

    @staticmethod
    def _performance_line_svg(series: list[dict[str, Any]], *, color: str) -> str:
        if not series:
            return ""
        values = [float(item["value"]) for item in series]
        min_value = min(values)
        max_value = max(values)
        span = max(max_value - min_value, 1.0)
        width = 320
        height = 112
        step = width / max(len(values) - 1, 1)
        points = []
        circles = []
        for index, value in enumerate(values):
            x = round(index * step, 2)
            y = round(height - ((value - min_value) / span * (height - 20)) - 10, 2)
            points.append(f"{x},{y}")
            if len(values) <= 240:
                circles.append(f"<circle cx='{x}' cy='{y}' r='3.5'></circle>")
        area_points = " ".join([f"0,{height}", *points, f"{round((len(values)-1)*step, 2)},{height}"])
        return (
            f"<svg class='performance-line-chart' viewBox='0 0 {width} {height}' role='img' aria-label='性能趋势图'>"
            f"<polygon class='performance-line-area' points='{area_points}' style='fill:{escape(color)}'></polygon>"
            f"<polyline class='performance-line-path' points='{' '.join(points)}' style='stroke:{escape(color)}'></polyline>"
            f"<g class='performance-line-points' style='fill:{escape(color)}'>"
            + "".join(circles)
            + "</g>"
            "</svg>"
        )
    def _performance_entry_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("最近没有可聚合的 monitoring snapshot。")
        cards = []
        for item in items:
            metrics = dict(item.get("metrics", {}) or {})
            metric_bits = [
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
                    ("frames", metrics.get("frame_count")),
                    ("battery", metrics.get("battery_level")),
                    ("battery_temp", metrics.get("battery_temperature")),
                    ("power", metrics.get("power_usage")),
                    ("rx", metrics.get("rx_bytes")),
                    ("tx", metrics.get("tx_bytes")),
                    ("trace_bytes", metrics.get("perfetto_trace_size_bytes")),
                )
                if value not in ("", None)
            ]
            apps = ", ".join(item.get("app_packages", []) or []) or "n/a"
            metric_bars = self._performance_metric_bars(metrics)
            cards.append(
                "<article class='card stack performance-entry-card'>"
                f"<h3>{escape(str(item.get('task_name', '')) or 'unknown task')}</h3>"
                f"<div class='meta'>captured_at={escape(str(item.get('captured_at', 'n/a') or 'n/a'))} / device={escape(str(item.get('device_id', 'n/a') or 'n/a'))}</div>"
                f"<div>backend={escape(str(item.get('backend', 'unknown') or 'unknown'))} / run_status={escape(str(item.get('run_status', 'unknown') or 'unknown'))}</div>"
                f"<div>apps={escape(apps)}</div>"
                + (
                    f"<div>key metrics：{escape(' / '.join(metric_bits))}</div>"
                    if metric_bits
                    else "<div class='meta'>当前快照没有稳定可展示的 key metrics。</div>"
                )
                + metric_bars
                + self._artifact_links(
                    "样本跳转",
                    [
                        ("Snapshot JSON", item.get("snapshot_path", "")),
                        ("Trace", item.get("trace_path", "")),
                    ],
                )
                + "<div>"
                + self._route_link_new_tab("Run 详情", item.get("run_detail_path", ""))
                + (
                    " / " + self._route_link_new_tab("Run JSON", item.get("run_api_path", ""))
                    if item.get("run_api_path", "")
                    else ""
                )
                + "</div>"
                + "</article>"
            )
        return "<div class='cards performance-entry-grid'>" + "".join(cards) + "</div>"

    @staticmethod
    def _performance_metric_bars(metrics: Mapping[str, Any]) -> str:
        specs = [
            ("CPU", "cpu_usage", 100.0),
            ("System CPU", "system_cpu_usage", 100.0),
            ("Memory", "memory_pss", 1024.0),
            ("Java Heap", "memory_java", 512.0),
            ("Native Heap", "memory_native", 512.0),
            ("Graphics", "memory_graphics", 512.0),
            ("FPS", "fps", 120.0),
            ("Jank Frames", "jank_frames", 60.0),
            ("Jank", "jank_percent", 100.0),
            ("Frame P99", "frame_time_99p", 100.0),
            ("GPU", "gpu_usage", 100.0),
            ("GPU P95", "gpu_p95_ms", 50.0),
            ("GPU P99", "gpu_p99_ms", 50.0),
            ("GPU Temp", "gpu_temperature", 100.0),
            ("Battery", "battery_level", 100.0),
            ("Battery Temp", "battery_temperature", 60.0),
            ("Power", "power_usage", 5000.0),
            ("RX", "rx_bytes", 65536.0),
            ("TX", "tx_bytes", 65536.0),
            ("Frames", "frame_count", 5000.0),
            ("Trace", "perfetto_trace_size_bytes", 100_000_000.0),
        ]
        rows = []
        for label, key, max_value in specs:
            raw = metrics.get(key)
            if raw in ("", None):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            width = max(2, min(100, int(value / max_value * 100)))
            rows.append(
                "<div class='performance-mini-bar'>"
                f"<span>{escape(label)}</span>"
                f"<div><i style='width:{escape(str(width))}%'></i></div>"
                f"<b>{escape(str(round(value, 2)))}</b>"
                "</div>"
            )
        return "<div class='performance-mini-bars'>" + "".join(rows) + "</div>" if rows else ""



__all__ = ["PerformanceMetricsCardsMixin"]
