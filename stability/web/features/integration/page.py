from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from ..tasks.page import TaskFormsMixin


class IntegrationPageMixin(TaskFormsMixin):
    def _render_integration(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        worker = dict(payload.get("worker", {}) or {})
        events = list(payload.get("events", []) or [])
        webhooks = list(payload.get("webhooks", []) or [])
        release_submissions = list(payload.get("release_submissions", []) or [])
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        operation_result = dict(payload.get("operation_result", {}) or {})
        if operation_result:
            body.append(
                "<details class='compact-details integration-operation-result' open>"
                "<summary>本次操作结果</summary>"
                "<pre class='mono compact-pre'>"
                + escape(json.dumps(operation_result, ensure_ascii=False, indent=2))
                + "</pre></details>"
            )
        body.extend(
            [
                self._admin_page_header(
                    "集成 Outbox",
                    subtitle="管理 webhook、IM/缺陷/提测同步、worker 和 dead-letter 操作。",
                    breadcrumbs=[("首页", "/"), ("集成 Outbox", "")],
                    actions=[
                        self._route_link("JSON API", "/api/integration"),
                        self._route_link("Outbox JSON", "/api/integration/outbox"),
                    ],
                ),
                self._admin_summary_strip(
                    [
                        ("事件数", summary.get("event_count", 0)),
                        ("Webhook 数", summary.get("webhook_count", 0)),
                        ("提测请求", summary.get("release_submission_count", 0)),
                        ("已送达", summary.get("delivered_count", 0)),
                        ("重试中", summary.get("retry_pending_count", 0)),
                        ("死信", summary.get("dead_letter_count", 0)),
                        ("告警事件", summary.get("alerting_event_count", 0)),
                        ("当前过滤", summary.get("filtered_event_count", 0)),
                    ]
                ),
                self._integration_filter_bar(dict(payload.get("filters", {}) or {})),
                self._integration_admin_workspace(payload, events=events, webhooks=webhooks, release_submissions=release_submissions),
                "<details class='compact-details'><summary>Feishu/IM 验收摘要</summary>"
                + self._integration_im_acceptance_summary(payload)
                + "</details>",
                "<details class='compact-details'><summary>2h/24h 联调 Checklist</summary>"
                + self._integration_im_acceptance_checklist(payload)
                + "</details>",
                "<details class='compact-details'><summary>回调合同</summary><pre class='mono compact-pre'>"
                + escape(json.dumps(dict(payload.get("callback_contract", {}) or {}), ensure_ascii=False, indent=2))
                + "</pre></details>",
                "<details class='compact-details'><summary>Worker 状态</summary><pre class='mono compact-pre'>"
                + escape(json.dumps(worker, ensure_ascii=False, indent=2))
                + "</pre></details>",
            ]
        )
        return self._layout(
            "集成 Outbox",
            "管理 webhook 注册、IM 通知、缺陷同步、单轮投递、worker、dead-letter replay 和 CI 准入回传。",
            "".join(body),
        )

    def _integration_filter_bar(self, filters: Mapping[str, Any]) -> str:
        return self._admin_filter_bar(
            action="/integration",
            values=filters,
            fields=[
                {"name": "keyword", "label": "关键词", "placeholder": "事件 / Webhook / 包名 / Run / 提测"},
                {
                    "name": "status",
                    "label": "状态",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "pending", "label": "pending"},
                        {"value": "retry_pending", "label": "retry_pending"},
                        {"value": "delivered", "label": "delivered"},
                        {"value": "dead_letter", "label": "dead_letter"},
                        {"value": "admission_synced", "label": "admission_synced"},
                        {"value": "failed", "label": "failed"},
                    ],
                },
                {
                    "name": "delivery_channel",
                    "label": "Channel",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "generic", "label": "generic"},
                        {"value": "ci_callback", "label": "ci_callback"},
                        {"value": "im_notify", "label": "im_notify"},
                        {"value": "feishu_bot", "label": "feishu_bot"},
                        {"value": "defect_sync", "label": "defect_sync"},
                        {"value": "release_submission", "label": "release_submission"},
                    ],
                },
                {"name": "event_type", "label": "事件类型", "placeholder": "admission_case.updated"},
                {"name": "target_type", "label": "目标类型", "placeholder": "issue / run / release_submission"},
                {"name": "package_name", "label": "包名", "placeholder": "com.example"},
                {"name": "backend", "label": "Backend", "placeholder": "solox / perfetto"},
                {"name": "created_from", "label": "开始日期", "type": "date"},
                {"name": "created_to", "label": "结束日期", "type": "date"},
                {"name": "page_size", "label": "每页", "type": "number"},
            ],
        )

    def _integration_admin_workspace(
        self,
        payload: Mapping[str, Any],
        *,
        events: Sequence[Mapping[str, Any]],
        webhooks: Sequence[Mapping[str, Any]],
        release_submissions: Sequence[Mapping[str, Any]],
    ) -> str:
        event_table_id = "integration-events-admin-table"
        event_columns = self._integration_event_columns()
        toolbar = self._admin_toolbar(
            title="Outbox 事件列表",
            description="查询、投递、回放和同步入口集中在列表操作区。",
            table_id=event_table_id,
            columns=event_columns,
            actions=[
                self._admin_drawer_button("当前身份", "integration-current-actor", class_name="secondary"),
                self._admin_drawer_button("注册 IM", "integration-im-webhook-form", class_name="secondary"),
                self._admin_drawer_button("缺陷系统", "integration-defect-webhook-form", class_name="secondary"),
                self._admin_drawer_button("提测平台", "integration-release-forms", class_name="secondary"),
                self._admin_drawer_button("Webhook 注册", "integration-webhook-form", class_name="secondary"),
                self._admin_drawer_button("投递与 Worker", "integration-worker-forms", class_name="secondary"),
                "<a class='button secondary' href='/integration'>刷新</a>",
            ],
        )
        event_table, event_drawers = self._integration_event_admin_table(events, table_id=event_table_id, columns=event_columns)
        webhook_table, webhook_drawers = self._integration_webhook_admin_table(webhooks)
        release_table, release_drawers = self._integration_release_submission_admin_table(release_submissions)
        pagination = self._admin_pagination(
            base_path="/integration",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return (
            "<section class='panel admin-list-panel'>"
            + toolbar
            + event_table
            + pagination
            + "<div class='admin-subtable-grid'>"
            + "<section class='admin-subtable'>"
            + self._admin_toolbar(
                title="已注册 Webhooks",
                description="按 channel、安全边界和事件订阅查看回调端。",
                table_id="integration-webhooks-admin-table",
                columns=self._integration_webhook_columns(),
            )
            + webhook_table
            + "</section>"
            + "<section class='admin-subtable'>"
            + self._admin_toolbar(
                title="提测请求",
                description="展示 release submission、执行 run 与准入同步结果。",
                table_id="integration-release-admin-table",
                columns=self._integration_release_columns(),
            )
            + release_table
            + "</section>"
            + "</div></section>"
            + self._integration_form_drawers(payload)
            + event_drawers
            + webhook_drawers
            + release_drawers
        )

    @staticmethod
    def _integration_event_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "event", "label": "事件"},
            {"key": "status", "label": "状态"},
            {"key": "channel", "label": "Channel"},
            {"key": "target", "label": "目标"},
            {"key": "package_backend", "label": "包名 / Backend"},
            {"key": "attempts", "label": "投递"},
            {"key": "created", "label": "创建时间"},
            {"key": "error", "label": "错误", "default_visible": False},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    @staticmethod
    def _integration_webhook_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "webhook", "label": "Webhook"},
            {"key": "channel", "label": "Channel"},
            {"key": "policy", "label": "策略"},
            {"key": "events", "label": "事件订阅", "default_visible": False},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    @staticmethod
    def _integration_release_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "submission", "label": "提测"},
            {"key": "status", "label": "状态"},
            {"key": "package", "label": "包名"},
            {"key": "run", "label": "Run"},
            {"key": "admission", "label": "准入"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _integration_event_admin_table(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for raw_item in events:
            item = dict(raw_item or {})
            event_id = str(item.get("event_id", "") or "")
            event_type = str(item.get("event_type", "") or "unknown")
            drawer_id = f"admin-integration-event-{self._dom_id_fragment(event_id or event_type)}"
            status = str(item.get("delivery_status", "") or "pending")
            target = f"{item.get('target_type', '')}:{item.get('target_id', '')}"
            last_error = str(item.get("last_error", "") or "")
            payload = dict(item.get("payload", {}) or {})
            channels = ", ".join(str(value) for value in list(item.get("delivery_channels", []) or [])) or "n/a"
            package_name = str(payload.get("package_name", "") or "n/a")
            backend = self._integration_event_backend_label(item)
            rows.append(
                {
                    "select": f"<input type='checkbox' name='event_id' value='{escape(event_id, quote=True)}' />",
                    "event": (
                        f"<strong>{escape(event_type)}</strong>"
                        f"<div class='mono'>{escape(event_id or 'n/a')}</div>"
                    ),
                    "status": self._admin_status(status, tone=self._integration_delivery_tone(status)),
                    "channel": f"<span title='{escape(channels, quote=True)}'>{escape(channels)}</span>",
                    "target": f"<span title='{escape(target, quote=True)}'>{escape(target or 'n/a')}</span>",
                    "package_backend": (
                        f"<span class='mono'>{escape(package_name)}</span>"
                        f"<div class='meta'>backend={escape(backend)}</div>"
                    ),
                    "attempts": (
                        f"attempts={escape(str(item.get('attempt_count', 0) or 0))}"
                        f"<div class='meta'>alert={escape(str(item.get('alert_status', 'none') or 'none'))}</div>"
                    ),
                    "created": escape(str(item.get("created_at", "") or "n/a")),
                    "error": f"<span title='{escape(last_error, quote=True)}'>{escape(last_error or '无')}</span>",
                    "actions": (
                        "<div class='admin-table-actions'>"
                        + self._admin_drawer_button("详情", drawer_id)
                        + self._admin_drawer_button("投递/回放", "integration-worker-forms")
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"Outbox 事件 · {event_type}",
                    self._integration_event_detail(item),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前没有匹配 outbox 事件。"), "".join(drawers)

    def _integration_webhook_admin_table(self, webhooks: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
        table_id = "integration-webhooks-admin-table"
        columns = self._integration_webhook_columns()
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for raw_item in webhooks:
            item = dict(raw_item or {})
            name = str(item.get("name", "") or "unnamed")
            drawer_id = f"admin-integration-webhook-{self._dom_id_fragment(name)}"
            subscribed = ", ".join(str(value) for value in list(item.get("subscribed_event_types", []) or [])) or "all"
            channel = str(item.get("delivery_channel", "") or "generic")
            rows.append(
                {
                    "select": f"<input type='checkbox' name='webhook_name' value='{escape(name, quote=True)}' />",
                    "webhook": (
                        f"<strong>{escape(name)}</strong>"
                        f"<div class='mono'>{escape(str(item.get('url', '') or 'n/a'))}</div>"
                    ),
                    "channel": self._admin_status(channel, tone="ok"),
                    "policy": (
                        f"{escape(str(item.get('failure_policy', '') or 'retryable_http'))}"
                        f"<div class='meta'>{escape(str(item.get('security_boundary', '') or 'shared_remote_callback'))}</div>"
                    ),
                    "events": f"<span title='{escape(subscribed, quote=True)}'>{escape(subscribed)}</span>",
                    "actions": (
                        "<div class='admin-table-actions'>"
                        + self._admin_drawer_button("详情", drawer_id)
                        + self._admin_drawer_button("执行投递", "integration-worker-forms")
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"Webhook · {name}",
                    self._integration_webhook_detail(item),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前还没有注册 webhook。"), "".join(drawers)

    def _integration_release_submission_admin_table(
        self,
        submissions: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        table_id = "integration-release-admin-table"
        columns = self._integration_release_columns()
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for raw_item in submissions:
            item = dict(raw_item or {})
            submission_id = str(item.get("submission_id", "") or "")
            drawer_id = f"admin-integration-release-{self._dom_id_fragment(submission_id)}"
            run_id = str(item.get("run_id", "") or "")
            task_id = str(item.get("task_id", "") or "")
            status = str(item.get("submission_status", "") or "received")
            rows.append(
                {
                    "select": f"<input type='checkbox' name='submission_id' value='{escape(submission_id, quote=True)}' />",
                    "submission": (
                        f"<strong>{escape(str(item.get('submission_title', '') or submission_id or '未命名提测'))}</strong>"
                        f"<div class='mono'>{escape(submission_id or 'n/a')}</div>"
                    ),
                    "status": self._admin_status(status, tone=self._integration_submission_tone(status)),
                    "package": f"<span class='mono'>{escape(str(item.get('package_name', '') or 'n/a'))}</span>",
                    "run": (
                        f"{self._admin_status(str(item.get('run_status', '') or 'n/a'), tone=self._status_tone(str(item.get('run_status', '') or 'unknown')))}"
                        f"<div class='mono'>{escape(run_id or 'n/a')}</div>"
                    ),
                    "admission": escape(str(item.get("admission_final_decision", "") or item.get("baseline_key", "") or "n/a")),
                    "actions": (
                        "<div class='admin-table-actions'>"
                        + self._admin_drawer_button("详情", drawer_id)
                        + self._admin_drawer_button("同步准入", "integration-release-forms")
                        + self._route_link_new_tab("JSON", item.get("api_path", ""))
                        + self._route_link_new_tab("任务", f"/tasks/task/{quote(task_id, safe='')}" if task_id else "")
                        + self._route_link_new_tab("Run", f"/runs/{quote(run_id, safe='')}" if run_id else "")
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"提测请求 · {submission_id}",
                    self._integration_release_detail(item),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前没有匹配提测请求。"), "".join(drawers)

    def _integration_form_drawers(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return "".join(
            [
                self._admin_drawer(
                    "integration-current-actor",
                    "当前身份",
                    self._current_actor_card(
                        current_actor=current_actor,
                        actors=list(self._collaboration_actors()),
                        current_path="/integration",
                    ),
                ),
                self._admin_drawer("integration-im-webhook-form", "IM 通知", self._integration_register_im_webhook_form(payload)),
                self._admin_drawer("integration-defect-webhook-form", "缺陷系统", self._integration_register_defect_webhook_form(payload)),
                self._admin_drawer("integration-release-forms", "提测平台", self._integration_release_submission_forms(payload)),
                self._admin_drawer("integration-webhook-form", "Webhook 注册", self._integration_register_webhook_form(payload)),
                self._admin_drawer("integration-worker-forms", "投递与 Worker", self._integration_worker_forms(payload)),
            ]
        )

    def _integration_event_detail(self, item: Mapping[str, Any]) -> str:
        payload = dict(item.get("payload", {}) or {})
        channels = ", ".join(str(value) for value in list(item.get("delivery_channels", []) or []))
        fields = [
            ("Event ID", item.get("event_id", "")),
            ("事件类型", item.get("event_type", "")),
            ("状态", item.get("delivery_status", "")),
            ("Channel", channels),
            ("目标", f"{item.get('target_type', '')}:{item.get('target_id', '')}"),
            ("包名", payload.get("package_name", "")),
            ("Backend", self._integration_event_backend_label(item)),
            ("创建人", item.get("created_by", "")),
            ("创建时间", item.get("created_at", "")),
            ("最近尝试", item.get("last_attempt_at", "")),
            ("下次重试", item.get("next_retry_at", "")),
            ("响应码", item.get("last_response_code", "")),
            ("错误分类", item.get("failure_category", "")),
        ]
        return (
            self._integration_detail_grid(fields)
            + "<details class='compact-details' open><summary>事件 Payload</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(dict(item.get("payload", {}) or {}), ensure_ascii=False, indent=2))
            + "</pre></details>"
            + "<details class='compact-details'><summary>完整事件 JSON</summary><pre class='mono compact-pre'>"
            + escape(json.dumps(dict(item), ensure_ascii=False, indent=2))
            + "</pre></details>"
        )

    @staticmethod
    def _integration_event_backend_label(item: Mapping[str, Any]) -> str:
        payload = dict(item.get("payload", {}) or {})
        backend = (
            payload.get("backend")
            or payload.get("monitoring_backend")
            or payload.get("collector_backend")
        )
        monitoring = payload.get("monitoring")
        if not backend and isinstance(monitoring, Mapping):
            backend = dict(monitoring).get("backend")
        return str(backend or "n/a")

    def _integration_webhook_detail(self, item: Mapping[str, Any]) -> str:
        fields = [
            ("名称", item.get("name", "")),
            ("Channel", item.get("delivery_channel", "")),
            ("Failure Policy", item.get("failure_policy", "")),
            ("安全边界", item.get("security_boundary", "")),
            ("需要 TLS", item.get("requires_tls", "")),
            ("Key ID", item.get("signature_key_id", "")),
            ("创建人", item.get("created_by", "")),
            ("创建时间", item.get("created_at", "")),
        ]
        return (
            self._integration_detail_grid(fields)
            + "<pre class='mono compact-pre'>"
            + escape(json.dumps(dict(item), ensure_ascii=False, indent=2))
            + "</pre>"
        )

    def _integration_release_detail(self, item: Mapping[str, Any]) -> str:
        fields = [
            ("Submission ID", item.get("submission_id", "")),
            ("来源", f"{item.get('source_platform', '')}:{item.get('source_request_id', '')}"),
            ("包名", item.get("package_name", "")),
            ("版本", item.get("version_name", "") or item.get("version_code", "")),
            ("Build ID", item.get("build_id", "")),
            ("Owner", item.get("owner_team", "")),
            ("任务", item.get("task_name", "") or item.get("task_id", "")),
            ("Run", item.get("run_id", "")),
            ("准入", item.get("admission_final_decision", "") or item.get("baseline_key", "")),
            ("Backend", item.get("monitoring_backend", "")),
        ]
        return (
            self._integration_detail_grid(fields)
            + "<pre class='mono compact-pre'>"
            + escape(json.dumps(dict(item), ensure_ascii=False, indent=2))
            + "</pre>"
        )

    @staticmethod
    def _integration_detail_grid(fields: Sequence[tuple[str, Any]]) -> str:
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
    def _integration_delivery_tone(status: str) -> str:
        value = str(status or "").lower()
        if value in {"dead_letter", "failed", "error"}:
            return "danger"
        if value in {"pending", "retry_pending", "retrying"}:
            return "warning"
        if value in {"delivered", "success"}:
            return "ok"
        return "muted"

    @staticmethod
    def _integration_submission_tone(status: str) -> str:
        value = str(status or "").lower()
        if value in {"failed", "rejected", "blocked"}:
            return "danger"
        if value in {"received", "run_created", "executed", "pending"}:
            return "warning"
        if value in {"admission_synced", "success", "passed"}:
            return "ok"
        return "muted"

    def _integration_register_webhook_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>注册 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-webhook', current_actor=current_actor), quote=True)}' class='stack integration-two-column-form'>"
            "<div class='integration-form-grid'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 ci-sync' required /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/webhook' data-webhook-url='1' required /></label>"
            "<label>事件类型<input type='text' name='event_types' value='admission_case.updated' placeholder='逗号分隔' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label data-required-conditional='external-webhook' data-required-label='外部必填'>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' data-webhook-signing-secret='1' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "<label>Delivery Channel<input type='text' name='delivery_channel' value='generic' /></label>"
            "</div>"
            "<div class='integration-form-footer'>"
            "<div class='meta'>外放边界：非本地 webhook 默认要求 https + signing_secret；投递头会携带签名、key id、idempotency key 和 delivery contract。</div>"
            "<button type='submit'>注册 Webhook</button>"
            "</div>"
            "</form></article></div>"
        )

    def _integration_register_im_webhook_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>注册 IM 通知 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-im-webhook', current_actor=current_actor), quote=True)}' class='stack integration-two-column-form'>"
            "<div class='integration-form-grid'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 team-im-notify' required /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/im-bot' data-webhook-url='1' required /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空使用稳定 IM 事件集' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label data-required-conditional='external-webhook' data-required-label='外部必填'>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' data-webhook-signing-secret='1' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "</div>"
            "<div class='integration-form-footer'>"
            "<div class='meta'>IM 通知消息体使用 asl.im_notify.v1，会把协作、准入更新和 outbox 告警整理成可读消息再投递。</div>"
            "<button type='submit'>注册 IM Webhook</button>"
            "</div>"
            "</form></article></div>"
        )

    def _integration_register_defect_webhook_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>注册缺陷同步 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-defect-webhook', current_actor=current_actor), quote=True)}' class='stack integration-two-column-form'>"
            "<div class='integration-form-grid'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 defect-sync' required /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/defect-bot' data-webhook-url='1' required /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空使用稳定缺陷事件集' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label data-required-conditional='external-webhook' data-required-label='外部必填'>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' data-webhook-signing-secret='1' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "</div>"
            "<div class='integration-form-footer'>"
            "<div class='meta'>缺陷消息体使用 asl.defect_sync.v1，会把 issue、缺陷映射、动作和 routing 信息整理成稳定合同再投递。</div>"
            "<button type='submit'>注册缺陷 Webhook</button>"
            "</div>"
            "</form></article></div>"
        )

    def _integration_im_acceptance_summary(self, payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("im_acceptance", {}) or {})
        duplicate_risk = dict(summary.get("duplicate_risk", {}) or {})
        noise_check = dict(summary.get("noise_check", {}) or {})
        metric_grid = self._metric_grid(
            [
                ("总事件数", summary.get("total_event_count", 0)),
                ("成功投递", summary.get("delivered_count", 0)),
                ("失败数", summary.get("failed_count", 0)),
                ("重试数", summary.get("retry_count", 0)),
                ("Dead Letter", summary.get("dead_letter_count", 0)),
                ("consumer_receipt", summary.get("consumer_receipt_count", 0)),
                ("deduplicated", summary.get("deduplicated_count", 0)),
                ("重复风险", duplicate_risk.get("level", "low") or "low"),
            ]
        )
        risk_items = "".join(
            f"<li>{escape(str(item))}</li>"
            for item in list(duplicate_risk.get("reasons", []) or [])
        )
        webhooks = ", ".join(str(item) for item in list(summary.get("webhook_names", []) or []) if str(item).strip())
        first_webhook = webhooks.split(", ")[0] if webhooks else ""
        cli_hint = "python -m stability.cli show-im-acceptance-summary --channel feishu_bot"
        if first_webhook:
            cli_hint += f" --webhook-name {first_webhook}"
        return (
            "<div class='stack'>"
            f"{metric_grid}"
            "<div class='cards'>"
            "<article class='card stack'>"
            "<h3>重复风险提示</h3>"
            f"<ul>{risk_items or '<li>当前摘要未发现明显重复投递风险。</li>'}</ul>"
            f"<div class='meta'>候选重复 receipt={escape(str(duplicate_risk.get('duplicate_candidate_count', 0) or 0))}</div>"
            "</article>"
            "<article class='card stack'>"
            "<h3>噪声检查占位</h3>"
            f"<pre class='mono'>{escape(json.dumps(noise_check, ensure_ascii=False, indent=2))}</pre>"
            "</article>"
            "<article class='card stack'>"
            "<h3>CLI 验收入口</h3>"
            f"<div class='mono'>{escape(cli_hint)}</div>"
            f"<div class='meta'>目标 webhook：{escape(webhooks or '暂无 IM/Feishu webhook')}</div>"
            "</article>"
            "</div>"
            "</div>"
        )

    def _integration_im_acceptance_checklist(self, payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("im_acceptance", {}) or {})
        checklist = dict(summary.get("checklist", {}) or {})

        def _items(title: str, values: list[dict[str, Any]]) -> str:
            rows = "".join(
                "<li>"
                f"<strong>{escape(str(item.get('status', 'manual') or 'manual'))}</strong> "
                f"{escape(str(item.get('item', '') or ''))}"
                "</li>"
                for item in values
            )
            return (
                "<article class='card stack'>"
                f"<h3>{escape(title)}</h3>"
                f"<ul>{rows}</ul>"
                "</article>"
            )

        return (
            "<div class='cards'>"
            + _items("2h 联调", [dict(item) for item in list(checklist.get("two_hour", []) or []) if isinstance(item, Mapping)])
            + _items("24h 联调", [dict(item) for item in list(checklist.get("twenty_four_hour", []) or []) if isinstance(item, Mapping)])
            + "</div>"
        )

    def _integration_release_submission_forms(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        release_device_selector = self._task_device_selector(
            [item for item in self._device_summaries() if bool(dict(item).get("is_schedulable", False))],
            allow_empty=True,
            label="设备",
        )
        metric_selector = self._task_metric_selector(default_selected=("cpu", "memory"))
        return (
            "<div class='cards integration-release-stack'>"
            "<article class='card stack'>"
            "<h3>创建提测请求</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/create-release-submission', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>来源平台<input type='text' name='source_platform' value='' placeholder='例如 release-center' required /></label>"
            "<label>来源请求 ID<input type='text' name='source_request_id' value='' placeholder='例如 REL-2026-001' required /></label>"
            "<label>包名<input type='text' name='package_name' value='' placeholder='com.example.app' required /></label>"
            "<label>版本名<input type='text' name='version_name' value='' placeholder='例如 1.0.1' /></label>"
            "<label>版本号<input type='text' name='version_code' value='' placeholder='例如 101' /></label>"
            "<label>Build ID<input type='text' name='build_id' value='' placeholder='例如 build-101' /></label>"
            "<label>发布通道<input type='text' name='release_channel' value='' placeholder='例如 beta / gray / store' /></label>"
            "<label>Owner Team<input type='text' name='owner_team' value='' placeholder='例如 android-client' /></label>"
            "<label>标题<input type='text' name='submission_title' value='' placeholder='留空则自动生成' /></label>"
            f"<label>模板<select name='template_type'>{self._task_template_options('cold_start_loop')}</select></label>"
            f"{release_device_selector}"
            f"{metric_selector}"
            "<label>采样间隔(秒)<input type='number' name='sampling_interval' value='5' min='0' /></label>"
            "<label>Monitoring Backend<select name='monitoring_backend'><option value=''>default</option><option value='solox'>solox</option><option value='perfetto'>perfetto</option></select></label>"
            "<label>立即执行<select name='execute_immediately'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Max Concurrency<input type='number' name='max_concurrency' value='1' min='1' /></label>"
            "<label>Retry Count<input type='number' name='retry_count' value='0' min='0' /></label>"
            f"{self._task_params_builder(wide=False, upload_url=self._actor_scoped_path('/tasks/actions/upload-apk', current_actor=current_actor), delete_url=self._actor_scoped_path('/tasks/actions/delete-apk', current_actor=current_actor))}"
            f"{self._json_textarea_with_help('task_params(JSON)', 'task_params', '例如 {\"loop_count\": 10}', self._task_params_help(), wide=False, rows=3)}"
            f"{self._json_textarea_with_help('metadata(JSON)', 'metadata', '例如 {\"source\":\"web\"}', self._metadata_help(), wide=False, rows=3)}"
            "<div class='integration-form-actions'><button type='submit'>创建提测请求</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>同步提测准入</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/sync-release-admission', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Submission ID<input type='text' name='submission_id' value='' placeholder='release_submission_...' required /></label>"
            "<label>Baseline Key<input type='text' name='baseline_key' value='' placeholder='例如 device_offline_default' required /></label>"
            "<div class='integration-form-actions'><button type='submit'>同步准入结论</button></div>"
            "</form>"
            "</article>"
            "<article class='card stack'>"
            "<h3>注册提测 Webhook</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/register-release-webhook', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>名称<input type='text' name='name' value='' placeholder='例如 release-sync' required /></label>"
            "<label>URL<input type='text' name='url' value='' placeholder='https://example.invalid/release-callback' data-webhook-url='1' required /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空使用稳定提测事件集' /></label>"
            "<label>签名 Secret Hint<input type='text' name='secret_hint' value='' placeholder='接收端如何验证' /></label>"
            "<label data-required-conditional='external-webhook' data-required-label='外部必填'>Signing Secret<input type='text' name='signing_secret' value='' placeholder='非本地 webhook 必填' data-webhook-signing-secret='1' /></label>"
            "<label>Signature Key ID<input type='text' name='signature_key_id' value='v1' /></label>"
            "<label>Accepted Key IDs<input type='text' name='accepted_signature_key_ids' value='' placeholder='逗号分隔' /></label>"
            "<label>Failure Policy<select name='failure_policy'><option value='retryable_http'>retryable_http</option><option value='best_effort'>best_effort</option><option value='fail_closed'>fail_closed</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>注册提测 Webhook</button></div>"
            "<div class='meta integration-form-wide'>提测消息体使用 asl.release_submission.v1，会把 submission、执行状态和准入同步结果按稳定合同投递。</div>"
            "</form>"
            "</article>"
            "</div>"
        )

    def _integration_worker_forms(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        worker = dict(payload.get("worker", {}) or {})
        webhook_names = ", ".join(list(worker.get("registered_webhook_names", []) or []))
        return (
            "<div class='integration-worker-list'>"
            + self._integration_delivery_worker_form(current_actor=current_actor, webhook_names=webhook_names)
            + self._integration_channel_worker_form("CI 回传 Worker", "/integration/actions/run-ci-worker", "全部 CI webhook", current_actor=current_actor)
            + self._integration_channel_worker_form("IM 通知 Worker", "/integration/actions/run-im-worker", "全部 IM webhook", current_actor=current_actor, hidden_channel="im_notify")
            + self._integration_channel_worker_form("Feishu 通知 Worker", "/integration/actions/run-im-worker", "全部 Feishu webhook", current_actor=current_actor, hidden_channel="feishu_bot")
            + self._integration_channel_worker_form("缺陷同步 Worker", "/integration/actions/run-defect-worker", "全部缺陷 webhook", current_actor=current_actor)
            + self._integration_channel_worker_form("提测同步 Worker", "/integration/actions/run-release-worker", "全部提测 webhook", current_actor=current_actor)
            + self._integration_replay_and_ci_forms(current_actor=current_actor)
            + "</div>"
        )

    def _integration_delivery_worker_form(self, *, current_actor: Mapping[str, Any], webhook_names: str) -> str:
        deliver_form = (
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/deliver-outbox', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Name<input type='text' name='webhook_name' value='' placeholder='ci-sync' required /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='留空表示全部' /></label>"
            "<label>Limit<input type='number' name='limit' value='20' min='1' /></label>"
            "<div class='integration-form-actions'><button type='submit'>执行单轮</button></div>"
            "</form>"
        )
        worker_form = (
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/run-worker', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label class='integration-worker-wide-field'>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示全部' /></label>"
            "<label class='integration-worker-wide-field'>事件类型<input type='text' name='event_types' value='' placeholder='逗号分隔；为空表示全部' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Rounds<input type='number' name='rounds' value='1' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<div class='integration-form-actions'><button type='submit'>执行 Worker</button></div>"
            "</form>"
        )
        return (
            self._integration_worker_action_row(
                "单轮投递",
                f"已注册 webhook：{webhook_names or '暂无'}",
                deliver_form,
            )
            + self._integration_worker_action_row(
                "Outbox Worker",
                "按 webhook 和事件类型批量投递，可配置轮次、间隔和 daemon。",
                worker_form,
            )
        )

    def _integration_channel_worker_form(
        self,
        title: str,
        action_path: str,
        placeholder: str,
        *,
        current_actor: Mapping[str, Any],
        hidden_channel: str = "",
    ) -> str:
        channel_input = f"<input type='hidden' name='channel' value='{escape(hidden_channel, quote=True)}' />" if hidden_channel else ""
        form = (
            f"<form method='post' action='{escape(self._actor_scoped_path(action_path, current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            f"{channel_input}"
            f"<label class='integration-worker-wide-field'>Webhook Names<input type='text' name='webhook_names' value='' placeholder='逗号分隔；为空表示{escape(placeholder)}' /></label>"
            "<label>Limit Per Webhook<input type='number' name='limit_per_webhook' value='20' min='1' /></label>"
            "<label>Interval Seconds<input type='number' name='interval_seconds' value='300' min='0' /></label>"
            "<label>Max Rounds<input type='number' name='max_rounds' value='1' min='0' /></label>"
            "<label>Max Runtime Seconds<input type='number' name='max_runtime_seconds' value='0' min='0' /></label>"
            "<label>Daemon<select name='daemon'><option value='1'>是</option><option value='0'>否</option></select></label>"
            "<label>Stop When Idle<select name='stop_when_idle'><option value='0'>否</option><option value='1'>是</option></select></label>"
            f"<div class='integration-form-actions'><button type='submit'>执行{escape(title)}</button></div>"
            "</form>"
        )
        return self._integration_worker_action_row(title, f"默认目标：{placeholder}", form)

    def _integration_replay_and_ci_forms(self, *, current_actor: Mapping[str, Any]) -> str:
        replay_form = (
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/replay-dead-letters', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label class='integration-worker-wide-field'>Event IDs<input type='text' name='event_ids' value='' placeholder='逗号分隔；为空表示按筛选回放' /></label>"
            "<label>事件类型<input type='text' name='event_types' value='' placeholder='逗号分隔' /></label>"
            "<label>Limit<input type='number' name='limit' value='20' min='1' /></label>"
            "<label>Execute<select name='execute'><option value='0'>仅预览</option><option value='1'>实际回放</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>处理 Dead Letter</button></div>"
            "</form>"
        )
        ci_form = (
            f"<form method='post' action='{escape(self._actor_scoped_path('/integration/actions/sync-ci-decisions', current_actor=current_actor), quote=True)}' class='integration-compact-form'>"
            "<label>Webhook Name<input type='text' name='webhook_name' value='' placeholder='ci-sync' required /></label>"
            "<label class='integration-worker-wide-field'>CI Endpoint<input type='text' name='ci_endpoint' value='' placeholder='可选；缺 webhook 时自动注册' /></label>"
            "<label class='integration-worker-wide-field'>事件类型<input type='text' name='event_types' value='admission_case.updated' /></label>"
            "<label>Limit<input type='number' name='limit' value='20' min='1' /></label>"
            "<label>Query Limit<input type='number' name='query_limit' value='0' min='0' /></label>"
            "<label>Dry Run<select name='dry_run'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div class='integration-form-actions'><button type='submit'>同步 CI 决策</button></div>"
            "</form>"
        )
        return (
            self._integration_worker_action_row(
                "Replay Dead Letters",
                "把 dead-letter 事件按筛选条件重新放回待投递队列。",
                replay_form,
            )
            + self._integration_worker_action_row(
                "同步 CI Admission 决策",
                "把准入结论同步回 CI 或自动注册临时 CI endpoint。",
                ci_form,
            )
        )

    @staticmethod
    def _integration_worker_action_row(title: str, description: str, form_html: str) -> str:
        return (
            "<article class='integration-worker-row'>"
            "<div class='integration-worker-info'>"
            f"<strong>{escape(title)}</strong>"
            f"<span>{escape(description)}</span>"
            "</div>"
            "<div class='integration-worker-controls'>"
            + form_html
            + "</div>"
            "</article>"
        )

    def _integration_webhook_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前还没有注册 webhook。")
        return "<div class='cards'>" + "".join(
            "<article class='card stack'>"
            f"<h3>{escape(str(item.get('name', '') or ''))}</h3>"
            f"<div class='meta'>{escape(str(item.get('delivery_channel', '') or 'generic'))} / {escape(str(item.get('failure_policy', '') or 'retryable_http'))}</div>"
            f"<div><span class='mono'>{escape(str(item.get('url', '') or ''))}</span></div>"
            f"<div>event_types={escape(', '.join(item.get('subscribed_event_types', []) or []) or 'all')}</div>"
            f"<div>security_boundary={escape(str(item.get('security_boundary', '') or 'shared_remote_callback'))}</div>"
            + (
                f"<div>key_id={escape(str(item.get('signature_key_id', '') or 'v1'))}</div>"
                if str(item.get("signature_key_id", "") or "").strip()
                else ""
            )
            + "</article>"
            for item in items
        ) + "</div>"

    def _integration_event_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有可展示的 outbox 事件。")
        cards = []
        for item in items[:20]:
            payload = dict(item.get("payload", {}) or {})
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('event_type', '') or ''))}</h3>"
                f"<div class='meta'>{escape(str(item.get('event_id', '') or ''))}</div>"
                f"<div>status={escape(str(item.get('delivery_status', 'pending') or 'pending'))} / attempts={escape(str(item.get('attempt_count', 0) or 0))}</div>"
                f"<div>target={escape(str(item.get('target_type', '') or ''))}:{escape(str(item.get('target_id', '') or ''))}</div>"
                f"<div>idempotency_key=<span class='mono'>{escape(str(item.get('idempotency_key', '') or ''))}</span></div>"
                + (
                    f"<div>final_decision={escape(str(payload.get('final_decision', '') or ''))}</div>"
                    if str(payload.get("final_decision", "") or "").strip()
                    else ""
                )
                + (
                    f"<div class='meta'>last_error={escape(str(item.get('last_error', '') or ''))}</div>"
                    if str(item.get("last_error", "") or "").strip()
                    else ""
                )
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"


__all__ = ["IntegrationPageMixin"]
