from __future__ import annotations

from .application_common import *
from .pages_admission_detail import ApplicationAdmissionDetailPagesMixin


class ApplicationRecordPagesMixin(ApplicationAdmissionDetailPagesMixin):
    def _render_tasks(self, payload: dict[str, Any]) -> str:
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        body.extend([
            self._metric_grid(
                [
                    ("任务数", payload["summary"]["task_count"]),
                    ("最近 Run 数", payload["summary"]["run_count"]),
                    ("失败 Run", payload["summary"]["run_status_counts"].get("failed", 0)),
                    ("成功 Run", payload["summary"]["run_status_counts"].get("success", 0)),
                    ("有监控 Run", payload["summary"].get("monitored_run_count", 0)),
                    ("带 Trace Run", payload["summary"].get("trace_run_count", 0)),
                ]
            ),
            self._workflow_nav_bar(active="tasks"),
            self._section(
                "操作入口",
                [self._task_operation_launcher(payload)],
            ),
            self._section(
                "任务与执行",
                [
                    "<div class='task-list-split'>"
                    "<article class='task-list-panel'>"
                    "<div class='task-list-panel-head'><h3>任务定义</h3><span>查看已有 Task，进入详情后可继续创建 Run。</span></div>"
                    + self._task_table(payload["tasks"], current_actor=dict(payload.get("current_actor", {}) or {}))
                    + "</article>"
                    "<article class='task-list-panel'>"
                    "<div class='task-list-panel-head'><h3>最近执行</h3><span>查看 Run 状态、监控摘要和详情入口。</span></div>"
                    + self._run_table(payload["runs"])
                    + "</article>"
                    "</div>"
                ],
            ),
        ])
        if payload.get("device_sync"):
            body.insert(1, self._notice(self._sync_hint(payload["device_sync"])))
        return self._layout(
            "任务大厅",
            "任务定义、执行状态和最近运行记录放在一页里，先把“跑了什么、跑成什么样”可视化。",
            "".join(body),
        )

    def _render_run_detail(self, payload: dict[str, Any]) -> str:
        run = dict(payload.get("run", {}) or {})
        task = dict(run.get("task", {}) or {})
        monitoring_summary = dict(run.get("monitoring_summary", {}) or {})
        task_id = str(run.get("task_id", "") or "")
        run_id = str(run.get("run_id", "") or "")
        run_path = f"/runs/{quote(str(run.get('run_id', '') or ''), safe='')}" if run.get("run_id") else "/tasks"
        body = [
            self._run_detail_compact_summary(run, task, monitoring_summary),
            self._workflow_nav_bar(
                active="run",
                task_path=f"/tasks/task/{quote(task_id, safe='')}" if task_id else "/tasks",
                run_path=run_path,
                artifact_path=f"/artifacts/run/{quote(run_id, safe='')}" if run_id else "",
                artifact_items=self._run_detail_artifact_items(run),
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
                    f"<p>{self._route_link('Run JSON', run.get('api_path', ''))}</p>",
                    self._notice(
                        str(monitoring_summary.get("summary_line", "") or "当前这条 Run 还没有可展示的监控快照。"),
                        tone="ok" if monitoring_summary.get("sample_count", 0) else "warning",
                    ),
                ],
            ),
            self._section("Execution Instances", [self._run_instance_monitoring_cards(list(run.get("instances", []) or []))]),
        ]
        return self._layout(
            "Run 详情",
            "这里把一条 Run 的执行实例、监控 backend、关键指标和 trace 入口一起摊开，方便从任务大厅继续下钻。",
            "".join(body),
        )

    def _render_performance(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        entries = list(payload.get("entries", []) or [])
        help_buttons, help_sections = self._page_help_sections("性能采样", summary=summary)
        body = [
            self._workflow_nav_bar(
                active="performance",
                run_path=str((entries[0] or {}).get("run_detail_path", "") or "/tasks") if entries else "/tasks",
                artifact_path=self._performance_artifact_path(entries[0] if entries else {}),
                artifact_items=self._performance_artifact_items(entries[0] if entries else {}),
            ),
            self._performance_compact_header(
                summary=summary,
                filters=filters,
                risk_detail_fields=list(payload.get("risk_detail_fields", []) or []),
            ),
            self._section("任务性能趋势", [self._performance_task_panels(entries)]),
            self._section(
                "Backend 分布图",
                [
                    self._performance_backend_chart(summary),
                ],
            ),
        ]
        return self._layout(
            "性能采样",
            "这页不是实时仪表盘，而是把最近执行实例已经落盘的 monitoring snapshot 收口起来，方便先判断有没有采到、采到了什么、值不值得继续下钻。",
            "".join(body),
            help_buttons=help_buttons,
            help_modal_sections=help_sections,
        )

    def _workflow_nav_bar(
        self,
        *,
        active: str,
        task_path: str = "/tasks",
        run_path: str = "/tasks",
        performance_path: str = "/performance",
        artifact_path: str = "",
        artifact_items: Sequence[tuple[str, Any]] | None = None,
    ) -> str:
        fallback_label, fallback_path = self._first_workflow_artifact(artifact_items or [])
        resolved_artifact_path = str(artifact_path or fallback_path or "").strip()
        artifact_label = "统一产物页" if artifact_path else fallback_label
        steps = [
            ("tasks", "任务", task_path, "定义目标、模板和设备"),
            ("run", "Run", run_path, "创建批次并执行"),
            ("performance", "性能", performance_path, "查看采样和趋势"),
            ("artifact", "产物", resolved_artifact_path or "/json-api", artifact_label or "报告 / Trace / JSON"),
        ]
        rendered = []
        for key, label, path, hint in steps:
            class_name = "workflow-step"
            if key == active:
                class_name += " active"
            if key == "artifact" and not resolved_artifact_path:
                class_name += " muted"
            rendered.append(
                f"<a class='{class_name}' href='{escape(str(path or '#'), quote=True)}'>"
                f"<strong>{escape(label)}</strong>"
                f"<span>{escape(str(hint))}</span>"
                "</a>"
            )
        return (
            "<nav class='workflow-nav-bar' aria-label='任务到产物操作链路'>"
            "<div class='workflow-nav-title'>任务 -> Run -> 性能 -> 产物</div>"
            "<div class='workflow-nav-steps'>"
            + "".join(rendered)
            + "</div>"
            "</nav>"
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

    @staticmethod
    def _performance_artifact_items(entry: Mapping[str, Any]) -> list[tuple[str, Any]]:
        return [
            ("Snapshot JSON", entry.get("snapshot_path", "")),
            ("Trace", entry.get("trace_path", "")),
            ("Run JSON", entry.get("run_api_path", "")),
        ]

    @staticmethod
    def _performance_artifact_path(entry: Mapping[str, Any]) -> str:
        run_id = str(entry.get("run_id", "") or "").strip()
        return f"/artifacts/run/{quote(run_id, safe='')}" if run_id else ""

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
            trace_path = str(monitor.get("trace_path", "") or item.get("monitoring_trace_path", "") or "")
            if trace_path:
                traces.append({"instance_id": instance_id, "device_id": device_id, "trace_path": trace_path})
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
                "report_count": sum(1 for item in reports if item.get("markdown_path") or item.get("html_path")),
                "trace_count": len(traces),
                "monitoring_snapshot_count": sum(1 for item in monitoring if item.get("snapshot_path")),
                "issue_count": int(dict(run.get("summary", {}) or {}).get("total_issues", 0) or sum(int(item.get("issue_count", 0) or 0) for item in issues)),
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
            self._run_artifact_summary(artifacts),
            self._workflow_nav_bar(
                active="artifact",
                task_path=f"/tasks/task/{quote(task_id, safe='')}" if task_id else "/tasks",
                run_path=f"/runs/{quote(run_id, safe='')}" if run_id else "/tasks",
                artifact_path=f"/artifacts/run/{quote(run_id, safe='')}" if run_id else "",
            ),
            self._section("Report", [self._run_artifact_report_cards(list(artifacts.get("reports", []) or []))]),
            self._section("Trace", [self._run_artifact_trace_cards(list(artifacts.get("traces", []) or []))]),
            self._section(
                "Monitoring Snapshot",
                [self._run_artifact_monitoring_cards(list(artifacts.get("monitoring", []) or []))],
            ),
            self._section("Issue Summary", [self._run_artifact_issue_cards(list(artifacts.get("issues", []) or []), run)]),
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
                links = self._notice("当前实例没有落盘 report 或执行日志。", tone="warning")
            cards.append(
                "<article class='card stack run-artifact-card'>"
                f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
                f"<div class='meta'>device={escape(str(item.get('device_id', '') or 'n/a'))}</div>"
                + links
                + "</article>"
            )
        return "<div class='cards run-artifact-grid'>" + "".join(cards) + "</div>" if cards else self._notice("当前 Run 没有 report 产物。", tone="warning")

    def _run_artifact_trace_cards(self, traces: Sequence[Mapping[str, Any]]) -> str:
        if not traces:
            return self._notice("当前 Run 没有 trace 产物。default/SoloX 后端通常没有 Perfetto trace；需要 trace 时使用 perfetto backend。", tone="warning")
        return "<div class='cards run-artifact-grid'>" + "".join(
            "<article class='card stack run-artifact-card'>"
            f"<h3>{escape(str(item.get('instance_id', '') or 'instance'))}</h3>"
            f"<div class='meta'>device={escape(str(item.get('device_id', '') or 'n/a'))}</div>"
            + self._artifact_links("Trace 文件", [("Perfetto Trace", item.get("trace_path", ""))])
            + "</article>"
            for item in traces
        ) + "</div>"

    def _run_artifact_monitoring_cards(self, monitoring_items: Sequence[Mapping[str, Any]]) -> str:
        cards = []
        for item in monitoring_items:
            metrics = dict(item.get("metrics", {}) or {})
            metric_line = ", ".join(f"{key}={value}" for key, value in metrics.items()) or "暂无关键指标"
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
        return "<div class='cards run-artifact-grid'>" + "".join(cards) + "</div>" if cards else self._notice("当前 Run 没有 monitoring snapshot。", tone="warning")

    @staticmethod
    def _run_artifact_issue_cards(issues: Sequence[Mapping[str, Any]], run: Mapping[str, Any]) -> str:
        if not issues:
            total = int(dict(run.get("summary", {}) or {}).get("total_issues", 0) or 0)
            if total <= 0:
                return "<div class='notice ok'>当前 Run 未记录 issue。</div>"
        cards = []
        for item in issues:
            highlights = ", ".join(str(value) for value in list(item.get("highlights", []) or [])) or "无高亮信号"
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
                + (f"<p>{escape(str(item.get('note', '') or ''))}</p>" if item.get("note") else "")
                + "</article>"
            )
        return "<div class='cards run-artifact-grid'>" + "".join(cards) + "</div>" if cards else "<div class='notice ok'>当前 Run 未记录 issue。</div>"

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

    @staticmethod
    def _run_detail_compact_summary(
        run: Mapping[str, Any], task: Mapping[str, Any], monitoring_summary: Mapping[str, Any]
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
            "<div class='runner-summary-row run-detail-summary-row'>"
            + chips
            + "</div>"
            "</section>"
        )

    def _render_json_api_index(self, payload: dict[str, Any]) -> str:
        api_endpoints = list(payload.get("api_endpoints", []) or [])
        body = [
            self._notice(
                "接口中心先给你展示可读入口，点进后可以查看原始数据，不会再直接弹出一大串 JSON。",
                tone="info",
            ),
            self._metric_grid(
                [
                    ("接口数", len(api_endpoints)),
                    ("页面入口", 9),
                    ("详情接口", 6),
                    ("健康检查", 1),
                ]
            ),
            self._section("常用接口", [self._json_api_cards(api_endpoints)]),
            self._section("怎么用", [self._json_api_usage_cards()]),
        ]
        return self._layout(
            "JSON API",
            "这里不直接渲染原始 JSON，而是把当前可用接口整理成导航页，方便从浏览器继续下钻。",
            "".join(body),
        )

    def _render_issues(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        body.extend([
            self._metric_grid(
                [
                    ("聚合问题数", summary["issue_count"]),
                    ("Critical", summary["severity_counts"].get("critical", 0)),
                    ("High", summary["severity_counts"].get("high", 0)),
                    ("Crash 类", summary["issue_type_counts"].get("crash", 0)),
                    ("处理中", summary["state_counts"].get("processing", 0)),
                    ("已解决", summary["state_counts"].get("resolved", 0)),
                    ("协作参与者", summary["actor_count"]),
                ]
            ),
            self._section(
                "当前身份",
                [
                    self._current_actor_card(
                        current_actor=dict(payload.get("current_actor", {}) or {}),
                        actors=list(payload.get("actors", []) or []),
                        current_path="/issues",
                    )
                ],
            ),
            self._section("Top Issue", [self._issue_cards(payload["issues"])]),
        ])
        return self._layout(
            "问题中心",
            "先看影响面最大的聚合问题，也可以直接完成认领、评论和状态流转。",
            "".join(body),
        )

    def _render_goldens(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        filters = payload.get("filters", {})
        filter_bits = [
            f"suite={payload.get('suite_version', '') or 'n/a'}",
            f"issue_type={filters.get('issue_type', '') or 'all'}",
            f"layer={filters.get('layer', '') or 'all'}",
            f"expectation={filters.get('expectation', '') or 'all'}",
            f"limit={filters.get('limit', 0)}",
        ]
        body = [
            self._metric_grid(
                [
                    ("Case 总数", summary["case_count"]),
                    ("Layer 数", summary["layer_count"]),
                    ("Issue Type 数", summary["issue_type_count"]),
                    ("Expectation 数", summary["expectation_count"]),
                ]
            ),
            self._section(
                "Suite 概览",
                [
                    f"<p>suite_path：<span class='mono'>{escape(str(payload.get('suite_path', '')))}</span></p>",
                    f"<p>{escape(' / '.join(filter_bits))}</p>",
                    "<p><a href='/goldens/diff'>打开 Golden Suite Diff 只读页</a></p>",
                    "<details class='compact-details'><summary>查看统计 JSON</summary><pre class='mono compact-pre'>"
                    + escape(
                        json.dumps(
                            {
                                "layer_counts": summary.get("layer_counts", {}),
                                "issue_type_counts": summary.get("issue_type_counts", {}),
                                "expectation_counts": summary.get("expectation_counts", {}),
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    + "</pre></details>",
                ],
            ),
            self._section("Golden Cases", [self._golden_case_cards(list(payload.get("cases", []) or []))]),
        ]
        return self._layout(
            "Golden Suite",
            "这里用只读方式查看正式样本库，先看有哪些 case，再按单条样本下钻到完整 payload。",
            "".join(body),
        )

    def _render_golden_diff(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        change_counts = dict(summary.get("change_counts", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("Diff 数", summary.get("diff_count", 0)),
                    ("Modified", change_counts.get("modified", 0)),
                    ("Added", change_counts.get("added", 0)),
                    ("Removed", change_counts.get("removed", 0)),
                    ("Unchanged", change_counts.get("unchanged", 0)),
                ]
            ),
            self._section(
                "Diff 过滤",
                [self._golden_diff_filter_bar(payload=payload)],
            ),
            self._section(
                "Diff Scope",
                [
                    f"<p>left_path：<span class='mono'>{escape(str(payload.get('left_path', '')))}</span></p>",
                    f"<p>right_path：<span class='mono'>{escape(str(payload.get('right_path', '')) or 'n/a')}</span></p>",
                    f"<p>left_version：{escape(str(payload.get('left_suite_version', '') or 'n/a'))} / right_version：{escape(str(payload.get('right_suite_version', '') or 'n/a'))}</p>",
                    f"<p>当前筛选：{escape(str(summary.get('diff_count', 0)))} / {escape(str(summary.get('total_diff_count', 0)))} 条；change_type={escape(str(filters.get('change_type', '') or 'all'))}；changed_field={escape(str(filters.get('changed_field', '') or 'all'))}；case_query={escape(str(filters.get('case_query', '') or 'n/a'))}</p>",
                    "<pre class='mono'>"
                    + escape(json.dumps(filters, ensure_ascii=False, indent=2))
                    + "</pre>",
                ],
            ),
        ]
        if not bool(payload.get("comparison_ready", False)):
            body.append(
                self._section(
                    "如何使用",
                    [
                        self._notice(str(dict(payload.get("help", {}) or {}).get("message", ""))),
                        "<pre class='mono'>"
                        + escape(str(dict(payload.get("help", {}) or {}).get("example", "")))
                        + "</pre>",
                    ],
                )
            )
        else:
            body.append(
                self._section(
                    "Changed Cases",
                    [self._golden_diff_cards(list(payload.get("entries", []) or []))],
                )
            )
        return self._layout(
            "Golden Suite Diff",
            "这里用只读方式对比两份 golden suite，直接看新增、删除、修改和字段级变化。",
            "".join(body),
        )

    def _render_admission(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        views = dict(payload.get("views", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("基线数", summary["baseline_count"]),
                    ("自动 Fail", summary["auto_decision_counts"].get("fail", 0)),
                    ("最终 Fail", summary["final_decision_counts"].get("fail", 0)),
                    ("人工覆盖", summary["override_count"]),
                    ("风险基线", summary["risk_baseline_count"]),
                    ("性能风险基线", summary["performance_risk_baseline_count"]),
                    ("覆盖不足基线", summary["coverage_gap_baseline_count"]),
                    ("Golden 基线", summary["golden_suite_baseline_count"]),
                    ("Golden 失败基线", summary["golden_suite_failed_baseline_count"]),
                    ("Golden 失败 Case", summary["golden_suite_failed_case_count_total"]),
                    ("Promote 记录", summary["action_counts"].get("promote", 0)),
                    ("Rollback 记录", summary["action_counts"].get("rollback", 0)),
                    ("Set 记录", summary["action_counts"].get("set", 0)),
                ]
            ),
            self._section(
                "当前身份",
                [
                    self._current_actor_card(
                        current_actor=dict(payload.get("current_actor", {}) or {}),
                        actors=list(payload.get("actors", []) or []),
                        current_path="/admission",
                    )
                ],
            ),
            self._section(
                "协作视图",
                [self._admission_view_cards(views)],
            ),
            self._section("质量门禁与准入 Case", [self._baseline_cards(payload["baselines"])]),
        ]
        return self._layout(
            "准入中心",
            "这里先看准入单协作视图和质量门禁结果，再继续下钻到当前报告、latest audit 和基线历史。",
            "".join(body),
        )

    def _render_golden_case_detail(self, payload: dict[str, Any]) -> str:
        summary = dict(payload["summary"])
        body = [
            self._metric_grid(
                [
                    ("Issue 数", summary.get("issue_count", 0)),
                    ("Layer", summary.get("layer", "")),
                    ("Expectation", summary.get("expectation", "")),
                    ("Include Unchanged", "yes" if summary.get("include_unchanged") else "no"),
                ]
            ),
            self._section(
                "Case Summary",
                [
                    (
                        "<div class='cards'><article class='card stack'>"
                        f"<h3>{escape(str(summary.get('case_id', '')))}</h3>"
                        f"<div class='meta'>{escape(str(summary.get('description', '')))}</div>"
                        f"<div><span class='pill'>{escape(str(summary.get('issue_type', '')))}</span>"
                        f"<span class='pill'>{escape(str(summary.get('layer', '')))}</span>"
                        f"<span class='pill'>{escape(str(summary.get('expectation', '')))}</span></div>"
                        f"<div>package：{escape(str(summary.get('package_name', '') or 'n/a'))}</div>"
                        f"<div>template：{escape(str(summary.get('template_type', '') or 'n/a'))}</div>"
                        f"<div>source_run：<span class='mono'>{escape(str(summary.get('source_run_id', '') or 'n/a'))}</span></div>"
                        f"<div><a href='/goldens'>返回 Golden Suite</a></div>"
                        "</article></div>"
                    )
                ],
            ),
            self._section(
                "Expected",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("expected", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-expected",
            ),
            self._section(
                "Baseline Rules",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("baseline_rules", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-baseline-rules",
            ),
            self._section(
                "Candidate Rules",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("candidate_rules", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-candidate-rules",
            ),
            self._section(
                "Filters",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("filters", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-filters",
            ),
            self._section(
                "Dataset",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("dataset", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-dataset",
            ),
            self._section(
                "Draft Metadata",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("draft_metadata", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-draft-metadata",
            ),
        ]
        return self._layout(
            f"Golden Case · {summary.get('case_id', '')}",
            "单条黄金样本会把 summary、expected、rules、filters 和 dataset 一次性展开，方便直接检查样本定义。",
            "".join(body),
        )

    def _render_not_found(self, route: str) -> str:
        return self._layout(
            "页面不存在",
            "这个路径目前还没有接进 Web 主入口。",
            self._notice(f"未找到页面：{escape(route)}"),
        )
