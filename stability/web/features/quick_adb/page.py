from __future__ import annotations

import json
import shlex
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote


class QuickAdbPageMixin:
    def _render_quick_adb(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        flash = dict(payload.get("flash", {}) or {})
        operation_result = dict(payload.get("operation_result", {}) or {})
        body = [
            self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")) if flash else "",
            self._admin_page_header(
                "快捷 ADB",
                subtitle="按 Android 调用链路组织常用诊断命令；目标选择、包名选择、执行和结果查看都在当前页完成。",
                breadcrumbs=[("首页", "/"), ("快捷 ADB", "")],
                actions=[self._route_link("设备池", "/device-pools"), self._route_link("JSON API", "/api/quick-adb")],
            ),
            self._admin_summary_strip(
                [
                    ("链路层级", summary.get("layer_count", 0)),
                    ("当前命令", summary.get("command_count", 0)),
                    ("命令总数", summary.get("total_command_count", 0)),
                    ("可用设备", summary.get("available_device_count", 0)),
                    ("执行策略", "白名单模板"),
                ]
            ),
            "<details class='panel quick-adb-layer-panel'><summary><strong>Android 调用链路</strong><span>点击链路只做命令过滤</span></summary>"
            + self._quick_adb_layer_flow(payload)
            + "</details>",
            self._quick_adb_filter_bar(payload),
            self._quick_adb_target_section(payload),
            self._quick_adb_command_workspace(payload),
            self._quick_adb_result_modal(operation_result),
        ]
        help_buttons, help_sections = self._quick_adb_help_sections()
        return self._layout(
            "快捷 ADB",
            "按 App、Framework、System Server、Native Service、HAL、Kernel/Driver、硬件链路组织常用 ADB 诊断命令。",
            "".join(body),
            help_buttons=help_buttons,
            help_modal_sections=help_sections,
        )

    def _quick_adb_target_section(self, payload: dict[str, Any]) -> str:
        return (
            "<details class='panel quick-adb-target-panel' open>"
            "<summary><strong>执行目标</strong><span>选择设备、包名和临时目标</span><b>收起/展开</b></summary>"
            "<div class='quick-adb-target-body'>"
            + self._quick_adb_target_controls(payload)
            + "</div>"
            "</details>"
        )

    def _quick_adb_filter_bar(self, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        layer_options = [{"value": "", "label": "全部"}] + [
            {"value": str(item.get("key", "") or ""), "label": str(item.get("label", "") or "")}
            for item in list(payload.get("layers", []) or [])
        ]
        group_options = [{"value": "", "label": "全部"}] + [
            {"value": str(item), "label": str(item)}
            for item in list(payload.get("group_options", []) or [])
        ]
        risk_options = [{"value": "", "label": "全部"}] + [
            {"value": str(item), "label": str(item)}
            for item in list(payload.get("risk_options", []) or [])
        ]
        param_options = [{"value": "", "label": "全部"}] + [
            {"value": str(item), "label": str(item)}
            for item in list(payload.get("param_options", []) or [])
        ]
        return self._admin_filter_bar(
            action="/quick-adb",
            values=filters,
            fields=[
                {"name": "keyword", "label": "关键词", "placeholder": "命令 / dumpsys / binder / meminfo"},
                {"name": "layer", "label": "链路", "type": "select", "options": layer_options},
                {"name": "group", "label": "分类", "type": "select", "options": group_options},
                {"name": "risk", "label": "风险", "type": "select", "options": risk_options},
                {"name": "param", "label": "参数", "type": "select", "options": param_options},
                {"name": "page_size", "label": "每页", "type": "number"},
            ],
        )

    def _quick_adb_help_sections(self) -> tuple[list[tuple[str, str]], dict[str, str]]:
        buttons = [
            ("help-quickstart", "选择命令"),
            ("help-sampling", "采集证据"),
            ("help-analysis", "判读结果"),
        ]
        sections = {
            "help-quickstart": self._help_card(
                "按链路选择命令",
                [
                    "先根据现象选择链路：App 问题看包、前台和 meminfo；黑屏卡顿看 Window、Display、SurfaceFlinger；重启和卡死看 bootreason、pstore、dmesg。",
                    "点击顶部链路卡片只做过滤；点击“全部链路”可以回到完整命令集。",
                    "Package 类命令需要填写包名，其它命令会直接使用当前页面的设备选择。",
                ],
                links=[("设备池", "/device-pools"), ("接口 JSON", "/api/quick-adb")],
                meta="这里的命令全部来自预置白名单，不执行页面外的任意输入命令。",
            ),
            "help-sampling": self._help_card(
                "采集时保留现场",
                [
                    "优先选择一个或多个设备，再执行对应命令；多选设备会逐台执行并在弹窗里按设备汇总。",
                    "先抓轻量快照，如 ps、top、dumpsys、dropbox、events，再按需要抓 bugreport。",
                    "带 may_require_privilege 的命令在 user build 上可能失败，失败本身只代表权限或内核能力不足。",
                ],
                code=[
                    "常用顺序：",
                    "1. logcat / events / dropbox",
                    "2. dumpsys window / display / power / SurfaceFlinger",
                    "3. meminfo / cpuinfo / df / thermal",
                    "4. bugreport / pstore / dmesg",
                ],
            ),
            "help-analysis": self._help_card(
                "从输出判断方向",
                [
                    "执行后先看弹窗顶部的 returncode、timeout 和设备明细，确认是否所有设备都拿到结果。",
                    "stdout 是主要证据，stderr 多用于判断权限、设备离线或命令不支持。",
                    "同一问题尽量同时保留时间点、设备、版本指纹、进程状态和日志证据，方便和报告、Top Issue、准入材料对齐。",
                ],
                links=[("问题中心", "/issues"), ("准入中心", "/admission")],
                meta="不要把空输出直接解释成无异常，先确认命令权限、构建类型和设备状态。",
            ),
        }
        return buttons, sections

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
        selected_devices = [
            str(item).strip()
            for item in list(payload.get("selected_device_ids", []) or [])
            if str(item).strip()
        ]
        selected_device_set = set(selected_devices)
        choice_device_ids = {
            str(item.get("device_id", "") or "")
            for item in choices
            if str(item.get("device_id", "") or "")
        }
        custom_devices = [device_id for device_id in selected_devices if device_id not in choice_device_ids]
        selected_packages = [
            str(item).strip()
            for item in list(payload.get("selected_package_names", []) or [])
            if str(item).strip()
        ]
        package_options = "".join(
            "<option value='"
            + escape(package_name, quote=True)
            + "' selected>"
            + escape(f"{package_name} [已选择]")
            + "</option>"
            for package_name in selected_packages
        )
        if not package_options:
            package_options = "<option value=''>选择设备后自动加载包名；也可以点击“加载包名”。</option>"
        selected_device_summary = self._quick_adb_selected_item_summary(
            "quick-adb-selected-devices",
            "当前已选设备",
            selected_devices,
            "尚未选择设备；勾选设备池设备或在临时设备里输入后会显示在这里。",
            chip_class="quick-adb-device-chip",
        )
        selected_package_summary = self._quick_adb_selected_item_summary(
            "quick-adb-selected-packages",
            "当前已选包名",
            selected_packages,
            "尚未选择包名；勾选下拉包名或在下方手动输入后会显示在这里。",
            chip_class="quick-adb-package-chip",
        )
        if choices:
            options = "".join(
                "<option value='"
                + escape(str(item.get("device_id", "") or ""), quote=True)
                + ("' selected>" if str(item.get("device_id", "") or "") in selected_device_set else "'>")
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
            "<textarea id='quick-adb-custom-device-ids' rows='2' placeholder='可选。多个设备用逗号、空格或换行分隔，例如 serial-1, 192.168.31.99:5555'>"
            + escape("\n".join(custom_devices))
            + "</textarea>"
            "</label>"
            f"<div class='meta'>{escape(hint)} 这个入口会应用到下方所有命令，多选后会按设备逐条执行并汇总输出。</div>"
            f"{selected_device_summary}"
            f"{selected_package_summary}"
            "<details class='quick-adb-package-panel'>"
            "<summary><strong>包名选择</strong><span>展开加载、搜索或手动输入包名</span></summary>"
            "<div class='quick-adb-package-body'>"
            "<div class='quick-adb-package-controls'>"
            "<label>包类型<select id='quick-adb-package-scope'>"
            "<option value='third_party'>第三方包</option>"
            "<option value='system'>系统包</option>"
            "<option value='all'>全部包</option>"
            "</select></label>"
            "<label>搜索<input id='quick-adb-package-query' type='search' placeholder='输入关键字过滤包名，例如 camera / settings / example' /></label>"
            "<button type='button' id='quick-adb-package-refresh'>加载包名</button>"
            "</div>"
            "<label>设备包名"
            "<select id='quick-adb-package-select' multiple size='8' data-empty-label='选择设备后自动加载包名；也可以点击“加载包名”。'>"
            f"{package_options}"
            "</select></label>"
            "<label>手动输入包名"
            "<textarea id='quick-adb-manual-packages' rows='2' placeholder='可选。多个包名用逗号、空格或换行分隔，例如 com.android.settings, com.example.app'></textarea>"
            "</label>"
            "<div id='quick-adb-package-status' class='meta'>下拉包名来自当前选中的第一个设备；多选包名会按设备和包名组合逐条执行。</div>"
            "</div></details>"
            "</div>"
        )

    @staticmethod
    def _quick_adb_selected_item_summary(
        element_id: str,
        title: str,
        items: list[str],
        empty_text: str,
        *,
        chip_class: str,
    ) -> str:
        if items:
            chips = "".join(
                f"<span class='{escape(chip_class, quote=True)}'>{escape(item)}</span>"
                for item in items
            )
            content = (
                f"<div class='quick-adb-selected-title'><strong>{escape(title)}</strong>"
                f"<span>{len(items)} 个</span></div><div class='quick-adb-selected-chip-list'>{chips}</div>"
            )
        else:
            content = (
                f"<div class='quick-adb-selected-title'><strong>{escape(title)}</strong><span>0 个</span></div>"
                f"<div class='quick-adb-selected-empty'>{escape(empty_text)}</div>"
            )
        return f"<div id='{escape(element_id, quote=True)}' class='quick-adb-selected-items'>{content}</div>"

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

    def _quick_adb_command_workspace(self, payload: Mapping[str, Any]) -> str:
        table_id = "quick-adb-admin-table"
        columns = self._quick_adb_command_columns()
        toolbar = self._admin_toolbar(
            title="快捷命令",
            description="命令按表格扫描；执行使用上方统一目标，多设备和多包名会自动拆分执行。",
            table_id=table_id,
            columns=columns,
            actions=[
                "<a class='button secondary' href='/quick-adb'>全部链路</a>",
                self._route_link("设备池", "/device-pools"),
            ],
        )
        table_html, drawers = self._quick_adb_command_table(payload, table_id=table_id, columns=columns)
        pagination = self._admin_pagination(
            base_path="/quick-adb",
            filters=dict(payload.get("filters", {}) or {}),
            page=int(dict(payload.get("pagination", {}) or {}).get("page", 1) or 1),
            page_size=int(dict(payload.get("pagination", {}) or {}).get("page_size", 20) or 20),
            total=int(dict(payload.get("pagination", {}) or {}).get("total", 0) or 0),
        )
        return (
            "<section class='panel admin-list-panel quick-adb-command-panel'>"
            + toolbar
            + table_html
            + pagination
            + "</section>"
            + drawers
        )

    @staticmethod
    def _quick_adb_command_columns() -> list[dict[str, Any]]:
        return [
            {"key": "select", "label": "", "locked": True},
            {"key": "command", "label": "名称"},
            {"key": "layer", "label": "链路"},
            {"key": "group", "label": "分类"},
            {"key": "adb_command", "label": "命令"},
            {"key": "params", "label": "参数"},
            {"key": "risk", "label": "风险"},
            {"key": "timeout", "label": "超时"},
            {"key": "actions", "label": "操作", "locked": True},
        ]

    def _quick_adb_command_table(
        self,
        payload: Mapping[str, Any],
        *,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> tuple[str, str]:
        commands = list(payload.get("commands", []) or [])
        if not commands:
            return self._admin_table(table_id=table_id, columns=columns, rows=[], empty_text="当前过滤条件下没有命令。"), ""
        current_actor = dict(payload.get("current_actor", {}) or {})
        rows: list[dict[str, str]] = []
        drawers: list[str] = []
        layer_labels = {
            str(item.get("key", "") or ""): str(item.get("label", "") or "")
            for item in list(payload.get("layers", []) or [])
        }
        for command in commands:
            item = dict(command or {})
            command_id = str(item.get("command_id", "") or "")
            title = str(item.get("title", "") or command_id)
            layer = str(item.get("layer", "") or "")
            params = [str(value) for value in list(item.get("params", []) or []) if str(value)]
            risk = str(item.get("risk", "") or "safe")
            drawer_id = f"quick-adb-command-{self._quick_adb_dom_id(command_id)}"
            args = shlex.join(["adb", *[str(arg) for arg in list(item.get("args", []) or [])]])
            rows.append(
                {
                    "select": f"<input type='checkbox' name='command_id' value='{escape(command_id, quote=True)}' />",
                    "command": (
                        f"<strong title='{escape(title, quote=True)}'>{escape(title)}</strong>"
                        f"<div class='mono' title='{escape(args, quote=True)}'>{escape(command_id)}</div>"
                    ),
                    "layer": escape(layer_labels.get(layer, layer) or "n/a"),
                    "group": escape(str(item.get("group", "") or "未分类")),
                    "adb_command": f"<span class='mono quick-adb-command-text' title='{escape(args, quote=True)}'>{escape(args)}</span>",
                    "params": self._quick_adb_param_chips(params),
                    "risk": self._quick_adb_risk_label(risk),
                    "timeout": escape(str(item.get("timeout_seconds", 20))) + "s",
                    "actions": (
                        "<div class='admin-table-actions quick-adb-table-actions'>"
                        + self._admin_drawer_button("详情", drawer_id)
                        + self._quick_adb_execute_form(item, current_actor=current_actor, compact=True)
                        + "</div>"
                    ),
                }
            )
            drawers.append(
                self._admin_drawer(
                    drawer_id,
                    f"ADB 命令 · {title}",
                    self._quick_adb_command_detail(item, current_actor=current_actor),
                )
            )
        return self._admin_table(table_id=table_id, columns=columns, rows=rows, empty_text="当前过滤条件下没有命令。"), "".join(drawers)

    @staticmethod
    def _quick_adb_dom_id(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "")) or "unknown"

    @staticmethod
    def _quick_adb_param_chips(params: Sequence[str]) -> str:
        if not params:
            return "<span class='admin-status admin-status-muted'>无</span>"
        return "".join(
            f"<span class='admin-status admin-status-warning'>{escape(str(param))}</span>"
            for param in params
        )

    @staticmethod
    def _quick_adb_risk_label(risk: str) -> str:
        tone = "muted" if risk == "safe" else "warning"
        return f"<span class='admin-status admin-status-{tone}'>{escape(risk or 'safe')}</span>"

    def _quick_adb_execute_form(
        self,
        command: Mapping[str, Any],
        *,
        current_actor: Mapping[str, Any],
        compact: bool = False,
    ) -> str:
        params = set(command.get("params", []) or [])
        needs_package = "package" in params
        command_id = str(command.get("command_id", "") or "")
        package_help = (
            "<details class='quick-adb-package-help'>"
            "<summary aria-label='Package 参数说明' title='Package 参数说明'>?</summary>"
            "<div class='quick-adb-package-help-body'>使用上方“包名选择”。可从设备包名下拉多选，也可以手动输入包名。</div>"
            "</details>"
            if needs_package and not compact
            else ""
        )
        risk = str(command.get("risk", "safe") or "safe")
        risk_html = "" if compact or risk == "safe" else f"<span class='pill'>{escape(risk)}</span>"
        action_path = self._actor_scoped_path("/quick-adb/actions/execute", current_actor=current_actor)
        package_hidden = (
            "<input type='hidden' name='package_names' value='' data-quick-adb-package-target='1' />"
            if needs_package
            else ""
        )
        form_class = "quick-adb-form quick-adb-table-form" if compact else "quick-adb-form"
        timeout_label = "Timeout" if not compact else "超时"
        timeout_value = escape(str(command.get("timeout_seconds", 20)), quote=True)
        timeout_control = (
            f"<input type='hidden' name='timeout_seconds' value='{timeout_value}' />"
            if compact
            else f"<label>{timeout_label}<input type='number' min='3' max='180' name='timeout_seconds' value='{timeout_value}' /></label>"
        )
        return (
            f"<form method='post' action='{escape(action_path, quote=True)}' class='{form_class}'>"
            f"<input type='hidden' name='command_id' value='{escape(command_id, quote=True)}' />"
            "<input type='hidden' name='device_ids' value='' data-quick-adb-device-target='1' />"
            f"{package_hidden}"
            "<div class='quick-adb-command-actions'>"
            f"{package_help}{risk_html}"
            f"{timeout_control}"
            "<button type='submit'>执行</button>"
            "</div>"
            "</form>"
        )

    def _quick_adb_command_detail(self, command: Mapping[str, Any], *, current_actor: Mapping[str, Any]) -> str:
        args = shlex.join(["adb", *[str(item) for item in list(command.get("args", []) or [])]])
        fields = [
            ("命令 ID", command.get("command_id", "")),
            ("标题", command.get("title", "")),
            ("链路", command.get("layer", "")),
            ("分类", command.get("group", "")),
            ("风险", command.get("risk", "")),
            ("默认超时", f"{command.get('timeout_seconds', 20)}s"),
            ("参数", ", ".join(str(item) for item in list(command.get("params", []) or [])) or "无"),
        ]
        detail_grid = "".join(
            "<div class='admin-detail-item'>"
            f"<small>{escape(str(label))}</small>"
            f"<strong>{escape(str(value or 'n/a'))}</strong>"
            "</div>"
            for label, value in fields
        )
        return (
            "<div class='admin-detail-grid'>"
            + detail_grid
            + "</div>"
            f"<p>{escape(str(command.get('description', '') or ''))}</p>"
            "<pre class='mono compact-pre'>"
            + escape(args)
            + "</pre>"
            + self._quick_adb_execute_form(command, current_actor=current_actor)
        )

    def _quick_adb_result(self, result: dict[str, Any]) -> str:
        if not result:
            return ""
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
                "package_count": len(set(command.get("package_names", []) or [])),
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

    def _quick_adb_result_modal(self, result: dict[str, Any]) -> str:
        if not result:
            return ""
        command = dict(result.get("command", {}) or {})
        title = str(command.get("title", "") or "执行结果")
        return (
            "<div class='task-modal quick-adb-result-modal is-open' aria-hidden='false' role='dialog' aria-modal='true'>"
            "<div class='task-modal-backdrop' data-task-modal-close='1'></div>"
            "<div class='task-modal-dialog'>"
            "<div class='task-modal-header'>"
            f"<h3>ADB 执行结果 - {escape(title)}</h3>"
            "<button type='button' class='task-modal-close' data-task-modal-close='1' aria-label='关闭执行结果'>x</button>"
            "</div>"
            "<div class='task-modal-body'>"
            + self._quick_adb_result(result)
            + "</div>"
            "</div>"
            "</div>"
        )

    @staticmethod
    def _quick_adb_execution_row(execution: dict[str, Any]) -> str:
        command = dict(execution.get("command", {}) or {})
        result = dict(execution.get("result", {}) or {})
        device_id = str(command.get("device_id", "") or "adb-default")
        package_name = str(command.get("package_name", "") or "")
        ok = bool(result.get("ok", False))
        title = device_id if not package_name else f"{device_id} / {package_name}"
        return (
            "<div class='quick-adb-execution-row'>"
            f"<strong>{escape(title)}</strong>"
            f"<span class='pill'>{'ok' if ok else 'failed'}</span>"
            f"<span class='meta'>returncode={escape(str(result.get('returncode')))} "
            f"timeout={escape(str(bool(result.get('timed_out', False))).lower())} "
            f"duration={escape(str(command.get('duration_ms', 0)))}ms</span>"
            "</div>"
        )
