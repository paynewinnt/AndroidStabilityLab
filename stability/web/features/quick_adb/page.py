from __future__ import annotations

import json
import shlex
from html import escape
from typing import Any
from urllib.parse import quote


class QuickAdbPageMixin:
    def _render_quick_adb(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        flash = dict(payload.get("flash", {}) or {})
        operation_result = dict(payload.get("operation_result", {}) or {})
        body = [
            self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")) if flash else "",
            self._metric_grid(
                [
                    ("链路层级", summary.get("layer_count", 0)),
                    ("当前命令", summary.get("command_count", 0)),
                    ("命令总数", summary.get("total_command_count", 0)),
                    ("执行策略", "预置模板"),
                ]
            ),
            self._section("Android 调用链路", [self._quick_adb_layer_flow(payload)]),
            self._section("执行目标", [self._quick_adb_target_controls(payload)]),
            self._section("快捷命令", [self._quick_adb_command_cards(payload)]),
            self._section("执行结果", [self._quick_adb_result(operation_result)]),
        ]
        return self._layout(
            "快捷 ADB",
            "按 App、Framework、System Server、Native Service、HAL、Kernel/Driver、硬件链路组织常用 ADB 诊断命令。",
            "".join(body),
        )

    def _quick_adb_layer_flow(self, payload: dict[str, Any]) -> str:
        active_layer = str(dict(payload.get("filters", {}) or {}).get("layer", "") or "")
        all_active = " active" if not active_layer else ""
        items = [
            f"<a class='quick-adb-layer{all_active}' href='/quick-adb'>"
            "<strong>全部链路</strong><span>清除过滤，显示全部快捷命令</span></a>"
        ]
        for layer in list(payload.get("layers", []) or []):
            key = str(layer.get("key", "") or "")
            label = str(layer.get("label", "") or "")
            bridge = str(layer.get("bridge", "") or "")
            active = " active" if key == active_layer else ""
            items.append(
                f"<a class='quick-adb-layer{active}' href='/quick-adb?layer={quote(key, safe='')}'>"
                f"<strong>{escape(label)}</strong><span>{escape(bridge)}</span></a>"
            )
        return "<div class='quick-adb-flow'>" + "".join(items) + "</div>"

    def _quick_adb_target_controls(self, payload: dict[str, Any]) -> str:
        choices = list(payload.get("device_choices", []) or [])
        if choices:
            options = "".join(
                "<option value='"
                + escape(str(item.get("device_id", "") or ""), quote=True)
                + "'>"
                + escape(self._quick_adb_device_option_label(dict(item)))
                + "</option>"
                for item in choices
            )
            selector = (
                "<label>设备池可用设备"
                "<select id='quick-adb-device-select' multiple size='6'>"
                + options
                + "</select></label>"
            )
            hint = "从设备池加载可调度设备；按住 Command/Ctrl 可多选。"
        else:
            selector = self._notice("设备池当前没有可调度设备。可以先去设备池刷新，或在下方填写临时设备。", tone="warning")
            hint = "没有设备池候选时，留空使用 adb 默认设备，或填写临时 TCP/USB serial。"
        return (
            "<div class='quick-adb-target'>"
            + selector
            + "<label>临时设备"
            "<textarea id='quick-adb-custom-device-ids' rows='2' placeholder='可选。多个设备用逗号、空格或换行分隔，例如 serial-1, 192.168.31.99:5555'></textarea>"
            "</label>"
            f"<div class='meta'>{escape(hint)} 这个入口会应用到下方所有命令，多选后会按设备逐条执行并汇总输出。</div>"
            "</div>"
        )

    @staticmethod
    def _quick_adb_device_option_label(item: dict[str, Any]) -> str:
        tags = ",".join(str(tag) for tag in list(item.get("tags", []) or []) if str(tag).strip())
        suffix = " / ".join(
            part
            for part in [
                str(item.get("group_name", "") or ""),
                str(item.get("team", "") or ""),
                tags,
            ]
            if part
        )
        label = str(item.get("label", "") or item.get("device_id", "") or "")
        device_id = str(item.get("device_id", "") or "")
        return f"{label} ({device_id}) - {suffix}" if suffix else f"{label} ({device_id})"

    def _quick_adb_command_cards(self, payload: dict[str, Any]) -> str:
        commands = list(payload.get("commands", []) or [])
        if not commands:
            return self._notice("当前过滤条件下没有命令。", tone="warning")
        current_actor = dict(payload.get("current_actor", {}) or {})
        grouped: dict[str, list[dict[str, Any]]] = {}
        for command in commands:
            grouped.setdefault(str(command.get("group", "") or "未分类"), []).append(dict(command))
        return "<div class='quick-adb-groups'>" + "".join(
            "<section class='quick-adb-group'>"
            f"<h3>{escape(group)}</h3>"
            "<div class='quick-adb-command-grid'>"
            + "".join(self._quick_adb_command_card(command, current_actor=current_actor) for command in group_commands)
            + "</div></section>"
            for group, group_commands in grouped.items()
        ) + "</div>"

    def _quick_adb_command_card(self, command: dict[str, Any], *, current_actor: dict[str, Any]) -> str:
        params = set(command.get("params", []) or [])
        needs_package = "package" in params
        command_id = str(command.get("command_id", "") or "")
        args = shlex.join(["adb", *[str(item) for item in list(command.get("args", []) or [])]])
        package_field = (
            "<label>Package<input type='text' name='package_name' placeholder='com.example.app' required /></label>"
            if needs_package
            else ""
        )
        risk = str(command.get("risk", "safe") or "safe")
        risk_html = "" if risk == "safe" else f"<span class='pill'>{escape(risk)}</span>"
        action_path = self._actor_scoped_path("/quick-adb/actions/execute", current_actor=current_actor)
        return (
            "<article class='card quick-adb-command-card'>"
            "<div class='quick-adb-command-head'>"
            f"<h4>{escape(str(command.get('title', '') or command_id))}</h4>{risk_html}"
            "</div>"
            f"<p>{escape(str(command.get('description', '') or ''))}</p>"
            f"<pre class='mono compact-pre'>{escape(args)}</pre>"
            f"<form method='post' action='{escape(action_path, quote=True)}' class='quick-adb-form'>"
            f"<input type='hidden' name='command_id' value='{escape(command_id, quote=True)}' />"
            "<input type='hidden' name='device_ids' value='' data-quick-adb-device-target='1' />"
            "<div class='form-grid'>"
            f"{package_field}"
            f"<label>Timeout<input type='number' min='3' max='180' name='timeout_seconds' value='{escape(str(command.get('timeout_seconds', 20)), quote=True)}' /></label>"
            "</div>"
            "<div class='form-actions compact-form-actions'><button type='submit'>执行</button></div>"
            "</form>"
            "</article>"
        )

    def _quick_adb_result(self, result: dict[str, Any]) -> str:
        if not result:
            return self._notice("尚未执行命令。选择上方任意命令后，输出会显示在这里。")
        command = dict(result.get("command", {}) or {})
        execution = dict(result.get("result", {}) or {})
        tone = "ok" if execution.get("ok") else "danger"
        stdout = str(execution.get("stdout", "") or "")
        stderr = str(execution.get("stderr", "") or "")
        output_path = str(command.get("output_path", "") or "")
        executions = list(result.get("executions", []) or [])
        payload = {
            "command": command,
            "result": {
                "ok": bool(execution.get("ok", False)),
                "returncode": execution.get("returncode"),
                "timed_out": bool(execution.get("timed_out", False)),
                "stdout_size": len(stdout),
                "stderr_size": len(stderr),
                "execution_count": len(executions) or 1,
            },
        }
        execution_cards = ""
        if executions:
            execution_cards = (
                "<article class='card stack'><h3>设备执行明细</h3><div class='quick-adb-execution-list'>"
                + "".join(self._quick_adb_execution_row(item) for item in executions)
                + "</div></article>"
            )
        return (
            self._notice(
                "执行成功。" if execution.get("ok") else "至少一个设备执行失败或超时，查看 stderr/returncode。",
                tone=tone,
            )
            + (
                f"<div class='notice'>输出文件：<span class='mono'>{escape(output_path)}</span></div>"
                if output_path
                else ""
            )
            + "<div class='cards quick-adb-result-grid'>"
            "<article class='card stack'><h3>命令</h3><pre class='mono'>"
            + escape(shlex.join([str(item) for item in list(command.get("full_command", []) or [])]))
            + "</pre><pre class='mono'>"
            + escape(json.dumps(payload, ensure_ascii=False, indent=2))
            + "</pre></article>"
            + execution_cards
            + "<article class='card stack'><h3>stdout</h3><pre class='mono compact-pre'>"
            + escape(stdout or "(empty)")
            + "</pre></article>"
            + "<article class='card stack'><h3>stderr</h3><pre class='mono compact-pre'>"
            + escape(stderr or "(empty)")
            + "</pre></article>"
            + "</div>"
        )

    @staticmethod
    def _quick_adb_execution_row(execution: dict[str, Any]) -> str:
        command = dict(execution.get("command", {}) or {})
        result = dict(execution.get("result", {}) or {})
        device_id = str(command.get("device_id", "") or "adb-default")
        ok = bool(result.get("ok", False))
        return (
            "<div class='quick-adb-execution-row'>"
            f"<strong>{escape(device_id)}</strong>"
            f"<span class='pill'>{'ok' if ok else 'failed'}</span>"
            f"<span class='meta'>returncode={escape(str(result.get('returncode')))} "
            f"timeout={escape(str(bool(result.get('timed_out', False))).lower())} "
            f"duration={escape(str(command.get('duration_ms', 0)))}ms</span>"
            "</div>"
        )
