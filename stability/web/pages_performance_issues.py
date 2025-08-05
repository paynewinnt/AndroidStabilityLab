from __future__ import annotations

from stability.scenario.registry import get_scenario_definition

from .application_common import *


class ApplicationPerformanceIssuesPagesMixin:
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
                + self._route_link("任务详情", f"/tasks/task/{quote(task_id, safe='')}" if task_id else "")
                + (" / " + self._route_link("Task JSON", f"/api/tasks/task/{quote(task_id, safe='')}") if task_id else "")
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
                + self._route_link("Run 详情", item.get("detail_path", ""))
                + (" / " + self._route_link("Run JSON", item.get("api_path", "")) if item.get("api_path", "") else "")
                + "</div>"
                "</article>"
            )
        return "<div class='record-list-cards'>" + "".join(cards) + "</div>"

    @classmethod
    def _task_template_cell(cls, template_type: str) -> str:
        template = str(template_type or "").strip()
        if not template:
            return "n/a"
        try:
            definition = get_scenario_definition(template)
        except KeyError:
            return f"<span class='mono'>{escape(template)}</span>"
        return (
            f"<div><span class='mono'>{escape(template)}</span> - {escape(definition.chinese_name)}</div>"
            f"<div class='meta'>{escape(definition.description)}</div>"
        )

    @staticmethod
    def _display_datetime(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.replace("T", " ", 1)

    def _performance_home_summary_card(self, payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        entries = list(payload.get("entries", []) or [])
        if not entries:
            return self._notice("当前还没有最近性能采样。先跑一轮带 monitoring 的执行，再回来看首页摘要卡。")
        latest = dict(entries[0] or {})
        backend_counts = dict(summary.get("backend_counts", {}) or {})
        backend_summary = ", ".join(f"{key}={value}" for key, value in backend_counts.items()) or "n/a"
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>最近性能采样</h3>"
            f"<div>latest sample：{escape(str(latest.get('captured_at', 'n/a') or 'n/a'))}</div>"
            f"<div>task={escape(str(latest.get('task_name', 'n/a') or 'n/a'))} / device={escape(str(latest.get('device_id', 'n/a') or 'n/a'))}</div>"
            f"<div>backend summary：{escape(backend_summary)}</div>"
            f"<div>{escape(str(latest.get('summary_line', '') or ''))}</div>"
            + "<div>"
            + self._route_link("Performance 页", "/performance")
            + " / "
            + self._route_link("Run 详情", latest.get("run_detail_path", ""))
            + (
                " / " + self._inline_link("Snapshot JSON", latest.get("snapshot_path", ""))
                if latest.get("snapshot_path", "")
                else ""
            )
            + (
                " / " + self._inline_link("Trace", latest.get("trace_path", ""))
                if latest.get("trace_path", "")
                else ""
            )
            + "</div>"
            + "</article>"
            "</div>"
        )

    def _performance_sampling_guide(self) -> str:
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>采样入口</h3>"
            "<div class='meta'>这页本身不发起采样，只展示已经完成执行并写入 `monitoring/snapshot.json` 的结果。</div>"
            "<pre class='mono'>"
            + escape(
                "\n".join(
                    [
                        "./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend solox",
                        "./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend perfetto",
                    ]
                )
            )
            + "</pre>"
            "<div class='meta'>默认 backend 仍取自 config/monitoring.json；不覆盖时通常会落到 adb_collector。</div>"
            "</article>"
            "<article class='card stack'>"
            "<h3>采样产物</h3>"
            "<div>每个 execution instance 会优先落这两类文件：</div>"
            "<div><span class='mono'>monitoring/snapshot.json</span>：结构化指标快照</div>"
            "<div><span class='mono'>monitoring/*.perfetto-trace</span>：Perfetto trace 侧车产物</div>"
            "<div class='meta'>所以这里看到的是“执行后结果”，不是持续轮询中的实时曲线。</div>"
            "</article>"
            "</div>"
        )

    def _performance_onboarding_notice(self, summary: Mapping[str, Any]) -> str:
        backend_counts = dict(summary.get("backend_counts", {}) or {})
        sample_count = int(summary.get("sample_count", 0) or 0)
        if sample_count <= 0:
            return self._notice_with_actions(
                "当前还没有监控样本。先从任务大厅或 list-runs 找到一条 run_id，再用 execute-run 带上 monitoring backend 重跑一轮。",
                tone="warning",
                actions=[("任务大厅", "/tasks"), ("性能 JSON", "/api/performance")],
            )
        if backend_counts and set(backend_counts.keys()) == {"adb_collector"}:
            return self._notice_with_actions(
                "当前这批样本全部来自 adb_collector，所以这里只能看到基础快照。想验证 SoloX 或 Perfetto 是否接入成功，请用 --monitoring-backend solox/perfetto 再跑一轮。",
                tone="warning",
                actions=[("任务大厅", "/tasks"), ("性能 JSON", "/api/performance")],
            )
        return self._notice_with_actions(
            "这页已经收到了监控样本。建议先看 Backend 分布确认采样来源，再打开 Run 详情或 Trace 继续下钻。",
            actions=[("任务大厅", "/tasks"), ("性能 JSON", "/api/performance")],
        )

    def _performance_quickstart_cards(self, summary: Mapping[str, Any]) -> str:
        backend_counts = dict(summary.get("backend_counts", {}) or {})
        backend_hint = "当前页面还没有任何样本。"
        if backend_counts:
            backend_hint = "当前 backend 分布：" + " / ".join(
                f"{backend}={count}" for backend, count in sorted(backend_counts.items())
            )
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>1. 找到 Run</h3>"
            "<div>先从 <a href='/tasks'>任务大厅</a> 找一条最近的 Run，或者直接用 CLI 列表确认 run_id。</div>"
            "<pre class='mono'>"
            + escape("./.venv/bin/python -m stability.cli list-runs")
            + "</pre>"
            "<div class='meta'>"
            + escape(backend_hint)
            + "</div>"
            "</article>"
            "<article class='card stack'>"
            "<h3>2. 带后端重跑</h3>"
            "<div>选择你要验证的采样后端。SoloX 更像应用层一站式采样，Perfetto 更适合后续 trace 深挖。</div>"
            "<pre class='mono'>"
            + escape(
                "\n".join(
                    [
                        "./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend solox",
                        "./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend perfetto",
                    ]
                )
            )
            + "</pre>"
            "</article>"
            "<article class='card stack'>"
            "<h3>3. 回来分析</h3>"
            "<div>执行结束后先回这页看 backend 和 key metrics，再打开 Run 详情、Snapshot JSON、Trace 做下钻。</div>"
            "<div><a href='/performance'>性能采样</a> / <a href='/tasks'>任务大厅</a> / Run 详情</div>"
            "<div class='meta'>这页负责先确认“有没有采到、采到了什么”，不是最终诊断页。</div>"
            "</article>"
            "</div>"
        )

    def _performance_analysis_guide(self) -> str:
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>先看什么</h3>"
            "<div>1. 先看 backend 和 sample_count，确认这轮到底有没有采到。</div>"
            "<div>2. 再看 key metrics，只做快速分诊，不在这里下最终结论。</div>"
            "<div>3. 如果值得深挖，再打开 Run 详情、Snapshot JSON 或 Trace。</div>"
            "</article>"
            "<article class='card stack'>"
            "<h3>怎么下钻</h3>"
            "<div><a href='/tasks'>任务大厅</a>：先找哪条 Run 带了监控</div>"
            "<div><a href='/performance'>性能采样</a>：看最近样本的 backend 和关键指标</div>"
            "<div>Run 详情：看每个 instance 的 backend、apps、metrics、log、report</div>"
            "<div class='meta'>如果是 Perfetto，最终分析还是应该回到 trace 文件和 SQL/trace viewer，而不是只看这页摘要。</div>"
            "</article>"
            "<article class='card stack'>"
            "<h3>分析命令</h3>"
            "<div>如果你要做趋势对比或回归判断，建议回到 CLI 的分析链路。</div>"
            "<pre class='mono'>"
            + escape(
                "\n".join(
                    [
                        "./.venv/bin/python -m stability.cli compare-performance-trends --help",
                        "./.venv/bin/python -m stability.cli judge-regression --help",
                    ]
                )
            )
            + "</pre>"
            "<div class='meta'>Portal 先负责收口最近样本，趋势判断和准入仍以分析服务输出为准。</div>"
            "</article>"
            "</div>"
        )

    def _performance_scope_notice(self, *, summary: Mapping[str, Any], filters: Mapping[str, Any]) -> str:
        sample_count = int(summary.get("sample_count", 0) or 0)
        monitored_run_count = int(summary.get("monitored_run_count", 0) or 0)
        trace_count = int(summary.get("trace_count", 0) or 0)
        run_limit = int(filters.get("run_limit", 0) or 0)
        limit = int(filters.get("limit", 0) or 0)
        message = (
            f"当前页面只聚合最近 {run_limit} 条 run 里的前 {limit} 个监控样本。"
            f"目前识别到 sample={sample_count} / monitored_runs={monitored_run_count} / trace={trace_count}。"
        )
        return self._notice(
            message
            + " 如果你刚跑完一轮却没在这里看到，先确认该 run 是否真的写入了 monitoring 产物，再打开对应 Run 详情核对。",
            tone="warning" if sample_count == 0 else "info",
        )

    def _performance_risk_contract_card(self, fields: list[str]) -> str:
        field_text = " / ".join(fields) if fields else "threshold_source / matched_scope / threshold_detail"
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>Risk Item Detail</h3>"
            "<div>准入和规则评审里出现性能风险时，JSON 会尽量透出阈值来源、匹配范围和阈值明细；旧服务层没有这些字段时仍保持兼容。</div>"
            f"<div class='meta'>fields={escape(field_text)}</div>"
            "</article></div>"
        )

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
            ("jank_percent", "Jank", "%", "#dc2626"),
            ("gpu_p95_ms", "GPU P95", "ms", "#0891b2"),
            ("battery_level", "Battery", "%", "#7c3aed"),
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
            key = str(item.get("task_id", "") or item.get("task_name", "") or "unknown-task")
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
            package_name = str(latest.get("package_name", "") or "n/a")
            run_ids = {str(item.get("run_id", "") or "") for item in group_items if str(item.get("run_id", "") or "")}
            latest_metrics = dict(latest.get("metrics", {}) or {})
            panels.append(
                "<details class='performance-task-panel performance-task-panel-compact'>"
                "<summary>"
                "<span>"
                f"<strong>{escape(task_name)}</strong>"
                f"<em>{escape(package_name)} / samples={len(group_items)} / runs={len(run_ids)}</em>"
                "</span>"
                f"<b>{escape(str(latest.get('captured_at', 'n/a') or 'n/a'))}</b>"
                "</summary>"
                "<div class='performance-task-body performance-task-body-compact'>"
                f"<div class='meta'>task_id={escape(task_id or 'n/a')} / latest backend={escape(str(latest.get('backend', 'unknown') or 'unknown'))}</div>"
                + self._performance_metric_bars(latest_metrics)
                + "<h3>任务性能趋势图</h3>"
                + self._performance_chart_panel(group_items)
                + "<details class='performance-sample-drawer'>"
                "<summary>查看具体性能数据（最近监控快照）</summary>"
                + self._performance_entry_cards(group_items)
                + "</details>"
                "</div>"
                "</details>"
            )
        return "<div class='performance-task-list'>" + "".join(panels) + "</div>"

    @staticmethod
    def _performance_metric_series(items: list[dict[str, Any]], metric_key: str) -> list[dict[str, Any]]:
        series: list[dict[str, Any]] = []
        for item in reversed(items[:12]):
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
                    ("mem_pss", metrics.get("memory_pss")),
                    ("fps", metrics.get("fps")),
                    ("gpu", metrics.get("gpu_usage")),
                    ("gpu_p95_ms", metrics.get("gpu_p95_ms")),
                    ("jank", metrics.get("jank_percent")),
                    ("battery", metrics.get("battery_level")),
                    ("power", metrics.get("power_usage")),
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
                    ("mem_pss", metrics.get("memory_pss")),
                    ("fps", metrics.get("fps")),
                    ("gpu", metrics.get("gpu_usage")),
                    ("gpu_p95_ms", metrics.get("gpu_p95_ms")),
                    ("gpu_p99_ms", metrics.get("gpu_p99_ms")),
                    ("jank", metrics.get("jank_percent")),
                    ("jank_frames", metrics.get("jank_frames")),
                    ("frames", metrics.get("frame_count")),
                    ("battery", metrics.get("battery_level")),
                    ("power", metrics.get("power_usage")),
                    ("rx", metrics.get("rx_bytes")),
                    ("tx", metrics.get("tx_bytes")),
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
                + self._route_link("Run 详情", item.get("run_detail_path", ""))
                + (" / " + self._route_link("Run JSON", item.get("run_api_path", "")) if item.get("run_api_path", "") else "")
                + "</div>"
                + "</article>"
            )
        return "<div class='cards performance-entry-grid'>" + "".join(cards) + "</div>"

    @staticmethod
    def _performance_metric_bars(metrics: Mapping[str, Any]) -> str:
        specs = [
            ("CPU", "cpu_usage", 100.0),
            ("Memory", "memory_pss", 1024.0),
            ("FPS", "fps", 120.0),
            ("Jank", "jank_percent", 100.0),
            ("GPU P95", "gpu_p95_ms", 50.0),
            ("GPU P99", "gpu_p99_ms", 50.0),
            ("Battery", "battery_level", 100.0),
            ("Power", "power_usage", 5000.0),
            ("RX", "rx_bytes", 65536.0),
            ("TX", "tx_bytes", 65536.0),
            ("Frames", "frame_count", 5000.0),
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

    def _issue_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有聚合问题。")
        cards = []
        for item in items:
            chips = "".join(
                f"<span class='pill'>{escape(str(chip))}</span>"
                for chip in (
                    item.get("issue_type", ""),
                    item.get("severity", ""),
                    f"occ:{item.get('occurrence_count', 0)}",
                    f"dev:{item.get('affected_device_count', 0)}",
                )
                if chip
            )
            cards.append(
                "<article class='card stack'>"
                + f"<h3>{escape(str(item.get('title', '')))}</h3>"
                + f"<div>{chips}</div>"
                + f"<div class='mono'>{escape(str(item.get('fingerprint', '')))}</div>"
                + f"<div>协作状态：{self._status_pill(str(item.get('workflow_state', 'new') or 'new'), tone=self._workflow_state_tone(str(item.get('workflow_state', 'new') or 'new')))}</div>"
                + f"<div>责任人：{escape(str(item.get('assignee_display_name', '') or item.get('assignee_id', '') or 'unassigned'))}</div>"
                + f"<div>评论：{escape(str(item.get('comment_count', 0) or 0))}</div>"
                + f"<div>缺陷：{escape(str(item.get('defect_link_count', 0) or 0))} / 可关闭={escape('yes' if item.get('has_acceptable_defect') else 'no')}</div>"
                + self._issue_evidence_summary(item)
                + self._issue_attribution_summary(item)
                + (
                    f"<div class='meta'>最新评论：{escape(str(item.get('latest_comment_by', '') or ''))} / {escape(str(item.get('latest_comment_body', '') or ''))}</div>"
                    if str(item.get("latest_comment_body", "") or "").strip()
                    else ""
                )
                + self._issue_defect_cards(list(item.get("defect_links", []) or []))
                + f"<div class='meta'>最近出现：{escape(str(item.get('last_seen_at', '')))}</div>"
                + f"<div>场景：{escape(', '.join(item.get('affected_scenarios', [])[:3]))}</div>"
                + f"<div>包名：{escape(', '.join(item.get('affected_packages', [])[:3]))}</div>"
                + self._issue_assign_form(item)
                + self._issue_transition_form(item)
                + self._issue_comment_form(item)
                + self._issue_create_defect_form(item)
                + self._issue_sync_defect_form(item)
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _issue_evidence_summary(self, item: Mapping[str, Any]) -> str:
        evidence_signals = item.get("evidence_signals", None)
        confirmation_level = str(item.get("confirmation_level", "") or "")
        if not evidence_signals and not confirmation_level:
            return ""
        if isinstance(evidence_signals, Mapping):
            evidence_text = json.dumps(dict(evidence_signals), ensure_ascii=False, sort_keys=True)
        elif isinstance(evidence_signals, (list, tuple)):
            evidence_text = ", ".join(str(value) for value in evidence_signals)
        else:
            evidence_text = str(evidence_signals or "n/a")
        return (
            "<div class='meta'>高级异常证据："
            f"confirmation_level={escape(confirmation_level or 'n/a')} / "
            f"evidence_signals={escape(evidence_text or 'n/a')}"
            "</div>"
        )

    def _issue_attribution_summary(self, item: Mapping[str, Any]) -> str:
        attribution = dict(item.get("attribution", {}) or {})
        if not attribution:
            return ""
        direction = str(attribution.get("direction_label", "") or attribution.get("direction", "") or "")
        confidence = str(attribution.get("confidence_score", "") or attribution.get("confidence", "") or "")
        matched_rule_ids = attribution.get("matched_rule_ids", None) or attribution.get("matched_rule_id", "")
        rows = [
            f"方向={escape(direction or 'n/a')}",
            f"置信度={escape(confidence or 'n/a')}",
            f"命中规则={escape(self._compact_value_text(matched_rule_ids) or 'n/a')}",
        ]
        evidence_text = self._compact_value_text(attribution.get("evidence_summary", ""))
        if evidence_text:
            rows.append(f"证据摘要={escape(evidence_text)}")
        next_steps_text = self._compact_value_text(attribution.get("recommended_next_steps", ""))
        if next_steps_text:
            rows.append(f"建议动作={escape(next_steps_text)}")
        review_notes_text = self._compact_value_text(attribution.get("review_notes", ""))
        if review_notes_text:
            rows.append(f"Review Notes={escape(review_notes_text)}")
        return "<div class='meta'>初步归因建议：" + " / ".join(rows) + "</div>"

    @staticmethod
    def _compact_value_text(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, Mapping):
            return json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value if str(item))
        return str(value)

    def _issue_assign_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        return (
            "<details><summary>认领 / 转派</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/assign', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>责任人<input type='text' name='assignee_id' value='developer' placeholder='developer' /></label>"
            "<div><button type='submit'>提交认领</button></div>"
            "</form></details>"
        )

    def _issue_transition_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current = str(item.get("workflow_state", "") or "new")
        current_actor = dict(item.get("current_actor", {}) or {})
        options = "".join(
            f"<option value='{escape(state, quote=True)}'{' selected' if state == current else ''}>{escape(state)}</option>"
            for state in ("new", "assigned", "processing", "confirmed", "resolved", "ignored")
        )
        return (
            "<details><summary>状态流转</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/transition', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            f"<label>目标状态<select name='workflow_state'>{options}</select></label>"
            "<label>原因<input type='text' name='reason' value='' placeholder='例如 已确认并转研发处理' /></label>"
            "<div><button type='submit'>更新状态</button></div>"
            "</form></details>"
        )

    def _issue_comment_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        return (
            "<details><summary>评论讨论</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/comment', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>评论<textarea name='body' rows='3' placeholder='记录复现、风险说明或处理结论'></textarea></label>"
            "<div><button type='submit'>提交评论</button></div>"
            "</form></details>"
        )

    def _issue_create_defect_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        default_title = str(item.get("title", "") or "")
        return (
            "<details><summary>创建缺陷请求</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/create-defect', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>系统标识<input type='text' name='system_key' value='defect_system' placeholder='例如 jira / zentao' /></label>"
            f"<label>标题<input type='text' name='title' value='{escape(default_title, quote=True)}' placeholder='缺陷标题' /></label>"
            "<label>责任团队<input type='text' name='team_key' value='' placeholder='可选，例如 client_android' /></label>"
            "<label>描述<textarea name='description' rows='3' placeholder='补充复现、影响范围、证据路径'></textarea></label>"
            "<div><button type='submit'>创建缺陷请求</button></div>"
            "</form></details>"
        )

    def _issue_sync_defect_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        latest_link = dict((list(item.get("defect_links", []) or []) or [{}])[-1] or {})
        return (
            "<details><summary>同步缺陷状态</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/sync-defect', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            f"<label>Link ID<input type='text' name='link_id' value='{escape(str(latest_link.get('link_id', '') or ''), quote=True)}' placeholder='优先使用 link_id' /></label>"
            f"<label>系统标识<input type='text' name='system_key' value='{escape(str(latest_link.get('system_key', '') or ''), quote=True)}' placeholder='例如 jira / zentao' /></label>"
            f"<label>缺陷单号<input type='text' name='defect_id' value='{escape(str(latest_link.get('defect_id', '') or ''), quote=True)}' placeholder='例如 AND-1234' /></label>"
            f"<label>状态<input type='text' name='status' value='{escape(str(latest_link.get('status', '') or ''), quote=True)}' placeholder='例如 fixed / verified / waived' /></label>"
            f"<label>链接<input type='text' name='url' value='{escape(str(latest_link.get('url', '') or ''), quote=True)}' placeholder='https://example.invalid/ticket/1234' /></label>"
            "<label>允许关闭<select name='acceptable_for_close'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div><button type='submit'>同步缺陷状态</button></div>"
            "</form></details>"
        )

    def _issue_defect_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "<div class='meta'>当前还没有关联缺陷。</div>"
        cards = []
        for item in items:
            cards.append(
                "<details><summary>缺陷联动</summary><article class='card stack'>"
                f"<div><span class='pill'>{escape(str(item.get('system_key', '') or 'defect_system'))}</span>"
                f" <span class='pill'>{escape(str(item.get('status', '') or 'pending'))}</span>"
                + (f" <span class='pill'>acceptable</span>" if item.get("acceptable_for_close") else "")
                + "</div>"
                f"<div>defect_id={escape(str(item.get('defect_id', '') or 'pending_create'))}</div>"
                f"<div>title={escape(str(item.get('title', '') or 'n/a'))}</div>"
                f"<div>sync_status={escape(str(item.get('sync_status', '') or 'n/a'))}</div>"
                + (
                    f"<div><a href='{escape(str(item.get('url', '') or ''), quote=True)}'>打开外部缺陷</a></div>"
                    if str(item.get("url", "") or "").strip()
                    else ""
                )
                + "</article></details>"
            )
        return "".join(cards)
