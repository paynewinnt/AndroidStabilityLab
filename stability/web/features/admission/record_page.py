from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from stability.scenario.registry import list_scenario_definitions

from .detail_page import AdmissionDetailPageMixin
from .golden_page import GoldenAdmissionPageMixin
from .quality_page import QualityPageMixin


class AdmissionRecordPageMixin(AdmissionDetailPageMixin, GoldenAdmissionPageMixin, QualityPageMixin):
    def _render_issues(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        body.extend([
            self._admin_page_header(
                "问题中心",
                subtitle="聚合问题以台账方式管理，认领、流转、评论和缺陷同步都在详情抽屉内完成。",
                breadcrumbs=[("首页", "/"), ("问题中心", "")],
                actions=[self._route_link("JSON API", "/api/issues")],
            ),
            self._admin_summary_strip(
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
            "<section class='panel admin-list-panel'>"
            + "<div class='admin-toolbar'>"
            + "<div class='admin-toolbar-heading'><strong>当前身份</strong><span>写操作会用当前身份记录协作动作。</span></div>"
            + "</div>"
            + self._current_actor_card(
                current_actor=dict(payload.get("current_actor", {}) or {}),
                actors=list(payload.get("actors", []) or []),
                current_path="/issues",
            )
            + "</section>",
            self._issue_admin_filter_bar(payload),
            self._issue_admin_workspace(payload),
        ])
        return self._layout(
            "问题中心",
            "先看影响面最大的聚合问题，也可以直接完成认领、评论和状态流转。",
            "".join(body),
        )

    def _issue_admin_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        return self._admin_filter_bar(
            action="/issues",
            values=filters,
            fields=[
                {"name": "keyword", "label": "关键词", "placeholder": "标题 / 指纹 / 责任人"},
                {
                    "name": "status",
                    "label": "状态",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "new", "label": "new"},
                        {"value": "assigned", "label": "assigned"},
                        {"value": "processing", "label": "processing"},
                        {"value": "confirmed", "label": "confirmed"},
                        {"value": "resolved", "label": "resolved"},
                        {"value": "ignored", "label": "ignored"},
                    ],
                },
                {
                    "name": "issue_type",
                    "label": "类型",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "crash", "label": "crash"},
                        {"value": "anr", "label": "anr"},
                        {"value": "performance", "label": "performance"},
                        {"value": "functional", "label": "functional"},
                        {"value": "compatibility", "label": "compatibility"},
                    ],
                },
                {
                    "name": "severity",
                    "label": "严重级别",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "critical", "label": "critical"},
                        {"value": "high", "label": "high"},
                        {"value": "medium", "label": "medium"},
                        {"value": "low", "label": "low"},
                    ],
                },
                {"name": "package_name", "label": "包名", "placeholder": "com.example"},
                {"name": "device_id", "label": "设备", "placeholder": "device id"},
                {
                    "name": "scenario",
                    "label": "场景",
                    "type": "select",
                    "options": [{"value": "", "label": "全部"}]
                    + [
                        {"value": str(item.value), "label": str(item.plain_label)}
                        for item in list_scenario_definitions()
                    ],
                },
                {"name": "created_from", "label": "开始日期", "type": "date"},
                {"name": "created_to", "label": "结束日期", "type": "date"},
            ],
        )

    def _issue_admin_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "issues-admin-table"
        columns = self._issue_admin_columns()
        toolbar = self._admin_toolbar(
            title="Top Issue",
            description="列表按聚合问题展示，点击详情后在抽屉里处理协作动作。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/issues'>刷新</a>",
            ],
        )
        table_html, drawers = self._issue_admin_table(payload, table_id=table_id, columns=columns)
        pagination = self._admin_pagination(
            base_path="/issues",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return "<section class='panel admin-list-panel'>" + toolbar + table_html + pagination + "</section>" + drawers

    @staticmethod
    def _issue_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "issue", "label": "问题"},
            {"key": "type", "label": "类型"},
            {"key": "severity", "label": "级别"},
            {"key": "state", "label": "状态"},
            {"key": "owner", "label": "责任人"},
            {"key": "scope", "label": "包名 / 设备 / 场景"},
            {"key": "occurrence", "label": "出现"},
            {"key": "affected", "label": "影响面"},
            {"key": "last_seen", "label": "最近出现"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _issue_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        issues = list(payload.get("issues", []) or [])
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for item_raw in issues:
            item = dict(item_raw or {})
            fingerprint = str(item.get("fingerprint", "") or "")
            title = str(item.get("title", "") or fingerprint or "未命名问题")
            drawer_id = f"admin-issue-detail-{self._dom_id_fragment(fingerprint)}"
            state = str(item.get("workflow_state", "") or "new")
            severity = str(item.get("severity", "") or "unknown")
            owner = str(item.get("assignee_display_name", "") or item.get("assignee_id", "") or "unassigned")
            packages = self._issue_scope_value(item.get("affected_packages", []) or [])
            devices = self._issue_scope_value(item.get("affected_devices", []) or [])
            scenarios = self._issue_scope_value(item.get("affected_scenarios", []) or [])
            affected = (
                f"{escape(str(item.get('affected_device_count', 0) or 0))} 设备 / "
                f"{escape(str(item.get('affected_run_count', 0) or 0))} Run / "
                f"{escape(str(item.get('affected_scenario_count', 0) or 0))} 场景"
            )
            rows.append(
                {
                    "select": f"<input type='checkbox' name='fingerprint' value='{escape(fingerprint, quote=True)}' />",
                    "issue": (
                        f"<strong title='{escape(title, quote=True)}'>{escape(title)}</strong>"
                        f"<div class='mono' title='{escape(fingerprint, quote=True)}'>{escape(fingerprint)}</div>"
                    ),
                    "type": self._admin_status(str(item.get("issue_type", "") or "n/a"), tone="muted"),
                    "severity": self._admin_status(severity, tone=self._issue_severity_tone(severity)),
                    "state": self._admin_status(state, tone=self._workflow_state_tone(state)),
                    "owner": escape(owner),
                    "scope": (
                        f"<span class='mono' title='{escape(packages, quote=True)}'>{escape(packages)}</span>"
                        f"<div class='meta' title='{escape(devices, quote=True)}'>device={escape(devices)}</div>"
                        f"<div class='meta' title='{escape(scenarios, quote=True)}'>scenario={escape(scenarios)}</div>"
                    ),
                    "occurrence": escape(str(item.get("occurrence_count", 0) or 0)),
                    "affected": affected,
                    "last_seen": escape(self._display_datetime(item.get("last_seen_at", "")) or "n/a"),
                    "actions": "<div class='admin-table-actions'>" + self._admin_drawer_button("详情 / 处理", drawer_id) + "</div>",
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"问题详情 · {title}",
                    self._issue_admin_detail(item),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前没有匹配问题。"), "".join(drawers)

    @staticmethod
    def _issue_scope_value(values: Sequence[Any], *, limit: int = 3) -> str:
        seen: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.append(text)
        if not seen:
            return "n/a"
        suffix = f" +{len(seen) - limit}" if len(seen) > limit else ""
        return ", ".join(seen[:limit]) + suffix

    def _issue_admin_detail(self, item: Mapping[str, Any]) -> str:
        fields = [
            ("指纹", item.get("fingerprint", "")),
            ("类型", item.get("issue_type", "")),
            ("级别", item.get("severity", "")),
            ("状态", item.get("workflow_state", "new") or "new"),
            ("责任人", item.get("assignee_display_name", "") or item.get("assignee_id", "") or "unassigned"),
            ("出现次数", item.get("occurrence_count", 0)),
            ("影响设备", item.get("affected_device_count", 0)),
            ("影响包名", ", ".join(item.get("affected_packages", [])[:4])),
            ("影响场景", ", ".join(item.get("affected_scenarios", [])[:4])),
            ("最近出现", self._display_datetime(item.get("last_seen_at", "")) or "n/a"),
        ]
        details = "".join(
            "<div class='admin-detail-item'>"
            f"<small>{escape(str(label))}</small>"
            f"<strong>{escape(str(value or 'n/a'))}</strong>"
            "</div>"
            for label, value in fields
        )
        return (
            "<div class='admin-detail-grid'>"
            + details
            + "</div>"
            + self._issue_cards([dict(item)])
        )

    @staticmethod
    def _issue_severity_tone(value: str) -> str:
        severity = str(value or "").lower()
        if severity in {"critical", "high"}:
            return "danger"
        if severity in {"medium", "warning"}:
            return "warning"
        if severity in {"low", "info"}:
            return "muted"
        return "ok"

    def _render_goldens(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        body = [
            self._admin_page_header(
                "Golden Suite",
                subtitle="以列表方式查看 golden case，可按类型、链路和期望结果快速筛选，再在抽屉内看明细。",
                breadcrumbs=[("首页", "/"), ("Golden Suite", "")],
                actions=[
                    self._route_link("JSON API", "/api/goldens"),
                    self._route_link("Diff", "/goldens/diff"),
                ],
            ),
            self._admin_summary_strip(
                [
                    ("Case 总数", summary["case_count"]),
                    ("全部 Case", summary.get("total_case_count", summary["case_count"])),
                    ("Layer 数", summary["layer_count"]),
                    ("Issue Type 数", summary["issue_type_count"]),
                    ("Expectation 数", summary["expectation_count"]),
                ]
            ),
            self._golden_suite_overview(payload),
            self._golden_admin_filter_bar(payload),
            self._golden_case_workspace(payload),
        ]
        return self._layout(
            "Golden Suite",
            "查看正式样本库、case 列表和单条样本 payload。",
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
            "对比两份 golden suite 的新增、删除、修改和字段级变化。",
            "".join(body),
        )

    def _render_admission(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        views = dict(payload.get("views", {}) or {})
        body = [
            self._admin_page_header(
                "准入中心",
                subtitle="以基线为主列表查看准入结果、风险和协作状态，详情与处理动作留在当前页面抽屉内。",
                breadcrumbs=[("首页", "/"), ("准入中心", "")],
                actions=[
                    self._route_link("JSON API", "/api/admission"),
                    self._route_link("Admission Cases", "/api/admission/cases"),
                ],
            ),
            self._admin_summary_strip(
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
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(title="当前身份", description="写操作会用当前身份记录协作动作。")
            + self._current_actor_card(
                current_actor=dict(payload.get("current_actor", {}) or {}),
                actors=list(payload.get("actors", []) or []),
                current_path="/admission",
            )
            + "</section>",
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(title="协作视图", description="按当前筛选结果聚合待处理、待确认和带风险放行。")
            + self._admission_view_cards(views)
            + "</section>",
            self._admission_admin_filter_bar(payload),
            self._admission_admin_workspace(payload),
        ]
        return self._layout(
            "准入中心",
            "查看准入单协作视图、质量门禁结果、当前报告、latest audit 和基线历史。",
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
