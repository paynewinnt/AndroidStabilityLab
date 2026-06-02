from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from stability.web.manifest import (
    api_endpoint_description,
    api_endpoint_kind,
    manifest_summary,
)


class CoreJsonApiPageMixin:
    def _render_json_api_index(self, payload: dict[str, Any]) -> str:
        api_endpoints = list(payload.get("api_endpoints", []) or [])
        summary = manifest_summary(
            {
                "pages": list(payload.get("pages", []) or []),
                "api_endpoints": api_endpoints,
                "write_actions": [],
            }
        )
        filters = self._json_api_filters(dict(payload.get("json_api_query", {}) or {}))
        filtered_endpoints = [
            item
            for item in api_endpoints
            if self._json_api_endpoint_matches(item, filters)
        ]
        page = int(filters["page"])
        page_size = int(filters["page_size"])
        page_endpoints = filtered_endpoints[(page - 1) * page_size : page * page_size]
        body = [
            self._admin_page_header(
                "JSON API",
                breadcrumbs=[("首页", "/"), ("接口中心", "")],
                actions=[
                    self._route_link("Manifest", "/api/manifest"),
                    self._route_link("OpenAPI", "/api/openapi.json"),
                ],
            ),
            self._admin_summary_strip(
                [
                    ("接口数", len(api_endpoints)),
                    ("当前过滤", len(filtered_endpoints)),
                    ("页面入口", summary["page_count"]),
                    ("详情接口", summary["detail_endpoint_count"]),
                    ("健康检查", summary["health_endpoint_count"]),
                ]
            ),
            self._json_api_filter_bar(filters),
            self._json_api_admin_workspace(
                page_endpoints, filters=filters, total=len(filtered_endpoints)
            ),
            self._section("怎么用", [self._json_api_usage_cards()]),
        ]
        return self._layout(
            "JSON API",
            "",
            "".join(body),
        )

    def _json_api_filter_bar(self, filters: Mapping[str, Any]) -> str:
        return self._admin_filter_bar(
            action="/json-api",
            values=filters,
            fields=[
                {
                    "name": "keyword",
                    "label": "关键词",
                    "placeholder": "接口 / 说明 / path",
                },
                {
                    "name": "kind",
                    "label": "类型",
                    "type": "select",
                    "options": [
                        {"value": "", "label": "全部"},
                        {"value": "read", "label": "读接口"},
                        {"value": "detail", "label": "详情模板"},
                        {"value": "health", "label": "健康检查"},
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

    def _json_api_admin_workspace(
        self,
        endpoints: Sequence[Mapping[str, Any]],
        *,
        filters: Mapping[str, Any],
        total: int,
    ) -> str:
        table_id = "json-api-admin-table"
        columns = self._json_api_columns()
        toolbar = self._admin_toolbar(
            title="接口列表",
            description="按 path、说明和类型过滤接口。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/json-api'>刷新</a>",
                self._route_link_new_tab("Manifest", "/api/manifest"),
                self._route_link_new_tab("OpenAPI", "/api/openapi.json"),
            ],
        )
        table_html, drawers = self._json_api_table(
            endpoints, table_id=table_id, columns=columns
        )
        pagination = self._admin_pagination(
            base_path="/json-api",
            filters=filters,
            page=int(filters.get("page", 1) or 1),
            page_size=int(filters.get("page_size", 20) or 20),
            total=total,
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
    def _json_api_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "api", "label": "接口"},
            {"key": "kind", "label": "类型"},
            {"key": "description", "label": "说明"},
            {"key": "curl", "label": "curl", "default_visible": False},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _json_api_table(
        self,
        endpoints: Sequence[Mapping[str, Any]],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for raw_item in endpoints:
            item = dict(raw_item or {})
            path = str(item.get("path", "") or "")
            label = str(item.get("label", path) or path)
            kind = self._json_api_kind(path)
            drawer_id = f"admin-json-api-{self._dom_id_fragment(path)}"
            description = self._json_api_description(path)
            curl = (
                f"curl http://127.0.0.1:8030{path}"
                if "<" not in path
                else f"curl http://127.0.0.1:8030{path}"
            )
            rows.append(
                {
                    "select": f"<input type='checkbox' name='api_path' value='{escape(path, quote=True)}' />",
                    "api": f"<strong>{escape(label)}</strong><div class='mono'>{escape(path)}</div>",
                    "kind": self._admin_status(
                        kind, tone="warning" if kind == "detail" else "ok"
                    ),
                    "description": escape(description),
                    "curl": f"<span class='mono'>{escape(curl)}</span>",
                    "actions": (
                        "<div class='admin-table-actions'>"
                        + self._admin_drawer_button("详情", drawer_id)
                        + (
                            self._route_link_new_tab("打开 JSON", path)
                            if "<" not in path
                            else "<span class='meta'>需替换参数</span>"
                        )
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"接口 · {label}",
                    self._json_api_detail(
                        label=label,
                        path=path,
                        kind=kind,
                        description=description,
                        curl=curl,
                    ),
                )
            )
        return self._admin_table(
            table_id=table_id,
            columns=columns,
            rows=rows,
            empty_text="当前没有匹配接口。",
        ), "".join(drawers)

    def _json_api_detail(
        self, *, label: str, path: str, kind: str, description: str, curl: str
    ) -> str:
        fields = [
            ("接口", label),
            ("Path", path),
            ("类型", kind),
            ("说明", description),
        ]
        return (
            "<div class='admin-detail-grid'>"
            + "".join(
                "<div class='admin-detail-item'>"
                f"<small>{escape(str(name))}</small>"
                f"<strong>{escape(str(value or 'n/a'))}</strong>"
                "</div>"
                for name, value in fields
            )
            + "</div><pre class='mono compact-pre'>"
            + escape(curl)
            + "</pre>"
        )

    def _json_api_filters(self, query: Mapping[str, Sequence[str]]) -> dict[str, Any]:
        raw_query = {
            str(key): [str(value) for value in list(values or [])]
            for key, values in dict(query or {}).items()
        }
        return {
            "keyword": self._str_query(raw_query, "keyword"),
            "kind": self._str_query(raw_query, "kind"),
            "page": max(self._int_query(raw_query, "page", default=1), 1),
            "page_size": min(
                max(self._int_query(raw_query, "page_size", default=50), 1), 100
            ),
        }

    def _json_api_endpoint_matches(
        self, item: Mapping[str, Any], filters: Mapping[str, Any]
    ) -> bool:
        path = str(item.get("path", "") or "")
        label = str(item.get("label", path) or path)
        description = self._json_api_description(path)
        keyword = str(filters.get("keyword", "") or "").lower()
        if keyword and keyword not in " ".join([path, label, description]).lower():
            return False
        kind = str(filters.get("kind", "") or "").lower()
        return not kind or kind == self._json_api_kind(path)

    @staticmethod
    def _json_api_kind(path: str) -> str:
        return api_endpoint_kind(path)

    @staticmethod
    def _json_api_description(path: str) -> str:
        return api_endpoint_description(path)
