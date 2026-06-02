from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from stability.web import renderers as portal_renderers
from stability.web.features.core.json_api_page import CoreJsonApiPageMixin


class CorePageMixin(CoreJsonApiPageMixin):
    @staticmethod
    def _core_select_options(
        values: Sequence[str], *, labels: Mapping[str, str] | None = None
    ) -> list[dict[str, str]]:
        label_map = dict(labels or {})
        return [{"value": "", "label": "全部"}] + [
            {"value": str(value), "label": label_map.get(str(value), str(value))}
            for value in values
            if str(value or "").strip()
        ]

    def _render_home(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        metrics = [
            ("平台模式", self._portal_mode()),
            ("设备总数", summary["device_count"]),
            ("在线设备", summary["online_device_count"]),
            ("可调度设备", summary["schedulable_device_count"]),
            ("最近失败 Run", summary["failed_run_count"]),
            ("性能样本", summary["performance_sample_count"]),
            ("Trace", summary["performance_trace_count"]),
            ("Top Issue", summary["top_issue_count"]),
            ("准入基线", summary["baseline_count"]),
            ("Runner", summary["runner_status"]),
            ("平台健康", summary.get("platform_health_status", "unknown")),
            ("日报轮次", summary["runner_daily_report_round_count"]),
        ]
        sections = [
            portal_renderers.metric_grid(metrics, class_name="grid home-summary-grid"),
            self._section(
                "Runner 摘要卡",
                [
                    self._runner_home_summary_cards(
                        dict(payload.get("runner", {}) or {})
                    )
                ],
            ),
            self._section(
                "平台自监控",
                [
                    self._platform_health_card(
                        dict(payload.get("platform_health", {}) or {})
                    )
                ],
            ),
            self._section(
                "最近性能采样",
                [
                    self._performance_home_summary_card(
                        dict(payload.get("performance", {}) or {})
                    )
                ],
            ),
            self._section(
                "平台状态",
                [
                    f"<p>最近生成时间：{escape(str(payload['generated_at']))}</p>",
                    f"<p>{escape(self._sync_hint(payload.get('device_sync')))}</p>",
                ],
            ),
            self._section(
                "后台巡检",
                [
                    self._runner_status_card(
                        dict(payload.get("runner", {}) or {}), include_link=True
                    )
                ],
            ),
            self._section(
                "今日可看的东西",
                [
                    self._mini_device_list(payload["devices"]),
                    self._mini_run_list(payload["runs"]),
                    self._mini_issue_list(payload["issues"]),
                ],
            ),
            self._section(
                "准入基线概览",
                [self._baseline_cards(payload["baselines"])],
            ),
        ]
        return self._layout(
            "Web 首页",
            "先把平台今天发生了什么、能不能跑、哪类问题最突出，直接放到一个入口里。",
            "".join(sections),
        )

    def _render_rules(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        entrypoint = dict(payload.get("entrypoint", {}) or {})
        validation = dict(entrypoint.get("validation", {}) or {})
        preview = dict(payload.get("preview", {}) or {})
        metrics = [
            ("来源", summary.get("source", "fallback")),
            ("当前版本", summary.get("current_version", "n/a") or "n/a"),
            (
                "校验",
                "valid" if summary.get("validation_valid", False) else "needs check",
            ),
            ("错误", summary.get("error_count", 0)),
            ("警告", summary.get("warning_count", 0)),
            ("可编辑字段", summary.get("editable_field_count", 0)),
        ]
        preview_block = (
            "<pre class='mono'>"
            + escape(json.dumps(preview, ensure_ascii=False, indent=2))
            + "</pre>"
            if preview
            else self._notice(
                "可用 query 参数预览：/rules?set.version=candidate-v2 或 /api/rules?set.version=candidate-v2。",
                tone="warning",
            )
        )
        body = [
            self._metric_grid(metrics),
            self._section(
                "规则入口摘要",
                [
                    "<ul class='link-list'>"
                    f"<li>配置路径：<span class='mono'>{escape(str(summary.get('config_path', '') or 'n/a'))}</span></li>"
                    f"<li>写入策略：<span class='mono'>{escape(str(summary.get('write_policy', '') or 'preview_only_no_config_write'))}</span></li>"
                    f"<li>API：<a href='/api/rules'>/api/rules</a>，Manifest：<a href='/api/manifest'>/api/manifest</a></li>"
                    "</ul>",
                ],
            ),
            self._section(
                "校验状态",
                [
                    self._notice(
                        "当前规则入口校验通过。"
                        if validation.get("valid", False)
                        else "当前规则入口需要校验或服务层暂未提供完整状态。",
                        tone="ok" if validation.get("valid", False) else "warning",
                    ),
                    "<pre class='mono'>"
                    + escape(json.dumps(validation, ensure_ascii=False, indent=2))
                    + "</pre>",
                ],
            ),
            self._section(
                "可编辑字段",
                [
                    "<div class='cards'>"
                    + "".join(
                        "<article class='card'><h3>"
                        + escape(str(field))
                        + "</h3><div class='meta'>必须通过 preview、diff、review、golden replay 和 baseline 审计流程验证。</div></article>"
                        for field in list(entrypoint.get("editable_fields", []) or [])
                    )
                    + "</div>"
                ],
            ),
            self._section(
                "风险提示与建议流程",
                [
                    "<div class='cards'>"
                    "<article class='card stack'><h3>风险提示</h3><ul class='link-list'>"
                    + "".join(
                        f"<li>{escape(str(item))}</li>"
                        for item in list(entrypoint.get("risk_prompts", []) or [])
                    )
                    + "</ul></article>"
                    "<article class='card stack'><h3>建议流程</h3><ul class='link-list'>"
                    + "".join(
                        f"<li><span class='mono'>{escape(str(item))}</span></li>"
                        for item in list(entrypoint.get("recommended_flow", []) or [])
                    )
                    + "</ul></article>"
                    "</div>",
                ],
            ),
            self._section(
                "相关策略文件",
                [
                    "<ul class='link-list'>"
                    + "".join(
                        f"<li><span class='mono'>{escape(str(path))}</span></li>"
                        for path in list(
                            entrypoint.get("related_policy_files", []) or []
                        )
                        if str(path)
                    )
                    + "</ul>",
                ],
            ),
            self._section("预览结果", [preview_block]),
        ]
        return self._layout(
            "规则中心",
            "只读展示规则配置入口、校验状态、风险提示和预览，不绕过审计直接写配置。",
            "".join(body),
        )

    def _render_platform(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        deployment = dict(payload.get("deployment", {}) or {})
        readiness = dict(payload.get("readiness", {}) or {})
        write_boundary = dict(payload.get("write_boundary", {}) or {})
        identity_capabilities = dict(payload.get("identity_capabilities", {}) or {})
        platform_health = dict(payload.get("platform_health", {}) or {})
        notes = list(payload.get("notes", []) or [])
        readiness_checks = dict(readiness.get("checks", {}) or {})
        mode = str(summary.get("portal_mode", "") or "local_ops_console")
        boundary_tone = "ok" if mode == "team_entry" else "warning"
        health_status = str(
            summary.get("platform_health_status", "unknown") or "unknown"
        )
        body = [
            self._admin_page_header(
                "平台说明",
                subtitle="说明 Android Stability Lab 的运行模式、服务就绪、身份边界和接口合同。",
                breadcrumbs=[("首页", "/"), ("平台说明", "")],
                actions=[],
            ),
            self._admin_summary_strip(
                [
                    ("平台模式", summary.get("portal_mode", "local_ops_console")),
                    ("平台健康", health_status),
                    (
                        "Ready",
                        "ok" if summary.get("readiness_ok", False) else "blocked",
                    ),
                    ("页面数", summary.get("page_count", 0)),
                    ("API 数", summary.get("api_count", 0)),
                    ("可写动作", summary.get("write_action_count", 0)),
                ]
            ),
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(
                title="平台定位",
                description="面向 Android 稳定性验证和值班排障的统一运维控制台。",
            )
            + self._notice(
                "平台聚合设备状态、任务执行、性能采样、报告产物、问题流转和准入结论，帮助团队在同一运行上下文中判断风险、追踪异常和完成交接。",
                tone="ok",
            )
            + self._platform_detail_grid(
                [
                    (
                        "平台用途",
                        "统一沉淀稳定性任务、Run、监控采样、证据产物和问题状态",
                    ),
                    (
                        "覆盖链路",
                        "设备可用性、ADB 诊断、长稳任务、性能趋势、报告归档和准入判断",
                    ),
                    ("使用对象", "值班同学、测试开发、稳定性负责人和外部系统接入方"),
                    (
                        "边界原则",
                        "读取面向共享观测；写操作必须具备身份解析、权限检查和审计记录",
                    ),
                ]
            )
            + "</section>",
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(
                title="运行边界",
                description="先确认入口是否只用于本机运维，还是已经作为团队共享入口。",
                actions=[],
            )
            + self._notice(
                "团队共享入口模式：所有查看者默认看到同一份平台数据，写操作由服务端解析身份并写审计。"
                if mode == "team_entry"
                else "当前 Web 入口按本地运维控制台设计；如要开放给团队，需要显式 public_base_url、反向代理和身份边界。",
                tone=boundary_tone,
            )
            + self._platform_detail_grid(
                [
                    (
                        "deployment",
                        deployment.get("deployment_label", "")
                        or "Android Stability Lab",
                    ),
                    ("mode", deployment.get("mode", "") or "local_ops_console"),
                    ("local base url", deployment.get("local_base_url", "")),
                    ("public base url", deployment.get("public_base_url", "")),
                    (
                        "allow remote",
                        str(deployment.get("allow_remote_access", False)).lower(),
                    ),
                    ("team boundary", deployment.get("team_boundary_version", "")),
                    (
                        "identity",
                        write_boundary.get(
                            "write_identity_resolution", "server_resolved_identity"
                        ),
                    ),
                    (
                        "trusted SSO",
                        str(
                            identity_capabilities.get("trusted_sso_header", False)
                        ).lower(),
                    ),
                ]
            )
            + "</section>",
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(
                title="就绪检查",
                description="关键 service、平台健康与共享入口边界。",
                table_id="platform-readiness-table",
                columns=self._platform_readiness_columns(),
                actions=[],
            )
            + self._notice(
                "平台关键服务已就绪。"
                if readiness.get("ok", False)
                else "仍有关键服务未就绪，当前入口不应作为正式团队入口使用。",
                tone="ok" if readiness.get("ok", False) else "danger",
            )
            + self._admin_table(
                table_id="platform-readiness-table",
                columns=self._platform_readiness_columns(),
                rows=self._platform_readiness_rows(readiness_checks),
                empty_text="当前没有 readiness 检查项。",
            )
            + self._platform_health_summary(platform_health)
            + "</section>",
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(
                title="安全与合同", description="写边界、审计字段和回调签名合同。"
            )
            + self._platform_detail_grid(
                [
                    (
                        "shared read surface",
                        str(write_boundary.get("shared_read_surface", True)).lower(),
                    ),
                    (
                        "same data for all",
                        str(
                            write_boundary.get("same_data_for_all_viewers", True)
                        ).lower(),
                    ),
                    (
                        "local session",
                        str(identity_capabilities.get("local_session", False)).lower(),
                    ),
                    (
                        "trusted SSO headers",
                        ", ".join(
                            str(item)
                            for item in list(
                                identity_capabilities.get("trusted_sso_headers", [])
                                or []
                            )
                        ),
                    ),
                    (
                        "request headers",
                        ", ".join(
                            str(item)
                            for item in list(
                                write_boundary.get("request_headers", []) or []
                            )
                        ),
                    ),
                    (
                        "audit fields",
                        ", ".join(
                            str(item)
                            for item in list(
                                write_boundary.get("write_audit_fields", []) or []
                            )
                        ),
                    ),
                    ("readiness endpoints", "/ready, /health, /api/platform-health"),
                    ("schema endpoints", "/api/manifest, /api/openapi.json"),
                ]
            )
            + "<details class='compact-details'><summary>回调安全合同</summary><pre class='mono compact-pre'>"
            + escape(
                json.dumps(
                    dict(payload.get("callback_contract", {}) or {}),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            + "</pre></details>"
            + "<details class='compact-details'><summary>使用建议</summary><ul class='link-list'>"
            + "".join(f"<li>{escape(str(item))}</li>" for item in notes)
            + "</ul></details>"
            + "</section>",
        ]
        return self._layout(
            "平台说明",
            "当前入口的运行模式、服务就绪和写操作边界。",
            "".join(body),
        )

    @staticmethod
    def _platform_detail_grid(fields: Sequence[tuple[str, Any]]) -> str:
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
        )

    @staticmethod
    def _platform_readiness_columns() -> list[dict[str, Any]]:
        return [
            {"key": "check", "label": "检查项"},
            {"key": "status", "label": "状态"},
        ]

    def _platform_readiness_rows(
        self, readiness_checks: Mapping[str, Any]
    ) -> list[dict[str, str]]:
        rows = []
        for name, value in readiness_checks.items():
            ready = bool(value)
            rows.append(
                {
                    "check": f"<span class='mono'>{escape(str(name))}</span>",
                    "status": self._admin_status(
                        "ready" if ready else "missing",
                        tone="ok" if ready else "danger",
                    ),
                }
            )
        return rows

    def _platform_health_summary(self, platform_health: Mapping[str, Any]) -> str:
        if not platform_health:
            return ""
        summary = dict(platform_health.get("summary", {}) or {})
        fields = [
            ("status", platform_health.get("status", "unknown")),
            ("severity", platform_health.get("severity", "unknown")),
            ("fail", summary.get("fail_count", 0)),
            ("warn", summary.get("warn_count", 0)),
            ("ok", summary.get("ok_count", 0)),
            ("snapshot", platform_health.get("generated_at", "")),
        ]
        return (
            "<details class='compact-details'><summary>平台健康摘要</summary>"
            + self._platform_detail_grid(fields)
            + "</details>"
        )

    def _render_doctor(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        webhook_hint = (
            "<a href='/doctor?check_webhooks=1'>显式发送飞书诊断 ping</a>"
            if not bool(payload.get("check_webhooks", False))
            else "<a href='/doctor'>切回只读配置检查</a>"
        )
        body = [
            self._admin_page_header(
                "诊断中心",
                subtitle="集中检查本地运行环境、设备链路、监控 backend 和集成 webhook。",
                breadcrumbs=[("首页", "/"), ("诊断中心", "")],
                actions=[
                    self._route_link("JSON API", "/api/doctor"),
                    self._route_link("平台健康", "/api/platform-health"),
                ],
            ),
            self._admin_summary_strip(
                [
                    ("总状态", "ok" if payload.get("ok", False) else "blocked"),
                    ("通过", summary.get("ok", 0)),
                    ("警告", summary.get("warn", 0)),
                    ("失败", summary.get("fail", 0)),
                    ("跳过", summary.get("skipped", 0)),
                    ("当前筛选", summary.get("filtered", summary.get("total", 0))),
                    ("全部诊断", summary.get("total", 0)),
                ]
            ),
            "<section class='panel admin-list-panel'>"
            + self._admin_toolbar(
                title="怎么用",
                description="默认只做只读检查，显式开启 webhook 时才会发送诊断 ping。",
            )
            + "<div class='admin-detail-grid'>"
            "<div class='admin-detail-item'><small>命令行诊断</small><strong>python -m stability.cli doctor</strong></div>"
            "<div class='admin-detail-item'><small>设备诊断</small><strong>doctor --device-id ... --package-name ...</strong></div>"
            f"<div class='admin-detail-item'><small>Webhook</small><strong>{webhook_hint}</strong></div>"
            "<div class='admin-detail-item'><small>说明</small><strong>页面适合快速判断 Python / ADB / 设备 / runtime / config / 端口 / 监控 / outbox 哪一类异常。</strong></div>"
            "</div></section>",
            self._doctor_admin_filter_bar(payload),
            self._doctor_admin_workspace(payload),
        ]
        return self._layout(
            "诊断中心",
            "集中检查本地运行环境、设备链路、监控 backend 和集成 webhook。",
            "".join(body),
        )

    def _doctor_admin_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        options = dict(payload.get("filter_options", {}) or {})
        return self._admin_filter_bar(
            action="/doctor",
            values=filters,
            fields=[
                {
                    "name": "keyword",
                    "label": "关键词",
                    "placeholder": "检查项 / 摘要 / details",
                },
                {
                    "name": "status",
                    "label": "状态",
                    "type": "select",
                    "options": self._core_select_options(
                        list(options.get("statuses", []) or [])
                    ),
                },
                {
                    "name": "device_id",
                    "label": "设备 ID",
                    "placeholder": "USB serial 或 ip:port",
                },
                {
                    "name": "package_name",
                    "label": "包名",
                    "placeholder": "可选，例如 com.example.app",
                },
                {
                    "name": "check_webhooks",
                    "label": "Webhook",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "只读检查"},
                        {"value": "1", "label": "发送诊断 ping"},
                    ],
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

    def _doctor_admin_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "doctor-admin-table"
        columns = self._doctor_admin_columns()
        toolbar = self._admin_toolbar(
            title="单设备深度诊断 / 诊断项",
            description="可按状态、设备和包名筛选，详情在抽屉内查看。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/doctor'>刷新</a>",
                "<a class='button secondary' href='/api/doctor'>导出 JSON</a>",
            ],
        )
        table_html, drawers = self._doctor_admin_table(
            payload, table_id=table_id, columns=columns
        )
        pagination = self._admin_pagination(
            base_path="/doctor",
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
    def _doctor_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "name", "label": "诊断项"},
            {"key": "status", "label": "状态"},
            {"key": "context", "label": "设备 / 包名"},
            {"key": "summary", "label": "摘要"},
            {"key": "detail_keys", "label": "Details", "default_visible": False},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _doctor_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        status_order = {"fail": 0, "warn": 1, "ok": 2, "skipped": 3}
        checks = [dict(item or {}) for item in list(payload.get("checks", []) or [])]
        checks.sort(
            key=lambda item: (
                status_order.get(str(item.get("status", "")), 9),
                str(item.get("name", "")),
            )
        )
        device_id = str(payload.get("device_id", "") or "n/a")
        package_name = str(payload.get("package_name", "") or "n/a")
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for check in checks:
            name = str(check.get("name", "") or "unknown")
            status = str(check.get("status", "") or "unknown")
            details = dict(check.get("details", {}) or {})
            drawer_id = f"admin-doctor-detail-{self._dom_id_fragment(name)}"
            detail_check = {
                **check,
                "context": {"device_id": device_id, "package_name": package_name},
            }
            rows.append(
                {
                    "select": f"<input type='checkbox' name='check' value='{escape(name, quote=True)}' />",
                    "name": f"<strong>{escape(name)}</strong>",
                    "status": self._admin_status(
                        status, tone=self._doctor_status_tone(status)
                    ),
                    "context": (
                        f"<span class='mono' title='{escape(device_id, quote=True)}'>{escape(device_id)}</span>"
                        f"<div class='meta' title='{escape(package_name, quote=True)}'>package={escape(package_name)}</div>"
                    ),
                    "summary": escape(str(check.get("summary", "") or "")),
                    "detail_keys": escape(
                        ", ".join(str(key) for key in details.keys()) or "n/a"
                    ),
                    "actions": "<div class='admin-table-actions'>"
                    + self._admin_drawer_button("查看诊断细节", drawer_id)
                    + "</div>",
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"诊断项 · {name}",
                    self._doctor_admin_detail(detail_check),
                )
            )
        return self._admin_table(
            table_id=table_id,
            columns=columns,
            rows=rows,
            empty_text="当前没有匹配诊断项。",
        ), "".join(drawers)

    def _doctor_admin_detail(self, check: Mapping[str, Any]) -> str:
        details = dict(check.get("details", {}) or {})
        context = dict(check.get("context", {}) or {})
        fields = [
            ("诊断项", check.get("name", "")),
            ("状态", check.get("status", "")),
            ("设备", context.get("device_id", "")),
            ("包名", context.get("package_name", "")),
            ("摘要", check.get("summary", "")),
            ("Detail Keys", ", ".join(str(key) for key in details.keys()) or "n/a"),
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
            + "</div><pre class='mono doctor-detail-pre'>"
            + escape(json.dumps(details, ensure_ascii=False, indent=2))
            + "</pre>"
        )

    @staticmethod
    def _doctor_status_tone(value: str) -> str:
        status = str(value or "").lower()
        if status == "fail":
            return "danger"
        if status == "warn":
            return "warning"
        if status == "skipped":
            return "muted"
        return "ok"

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
            self._notice(
                "查看长稳默认值和可覆盖参数；“套用创建任务”会跳到任务大厅并预填创建长稳任务表单。",
                tone="ok",
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


__all__ = ["CorePageMixin"]
