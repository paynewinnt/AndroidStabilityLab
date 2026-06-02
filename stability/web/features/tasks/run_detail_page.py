from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote


class TasksRunDetailPageMixin:
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
