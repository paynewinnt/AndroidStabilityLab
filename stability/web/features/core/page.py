from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.parse import quote
from stability.web import renderers as portal_renderers


class CorePageMixin:
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
                [self._runner_home_summary_cards(dict(payload.get("runner", {}) or {}))],
            ),
            self._section(
                "平台自监控",
                [self._platform_health_card(dict(payload.get("platform_health", {}) or {}))],
            ),
            self._section(
                "最近性能采样",
                [self._performance_home_summary_card(dict(payload.get("performance", {}) or {}))],
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
                [self._runner_status_card(dict(payload.get("runner", {}) or {}), include_link=True)],
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
            self._section(
                "可用 API",
                [
                    "<ul class='link-list'>"
                    + "".join(
                        f"<li><a href='{escape(item['path'])}'>{escape(item['label'])}</a></li>"
                        for item in payload["api_endpoints"]
                    )
                    + "</ul>"
                ],
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
            ("校验", "valid" if summary.get("validation_valid", False) else "needs check"),
            ("错误", summary.get("error_count", 0)),
            ("警告", summary.get("warning_count", 0)),
            ("可编辑字段", summary.get("editable_field_count", 0)),
        ]
        preview_block = (
            "<pre class='mono'>" + escape(json.dumps(preview, ensure_ascii=False, indent=2)) + "</pre>"
            if preview
            else self._notice("可用 query 参数预览：/rules?set.version=candidate-v2 或 /api/rules?set.version=candidate-v2。页面不会直接写 config 文件。", tone="warning")
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
                        "当前规则入口校验通过。" if validation.get("valid", False) else "当前规则入口需要校验或服务层暂未提供完整状态。",
                        tone="ok" if validation.get("valid", False) else "warning",
                    ),
                    "<pre class='mono'>" + escape(json.dumps(validation, ensure_ascii=False, indent=2)) + "</pre>",
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
                    + "".join(f"<li>{escape(str(item))}</li>" for item in list(entrypoint.get("risk_prompts", []) or []))
                    + "</ul></article>"
                    "<article class='card stack'><h3>建议流程</h3><ul class='link-list'>"
                    + "".join(f"<li><span class='mono'>{escape(str(item))}</span></li>" for item in list(entrypoint.get("recommended_flow", []) or []))
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
                        for path in list(entrypoint.get("related_policy_files", []) or [])
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
        surface = dict(payload.get("surface", {}) or {})
        write_boundary = dict(payload.get("write_boundary", {}) or {})
        identity_capabilities = dict(payload.get("identity_capabilities", {}) or {})
        notes = list(payload.get("notes", []) or [])
        readiness_checks = dict(readiness.get("checks", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("平台模式", summary.get("portal_mode", "local_ops_console")),
                    ("共享入口", summary.get("public_base_url", "n/a") or "n/a"),
                    ("页面数", summary.get("page_count", 0)),
                    ("API 数", summary.get("api_count", 0)),
                    ("可写动作", summary.get("write_action_count", 0)),
                    ("Ready", "ok" if summary.get("readiness_ok", False) else "blocked"),
                ]
            ),
            self._section(
                "部署摘要",
                [
                    "<ul class='link-list'>"
                    f"<li>deployment：{escape(str(deployment.get('deployment_label', '') or 'Android Stability Lab'))}</li>"
                    f"<li>mode：{escape(str(deployment.get('mode', '') or 'local_ops_console'))}</li>"
                    f"<li>local base url：<span class='mono'>{escape(str(deployment.get('local_base_url', '') or ''))}</span></li>"
                    f"<li>public base url：<span class='mono'>{escape(str(deployment.get('public_base_url', '') or ''))}</span></li>"
                    f"<li>ready endpoint：<a href='/ready'>/ready</a>，health endpoint：<a href='/health'>/health</a></li>"
                    f"<li>manifest：<a href='{escape(str(payload.get('api_manifest_path', '') or '/api/manifest'), quote=True)}'>/api/manifest</a>，openapi：<a href='{escape(str(payload.get('openapi_path', '') or '/api/openapi.json'), quote=True)}'>/api/openapi.json</a></li>"
                    "</ul>",
                ],
            ),
            self._section(
                "责任入口",
                [
                    "<ul class='link-list'>"
                    "<li>用户目录：<a href='/api/users'>/api/users</a>，统一展示 actor/profile 与外部身份。</li>"
                    "<li>责任同步：<a href='/api/responsibility'>/api/responsibility</a>，只读汇总 issue、admission、defect 和 release 责任字段。</li>"
                    "<li>设备池治理：<a href='/device-pools'>/device-pools</a>，面向调度前检查 group/team/tag 与不可调度原因。</li>"
                    "<li>快捷 ADB：<a href='/quick-adb'>/quick-adb</a>，按 Android 调用链路执行预置诊断命令。</li>"
                    "</ul>",
                ],
            ),
            self._section(
                "边界说明",
                [
                    self._notice(
                        "团队共享入口模式下，所有查看者默认看到同一份平台数据；写操作继续要求服务端解析 identity，并稳定记录 request_id / audit_event_id / permission_check_id。",
                        tone="ok" if self._portal_mode() == "team_entry" else "warning",
                    ),
                    "<ul class='link-list'>"
                    f"<li>shared read surface：{escape(str(write_boundary.get('shared_read_surface', True)).lower())}</li>"
                    f"<li>same data for all viewers：{escape(str(write_boundary.get('same_data_for_all_viewers', True)).lower())}</li>"
                    f"<li>write identity resolution：{escape(str(write_boundary.get('write_identity_resolution', '') or 'server_resolved_identity'))}</li>"
                    f"<li>identity capabilities：local_session={escape(str(identity_capabilities.get('local_session', False)).lower())}，trusted_sso_header={escape(str(identity_capabilities.get('trusted_sso_header', False)).lower())}</li>"
                    f"<li>write audit fields：{escape(', '.join(str(item) for item in write_boundary.get('write_audit_fields', []) or []))}</li>"
                    "</ul>",
                ],
            ),
            self._section(
                "就绪状态",
                [
                    self._notice(
                        "平台关键服务已就绪。" if readiness.get("ok", False) else "仍有关键服务未就绪，当前共享入口不应作为正式团队入口使用。",
                        tone="ok" if readiness.get("ok", False) else "danger",
                    ),
                    "<ul class='link-list'>"
                    + "".join(
                        f"<li>{escape(name)}：{escape('ready' if bool(value) else 'missing')}</li>"
                        for name, value in readiness_checks.items()
                    )
                    + "</ul>",
                ],
            ),
            self._section(
                "页面与 API 清单",
                [
                    "<div class='cards'>"
                    "<article class='card stack'><h3>页面入口</h3><ul class='link-list'>"
                    + "".join(
                        f"<li><a href='{escape(str(item.get('path', '') or ''), quote=True)}'>{escape(str(item.get('label', '') or item.get('path', '')))}</a></li>"
                        for item in surface.get("pages", []) or []
                    )
                    + "</ul></article>"
                    "<article class='card stack'><h3>API 入口</h3><ul class='link-list'>"
                    + "".join(
                        f"<li><a href='{escape(str(item.get('path', '') or ''), quote=True)}'>{escape(str(item.get('path', '') or ''))}</a></li>"
                        for item in surface.get("api_endpoints", []) or []
                    )
                    + "</ul></article>"
                    "<article class='card stack'><h3>可写动作</h3><ul class='link-list'>"
                    + "".join(
                        f"<li><span class='mono'>{escape(str(item.get('path', '') or ''))}</span></li>"
                        for item in surface.get("write_actions", []) or []
                    )
                    + "</ul></article>"
                    "</div>",
                ],
            ),
            self._section(
                "使用建议",
                [
                    "<ul class='link-list'>"
                    + "".join(f"<li>{escape(str(item))}</li>" for item in notes)
                    + "</ul>"
                ],
            ),
            self._section(
                "回调安全合同",
                [
                    "<pre class='mono'>" + escape(json.dumps(dict(payload.get("callback_contract", {}) or {}), ensure_ascii=False, indent=2)) + "</pre>"
                ],
            ),
        ]
        return self._layout(
            "平台说明",
            "把当前部署模式、共享入口、就绪状态和可用页面/API 一次说明清楚，便于作为团队入口使用。",
            "".join(body),
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

    def _render_doctor(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        checks = list(payload.get("checks", []) or [])
        status_order = {"fail": 0, "warn": 1, "ok": 2, "skipped": 3}
        checks.sort(key=lambda item: (status_order.get(str(dict(item).get("status", "")), 9), str(dict(item).get("name", ""))))
        cards = []
        for raw_check in checks:
            check = dict(raw_check or {})
            status = str(check.get("status", "unknown") or "unknown")
            badge_class = "pill"
            tone = "info"
            if status == "fail":
                badge_class = "pill danger"
                tone = "danger"
            elif status == "warn":
                badge_class = "pill warning"
                tone = "warning"
            elif status == "skipped":
                badge_class = "pill muted"
            details = dict(check.get("details", {}) or {})
            cards.append(
                "<article class='card stack'>"
                f"<div><span class='{badge_class}'>{escape(status)}</span></div>"
                f"<h3>{escape(str(check.get('name', '') or 'unknown'))}</h3>"
                + self._notice(escape(str(check.get("summary", "") or "")), tone=tone)
                + self._compact_details(
                    "查看诊断细节",
                    "<pre class='mono doctor-detail-pre'>" + escape(json.dumps(details, ensure_ascii=False, indent=2)) + "</pre>",
                )
                + "</article>"
            )
        webhook_hint = (
            "<a href='/doctor?check_webhooks=1'>显式发送飞书诊断 ping</a>"
            if not bool(payload.get("check_webhooks", False))
            else "<a href='/doctor'>切回只读配置检查</a>"
        )
        device_id = str(payload.get("device_id", "") or "")
        package_name = str(payload.get("package_name", "") or "")
        body = [
            self._metric_grid(
                [
                    ("总状态", "ok" if payload.get("ok", False) else "blocked"),
                    ("通过", summary.get("ok", 0)),
                    ("警告", summary.get("warn", 0)),
                    ("失败", summary.get("fail", 0)),
                    ("跳过", summary.get("skipped", 0)),
                    ("生成时间", payload.get("generated_at", "")),
                ]
            ),
            self._section(
                "怎么用",
                [
                    "<div class='cards'>"
                    "<article class='card stack'><h3>命令行诊断</h3>"
                    "<pre class='mono'>python -m stability.cli doctor\n"
                    "python -m stability.cli doctor --device-id 192.168.31.99:5555 --package-name com.example.app\n"
                    "python -m stability.cli doctor --check-webhooks</pre>"
                    "<div class='meta'>默认不发送飞书消息；只有加 --check-webhooks 或页面显式点击时才发诊断 ping。</div>"
                    "</article>"
                    "<article class='card stack'><h3>Web 诊断</h3>"
                    f"<div>{webhook_hint}</div>"
                    "<div class='meta'>页面适合快速判断问题属于 Python/ADB/设备/runtime/config/端口/监控/outbox 哪一类。</div>"
                    "</article>"
                    "</div>"
                ],
            ),
            self._section(
                "单设备深度诊断",
                [
                    "<form method='get' action='/doctor' class='compact-filter-form'>"
                    "<div class='device-filter-row'>"
                    f"<label>设备 ID<input type='text' name='device_id' value='{escape(device_id, quote=True)}' placeholder='192.168.31.99:5555 或 USB serial' /></label>"
                    f"<label>包名<input type='text' name='package_name' value='{escape(package_name, quote=True)}' placeholder='可选，例如 com.example.app' /></label>"
                    "<button type='submit'>开始诊断</button>"
                    "</div>"
                    "<div class='meta'>会检查目标设备授权、shell、可选包名、设备端 perfetto、/data/local/tmp 写入和无线 ADB TCP 可达性。</div>"
                    "</form>"
                ],
            ),
            self._section("诊断项", ["<div class='cards doctor-check-grid'>" + "".join(cards) + "</div>"]),
        ]
        return self._layout(
            "诊断中心",
            "集中检查本地运行环境、设备链路、监控 backend 和集成 webhook，先定位问题属于哪一层。",
            "".join(body),
        )

    def _render_long_run_templates(self, payload: dict[str, Any]) -> str:
        templates = list(payload.get("templates", []) or [])
        selected = dict(payload.get("template", {}) or {})
        plan = dict(payload.get("plan", {}) or {})
        cards: list[str] = []
        for item in templates:
            template = dict(item or {})
            key = str(template.get("template_key", "") or template.get("template_id", "") or template.get("key", "") or "")
            defaults = dict(template.get("defaults", {}) or {})
            overridable = list(template.get("overridable_parameters", []) or [])
            tags = list(template.get("default_tags", []) or defaults.get("tags", []) or [])
            risk_notes = list(template.get("risk_notes", []) or [])
            chinese_explanation = str(template.get("chinese_explanation", "") or "")
            chinese_purpose = str(template.get("chinese_purpose", "") or "")
            summary_items = [
                ("类型", template.get("template_type", "") or defaults.get("template_type", "")),
                ("间隔", f"{defaults.get('interval_minutes', '-') } min"),
                ("轮次", f"{defaults.get('max_rounds', '-') } rounds"),
                ("设备", defaults.get("desired_device_count", "-")),
                ("轮转", defaults.get("rotation_strategy", "-")),
            ]
            summary = "".join(
                "<span class='pill'>"
                f"{escape(label)}：{escape(str(value))}"
                "</span>"
                for label, value in summary_items
                if str(value or "").strip()
            )
            tag_line = " ".join(f"<span class='pill muted'>{escape(str(tag))}</span>" for tag in tags)
            risk_line = ""
            if risk_notes:
                risk_line = (
                    "<p class='long-run-template-risk'>"
                    + "；".join(escape(str(item)) for item in risk_notes[:2])
                    + ("..." if len(risk_notes) > 2 else "")
                    + "</p>"
                )
            cards.append(
                "<article class='card long-run-template-card'>"
                "<div class='long-run-template-card-head'>"
                f"<h3>{escape(str(template.get('name', '') or key or '未命名模板'))}</h3>"
                "<div class='action-links'>"
                f"<a href='/long-run-templates?template_key={quote(key)}'>预览计划</a>"
                f"<a href='/tasks?long_run_template={quote(key)}'>套用创建任务</a>"
                "</div>"
                "</div>"
                f"<p class='meta compact'>key={escape(key)}</p>"
                "<p class='long-run-template-desc'>"
                "<strong>作用</strong>："
                f"{escape(str(chinese_purpose or chinese_explanation or template.get('description', '') or '长稳运行模板默认值。'))}"
                + (f" <span class='meta compact'>中文解释：{escape(chinese_explanation)}</span>" if chinese_explanation else "")
                + "</p>"
                f"<p class='template-summary'>{summary}</p>"
                + (f"<p class='long-run-template-tags'>{tag_line}</p>" if tag_line else "")
                + risk_line
                + "<details class='compact-details'><summary>默认值 / 可覆盖参数</summary>"
                "<pre class='mono compact-pre'>"
                + escape(json.dumps(defaults, ensure_ascii=False, indent=2))
                + "</pre><pre class='mono compact-pre'>"
                + escape(json.dumps(overridable, ensure_ascii=False, indent=2))
                + "</pre></details>"
                "</article>"
            )
        detail = ""
        if selected:
            selected_key = str(
                payload.get("template_key", "")
                or selected.get("template_key", "")
                or selected.get("template_id", "")
                or ""
            )
            selected_defaults = dict(selected.get("defaults", {}) or {})
            override_values = dict(payload.get("overrides", {}) or {})
            override_fields = [
                ("interval_minutes", "间隔分钟", selected_defaults.get("interval_minutes", "60")),
                ("max_rounds", "最大轮次", selected_defaults.get("max_rounds", "12")),
                ("desired_device_count", "期望设备数", selected_defaults.get("desired_device_count", "2")),
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
            preview_form = (
                f"<form method='get' action='/long-run-templates' class='compact-long-run-preview-form'>"
                f"<input type='hidden' name='template_key' value='{escape(selected_key)}' />"
                "<p class='muted compact'>只读预览：只生成计划，不创建任务、不启动执行。</p>"
                f"<div class='form-grid-three'>{override_inputs}</div>"
                "<div class='form-actions'><button type='submit'>预览覆盖参数</button></div>"
                "</form>"
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
                        + escape(json.dumps(plan.get(key, {}), ensure_ascii=False, indent=2))
                        + "</pre>"
                        "</details>"
                    )
            if plan.get("notes"):
                plan_sections.append(
                    "<article class='card compact-note-card'>"
                    "<h3>说明</h3>"
                    + "".join(f"<p>{escape(str(item))}</p>" for item in list(plan.get("notes", []) or []))
                    + "</article>"
                )
            detail = (
                "<section class='card long-run-template-preview'>"
                "<div class='long-run-template-card-head'>"
                "<h2>模板计划预览</h2>"
                "<div class='action-links'>"
                f"<a href='/tasks?long_run_template={quote(selected_key)}'>套用创建任务</a>"
                "<a href='/runner'>去 Runner 配置</a>"
                "</div>"
                "</div>"
                + preview_form
                + "<div class='long-run-plan-grid'>"
                + "".join(plan_sections)
                + "</div>"
                + "<details class='compact-details'><summary>原始 JSON</summary>"
                "<pre class='mono compact-pre'>"
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
                + "</pre></details>"
                "</section>"
            )
        body = [
            "<div class='long-run-template-page'>",
            self._notice(
                "这里用于查看长稳默认值和可覆盖参数；点击“套用创建任务”会跳到任务大厅并预填创建长稳任务表单，只有提交表单后才会写入无人值守配置。",
                tone="ok",
            ),
            "<div class='long-run-template-topline'>"
            + self._metric_grid(
                [
                    ("模板数量", payload.get("template_count", 0)),
                    ("来源", payload.get("source", "fallback")),
                    ("Runner", "/runner"),
                    ("API", "/api/long-run-templates"),
                ]
            )
            + "</div>",
            "<section class='card long-run-template-list-section'>"
            "<div class='long-run-template-card-head'><h2>模板列表</h2><a href='/runner'>去 Runner 配置</a></div>"
            "<div class='long-run-template-grid'>"
            + "".join(cards or [self._notice("当前没有可展示的长稳模板。")])
            + "</div>"
            "</section>",
            detail,
            "</div>",
        ]
        return self._layout(
            "长稳运行模板",
            "集中查看长稳模板族的默认值、可覆盖参数和入口计划，也可以一键套用到任务大厅创建长稳任务。",
            "".join(body),
        )


__all__ = ["CorePageMixin"]
