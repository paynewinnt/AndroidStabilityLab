from __future__ import annotations

from stability.scenario.registry import (
    METRIC_REGISTRY,
    default_metric_template_scopes,
    get_param_sections_for_web,
    get_scenario_definition,
    get_template_form_schema,
    list_scenario_definitions,
    metric_template_scopes,
)
from stability.time_utils import now_beijing_string

from ...application_common import *


def _generated_at_now() -> str:
    return now_beijing_string()


class TasksPageMixin:
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


class TaskFormsMixin:
    def _task_create_form(self, payload: Mapping[str, Any]) -> str:
        return self._long_run_task_create_form(payload) + self._standard_task_create_form(payload)

    def _task_operation_launcher(self, payload: Mapping[str, Any]) -> str:
        return (
            "<div class='task-operation-hub'>"
            "<div class='task-operation-buttons'>"
            + self._task_modal_button("创建长稳任务", "long-run-task", "配置长稳模板、轮转、补位、监控和日报/周报。")
            + self._task_modal_button("创建任务", "standard-task", "创建一次性或调试用 Task，不自动写入无人值守配置。")
            + self._task_modal_button("创建 Run", "create-run", "基于已有任务生成一次具体执行批次。")
            + self._task_modal_button("执行 Run", "execute-run", "选择监控 backend、并发、重试并开始执行。")
            + self._task_modal_button("归档 / 隐藏", "delete-task-run", "不物理删除，只从默认列表隐藏并记录审计事件。")
            + "</div>"
            "<div class='task-operation-note'>新增入口已收进弹窗；列表在下方分区展示，避免任务页被长表单撑开。</div>"
            "</div>"
            + self._task_modal("long-run-task", "创建长稳任务", self._long_run_task_create_form(payload))
            + self._task_modal("standard-task", "创建任务", self._standard_task_create_form(payload))
            + self._task_modal("create-run", "创建 Run", self._run_create_form(payload))
            + self._task_modal("execute-run", "执行 Run", self._run_execute_form(payload))
            + self._task_modal("delete-task-run", "归档 / 隐藏", self._task_delete_boundary_card(payload))
        )

    @staticmethod
    def _task_modal_button(title: str, modal_id: str, hint: str) -> str:
        return (
            "<button type='button' class='task-operation-button' "
            f"data-task-modal-target='{escape(modal_id, quote=True)}' title='{escape(hint, quote=True)}'>"
            f"<strong>{escape(title)}</strong>"
            "</button>"
        )

    @staticmethod
    def _task_modal(modal_id: str, title: str, body: str) -> str:
        return (
            f"<div id='task-modal-{escape(modal_id, quote=True)}' class='task-modal' aria-hidden='true'>"
            "<div class='task-modal-backdrop' data-task-modal-close='1'></div>"
            "<div class='task-modal-dialog' role='dialog' aria-modal='true'>"
            "<div class='task-modal-header'>"
            f"<h3>{escape(title)}</h3>"
            "<button type='button' class='task-modal-close' data-task-modal-close='1' aria-label='关闭弹窗'>x</button>"
            "</div>"
            f"<div class='task-modal-body'>{body}</div>"
            "</div>"
            "</div>"
        )

    def _task_delete_boundary_card(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        options = "".join(
            self._task_option(item)
            for item in list(payload.get("tasks", []) or [])
            if str(item.get("task_id", "") or "").strip() and not bool(item.get("archived") or item.get("hidden"))
        )
        return (
            "<article class='card stack task-delete-boundary-card'>"
            "<h3>归档任务</h3>"
            "<p>这里执行的是软删除：任务会从默认任务列表隐藏，Run、监控快照、报告和准入证据不会被物理删除。</p>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/archive-task', current_actor=current_actor), quote=True)}' class='stack'>"
            "<label>任务<select name='task_id'>" + (options or "<option value=''>当前没有可归档任务</option>") + "</select></label>"
            "<label>归档原因<textarea name='reason' rows='2' placeholder='例如 临时调试任务已结束，隐藏避免干扰列表。'></textarea></label>"
            "<div class='notice warning'>归档会记录服务端解析身份、request_id、session_id、audit_event_id，并投递 task.archived outbox 事件；不会删除任何历史产物。</div>"
            "<div class='form-actions'><button type='submit'>归档并隐藏</button></div>"
            "</form>"
            "</article>"
        )

    def _standard_task_create_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        defaults = dict(payload.get("operation_defaults", {}) or {})
        selected_template = str(defaults.get("template_type", "") or "cold_start_loop")
        template_schema = get_template_form_schema(selected_template)
        template_options = self._task_template_options(selected_template)
        device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=True,
        )
        metric_selector = self._task_metric_selector(default_selected=tuple(template_schema["metrics"]["default"]))
        return (
            "<article class='card stack task-create-card'>"
            "<h3>创建任务 <span class='heading-hint'>定义要测什么 App、用什么模板、可选哪些设备。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-task', current_actor=current_actor), quote=True)}' class='stack task-create-form'>"
            "<section class='task-form-section task-form-section-basic'>"
            "<div class='task-form-section-title'>基础信息</div>"
            "<div class='form-grid-three task-basic-grid'>"
            "<label>任务名<input type='text' name='task_name' value='' placeholder='例如 首页冷启动回归' /></label>"
            "<label>包名<input type='text' name='package_name' value='' placeholder='com.example.app' /></label>"
            f"<label>模板<select name='template_type'>{template_options}</select></label>"
            "</div>"
            f"{self._task_template_risk_notice(template_schema)}"
            "</section>"
            "<div class='task-create-layout'>"
            "<section class='task-form-section task-create-target'>"
            "<div class='task-form-section-title'>执行目标</div>"
            f"{device_selector}"
            "<div class='task-target-controls'>"
            "<label class='sampling-field'>采样间隔(秒)<input type='number' name='sampling_interval' value='5' min='0' /></label>"
            "<div class='meta'>和设备选择放在一起，便于一次确认调度范围与采样频率。</div>"
            "</div>"
            "</section>"
            "<section class='task-form-section task-create-metrics'>"
            "<div class='task-form-section-title'>监控指标</div>"
            f"{metric_selector}"
            "</section>"
            "</div>"
            "<section class='task-form-section task-form-section-params'>"
            "<div class='task-form-section-title'>参数表单</div>"
            "<div class='form-grid-three task-params-grid'>"
            f"{self._task_params_builder(managed_apks=list(payload.get('managed_apks', []) or []), upload_url=self._actor_scoped_path('/tasks/actions/upload-apk', current_actor=current_actor), delete_url=self._actor_scoped_path('/tasks/actions/delete-apk', current_actor=current_actor))}"
            f"{self._json_textarea_with_help('task_params(JSON)', 'task_params', '例如 {\"loop_count\": 10}', self._task_params_help())}"
            f"{self._json_textarea_with_help('metadata(JSON)', 'metadata', '例如 {\"source\":\"web\"}', self._metadata_help())}"
            "</div>"
            "</section>"
            "<div class='form-actions'><button type='submit'>创建任务</button></div>"
            "</form></article>"
        )

    def _long_run_task_create_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        defaults = dict(payload.get("operation_defaults", {}) or {})
        selected_template = str(defaults.get("template_type", "") or "monkey")
        template_schema = get_template_form_schema(selected_template)
        template_options = self._task_template_options(selected_template)
        primary_device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=True,
            label="指定设备 / 自动调度",
            field_name="devices",
            empty_title="自动调度",
            empty_hint="不绑定设备；无人值守轮次按设备池挑选",
        )
        backup_device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=True,
            label="候补设备",
            field_name="backup_devices",
            empty_title="不指定候补设备",
            empty_hint="主设备不可用时才尝试补位",
        )
        metric_selector = self._task_metric_selector(default_selected=tuple(template_schema["metrics"]["default"]))
        return (
            "<article class='card stack task-create-card long-run-task-create-card'>"
            "<h3>创建长稳任务 <span class='heading-hint'>一次提交创建普通 Task，并写入 runner 可见的无人值守配置。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-task', current_actor=current_actor), quote=True)}' class='stack task-create-form long-run-task-create-form'>"
            "<input type='hidden' name='configure_unattended' value='1' />"
            "<section class='task-form-section task-form-section-basic'>"
            "<div class='task-form-section-title'>测试目标</div>"
            "<div class='form-grid-three task-basic-grid'>"
            "<label>任务名<input type='text' name='task_name' value='' placeholder='例如 直播间 overnight 长稳' required /></label>"
            "<label>包名<input type='text' name='package_name' value='' placeholder='com.example.app' required /></label>"
            f"<label>长稳模板<select name='template_type'>{template_options}</select></label>"
            "</div>"
            f"{self._task_template_risk_notice(template_schema)}"
            "<div class='meta'>模板覆盖前后台切换、Monkey、冷启动、安装卸载、重启、待机唤醒；这里只做最小长稳闭环，不做复杂排班平台。</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>运行策略</div>"
            "<div class='form-grid-three'>"
            "<label>运行时长(小时)<input type='number' name='runtime_hours' value='12' min='1' /></label>"
            "<label>轮转间隔(分钟)<input type='number' name='interval_minutes' value='60' min='1' /></label>"
            "<label>失败重试<input type='number' name='retry_count' value='1' min='0' /></label>"
            "<label>期望设备数<input type='number' name='desired_device_count' value='1' min='1' /></label>"
            "<label>失败阈值<input type='number' name='failure_threshold' value='3' min='1' /></label>"
            "<label>自动补位<select name='auto_backfill'><option value='1'>开启</option><option value='0'>关闭</option></select></label>"
            "<label>轮转策略<select name='rotation_strategy'><option value='round_robin'>round_robin</option><option value='fixed'>fixed</option></select></label>"
            "<label>轮转推进<select name='rotation_advance_policy'><option value='every_round'>every_round</option><option value='failure_only'>failure_only</option></select></label>"
            "<label>立即开始<select name='start_now'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>设备策略</div>"
            "<div class='unattended-device-grid'>"
            f"<div class='unattended-device-slot'>{primary_device_selector}</div>"
            f"<div class='unattended-device-slot'>{backup_device_selector}</div>"
            "</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>监控策略</div>"
            "<div class='long-run-monitoring-grid'>"
            "<div class='long-run-monitoring-controls'>"
            "<label>Monitoring Backend<select name='monitoring_backend'><option value='default'>default - 基础 ADB 快照</option><option value='solox'>solox - 实时性能采样</option><option value='perfetto'>perfetto - 系统 Trace</option></select></label>"
            "<label>采样间隔(秒)<input type='number' name='sampling_interval' value='5' min='0' /></label>"
            "<div class='meta'>先选采集方式和频率，再勾选这条长稳任务要沉淀的指标。</div>"
            "</div>"
            f"{metric_selector}"
            "</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>输出</div>"
            "<div class='form-grid-three'>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='daily_report' checked /><span>日报<small>runner daily report</small></span></label>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='weekly_report' checked /><span>周报<small>runner weekly report</small></span></label>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='exception_summary' checked /><span>异常摘要<small>失败/掉线/隔离摘要</small></span></label>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='admission_assist' checked /><span>准入辅助结果说明<small>供准入/提测决策参考</small></span></label>"
            "</div>"
            "<label>结果说明<textarea name='output_note' rows='2' placeholder='例如 每天早上看日报，异常摘要同步到准入辅助说明。'></textarea></label>"
            "</section>"
            "<section class='task-form-section task-form-section-params'>"
            "<div class='task-form-section-title'>模板参数</div>"
            "<div class='form-grid-three task-params-grid'>"
            f"{self._task_params_builder(managed_apks=list(payload.get('managed_apks', []) or []), upload_url=self._actor_scoped_path('/tasks/actions/upload-apk', current_actor=current_actor), delete_url=self._actor_scoped_path('/tasks/actions/delete-apk', current_actor=current_actor))}"
            f"{self._json_textarea_with_help('task_params(JSON)', 'task_params', '例如 {\"event_count\": 5000, \"throttle_ms\": 300}', self._task_params_help())}"
            f"{self._json_textarea_with_help('metadata(JSON)', 'metadata', '例如 {\"owner_team\":\"android-client\"}', self._metadata_help())}"
            "</div>"
            "</section>"
            "<div class='form-actions'>"
            "<button type='submit'>创建长稳任务并配置无人值守</button>"
            "<a href='/runner'>查看 runner 页面</a>"
            "</div>"
            "</form></article>"
        )

    def _run_create_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=False,
        )
        options = "".join(
            self._task_option(item)
            for item in list(payload.get("tasks", []) or [])
            if str(item.get("task_id", "") or "").strip()
        )
        return (
            "<article class='card stack'>"
            "<h3>创建 Run <span class='heading-hint'>基于某个任务生成一次具体执行批次。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='stack'>"
            "<div class='form-grid-three'>"
            "<label>任务<select name='task_id'>" + options + "</select></label>"
            f"{device_selector}"
            "<label>metadata(JSON)<textarea name='metadata' rows='2' placeholder='例如 {\"source\":\"web\"}'></textarea></label>"
            "</div>"
            "<div class='form-actions'><button type='submit'>创建 Run</button></div>"
            "</form></article>"
        )

    def _run_execute_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        defaults = dict(payload.get("operation_defaults", {}) or {})
        options = "".join(
            f"<option value='{escape(str(item.get('run_id', '') or ''), quote=True)}'>{escape(str(item.get('run_id', '') or ''))} / {escape(str(item.get('task_name', '') or ''))}</option>"
            for item in list(payload.get("runs", []) or [])
            if str(item.get("run_id", "") or "").strip()
        )
        selected_backend = str(defaults.get("monitoring_backend", "default") or "default")
        return (
            "<article class='card stack'>"
            "<h3>执行 Run <span class='heading-hint'>真正开始跑，并选择 monitoring backend、并发、重试等执行参数。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/execute-run', current_actor=current_actor), quote=True)}' class='stack'>"
            "<div class='form-grid-three'>"
            "<label>Run<select name='run_id'>" + options + "</select></label>"
            f"<label>Monitoring Backend<select name='monitoring_backend'><option value='default'{' selected' if selected_backend == 'default' else ''}>default - 基础 ADB 快照</option><option value='solox'{' selected' if selected_backend == 'solox' else ''}>solox - 实时性能采样</option><option value='perfetto'{' selected' if selected_backend == 'perfetto' else ''}>perfetto - 系统 Trace</option></select></label>"
            "<label>重试次数<input type='number' name='retry_count' value='0' min='0' /></label>"
            "</div>"
            "<div class='form-grid-three'>"
            "<label>并发数<input type='number' name='max_concurrency' value='1' min='1' /></label>"
            "<label>停止于失败<select name='stop_on_failure'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "</div>"
            "<div class='form-actions'><button type='submit'>执行 Run</button></div>"
            "</form></article>"
        )

    @staticmethod
    def _task_option(item: Mapping[str, Any]) -> str:
        task_id = str(item.get("task_id", "") or "").strip()
        task_name = str(item.get("task_name", "") or task_id).strip()
        template_type = str(item.get("template_type", "") or "").strip()
        package_name = str(item.get("package_name", "") or "").strip()
        created_at = str(item.get("created_at", "") or "").strip().replace("T", " ", 1)
        short_id = task_id[-8:] if len(task_id) > 8 else task_id
        template_label = TaskFormsMixin._task_template_plain_label(template_type)
        detail_parts = [part for part in [template_label, package_name, f"id:{short_id}", created_at[:16]] if part]
        label = task_name + (" / " + " / ".join(detail_parts) if detail_parts else "")
        return f"<option value='{escape(task_id, quote=True)}'>{escape(label)}</option>"

    @classmethod
    def _json_textarea_with_help(
        cls,
        label: str,
        name: str,
        placeholder: str,
        help_html: str,
        *,
        wide: bool = True,
        rows: int = 2,
    ) -> str:
        class_name = "json-field-with-help"
        if wide:
            class_name += " form-field-wide"
        return (
            f"<div class='{class_name}'>"
            "<div class='json-field-header'>"
            f"<span>{escape(label)}</span>"
            "<details class='json-param-help'>"
            "<summary>查看参数</summary>"
            f"<div class='json-param-help-body'>{help_html}</div>"
            "</details>"
            "</div>"
            f"<textarea name='{escape(name, quote=True)}' rows='{int(rows)}' placeholder='{escape(placeholder, quote=True)}'></textarea>"
            "</div>"
        )

    @classmethod
    def _task_params_builder(
        cls,
        *,
        wide: bool = True,
        managed_apks: Sequence[Mapping[str, Any]] = (),
        upload_url: str = "/tasks/actions/upload-apk",
        delete_url: str = "/tasks/actions/delete-apk",
    ) -> str:
        class_name = "task-param-builder"
        if wide:
            class_name += " form-field-wide"
        section_html = []
        for section in get_param_sections_for_web():
            field_html = "".join(
                cls._task_param_builder_input(
                    field.key,
                    field.input_type,
                    field.label,
                    field.placeholder,
                    default=field.default,
                    managed_apks=managed_apks,
                    upload_url=upload_url,
                    delete_url=delete_url,
                )
                for field in section.fields
            )
            section_html.append(
                "<div class='task-param-builder-section' "
                f"data-template-scope='{escape(' '.join(section.template_scopes), quote=True)}'>"
                f"<div class='meta'>{escape(section.title)}</div>"
                "<div class='task-param-builder-grid'>"
                + field_html
                + "</div>"
                "</div>"
            )
        return (
            f"<div class='{class_name}' data-task-param-builder='1'>"
            "<div class='json-field-header'>"
            "<span>参数表单</span>"
            "<span class='meta'>填写后自动生成下方 task_params(JSON)，也可以继续手写 JSON。</span>"
            "</div>"
            + "".join(section_html)
            + "</div>"
        )

    @staticmethod
    def _task_param_builder_input(
        key: str,
        kind: str,
        label: str,
        placeholder: str,
        *,
        default: object | None = None,
        managed_apks: Sequence[Mapping[str, Any]] = (),
        upload_url: str = "/tasks/actions/upload-apk",
        delete_url: str = "/tasks/actions/delete-apk",
    ) -> str:
        escaped_key = escape(key, quote=True)
        escaped_label = escape(label)
        escaped_placeholder = escape(placeholder, quote=True)
        default_attr = "" if default in (None, "") else f" value='{escape(str(default), quote=True)}'"
        if kind == "apk_manager":
            options = "".join(
                f"<option value='{escape(str(item.get('path', '') or ''), quote=True)}'>"
                f"{escape(str(item.get('name', '') or item.get('path', '') or 'APK'))}"
                "</option>"
                for item in managed_apks
                if str(item.get("path", "") or "").strip()
            )
            return (
                "<div class='task-param-builder-input task-apk-manager' data-apk-manager='1' "
                f"data-apk-upload-url='{escape(upload_url, quote=True)}' "
                f"data-apk-delete-url='{escape(delete_url, quote=True)}'>"
                "<div class='task-apk-manager-head'>"
                f"<span>{escaped_label}<small>上传、删除并选择安装卸载循环使用的 APK</small></span>"
                "<button type='button' class='secondary' data-apk-upload-button='1'>上传 APK</button>"
                "<button type='button' class='secondary danger' data-apk-delete-button='1'>删除</button>"
                "</div>"
                "<input type='file' accept='.apk,application/vnd.android.package-archive' data-apk-upload-input='1' hidden />"
                "<label class='task-apk-select-label'>"
                "已管理 APK"
                "<select data-apk-select='1'>"
                "<option value=''>请选择已上传 APK</option>"
                + options +
                "</select>"
                "</label>"
                "<div class='meta' data-apk-manager-status='1'>上传后会加入下拉列表；选择后自动写入下方 apk_path。</div>"
                "</div>"
            )
        input_type = "number" if kind == "number" else "text"
        if kind == "checkbox":
            return (
                "<label class='task-param-builder-check'>"
                f"<input type='checkbox' data-task-param-key='{escaped_key}' data-task-param-type='boolean' />"
                f"<span>{escaped_label}<small>{escape(key)}</small></span>"
                "</label>"
            )
        return (
            "<label class='task-param-builder-input'>"
            f"<span>{escaped_label}<small>{escape(key)}</small></span>"
            f"<input type='{input_type}' data-task-param-key='{escaped_key}' data-task-param-type='{escape(kind, quote=True)}' placeholder='{escaped_placeholder}'{default_attr} />"
            "</label>"
        )

    @staticmethod
    def _task_params_help() -> str:
        groups = []
        for section in get_param_sections_for_web():
            groups.append(
                (
                    section.title,
                    section.template_scopes,
                    tuple(
                        (
                            " / ".join((field.key, *field.aliases)),
                            field.description,
                        )
                        for field in section.fields
                    ),
                )
            )
        return TaskFormsMixin._help_group_html(groups)

    @staticmethod
    def _metadata_help() -> str:
        groups = [
            (
                "常用字段",
                [
                    ("source", "来源，例如 web、codex、release-center。"),
                    ("branch", "代码分支或测试分支。"),
                    ("build_id", "构建 ID，方便和 CI / 提测系统对齐。"),
                    ("version_name / version_code", "版本名和版本号。"),
                    ("release_channel", "发布通道，例如 beta、gray、store。"),
                    ("owner_team", "责任团队。"),
                    ("note", "补充说明，便于后续排查。"),
                ],
            ),
            (
                "联动建议",
                [
                    ("ticket_id / ci_run_id", "外部缺陷或 CI 流水线编号。"),
                    ("baseline_key", "需要关联准入基线时填写。"),
                    ("tags", "自定义标签；建议用数组或逗号字符串。"),
                ],
            ),
        ]
        return TaskFormsMixin._help_group_html(groups)

    @staticmethod
    def _help_group_html(groups: Sequence[tuple[Any, ...]]) -> str:
        sections = []
        for group in groups:
            if len(group) == 3:
                title, templates, items = group
            else:
                title, items = group
                templates = ("all",)
            template_attr = " ".join(str(item) for item in templates if str(item).strip()) or "all"
            rows = "".join(
                "<tr>"
                f"<td class='mono'>{escape(str(key))}</td>"
                f"<td>{escape(str(description))}</td>"
                "</tr>"
                for key, description in items
            )
            sections.append(
                f"<div class='json-param-help-section' data-template-scope='{escape(template_attr, quote=True)}'>"
                f"<strong>{escape(str(title))}</strong>"
                "<table class='compact-table'><tbody>"
                + rows
                + "</tbody></table>"
                "</div>"
            )
        return "".join(sections)

    @staticmethod
    def _task_metric_selector(*, default_selected: Sequence[str] = ("cpu", "memory")) -> str:
        selected = {str(item or "").strip().lower() for item in default_selected}
        cards = []
        for value, metric in METRIC_REGISTRY.items():
            checked = " checked" if value in selected else ""
            scopes = " ".join(metric_template_scopes(value))
            default_scopes = " ".join(default_metric_template_scopes(value))
            cards.append(
                "<label class='device-choice-card metric-choice-card' "
                f"data-template-scope='{escape(scopes, quote=True)}' "
                f"data-default-template-scope='{escape(default_scopes, quote=True)}'>"
                f"<input type='checkbox' name='metrics' value='{escape(value, quote=True)}'{checked} />"
                "<span>"
                f"<strong>{escape(metric.title)}</strong>"
                f"<small>{escape(value)} / {escape(metric.description)}</small>"
                "</span>"
                "</label>"
            )
        return (
            "<div class='device-checkbox-field metric-checkbox-field'>"
            "<div class='meta'>指标</div>"
            "<div class='device-choice-grid metric-choice-grid'>"
            + "".join(cards)
            + "</div>"
            "<span class='meta'>可多选；默认 CPU + Memory，SoloX 可采 network / battery / fps / gpu，Perfetto 可辅助 trace/network。</span>"
            "</div>"
        )

    @staticmethod
    def _task_device_selector(
        devices: list[Mapping[str, Any]],
        *,
        allow_empty: bool,
        label: str = "设备",
        field_name: str = "devices",
        empty_title: str = "自动调度（不指定设备）",
        empty_hint: str = "执行时按设备池选择",
    ) -> str:
        help_text = (
            "可勾选一台或多台；选择“自动调度”则任务不绑定具体设备。"
            if allow_empty
            else "必须勾选至少一台可调度设备。"
        )
        if not devices:
            message = "当前没有可调度设备，请先到设备池刷新或连接设备"
            return (
                "<div class='device-checkbox-field'>"
                f"<div class='meta'>{escape(label)}</div>"
                f"<div class='empty-state'>{escape(message)}</div>"
                f"<span class='meta'>{escape(message)}</span>"
                "</div>"
            )
        cards = []
        if allow_empty:
            cards.append(
                "<label class='device-choice-card device-choice-auto'>"
                f"<input type='checkbox' name='{escape(field_name, quote=True)}' value='' checked />"
                f"<span><strong>{escape(empty_title)}</strong><small>{escape(empty_hint)}</small></span>"
                "</label>"
            )
        for item in devices:
            device_id = str(item.get("device_id", "") or item.get("serial", "") or "").strip()
            if not device_id:
                continue
            model = str(item.get("model", "") or item.get("display_name", "") or "").strip()
            group_name = str(item.get("group_name", "") or "").strip() or "未分组"
            team_name = str(item.get("team_name", "") or item.get("team", "") or "").strip() or "未分配"
            cards.append(
                "<label class='device-choice-card'>"
                f"<input type='checkbox' name='{escape(field_name, quote=True)}' value='{escape(device_id, quote=True)}' />"
                "<span>"
                f"<strong>{escape(device_id)}</strong>"
                f"<small>{escape(' / '.join(part for part in [model, group_name, team_name] if part))}</small>"
                "</span>"
                "</label>"
            )
        return (
            "<div class='device-checkbox-field'>"
            f"<div class='meta'>{escape(label)}</div>"
            "<div class='device-choice-grid'>"
            + "".join(cards)
            + "</div>"
            f"<span class='meta'>{escape(help_text)}</span>"
            "</div>"
        )

    @staticmethod
    def _task_template_options(selected: str) -> str:
        return "".join(
            f"<option value='{escape(item.value, quote=True)}'{' selected' if selected == item.value else ''}>{escape(item.option_label)}</option>"
            for item in list_scenario_definitions()
        )

    @staticmethod
    def _task_template_risk_notice(schema: Mapping[str, Any]) -> str:
        risk = dict(schema.get("risk", {}) or {})
        level = str(risk.get("risk_level", "") or "low")
        notes = []
        if risk.get("requires_apk"):
            notes.append("需要 APK")
        if risk.get("changes_device_state"):
            notes.append("会改变设备状态")
        risk_note = str(risk.get("risk_note", "") or "").strip()
        summary = "；".join(notes) if notes else "常规执行模板"
        if risk_note:
            summary = f"{summary}；{risk_note}"
        tone = "warning" if level in {"medium", "high"} else "ok"
        return (
            f"<div class='notice {tone} task-template-risk' data-template-risk='1'>"
            f"当前模板风险：<strong>{escape(level)}</strong>，{escape(summary)}"
            "</div>"
        )

    @staticmethod
    def _task_template_plain_label(template_type: str) -> str:
        template = str(template_type or "").strip()
        if not template:
            return ""
        try:
            return get_scenario_definition(template).plain_label
        except KeyError:
            pass
        return template

    @staticmethod
    def _task_template_definitions() -> tuple[tuple[str, str, str], ...]:
        return tuple((item.value, item.chinese_name, item.description) for item in list_scenario_definitions())


