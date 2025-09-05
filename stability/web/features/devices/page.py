from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping, Sequence


class DevicesPageMixin:
    def _render_device_pools(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        pools = list(payload.get("pools", []) or [])
        flash = dict(payload.get("flash", {}) or {})
        filter_hint = " / ".join(
            item
            for item in [
                f"group={filters.get('group')}" if filters.get("group") else "",
                f"team={filters.get('team')}" if filters.get("team") else "",
                f"tag={','.join(filters.get('tags', []) or [])}" if filters.get("tags") else "",
            ]
            if item
        ) or "全部设备"
        flash_html = self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")) if flash else ""
        body = [
            flash_html,
            self._admin_page_header(
                "设备池",
                subtitle="按 group/team/tag 管理可调度设备，刷新、连接和标记编辑都留在列表上下文内。",
                breadcrumbs=[("首页", "/"), ("设备池", "")],
                actions=[self._route_link("API", "/api/device-pools")],
            ),
            self._admin_summary_strip(
                [
                    ("设备池", summary.get("pool_count", 0)),
                    ("设备总数", summary.get("device_count", 0)),
                    ("在线设备", summary.get("online_device_count", 0)),
                    ("可调度设备", summary.get("schedulable_device_count", 0)),
                    ("不可调度设备", summary.get("unschedulable_device_count", 0)),
                    ("当前过滤", filter_hint),
                ]
            ),
            self._device_pool_filter_bar(filters),
            self._device_pool_admin_workspace(payload, pools=pools),
        ]
        return self._layout(
            "设备池",
            "按 group/team/tag 汇总设备池，让团队在创建任务或巡检前先看到可调度设备与不可调度原因。",
            "".join(body),
        )

    def _device_pool_filter_bar(self, filters: Mapping[str, Any]) -> str:
        values = dict(filters or {})
        values["tag"] = ",".join(values.get("tags", []) or [])
        return self._admin_filter_bar(
            action="/device-pools",
            values=values,
            fields=[
                {"name": "group", "label": "Group", "placeholder": "例如 lab-a"},
                {"name": "team", "label": "Team", "placeholder": "例如 app-team"},
                {"name": "tag", "label": "Tag", "placeholder": "例如 smoke,android14"},
            ],
        )

    def _device_pool_admin_workspace(self, payload: Mapping[str, Any], *, pools: Sequence[Mapping[str, Any]]) -> str:
        table_id = "device-pools-admin-table"
        columns = self._device_pool_admin_columns()
        summary = dict(payload.get("summary", {}) or {})
        toolbar = self._admin_toolbar(
            title="设备池列表",
            description="刷新 ADB、连接无线设备和编辑设备标记。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/device-pools'>刷新页面</a>",
                self._route_link("任务大厅", "/tasks"),
            ],
        )
        table_html, drawers = self._device_pool_admin_table(payload, pools=pools, table_id=table_id, columns=columns)
        stats_json = escape(
            json.dumps(
                {
                    "group_counts": summary.get("group_counts", {}),
                    "team_counts": summary.get("team_counts", {}),
                    "tag_counts": summary.get("tag_counts", {}),
                    "unschedulable_reason_counts": summary.get("unschedulable_reason_counts", {}),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return (
            "<section class='panel admin-list-panel'>"
            + toolbar
            + "<details class='compact-details device-refresh-drawer'><summary>设备状态刷新</summary>"
            + self._device_refresh_controls(payload)
            + "</details>"
            + table_html
            + "<details class='compact-details'><summary>统计明细</summary><pre class='mono compact-pre'>"
            + stats_json
            + "</pre></details>"
            + "</section>"
            + drawers
        )

    @staticmethod
    def _device_pool_admin_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "pool", "label": "设备池"},
            {"key": "devices", "label": "设备"},
            {"key": "online", "label": "在线"},
            {"key": "schedulable", "label": "可调度"},
            {"key": "blocked", "label": "不可调度"},
            {"key": "tags", "label": "Tag"},
            {"key": "reasons", "label": "阻塞原因"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _device_pool_admin_table(
        self,
        payload: Mapping[str, Any],
        *,
        pools: Sequence[Mapping[str, Any]],
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        actor = dict(payload.get("current_actor", {}) or {})
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        for pool in pools:
            item = dict(pool or {})
            group_name = str(item.get("group_name", "") or "ungrouped")
            team = str(item.get("team", "") or "unassigned")
            pool_key = str(item.get("pool_key", "") or f"{group_name}:{team}")
            drawer_id = f"admin-device-pool-{self._dom_id_fragment(pool_key)}"
            tags = ", ".join(str(tag) for tag in list(item.get("tags", []) or [])) or "n/a"
            reason_counts = dict(item.get("unschedulable_reason_counts", {}) or {})
            reasons = ", ".join(f"{key}:{value}" for key, value in sorted(reason_counts.items())) or "无"
            blocked_count = int(item.get("unschedulable_device_count", 0) or 0)
            rows.append(
                {
                    "select": f"<input type='checkbox' name='pool_key' value='{escape(pool_key, quote=True)}' />",
                    "pool": (
                        f"<strong>{escape(group_name)} / {escape(team)}</strong>"
                        f"<div class='mono'>{escape(pool_key)}</div>"
                    ),
                    "devices": escape(str(item.get("device_count", 0) or 0)),
                    "online": escape(str(item.get("online_device_count", 0) or 0)),
                    "schedulable": self._admin_status(str(item.get("schedulable_device_count", 0) or 0), tone="ok"),
                    "blocked": self._admin_status(str(blocked_count), tone="warning" if blocked_count else "muted"),
                    "tags": f"<span title='{escape(tags, quote=True)}'>{escape(tags)}</span>",
                    "reasons": f"<span title='{escape(reasons, quote=True)}'>{escape(reasons)}</span>",
                    "actions": (
                        "<div class='admin-table-actions'>"
                        + self._admin_drawer_button("详情/编辑", drawer_id)
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"设备池 · {group_name} / {team}",
                    self._device_pool_cards([item], current_actor=actor),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前过滤条件下没有设备池。"), "".join(drawers)

    def _device_refresh_controls(self, payload: Mapping[str, Any]) -> str:
        actions = dict(payload.get("device_actions", {}) or {})
        sync = dict(payload.get("device_sync", {}) or {})
        actor = dict(payload.get("current_actor", {}) or {})
        refresh_path = self._actor_scoped_path(
            str(actions.get("refresh_path") or "/device-pools/actions/refresh"),
            current_actor=actor,
        )
        connect_path = self._actor_scoped_path(
            str(actions.get("connect_path") or "/device-pools/actions/connect"),
            current_actor=actor,
        )
        pair_connect_path = self._actor_scoped_path(
            str(actions.get("pair_connect_path") or "/device-pools/actions/pair-connect"),
            current_actor=actor,
        )
        sync_line = ""
        if sync:
            sync_line = (
                "<div class='notice ok'>最近刷新："
                f"mode={escape(str(sync.get('mode', '') or ''))} "
                f"scanned={escape(str(sync.get('scanned_count', sync.get('found', 'n/a'))))} "
                f"updated={escape(str(sync.get('updated_count', sync.get('updated_device_id', 'n/a'))))}"
                "</div>"
            )
        return (
            "<div class='device-action-bar'>"
            f"<form method='post' action='{escape(refresh_path, quote=True)}' class='inline-action-form'>"
            "<button type='submit' title='刷新 ADB 设备' aria-label='刷新 ADB 设备'>刷新 ADB</button>"
            "</form>"
            f"<form method='post' action='{escape(connect_path, quote=True)}' class='inline-action-form device-connect-inline-form'>"
            "<label class='device-connect-field' title='连接 TCP 设备并刷新'>"
            "<span>TCP 设备</span>"
            "<input type='text' name='device_id' placeholder='192.168.31.99:5555' required />"
            "</label>"
            "<button type='submit' title='连接并刷新' aria-label='连接并刷新'>连接</button>"
            "</form>"
            "</div>"
            "<details class='wireless-pair-panel'>"
            "<summary>第一次无线调试？先配对再连接</summary>"
            "<div class='meta'>手机无线调试页有两组地址：底部弹窗的配对地址 + 配对码用于配对；页面上的 IP 地址用于后续连接。</div>"
            f"<form method='post' action='{escape(pair_connect_path, quote=True)}' class='wireless-pair-form'>"
            "<div class='form-grid-three'>"
            "<label title='配对地址和端口'>配对地址<input type='text' name='pair_device_id' placeholder='192.168.31.101:40539' required /></label>"
            "<label>配对码<input type='text' name='pairing_code' inputmode='numeric' placeholder='645916' required /></label>"
            "<label title='连接地址和端口'>连接地址<input type='text' name='connect_device_id' placeholder='192.168.31.101:42201' required /></label>"
            "</div>"
            "<div class='form-actions compact-form-actions'><button type='submit'>配对并连接</button></div>"
            "</form>"
            "</details>"
            + sync_line
            + "<div class='meta'>已配对设备直接填 IP 地址和端口后点“连接”；首次配对再展开上方入口。</div>"
        )

__all__ = ["DevicesPageMixin"]
