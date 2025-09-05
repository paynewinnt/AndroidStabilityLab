from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from stability.web.application_common import WebPortalApplication


class RunnerCorePageMixin:
    def _render_runner(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        runner = dict(payload.get("runner", {}) or {})
        platform_health = dict(payload.get("platform_health", {}) or {})
        last_patrol = dict(payload.get("last_patrol", {}) or {})
        recent_patrols = list(payload.get("recent_patrols", []) or [])
        latest_patrol_relation = dict(payload.get("latest_patrol_relation", {}) or {})
        unattended_tasks = list(payload.get("unattended_tasks", []) or [])
        long_run_templates = dict(payload.get("long_run_templates", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        body.append(
            self._admin_page_header(
                "后台巡检状态",
                subtitle="查看 patrol runner 锁、心跳、最近轮次、日报/周报和无人值守配置。",
                breadcrumbs=[("首页", "/"), ("巡检状态", "")],
                actions=[
                    self._route_link("JSON API", "/api/runner"),
                    self._route_link("长稳模板", "/long-run-templates"),
                    self._route_link("任务大厅", "/tasks"),
                ],
            )
        )
        body.append(self._runner_compact_summary(summary, unattended_task_count=len(unattended_tasks)))
        body.append(self._workflow_nav_bar(active="run", artifact_items=self._runner_artifact_items(runner)))
        body.append(self._section("最新心跳关联提示", [self._runner_latest_patrol_relation_notice(latest_patrol_relation)]))
        if not bool(runner.get("heartbeat_present", False)):
            body.append(
                self._notice(
                    "当前还没有 patrol runner 心跳。先执行 run-unattended-patrol-runner，或者等待首次后台巡检写入状态。"
                )
            )
        elif bool(runner.get("is_stale", False)):
            body.append(
                self._notice(
                    "当前 runner lock 看起来已经 stale。建议先确认旧进程是否仍存活，再决定是否重新拉起后台 runner。",
                    tone="danger",
                )
            )
        body.append(self._runner_patrol_quick_actions(filters=filters))
        body.extend(
            [
                self._section("长稳模板", [self._runner_long_run_template_links(long_run_templates)]),
                self._section("配置无人值守", [self._runner_collapsed_unattended_config(payload)]),
                self._section("无人值守任务", [self._unattended_task_cards(unattended_tasks)]),
                self._section("当前状态", [self._runner_status_card(runner)]),
                self._section("平台自监控", [self._platform_health_card(platform_health)]),
                self._section("Latest Daily Report", [self._runner_daily_report_card(runner)]),
                self._section("Latest Weekly Report", [self._runner_weekly_report_card(runner)]),
                self._section(
                    "最近一轮 Patrol",
                    ["<pre class='mono'>" + escape(json.dumps(last_patrol, ensure_ascii=False, indent=2)) + "</pre>"],
                ),
                self._runner_patrol_filter_bar(filters=filters),
                self._runner_patrol_admin_workspace(payload, recent_patrols),
                self._section(
                    "路径与心跳",
                    [
                        "<pre class='mono'>"
                        + escape(
                            json.dumps(
                                {
                                    "root_dir": runner.get("root_dir", ""),
                                    "lock_path": runner.get("lock_path", ""),
                                    "heartbeat_path": runner.get("heartbeat_path", ""),
                                    "daily_report_paths": runner.get("daily_report_paths", {}),
                                    "status": runner.get("status", ""),
                                    "lock_state": runner.get("lock_state", ""),
                                    "observed_at": runner.get("observed_at", ""),
                                    "started_at": runner.get("started_at", ""),
                                    "last_heartbeat_at": runner.get("last_heartbeat_at", ""),
                                    "finished_at": runner.get("finished_at", ""),
                                    "stopped_reason": runner.get("stopped_reason", ""),
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                        + "</pre>"
                    ],
                ),
            ]
        )
        return self._layout(
            "后台巡检状态",
            "展示 patrol runner 的锁、心跳和最近一轮巡检摘要。",
            "".join(body),
        )

    def _runner_patrol_admin_workspace(
        self,
        payload: Mapping[str, Any],
        patrols: Sequence[Mapping[str, Any]],
    ) -> str:
        table_id = "runner-patrol-admin-table"
        columns = self._runner_patrol_columns()
        toolbar = self._admin_toolbar(
            title="最近 Patrol 历史",
            description="按轮次展示巡检状态，支持列设置和分页，详情在抽屉内查看。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/runner'>刷新</a>",
                "<a class='button secondary' href='/api/runner'>导出 JSON</a>",
            ],
        )
        filter_bar = self._runner_patrol_admin_filter_bar(dict(payload.get("filters", {}) or {}))
        table_html, drawers = self._runner_patrol_admin_table(patrols, table_id=table_id, columns=columns)
        pagination = self._admin_pagination(
            base_path="/runner",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return (
            "<section class='panel admin-list-panel'>"
            + toolbar
            + filter_bar
            + table_html
            + pagination
            + "</section>"
            + drawers
        )

    def _runner_patrol_admin_filter_bar(self, filters: Mapping[str, Any]) -> str:
        return self._admin_filter_bar(
            action="/runner",
            values=filters,
            fields=[
                {"name": "keyword", "label": "关键词", "placeholder": "cycle / 时间 / 严重度"},
                {
                    "name": "patrol_filter",
                    "label": "异常类型",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "failed", "label": "失败轮次"},
                        {"value": "offline", "label": "掉线轮次"},
                        {"value": "quarantined", "label": "隔离轮次"},
                    ],
                },
                {
                    "name": "severity_filter",
                    "label": "严重度",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部严重度"},
                        {"value": "normal", "label": "正常"},
                        {"value": "medium", "label": "中"},
                        {"value": "high", "label": "高"},
                        {"value": "critical", "label": "严重"},
                    ],
                },
                {
                    "name": "page_size",
                    "label": "每页",
                    "type": "select",
                    "options": [{"value": "10", "label": "10"}, {"value": "20", "label": "20"}, {"value": "50", "label": "50"}],
                },
            ],
        )

    @staticmethod
    def _runner_patrol_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "cycle", "label": "Cycle"},
            {"key": "finished_at", "label": "Finished At"},
            {"key": "severity", "label": "严重度"},
            {"key": "tasks", "label": "任务"},
            {"key": "failed_rate", "label": "失败率"},
            {"key": "offline_rate", "label": "掉线率"},
            {"key": "recovery_rate", "label": "恢复率", "default_visible": False},
            {"key": "quarantine", "label": "隔离"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _runner_patrol_admin_table(
        self,
        patrols: Sequence[Mapping[str, Any]],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for item_raw in patrols:
            item = dict(item_raw or {})
            cycle = int(item.get("cycle_index", 0) or 0)
            drawer_id = f"admin-runner-patrol-{self._dom_id_fragment(str(cycle))}"
            severity = dict(item.get("severity", {}) or self._runner_patrol_severity(item))
            finished_at = str(item.get("finished_at", "") or item.get("generated_at", "") or "n/a")
            rows.append(
                {
                    "select": f"<input type='checkbox' name='cycle_index' value='{escape(str(cycle), quote=True)}' />",
                    "cycle": escape(str(cycle)),
                    "finished_at": escape(finished_at),
                    "severity": self._admin_status(str(severity.get("label", "正常") or "正常"), tone=str(severity.get("tone", "ok") or "ok")),
                    "tasks": (
                        f"exec={escape(str(item.get('executed_task_count', 0) or 0))}"
                        f"<div class='meta'>due={escape(str(item.get('due_task_count', 0) or 0))} / skipped={escape(str(item.get('skipped_task_count', 0) or 0))}</div>"
                    ),
                    "failed_rate": escape(str(item.get("failed_rate", 0.0) or 0.0)),
                    "offline_rate": escape(str(item.get("offline_rate", 0.0) or 0.0)),
                    "recovery_rate": escape(str(item.get("recovery_success_rate", 0.0) or 0.0)),
                    "quarantine": escape(str(item.get("quarantined_device_count", 0) or 0)),
                    "actions": "<div class='admin-table-actions'>" + self._admin_drawer_button("详情", drawer_id) + "</div>",
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"Patrol 详情 · Cycle {cycle}",
                    self._runner_patrol_admin_detail(item),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前还没有可展示的 patrol 历史。"), "".join(drawers)

    def _runner_patrol_admin_detail(self, item: Mapping[str, Any]) -> str:
        severity = dict(item.get("severity", {}) or self._runner_patrol_severity(item))
        fields = [
            ("Cycle", item.get("cycle_index", 0)),
            ("Generated At", item.get("generated_at", "")),
            ("Started At", item.get("started_at", "")),
            ("Finished At", item.get("finished_at", "")),
            ("严重度", severity.get("label", "正常")),
            ("任务数", item.get("task_count", 0)),
            ("Due", item.get("due_task_count", 0)),
            ("Executed", item.get("executed_task_count", 0)),
            ("Skipped", item.get("skipped_task_count", 0)),
            ("Failed Rate", item.get("failed_rate", 0.0)),
            ("Offline Rate", item.get("offline_rate", 0.0)),
            ("Recovery Rate", item.get("recovery_success_rate", 0.0)),
            ("Quarantined", item.get("quarantined_device_count", 0)),
            ("probe_attempts", item.get("quarantine_probe_attempt_count", 0)),
            ("probe_recovered", item.get("quarantine_probe_recovered_count", 0)),
        ]
        return (
            "<div class='admin-detail-grid'>"
            + "".join(
                "<div class='admin-detail-item'>"
                f"<small>{escape(str(label))}</small>"
                f"<strong>{escape(str(value or 'n/a'))}</strong>"
                "</div>"
                for label, value in fields
            )
            + "</div>"
            + (self._runner_patrol_detail_block(item) or "<span class='meta'>正常轮次</span>")
            + "<details class='compact-details'><summary>原始 JSON</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(dict(item), ensure_ascii=False, indent=2))
            + "</pre></details>"
        )

    @staticmethod
    def _runner_compact_summary(summary: Mapping[str, Any], *, unattended_task_count: int) -> str:
        status_items = [
            ("Runner 状态", summary.get("status", "missing")),
            ("平台健康", summary.get("platform_health_status", "unknown")),
            ("锁状态", summary.get("lock_state", "released")),
            ("Cycle 数", summary.get("cycle_count", 0)),
            ("Heartbeat Age(s)", summary.get("heartbeat_age_seconds", "n/a")),
            ("执行任务", summary.get("executed_task_count", 0)),
            ("隔离设备", summary.get("quarantined_device_count", 0)),
            ("最新异常严重度", summary.get("latest_patrol_severity", "正常")),
            ("无人值守任务", unattended_task_count),
        ]
        report_items = [
            ("日报日期", summary.get("daily_report_date", "n/a") or "n/a"),
            ("日报轮次", summary.get("daily_report_round_count", 0)),
            ("日报失败轮次", summary.get("daily_report_failed_round_count", 0)),
            ("周报周键", summary.get("weekly_report_week_key", "n/a") or "n/a"),
            ("周报轮次", summary.get("weekly_report_round_count", 0)),
            ("周报失败轮次", summary.get("weekly_report_failed_round_count", 0)),
            ("周报活跃天数", summary.get("weekly_report_active_day_count", 0)),
            ("周报隔离设备", summary.get("weekly_report_quarantined_device_count", 0)),
        ]

        def render_items(items: Sequence[tuple[str, Any]]) -> str:
            return "".join(
                "<span class='runner-summary-chip'>"
                f"<small>{escape(label)}</small>"
                f"<strong>{escape(str(value))}</strong>"
                "</span>"
                for label, value in items
            )

        return (
            "<section class='card runner-summary-compact'>"
            "<div class='runner-summary-row'>"
            + render_items(status_items)
            + "</div>"
            "<div class='runner-summary-row runner-summary-row-muted'>"
            + render_items(report_items)
            + "</div>"
            "</section>"
        )

    def _runner_collapsed_unattended_config(self, payload: Mapping[str, Any]) -> str:
        return (
            "<details class='runner-config-drawer'>"
            "<summary>展开配置表单</summary>"
            "<div class='runner-config-drawer-body'>"
            + self._unattended_config_form(payload)
            + "</div>"
            "</details>"
        )

    @staticmethod
    def _runner_artifact_items(runner: Mapping[str, Any]) -> list[tuple[str, Any]]:
        daily_paths = dict(runner.get("daily_report_paths", {}) or {})
        weekly_paths = dict(runner.get("weekly_report_paths", {}) or {})
        return [
            ("日报 HTML", daily_paths.get("report_html_path", "")),
            ("日报 JSON", daily_paths.get("report_json_path", "")),
            ("周报 HTML", weekly_paths.get("report_html_path", "")),
            ("周报 JSON", weekly_paths.get("report_json_path", "")),
            ("Runner 心跳", runner.get("heartbeat_path", "")),
        ]

    def _runner_long_run_template_links(self, payload: dict[str, Any]) -> str:
        templates = list(payload.get("templates", []) or [])
        if not templates:
            return self._notice("当前没有可展示的长稳模板。")
        links = [
            f"<a href='/long-run-templates?template_key={quote(str((item or {}).get('template_key', '') or (item or {}).get('template_id', '') or (item or {}).get('key', '') or ''))}'>"
            + escape(
                str(
                    (item or {}).get("name", "")
                    or (item or {}).get("template_key", "")
                    or (item or {}).get("template_id", "")
                    or "模板"
                )
            )
            + "</a>"
            for item in templates[:5]
        ]
        return (
            "<div class='runner-long-run-template-strip'>"
            "<div>"
            f"<strong>模板数：{escape(str(payload.get('template_count', len(templates)) or 0))}</strong>"
            f"<span class='meta'>来源：{escape(str(payload.get('source', 'fallback') or 'fallback'))}</span>"
            "</div>"
            "<div class='runner-template-links'>"
            + "".join(f"<span class='pill'>{link}</span>" for link in links)
            + "<span class='pill'><a href='/long-run-templates'>全部模板</a></span>"
            + "<span class='pill'><a href='/api/long-run-templates'>JSON API</a></span>"
            + "</div>"
            "</div>"
        )

    def _runner_patrol_history_table(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前还没有可展示的 patrol 历史。")
        rows = []
        for item in items:
            detail_block = self._runner_patrol_detail_block(item)
            severity = dict(item.get("severity", {}) or self._runner_patrol_severity(item))
            rows.append(
                "<tr>"
                f"<td data-label='Cycle'>{escape(str(item.get('cycle_index', 0) or 0))}</td>"
                f"<td data-label='Finished At'>{escape(str(item.get('finished_at', '') or item.get('generated_at', '') or 'n/a'))}</td>"
                f"<td data-label='严重度'>{self._status_pill(str(severity.get('label', '正常') or '正常'), tone=str(severity.get('tone', 'ok') or 'ok'))}</td>"
                f"<td data-label='执行任务'>{escape(str(item.get('executed_task_count', 0) or 0))}</td>"
                f"<td data-label='失败率'>{escape(str(item.get('failed_rate', 0.0) or 0.0))}</td>"
                f"<td data-label='掉线率'>{escape(str(item.get('offline_rate', 0.0) or 0.0))}</td>"
                f"<td data-label='恢复率'>{escape(str(item.get('recovery_success_rate', 0.0) or 0.0))}</td>"
                f"<td data-label='隔离设备'>{escape(str(item.get('quarantined_device_count', 0) or 0))}</td>"
                f"<td data-label='详情'>{detail_block or '<span class=\"meta\">正常轮次</span>'}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Cycle</th><th>Finished At</th><th>严重度</th><th>执行任务</th><th>失败率</th><th>掉线率</th><th>恢复率</th><th>隔离设备</th><th>详情</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    @staticmethod
    def _runner_patrol_detail_block(item: Mapping[str, Any]) -> str:
        failed_rate = float(item.get("failed_rate", 0.0) or 0.0)
        offline_rate = float(item.get("offline_rate", 0.0) or 0.0)
        quarantined_device_count = int(item.get("quarantined_device_count", 0) or 0)
        if failed_rate <= 0.0 and offline_rate <= 0.0 and quarantined_device_count <= 0:
            return ""
        detail_items = [
            ("generated_at", item.get("generated_at", "") or "n/a"),
            ("started_at", item.get("started_at", "") or "n/a"),
            ("task_count", item.get("task_count", 0) or 0),
            ("due_task_count", item.get("due_task_count", 0) or 0),
            ("skipped_task_count", item.get("skipped_task_count", 0) or 0),
            ("probe_attempts", item.get("quarantine_probe_attempt_count", 0) or 0),
            ("probe_recovered", item.get("quarantine_probe_recovered_count", 0) or 0),
        ]
        return (
            "<details>"
            "<summary>展开异常详情</summary>"
            "<div class='stack'>"
            + "".join(
                f"<div>{escape(str(label))}: <span class='mono'>{escape(str(value))}</span></div>"
                for label, value in detail_items
            )
            + "</div>"
            "</details>"
        )

    def _runner_patrol_filter_bar(self, *, filters: Mapping[str, Any]) -> str:
        patrol_filter = str(filters.get("patrol_filter", "") or "")
        severity_filter = str(filters.get("severity_filter", "") or "")
        total = int(filters.get("history_count_total", 0) or 0)
        filtered = int(filters.get("history_count_filtered", 0) or 0)
        severity_counts = dict(filters.get("severity_counts", {}) or {})
        links = [
            self._runner_patrol_filter_link(
                label="全部",
                patrol_filter="",
                severity_filter=severity_filter,
                active=(not patrol_filter),
            ),
            self._runner_patrol_filter_link(
                label="失败轮次",
                patrol_filter="failed",
                severity_filter=severity_filter,
                active=(patrol_filter == "failed"),
            ),
            self._runner_patrol_filter_link(
                label="掉线轮次",
                patrol_filter="offline",
                severity_filter=severity_filter,
                active=(patrol_filter == "offline"),
            ),
            self._runner_patrol_filter_link(
                label="隔离轮次",
                patrol_filter="quarantined",
                severity_filter=severity_filter,
                active=(patrol_filter == "quarantined"),
            ),
        ]
        severity_links = [
            self._runner_patrol_filter_link(
                label="全部严重度",
                patrol_filter=patrol_filter,
                severity_filter="",
                active=(not severity_filter),
            ),
            self._runner_patrol_filter_link(
                label=f"中 ({int(severity_counts.get('medium', 0) or 0)})",
                patrol_filter=patrol_filter,
                severity_filter="medium",
                active=(severity_filter == "medium"),
            ),
            self._runner_patrol_filter_link(
                label=f"高 ({int(severity_counts.get('high', 0) or 0)})",
                patrol_filter=patrol_filter,
                severity_filter="high",
                active=(severity_filter == "high"),
            ),
            self._runner_patrol_filter_link(
                label=f"严重 ({int(severity_counts.get('critical', 0) or 0)})",
                patrol_filter=patrol_filter,
                severity_filter="critical",
                active=(severity_filter == "critical"),
            ),
        ]
        return (
            "<div class='cards'><article class='card stack'>"
            f"<div class='meta'>history 过滤：{filtered} / {total}</div>"
            "<div><strong>异常类型：</strong> " + " ".join(links) + "</div>"
            "<div><strong>严重度过滤：</strong> " + " ".join(severity_links) + "</div>"
            "</article></div>"
        )

    def _runner_patrol_quick_actions(self, *, filters: Mapping[str, Any]) -> str:
        counts = dict(filters.get("filter_counts", {}) or {})
        actions = [
            ("一键看失败轮次", "/runner?patrol_filter=failed", int(counts.get("failed", 0) or 0)),
            ("一键看掉线轮次", "/runner?patrol_filter=offline", int(counts.get("offline", 0) or 0)),
            ("一键看隔离轮次", "/runner?patrol_filter=quarantined", int(counts.get("quarantined", 0) or 0)),
        ]
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>异常轮次快捷入口</h3>"
            "<div class='meta'>点一下就跳到对应过滤结果。</div>"
            "<div class='action-links'>"
            + "".join(
                f"<a class='action-link' href='{escape(href, quote=True)}'>{escape(label)} ({count})</a>"
                for label, href, count in actions
            )
            + "</div>"
            "</article></div>"
        )

    def _runner_latest_patrol_relation_notice(self, relation: Mapping[str, Any]) -> str:
        if not bool(relation.get("available", False)):
            return self._notice("当前还没有足够的 patrol 历史，暂时无法判断最新心跳对应的最新 patrol 是否异常。")
        class_name = "notice danger" if str(relation.get("status", "") or "") == "anomalous" else "notice"
        actions = [
            (str(item.get("label", "")), str(item.get("href", "")))
            for item in list(relation.get("actions", []) or [])
            if str(item.get("label", "")).strip() and str(item.get("href", "")).strip()
        ]
        severity = dict(relation.get("severity", {}) or {})
        impact_message = str(relation.get("impact_message", "") or "")
        action_links = ""
        if actions:
            action_links = "<div class='action-links'>" + "".join(
                f"<a class='action-link' href='{escape(href, quote=True)}'>{escape(label)}</a>"
                for label, href in actions
            ) + "</div>"
        severity_markup = self._status_pill(
            str(severity.get("label", "正常") or "正常"),
            tone=str(severity.get("tone", "ok") or "ok"),
        )
        severity_reason = str(severity.get("reason", "") or "")
        detail_block = (
            "<div>"
            f"{severity_markup}"
            + (
                f"<span class='meta'>异常严重度分层：{escape(severity_reason)}</span>"
                if severity_reason
                else ""
            )
            + "</div>"
            f"<div class='meta'>{escape(impact_message)}</div>"
            if impact_message
            else (
                "<div>"
                f"{severity_markup}"
                + (
                    f"<span class='meta'>异常严重度分层：{escape(severity_reason)}</span>"
                    if severity_reason
                    else ""
                )
                + "</div><div class='meta'>当前没有可展示的任务影响范围摘要。</div>"
            )
        )
        return (
            f"<div class='{class_name}'>"
            f"{escape(str(relation.get('message', '') or '当前没有可展示的最新心跳关联提示。'))}"
            f"{detail_block}"
            f"{action_links}"
            "</div>"
        )

    @staticmethod
    def _runner_latest_patrol(last_patrol: Mapping[str, Any], recent_patrols: list[dict[str, Any]]) -> dict[str, Any]:
        if recent_patrols:
            return dict(recent_patrols[-1])
        return dict(last_patrol or {})

    @staticmethod
    def _runner_latest_patrol_relation(item: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(item or {})
        if not payload:
            return {"available": False, "status": "unknown", "message": "", "actions": []}
        cycle_index = int(payload.get("cycle_index", 0) or 0)
        cycle_label = f"第 {cycle_index} 轮" if cycle_index > 0 else "最新一轮"
        failed_rate = float(payload.get("failed_rate", 0.0) or 0.0)
        offline_rate = float(payload.get("offline_rate", 0.0) or 0.0)
        quarantined_count = int(payload.get("quarantined_device_count", 0) or 0)
        severity = dict(payload.get("severity", {}) or WebPortalApplication._runner_patrol_severity(payload))
        impact_message = WebPortalApplication._runner_patrol_impact_message(payload)
        labels: list[str] = []
        actions: list[dict[str, str]] = []
        if failed_rate > 0.0:
            labels.append("失败")
            actions.append({"label": "跳到失败轮次过滤", "href": "/runner?patrol_filter=failed"})
        if offline_rate > 0.0:
            labels.append("掉线")
            actions.append({"label": "跳到掉线轮次过滤", "href": "/runner?patrol_filter=offline"})
        if quarantined_count > 0:
            labels.append("隔离")
            actions.append({"label": "跳到隔离轮次过滤", "href": "/runner?patrol_filter=quarantined"})
        if labels:
            return {
                "available": True,
                "status": "anomalous",
                "cycle_index": cycle_index,
                "labels": labels,
                "severity": severity,
                "message": f"最新心跳对应的最新 patrol {cycle_label} 仍属于异常轮次：{' / '.join(labels)}。",
                "impact_message": impact_message,
                "actions": actions,
            }
        return {
            "available": True,
            "status": "normal",
            "cycle_index": cycle_index,
            "labels": [],
            "severity": severity,
            "message": f"最新心跳对应的最新 patrol {cycle_label} 当前正常，可以继续查看全部 patrol 历史。",
            "impact_message": impact_message,
            "actions": [{"label": "查看全部 patrol 历史", "href": "/runner"}],
        }

    @staticmethod
    def _runner_patrol_with_severity(item: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(item or {})
        payload["severity"] = WebPortalApplication._runner_patrol_severity(payload)
        return payload

    @staticmethod
    def _runner_patrol_severity(item: Mapping[str, Any]) -> dict[str, str]:
        failed_rate = float(item.get("failed_rate", 0.0) or 0.0)
        offline_rate = float(item.get("offline_rate", 0.0) or 0.0)
        quarantined_count = int(item.get("quarantined_device_count", 0) or 0)
        skipped_task_count = int(item.get("skipped_task_count", 0) or 0)
        if quarantined_count > 0 or (failed_rate > 0.0 and skipped_task_count > 0):
            return {
                "level": "critical",
                "label": "严重",
                "tone": "danger",
                "reason": "已出现隔离设备，或失败已伴随任务跳过，说明本轮异常已明显影响执行。",
            }
        if failed_rate > 0.0:
            return {
                "level": "high",
                "label": "高",
                "tone": "warning",
                "reason": "本轮已出现执行失败，建议优先查看失败任务与补位结果。",
            }
        if offline_rate > 0.0:
            return {
                "level": "medium",
                "label": "中",
                "tone": "warning",
                "reason": "本轮出现掉线或恢复波动，建议先确认网络与恢复链路。",
            }
        return {
            "level": "normal",
            "label": "正常",
            "tone": "ok",
            "reason": "本轮未出现失败、掉线或隔离，可继续看全部巡检历史。",
        }

    @staticmethod
    def _runner_patrol_impact_message(item: Mapping[str, Any]) -> str:
        fields = ["task_count", "due_task_count", "executed_task_count", "skipped_task_count"]
        if not any(field in item for field in fields):
            return "任务影响范围：当前摘要未携带 task_count / due_task_count / executed_task_count / skipped_task_count。"
        task_count = int(item.get("task_count", 0) or 0)
        due_task_count = int(item.get("due_task_count", 0) or 0)
        executed_task_count = int(item.get("executed_task_count", 0) or 0)
        skipped_task_count = int(item.get("skipped_task_count", 0) or 0)
        return (
            "任务影响范围："
            f"task_count={task_count} / "
            f"due_task_count={due_task_count} / "
            f"executed_task_count={executed_task_count} / "
            f"skipped_task_count={skipped_task_count}"
        )

    @staticmethod
    def _runner_patrol_filter_link(
        *,
        label: str,
        patrol_filter: str,
        severity_filter: str,
        active: bool,
    ) -> str:
        query_parts: list[str] = []
        if patrol_filter:
            query_parts.append(f"patrol_filter={quote(patrol_filter, safe='')}")
        if severity_filter:
            query_parts.append(f"severity_filter={quote(severity_filter, safe='')}")
        suffix = f"?{'&'.join(query_parts)}" if query_parts else ""
        class_name = "pill" if active else "pill"
        return f"<a class='{class_name}' href='/runner{suffix}'>{escape(label)}</a>"

    @staticmethod
    def _status_pill(label: str, *, tone: str = "ok") -> str:
        pill_tone = {
            "danger": "pill-danger",
            "warning": "pill-warning",
            "ok": "pill-ok",
        }.get(tone, "pill-ok")
        return f"<span class='pill {pill_tone}'>{escape(label)}</span>"

    @staticmethod
    def _workflow_state_tone(value: str) -> str:
        state = str(value or "").strip().lower()
        if state in {"resolved", "approved"}:
            return "ok"
        if state in {"ignored", "confirmed", "assigned", "pending_confirmation", "approved_with_risk"}:
            return "warning"
        if state in {"processing", "reviewing", "rejected"}:
            return "danger"
        return "ok"

    @staticmethod
    def _filter_runner_patrols(
        items: list[dict[str, Any]],
        *,
        patrol_filter: str,
        severity_filter: str,
        keyword: str = "",
    ) -> list[dict[str, Any]]:
        filtered = list(items)
        if patrol_filter == "failed":
            filtered = [item for item in filtered if float(item.get("failed_rate", 0.0) or 0.0) > 0.0]
        elif patrol_filter == "offline":
            filtered = [item for item in filtered if float(item.get("offline_rate", 0.0) or 0.0) > 0.0]
        elif patrol_filter == "quarantined":
            filtered = [item for item in filtered if int(item.get("quarantined_device_count", 0) or 0) > 0]
        if severity_filter:
            filtered = [
                item
                for item in filtered
                if str(dict(item.get("severity", {}) or {}).get("level", "") or "") == severity_filter
            ]
        query = str(keyword or "").lower()
        if query:
            filtered = [
                item
                for item in filtered
                if query
                in " ".join(
                    str(value or "")
                    for value in (
                        item.get("cycle_index", ""),
                        item.get("generated_at", ""),
                        item.get("started_at", ""),
                        item.get("finished_at", ""),
                        item.get("task_count", ""),
                        item.get("executed_task_count", ""),
                        item.get("failed_rate", ""),
                        item.get("offline_rate", ""),
                        item.get("recovery_success_rate", ""),
                        item.get("quarantined_device_count", ""),
                        dict(item.get("severity", {}) or {}).get("level", ""),
                        dict(item.get("severity", {}) or {}).get("label", ""),
                        dict(item.get("severity", {}) or {}).get("reason", ""),
                    )
                ).lower()
            ]
        return filtered
