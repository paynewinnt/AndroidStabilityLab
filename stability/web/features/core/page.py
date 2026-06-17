from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from stability.web import renderers as portal_renderers
from stability.web.features.core.doctor_page import DoctorPageMixin
from stability.web.features.core.json_api_page import CoreJsonApiPageMixin
from stability.web.features.core.long_run_templates_page import LongRunTemplatesPageMixin


class CorePageMixin(DoctorPageMixin, LongRunTemplatesPageMixin, CoreJsonApiPageMixin):
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


__all__ = ["CorePageMixin"]
