from __future__ import annotations

from html import escape
from math import ceil
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode


class AdminComponentsMixin:
    @staticmethod
    def _admin_page_header(
        title: str,
        *,
        subtitle: str = "",
        breadcrumbs: Sequence[tuple[str, str]] = (),
        actions: Sequence[str] = (),
    ) -> str:
        crumb_items = []
        for label, path in breadcrumbs:
            label_text = str(label or "").strip()
            path_text = str(path or "").strip()
            if not label_text:
                continue
            if path_text:
                crumb_items.append(f"<a href='{escape(path_text, quote=True)}'>{escape(label_text)}</a>")
            else:
                crumb_items.append(f"<span>{escape(label_text)}</span>")
        crumbs = "<nav class='admin-breadcrumb'>" + "<span>/</span>".join(crumb_items) + "</nav>" if crumb_items else ""
        action_html = "<div class='admin-page-actions'>" + "".join(actions) + "</div>" if actions else ""
        subtitle_html = f"<div class='admin-page-subtitle'>{escape(subtitle)}</div>" if subtitle else ""
        return (
            "<header class='admin-page-header'>"
            "<div class='admin-page-heading'>"
            + crumbs
            + f"<h1>{escape(title)}</h1>"
            + subtitle_html
            + "</div>"
            + action_html
            + "</header>"
        )

    @staticmethod
    def _admin_summary_strip(items: Sequence[tuple[str, Any]], *, compact: bool = True) -> str:
        class_name = "admin-summary-strip admin-summary-compact" if compact else "admin-summary-strip"
        cells = "".join(
            "<span class='admin-summary-item'>"
            f"<small>{escape(str(label))}</small>"
            f"<strong>{escape(str(value))}</strong>"
            "</span>"
            for label, value in items
        )
        return f"<section class='{class_name}'>{cells}</section>"

    @staticmethod
    def _admin_filter_bar(
        *,
        action: str,
        fields: Sequence[Mapping[str, Any]],
        values: Mapping[str, Any],
        hidden: Mapping[str, Any] | None = None,
    ) -> str:
        rendered_fields = []
        for field in fields:
            name = str(field.get("name", "") or "").strip()
            if not name:
                continue
            label = str(field.get("label", name) or name)
            field_type = str(field.get("type", "text") or "text")
            value = str(values.get(name, field.get("value", "")) or "")
            placeholder = str(field.get("placeholder", "") or "")
            if field_type == "select":
                options = []
                for option in list(field.get("options", []) or []):
                    if isinstance(option, Mapping):
                        option_value = str(option.get("value", "") or "")
                        option_label = str(option.get("label", option_value) or option_value)
                    else:
                        option_value = str(option)
                        option_label = str(option)
                    selected = " selected" if option_value == value else ""
                    options.append(
                        f"<option value='{escape(option_value, quote=True)}'{selected}>{escape(option_label)}</option>"
                    )
                control = f"<select name='{escape(name, quote=True)}'>{''.join(options)}</select>"
            else:
                control = (
                    f"<input type='{escape(field_type, quote=True)}' name='{escape(name, quote=True)}' "
                    f"value='{escape(value, quote=True)}' placeholder='{escape(placeholder, quote=True)}' />"
                )
            safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name)
            wide_names = {
                "keyword",
                "package_name",
                "device_id",
                "target_type",
                "event_type",
                "group",
                "team",
                "tag",
            }
            field_classes = ["admin-filter-field", f"admin-filter-field-{safe_name}"]
            if name in wide_names or bool(field.get("wide", False)):
                field_classes.append("admin-filter-field-wide")
            rendered_fields.append(
                f"<label class='{escape(' '.join(field_classes), quote=True)}'>"
                f"<span>{escape(label)}</span>"
                + control
                + "</label>"
            )
        hidden_inputs = "".join(
            f"<input type='hidden' name='{escape(str(key), quote=True)}' value='{escape(str(value), quote=True)}' />"
            for key, value in dict(hidden or {}).items()
            if str(value or "").strip()
        )
        return (
            f"<form method='get' action='{escape(action, quote=True)}' class='admin-filter-bar'>"
            + hidden_inputs
            + "<div class='admin-filter-fields'>"
            + "".join(rendered_fields)
            + "</div>"
            "<div class='admin-filter-actions'>"
            "<button type='submit'>查询</button>"
            f"<a class='button secondary' href='{escape(action, quote=True)}'>重置</a>"
            "</div>"
            "</form>"
        )

    @staticmethod
    def _admin_toolbar(
        *,
        title: str = "",
        description: str = "",
        actions: Sequence[str] = (),
        table_id: str = "",
        columns: Sequence[Mapping[str, Any]] = (),
    ) -> str:
        heading = ""
        if title or description:
            heading = (
                "<div class='admin-toolbar-heading'>"
                + (f"<strong>{escape(title)}</strong>" if title else "")
                + (f"<span>{escape(description)}</span>" if description else "")
                + "</div>"
            )
        column_button = (
            f"<button type='button' class='secondary' data-admin-column-settings-target='{escape(table_id, quote=True)}'>列设置</button>"
            if table_id and columns
            else ""
        )
        return (
            "<div class='admin-toolbar'>"
            + heading
            + "<div class='admin-toolbar-actions'>"
            + "".join(actions)
            + column_button
            + "</div>"
            + "</div>"
            + (AdminComponentsMixin._admin_column_settings(table_id=table_id, columns=columns) if table_id and columns else "")
        )

    @staticmethod
    def _admin_column_settings(*, table_id: str, columns: Sequence[Mapping[str, Any]]) -> str:
        toggles = []
        for column in columns:
            key = str(column.get("key", "") or "").strip()
            if not key or bool(column.get("locked", False)):
                continue
            label = str(column.get("label", key) or key)
            checked = " checked" if bool(column.get("default_visible", True)) else ""
            toggles.append(
                "<label>"
                f"<input type='checkbox' data-admin-table-col-toggle='{escape(table_id, quote=True)}' "
                f"data-admin-col='{escape(key, quote=True)}'{checked} />"
                f"<span>{escape(label)}</span>"
                "</label>"
            )
        if not toggles:
            return ""
        return (
            f"<div class='admin-column-settings' data-admin-column-settings-panel='{escape(table_id, quote=True)}' hidden>"
            "<div class='admin-column-settings-head'><strong>列设置</strong><span>勾选要展示的字段，设置会保存在当前浏览器。</span></div>"
            "<div class='admin-column-settings-grid'>"
            + "".join(toggles)
            + "</div></div>"
        )

    @staticmethod
    def _admin_table(
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
        rows: Sequence[Mapping[str, str]],
        empty_text: str = "暂无数据。",
    ) -> str:
        header = "".join(
            f"<th data-admin-col='{escape(str(column.get('key', '') or ''), quote=True)}'>{escape(str(column.get('label', '') or ''))}</th>"
            for column in columns
        )
        if not rows:
            return (
                f"<div class='admin-table-wrap'><table id='{escape(table_id, quote=True)}' class='admin-table'>"
                f"<thead><tr>{header}</tr></thead>"
                f"<tbody><tr><td colspan='{len(columns)}' class='admin-empty-cell'>{escape(empty_text)}</td></tr></tbody>"
                "</table></div>"
            )
        body_rows = []
        for row in rows:
            cells = "".join(
                f"<td data-admin-col='{escape(str(column.get('key', '') or ''), quote=True)}'>"
                + str(row.get(str(column.get("key", "") or ""), ""))
                + "</td>"
                for column in columns
            )
            body_rows.append(f"<tr>{cells}</tr>")
        return (
            f"<div class='admin-table-wrap'><table id='{escape(table_id, quote=True)}' class='admin-table'>"
            f"<thead><tr>{header}</tr></thead>"
            "<tbody>"
            + "".join(body_rows)
            + "</tbody></table></div>"
        )

    @staticmethod
    def _admin_drawer(drawer_id: str, title: str, body: str, *, footer: str = "") -> str:
        return (
            f"<aside id='{escape(drawer_id, quote=True)}' class='admin-drawer' aria-hidden='true'>"
            "<div class='admin-drawer-backdrop' data-admin-drawer-close='1'></div>"
            "<div class='admin-drawer-panel' role='dialog' aria-modal='true'>"
            "<div class='admin-drawer-header'>"
            f"<h3>{escape(title)}</h3>"
            "<button type='button' class='admin-drawer-close' data-admin-drawer-close='1' aria-label='关闭抽屉'>x</button>"
            "</div>"
            "<div class='admin-drawer-body'>"
            + body
            + "</div>"
            + (f"<div class='admin-drawer-footer'>{footer}</div>" if footer else "")
            + "</div></aside>"
        )

    @staticmethod
    def _admin_drawer_button(label: str, drawer_id: str, *, class_name: str = "link-button") -> str:
        return (
            f"<button type='button' class='{escape(class_name, quote=True)}' "
            f"data-admin-drawer-target='{escape(drawer_id, quote=True)}'>{escape(label)}</button>"
        )

    @staticmethod
    def _admin_pagination(
        *,
        base_path: str,
        filters: Mapping[str, Any],
        page: int,
        page_size: int,
        total: int,
    ) -> str:
        page = max(int(page or 1), 1)
        page_size = max(int(page_size or 20), 1)
        total = max(int(total or 0), 0)
        page_count = max(ceil(total / page_size), 1)

        def link(label: str, target_page: int, *, disabled: bool = False, active: bool = False) -> str:
            if disabled:
                return f"<span class='admin-page-link disabled'>{escape(label)}</span>"
            params = {
                key: value
                for key, value in dict(filters or {}).items()
                if str(value or "").strip()
            }
            params["page"] = str(target_page)
            params["page_size"] = str(page_size)
            href = f"{base_path}?{urlencode(params)}"
            class_name = "admin-page-link active" if active else "admin-page-link"
            return f"<a class='{class_name}' href='{escape(href, quote=True)}'>{escape(label)}</a>"

        window_start = max(1, page - 2)
        window_end = min(page_count, page + 2)
        links = [
            link("上一页", page - 1, disabled=page <= 1),
            *(link(str(index), index, active=index == page) for index in range(window_start, window_end + 1)),
            link("下一页", page + 1, disabled=page >= page_count),
        ]
        return (
            "<div class='admin-pagination'>"
            f"<span>共 {total} 条 / 第 {page} 页 / 共 {page_count} 页</span>"
            "<div class='admin-page-links'>"
            + "".join(links)
            + "</div></div>"
        )

    @staticmethod
    def _admin_status(label: str, *, tone: str = "ok") -> str:
        tone_class = {
            "danger": "admin-status-danger",
            "warning": "admin-status-warning",
            "muted": "admin-status-muted",
            "ok": "admin-status-ok",
        }.get(tone, "admin-status-ok")
        return f"<span class='admin-status {tone_class}'>{escape(str(label or 'unknown'))}</span>"


__all__ = ["AdminComponentsMixin"]
