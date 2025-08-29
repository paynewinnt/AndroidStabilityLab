from __future__ import annotations

from html import escape
from typing import Any, Mapping


class PerformanceHomeHelpMixin:
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
        window_hours = int(filters.get("window_hours", 24) or 24)
        message = (
            f"当前页面聚合最近 {run_limit} 条 run；每条 run 的趋势图展示采样窗口内的全部样本，单条 run 最多 {window_hours} 小时。"
            f"目前识别到 sample={sample_count} / monitored_runs={monitored_run_count} / trace={trace_count}。"
        )
        return self._notice(
            message
            + " 明细卡片默认只折叠展示最近 50 条，完整样本以 run 目录里的 samples.json 为准；如果刚跑完一轮却没看到，先确认该 run 是否写入了 monitoring 产物。",
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


__all__ = ["PerformanceHomeHelpMixin"]
