from __future__ import annotations

import json
from html import escape
from urllib.parse import quote
from typing import Any, Mapping, Sequence


class LongRunTemplatesPageMixin:
    def _render_long_run_templates(self, payload: dict[str, Any]) -> str:
        templates = list(payload.get("templates", []) or [])
        selected = dict(payload.get("template", {}) or {})
        plan = dict(payload.get("plan", {}) or {})
        if payload.get("preview_only") and selected:
            return self._layout(
                "长稳模板计划预览",
                "只展示当前模板的计划预览。",
                self._long_run_template_preview_panel(payload, selected, plan),
            )
        body = [
            self._admin_page_header(
                "长稳运行模板",
                subtitle="集中查看长稳模板族的默认值、可覆盖参数和入口计划，也可以一键套用到任务大厅。",
                breadcrumbs=[("首页", "/"), ("长稳模板", "")],
                actions=[
                    self._route_link("JSON API", "/api/long-run-templates"),
                    self._route_link("去 Runner 配置", "/runner"),
                ],
            ),
            self._admin_summary_strip(
                [
                    ("模板数量", payload.get("template_count", 0)),
                    (
                        "全部模板",
                        payload.get(
                            "total_template_count", payload.get("template_count", 0)
                        ),
                    ),
                    ("来源", payload.get("source", "fallback")),
                    ("Runner", "/runner"),
                    ("API", "/api/long-run-templates"),
                ]
            ),
            self._long_run_template_filter_bar(payload),
            self._long_run_template_workspace(payload, templates),
            self._long_run_template_preview_panel(payload, selected, plan)
            if selected
            else "",
        ]
        return self._layout(
            "长稳运行模板",
            "集中查看长稳模板族的默认值、可覆盖参数和入口计划，也可以一键套用到任务大厅创建长稳任务。",
            "".join(body),
        )

    def _long_run_template_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        options = dict(payload.get("filter_options", {}) or {})
        return self._admin_filter_bar(
            action="/long-run-templates",
            values=filters,
            hidden={"template_key": payload.get("template_key", "") or ""},
            fields=[
                {
                    "name": "keyword",
                    "label": "关键词",
                    "placeholder": "模板名 / key / 作用 / tag",
                },
                {
                    "name": "template_type",
                    "label": "类型",
                    "type": "select",
                    "options": self._core_select_options(
                        list(options.get("template_types", []) or [])
                    ),
                },
                {
                    "name": "page_size",
                    "label": "每页",
                    "type": "select",
                    "options": [
                        {"value": "10", "label": "10"},
                        {"value": "20", "label": "20"},
                        {"value": "50", "label": "50"},
                    ],
                },
            ],
        )

    def _long_run_template_workspace(
        self, payload: Mapping[str, Any], templates: Sequence[Mapping[str, Any]]
    ) -> str:
        table_id = "long-run-templates-admin-table"
        columns = self._long_run_template_columns()
        toolbar = self._admin_toolbar(
            title="模板列表",
            description="按模板维度查看类型、间隔、轮次和套用入口。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/long-run-templates'>刷新</a>",
                "<a class='button secondary' href='/api/long-run-templates'>导出 JSON</a>",
                "<a class='button secondary' href='/runner'>去 Runner 配置</a>",
            ],
        )
        table_html, drawers = self._long_run_template_table(
            templates, table_id=table_id, columns=columns
        )
        pagination = self._admin_pagination(
            base_path="/long-run-templates",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(
                dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20
            ),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return (
            "<section class='panel admin-list-panel'>"
            + toolbar
            + table_html
            + pagination
            + "</section>"
            + drawers
        )

    @staticmethod
    def _long_run_template_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "template", "label": "模板"},
            {"key": "type", "label": "类型"},
            {"key": "interval", "label": "间隔"},
            {"key": "rounds", "label": "轮次"},
            {"key": "devices", "label": "设备"},
            {"key": "rotation", "label": "轮转", "default_visible": False},
            {"key": "tags", "label": "标签", "default_visible": False},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _long_run_template_table(
        self,
        templates: Sequence[Mapping[str, Any]],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for item_raw in templates:
            template = dict(item_raw or {})
            key = self._long_run_template_key(template)
            defaults = dict(template.get("defaults", {}) or {})
            tags = list(
                template.get("default_tags", []) or defaults.get("tags", []) or []
            )
            drawer_id = f"admin-long-run-template-{self._dom_id_fragment(key)}"
            purpose = str(
                template.get("chinese_purpose", "")
                or template.get("chinese_explanation", "")
                or template.get("description", "")
                or "长稳运行模板默认值。"
            )
            rows.append(
                {
                    "select": f"<input type='checkbox' name='template_key' value='{escape(key, quote=True)}' />",
                    "template": (
                        f"<strong>{escape(str(template.get('name', '') or key or '未命名模板'))}</strong>"
                        f"<div class='mono'>{escape(key)}</div>"
                        f"<div class='meta'>作用：{escape(purpose)}</div>"
                    ),
                    "type": escape(self._long_run_template_type(template)),
                    "interval": f"{escape(str(defaults.get('interval_minutes', '-') or '-'))} min",
                    "rounds": f"{escape(str(defaults.get('max_rounds', '-') or '-'))} rounds",
                    "devices": escape(
                        str(defaults.get("desired_device_count", "-") or "-")
                    ),
                    "rotation": escape(
                        str(defaults.get("rotation_strategy", "-") or "-")
                    ),
                    "tags": " ".join(
                        f"<span class='pill muted'>{escape(str(tag))}</span>"
                        for tag in tags
                    )
                    or "n/a",
                    "actions": (
                        "<div class='admin-table-actions'>"
                        + self._admin_drawer_button("详情", drawer_id)
                        + (
                            f"<a class='button secondary' href='/long-run-templates?template_key={quote(key)}&amp;preview_only=1' "
                            f"data-file-preview-link='1' data-file-preview-title='预览计划' data-file-preview-path='{escape(key, quote=True)}'>预览计划</a>"
                        )
                        + (
                            f"<a class='button secondary' href='/tasks?long_run_template={quote(key)}' "
                            f"data-file-preview-link='1' data-file-preview-title='套用创建任务' data-file-preview-path='{escape(key, quote=True)}'>套用创建任务</a>"
                        )
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"长稳模板 · {template.get('name', key)}",
                    self._long_run_template_detail(template),
                )
            )
        return self._admin_table(
            table_id=table_id,
            columns=columns,
            rows=rows,
            empty_text="当前没有可展示的长稳模板。",
        ), "".join(drawers)

    @staticmethod
    def _long_run_template_key(template: Mapping[str, Any]) -> str:
        return str(
            template.get("template_key", "")
            or template.get("template_id", "")
            or template.get("key", "")
            or ""
        )

    @staticmethod
    def _long_run_template_type(template: Mapping[str, Any]) -> str:
        defaults = dict(template.get("defaults", {}) or {})
        return str(
            template.get("template_type", "")
            or defaults.get("template_type", "")
            or "n/a"
        )

    def _long_run_template_detail(self, template: Mapping[str, Any]) -> str:
        defaults = dict(template.get("defaults", {}) or {})
        overridable = list(template.get("overridable_parameters", []) or [])
        risk_notes = list(template.get("risk_notes", []) or [])
        fields = [
            ("Key", self._long_run_template_key(template)),
            ("名称", template.get("name", "")),
            ("类型", self._long_run_template_type(template)),
            ("间隔", f"{defaults.get('interval_minutes', '-')} min"),
            ("轮次", defaults.get("max_rounds", "-")),
            ("设备", defaults.get("desired_device_count", "-")),
            ("轮转", defaults.get("rotation_strategy", "-")),
            ("中文解释", template.get("chinese_explanation", "") or "n/a"),
            (
                "作用",
                template.get("chinese_purpose", "")
                or template.get("description", "")
                or "n/a",
            ),
        ]
        key = self._long_run_template_key(template)
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
            + (
                "<div class='notice warning'>"
                + "；".join(escape(str(item)) for item in risk_notes)
                + "</div>"
                if risk_notes
                else ""
            )
            + (
                f"<p><a href='/long-run-templates?template_key={quote(key)}&amp;preview_only=1' "
                f"data-file-preview-link='1' data-file-preview-title='预览计划' data-file-preview-path='{escape(key, quote=True)}'>预览计划</a>"
                f" / <a href='/tasks?long_run_template={quote(key)}' data-file-preview-link='1' "
                f"data-file-preview-title='套用创建任务' data-file-preview-path='{escape(key, quote=True)}'>套用创建任务</a></p>"
            )
            + "<details class='compact-details'><summary>默认值 / 可覆盖参数</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(defaults, ensure_ascii=False, indent=2))
            + "</pre><pre class='mono compact-pre'>"
            + escape(json.dumps(overridable, ensure_ascii=False, indent=2))
            + "</pre></details>"
        )

    def _long_run_template_preview_panel(
        self,
        payload: Mapping[str, Any],
        selected: Mapping[str, Any],
        plan: Mapping[str, Any],
    ) -> str:
        selected_key = str(
            payload.get("template_key", "")
            or selected.get("template_key", "")
            or selected.get("template_id", "")
            or ""
        )
        selected_defaults = dict(selected.get("defaults", {}) or {})
        override_values = dict(payload.get("overrides", {}) or {})
        override_fields = [
            (
                "interval_minutes",
                "间隔分钟",
                selected_defaults.get("interval_minutes", "60"),
            ),
            ("max_rounds", "最大轮次", selected_defaults.get("max_rounds", "12")),
            (
                "desired_device_count",
                "期望设备数",
                selected_defaults.get("desired_device_count", "2"),
            ),
            ("primary_device_ids", "主设备 ID，逗号分隔", ""),
            ("backup_device_ids", "备用设备 ID，逗号分隔", ""),
            ("task_name", "任务名", ""),
        ]
        override_inputs = "".join(
            "<label>"
            f"{escape(label)}"
            f"<input name='override' value='{escape(str(key))}={escape(str(override_values.get(key, default)))}' />"
            "</label>"
            for key, label, default in override_fields
        )
        plan_sections = []
        for title, key in (
            ("无人值守配置", "configure_kwargs"),
            ("Runner 参数", "runner_kwargs"),
            ("任务元数据建议", "task_metadata_suggestions"),
        ):
            if key in plan:
                plan_sections.append(
                    "<details class='card compact-details'>"
                    f"<summary>{escape(title)} JSON</summary>"
                    "<pre class='mono compact-pre'>"
                    + escape(
                        json.dumps(plan.get(key, {}), ensure_ascii=False, indent=2)
                    )
                    + "</pre></details>"
                )
        if plan.get("notes"):
            plan_sections.append(
                "<article class='card compact-note-card'><h3>说明</h3>"
                + "".join(
                    f"<p>{escape(str(item))}</p>"
                    for item in list(plan.get("notes", []) or [])
                )
                + "</article>"
            )
        return (
            "<section class='panel admin-list-panel long-run-template-preview'>"
            + self._admin_toolbar(
                title="模板计划预览",
                description="预览当前模板计划。",
                actions=[
                    (
                        f"<a class='button secondary' href='/tasks?long_run_template={quote(selected_key)}' "
                        f"data-file-preview-link='1' data-file-preview-title='套用创建任务' data-file-preview-path='{escape(selected_key, quote=True)}'>套用创建任务</a>"
                    ),
                    "<a class='button secondary' href='/runner'>去 Runner 配置</a>",
                ],
            )
            + f"<form method='get' action='/long-run-templates' class='compact-long-run-preview-form'>"
            + f"<input type='hidden' name='template_key' value='{escape(selected_key, quote=True)}' />"
            + (
                "<input type='hidden' name='preview_only' value='1' />"
                if payload.get("preview_only")
                else ""
            )
            + f"<div class='form-grid-three'>{override_inputs}</div>"
            + "<div class='form-actions'><button type='submit'>预览覆盖参数</button></div></form>"
            + "<div class='long-run-plan-grid'>"
            + "".join(plan_sections)
            + "</div><details class='compact-details'><summary>原始 JSON</summary><pre class='mono compact-pre'>"
            + escape(
                json.dumps(
                    {
                        "template_key": selected_key,
                        "template": selected,
                        "overrides": payload.get("overrides", {}),
                        "plan": plan,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            + "</pre></details></section>"
        )
