from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping


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
        body = [
            self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")) if flash else "",
            self._metric_grid(
                [
                    ("设备池", summary.get("pool_count", 0)),
                    ("设备总数", summary.get("device_count", 0)),
                    ("在线设备", summary.get("online_device_count", 0)),
                    ("可调度设备", summary.get("schedulable_device_count", 0)),
                    ("不可调度设备", summary.get("unschedulable_device_count", 0)),
                    ("当前过滤", filter_hint),
                ]
            ),
            self._section(
                "过滤入口",
                [
                    "<form method='get' action='/device-pools' class='compact-filter-form'>"
                    "<div class='device-filter-row'>"
                    f"<label>Group<input type='text' name='group' value='{escape(str(filters.get('group', '') or ''), quote=True)}' placeholder='例如 lab-a' /></label>"
                    f"<label>Team<input type='text' name='team' value='{escape(str(filters.get('team', '') or ''), quote=True)}' placeholder='例如 app-team' /></label>"
                    f"<label>Tag<input type='text' name='tag' value='{escape(','.join(filters.get('tags', []) or []), quote=True)}' placeholder='例如 smoke,android14' /></label>"
                    "<button type='submit'>查看</button>"
                    "<a class='action-link device-filter-api-link' href='/api/device-pools'>API</a>"
                    "</div>"
                    "</form>"
                ],
            ),
            self._section("设备状态刷新", [self._device_refresh_controls(payload)]),
            self._section(
                "设备池列表",
                [self._device_pool_cards(pools, current_actor=dict(payload.get("current_actor", {}) or {}))],
            ),
            self._section(
                "统计明细",
                [
                    "<pre class='mono'>"
                    + escape(
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
                    + "</pre>"
                ],
            ),
        ]
        return self._layout(
            "设备池",
            "按 group/team/tag 汇总设备池，让团队在创建任务或巡检前先看到可调度设备与不可调度原因。",
            "".join(body),
        )

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
