from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence


class DoctorPageMixin:
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