class TaskDetailPageMixin(TaskFormsMixin):
    def _task_detail_payload(
        self,
        task_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_service = getattr(self._bundle, "task_service", None)
        if task_service is None or not hasattr(task_service, "get_task"):
            raise ValueError("Task service is unavailable.")
        task = task_service.get_task(task_id)
        task_payload = self._describe_task_payload(task)
        run_history_service = getattr(self._bundle, "run_history_service", None)
        runs: list[dict[str, Any]] = []
        if run_history_service is not None and hasattr(run_history_service, "list_runs"):
            runs = self._decorate_runs_with_monitoring(list(run_history_service.list_runs(task_id=task_id, limit=30)))
        return {
            "page": "task_detail",
            "title": f"任务详情 · {task_payload.get('task_name', task_id) or task_id}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "query": dict(query or {}),
            "task": {
                **task_payload,
                "detail_path": f"/tasks/task/{quote(task_id, safe='')}",
                "api_path": f"/api/tasks/task/{quote(task_id, safe='')}",
            },
            "runs": runs,
        }

    def _render_task_detail(self, payload: dict[str, Any]) -> str:
        task = dict(payload.get("task", {}) or {})
        runs = list(payload.get("runs", []) or [])
        body = [
            self._metric_grid(
                [
                    ("任务", task.get("task_name", "n/a") or "n/a"),
                    ("模板", task.get("template_type", "n/a") or "n/a"),
                    ("设备数", task.get("planned_device_count", 0)),
                    ("最近 Run", len(runs)),
                    ("采样间隔", dict(task.get("sampling_config", {}) or {}).get("interval_seconds", 0)),
                    ("创建人", task.get("created_by", "n/a") or "n/a"),
                ]
            ),
            self._section(
                "任务定义",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(task, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
            ),
            self._section("创建 Run", [self._task_detail_create_run_form(task, current_actor=dict(payload.get("current_actor", {}) or {}))]),
            self._section("关联 Runs", [self._run_table(runs)]),
        ]
        return self._layout(
            "任务详情",
            "这里对应 CLI 的 show-task，先确认任务定义，再从同页直接创建新的 Run。",
            "".join(body),
        )

    def _unattended_detail_payload(
        self,
        task_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        unattended_service = getattr(self._bundle, "unattended_service", None)
        if unattended_service is None or not hasattr(unattended_service, "get_task_record"):
            raise ValueError("Unattended service is unavailable.")
        record = unattended_service.get_task_record(task_id)
        daily_report = {}
        weekly_report = {}
        if hasattr(unattended_service, "build_daily_report"):
            try:
                daily_report = self._unattended_daily_report_payload(unattended_service.build_daily_report(task_id=task_id))
            except Exception:
                daily_report = {}
        if hasattr(unattended_service, "build_weekly_report"):
            try:
                weekly_report = self._unattended_weekly_report_payload(unattended_service.build_weekly_report(task_id=task_id))
            except Exception:
                weekly_report = {}
        return {
            "page": "unattended_detail",
            "title": f"无人值守详情 · {task_id}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "query": dict(query or {}),
            "task": self._unattended_task_payload(record),
            "daily_report": daily_report,
            "weekly_report": weekly_report,
        }

    def _render_unattended_detail(self, payload: dict[str, Any]) -> str:
        task = dict(payload.get("task", {}) or {})
        daily_report = dict(payload.get("daily_report", {}) or {})
        weekly_report = dict(payload.get("weekly_report", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("Task ID", task.get("task_id", "n/a") or "n/a"),
                    ("启用", "yes" if task.get("enabled") else "no"),
                    ("间隔(分钟)", task.get("interval_minutes", 0)),
                    ("主设备", len(task.get("primary_device_ids", []) or [])),
                    ("备设备", len(task.get("backup_device_ids", []) or [])),
                    ("Due", "yes" if task.get("due") else "no"),
                ]
            ),
            self._section(
                "无人值守配置",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(task, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
            ),
            self._section("执行动作", [self._unattended_detail_actions_form(task, current_actor=dict(payload.get("current_actor", {}) or {}))]),
            self._section(
                "Latest Daily Report",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(daily_report, ensure_ascii=False, indent=2))
                    + "</pre>"
                    if daily_report
                    else self._notice("当前还没有可展示的日报。")
                ],
            ),
            self._section(
                "Latest Weekly Report",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(weekly_report, ensure_ascii=False, indent=2))
                    + "</pre>"
                    if weekly_report
                    else self._notice("当前还没有可展示的周报。")
                ],
            ),
        ]
        return self._layout(
            "无人值守详情",
            "这里对应 CLI 的 show-unattended-task，先看配置，再决定是否手动跑一轮或执行 patrol。",
            "".join(body),
        )

    def _task_detail_create_run_form(self, task: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        task_id = str(task.get("task_id", "") or "")
        device_selector = self._task_device_selector(
            [item for item in self._device_summaries() if bool(dict(item).get("is_schedulable", False))],
            allow_empty=False,
            label="目标设备",
        )
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>基于当前任务创建 Run</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            f"{device_selector}"
            "<label>metadata(JSON)<textarea name='metadata' rows='3' placeholder='例如 {\"source\":\"web\"}'></textarea></label>"
            "<div><button type='submit'>创建 Run</button></div>"
            "</form>"
            "</article></div>"
        )

    def _unattended_detail_actions_form(self, task: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        task_id = str(task.get("task_id", "") or "")
        return (
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>手动跑一轮</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/run-unattended-round', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            "<option value='default'>default</option>"
            "<option value='solox'>solox</option>"
            "<option value='perfetto'>perfetto</option>"
            "</select></label>"
            "<div><button type='submit'>执行轮次</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>触发 Patrol</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/runner/actions/patrol-unattended', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='task_id' value='{escape(task_id, quote=True)}' />"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            "<option value='default'>default</option>"
            "<option value='solox'>solox</option>"
            "<option value='perfetto'>perfetto</option>"
            "</select></label>"
            "<div><button type='submit'>执行 Patrol</button></div>"
            "</form>"
            "</article>"
            "</div>"
        )


__all__ = ["TasksPageMixin", "TaskFormsMixin", "TaskDetailPageMixin"]
