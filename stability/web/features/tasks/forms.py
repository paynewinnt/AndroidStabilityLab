from __future__ import annotations

from stability.scenario.registry import (
    METRIC_REGISTRY,
    default_metric_template_scopes,
    get_param_sections_for_web,
    get_scenario_definition,
    get_template_form_schema,
    list_scenario_definitions,
    metric_template_scopes,
)
from stability.time_utils import now_beijing_string

import json
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote


def _generated_at_now() -> str:
    return now_beijing_string()


class TaskFormsMixin:
    def _task_create_form(self, payload: Mapping[str, Any]) -> str:
        return self._long_run_task_create_form(payload) + self._standard_task_create_form(payload)

    def _task_operation_launcher(self, payload: Mapping[str, Any]) -> str:
        defaults = dict(payload.get("operation_defaults", {}) or {})
        auto_open_modal = str(defaults.get("auto_open_modal", "") or "")
        auto_open_marker = (
            f"<span hidden data-task-auto-open='{escape(auto_open_modal, quote=True)}'></span>"
            if auto_open_modal
            else ""
        )
        return (
            "<div class='task-operation-hub'>"
            "<div class='task-operation-buttons'>"
            + self._task_modal_button("创建长稳任务", "long-run-task", "配置长稳模板、轮转、补位、监控和日报/周报。")
            + self._task_modal_button("创建任务", "standard-task", "创建一次性或调试用 Task，不自动写入无人值守配置。")
            + self._task_modal_button("创建 Run", "create-run", "基于已有任务生成一次具体执行批次。")
            + self._task_modal_button("执行 Run", "execute-run", "选择监控 backend、并发、重试并开始执行。")
            + self._task_modal_button("归档 / 隐藏", "delete-task-run", "不物理删除，只从默认列表隐藏并记录审计事件。")
            + "</div>"
            "<div class='task-operation-note'>任务列表现在是主入口；Run 创建、执行和停止也可以直接从每个任务行打开。</div>"
            "</div>"
            + auto_open_marker
            + self._task_modal("long-run-task", "创建长稳任务", self._long_run_task_create_form(payload))
            + self._task_modal("standard-task", "创建任务", self._standard_task_create_form(payload))
            + self._task_modal("create-run", "创建 Run", self._run_create_form(payload))
            + self._task_modal("execute-run", "执行 Run", self._run_execute_form(payload))
            + self._task_modal("delete-task-run", "归档 / 隐藏", self._task_delete_boundary_card(payload))
        )

    @staticmethod
    def _task_modal_button(title: str, modal_id: str, hint: str) -> str:
        return (
            "<button type='button' class='task-operation-button' "
            f"data-task-modal-target='{escape(modal_id, quote=True)}' title='{escape(hint, quote=True)}'>"
            f"<strong>{escape(title)}</strong>"
            "</button>"
        )

    @staticmethod
    def _task_modal(modal_id: str, title: str, body: str) -> str:
        return (
            f"<div id='task-modal-{escape(modal_id, quote=True)}' class='task-modal' aria-hidden='true'>"
            "<div class='task-modal-backdrop' data-task-modal-close='1'></div>"
            "<div class='task-modal-dialog' role='dialog' aria-modal='true'>"
            "<div class='task-modal-header'>"
            f"<h3>{escape(title)}</h3>"
            "<button type='button' class='task-modal-close' data-task-modal-close='1' aria-label='关闭弹窗'>x</button>"
            "</div>"
            f"<div class='task-modal-body'>{body}</div>"
            "</div>"
            "</div>"
        )

    def _task_delete_boundary_card(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        options = "".join(
            self._task_option(item)
            for item in list(payload.get("tasks", []) or [])
            if str(item.get("task_id", "") or "").strip() and not bool(item.get("archived") or item.get("hidden"))
        )
        return (
            "<article class='card stack task-delete-boundary-card'>"
            "<h3>归档任务</h3>"
            "<p>这里执行的是软删除：任务会从默认任务列表隐藏，Run、监控快照、报告和准入证据不会被物理删除。</p>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/archive-task', current_actor=current_actor), quote=True)}' class='stack'>"
            "<label>任务<select name='task_id' required>" + (options or "<option value=''>当前没有可归档任务</option>") + "</select></label>"
            "<label>归档原因<textarea name='reason' rows='2' placeholder='例如 临时调试任务已结束，隐藏避免干扰列表。'></textarea></label>"
            "<div class='notice warning'>归档会记录服务端解析身份、request_id、session_id、audit_event_id，并投递 task.archived outbox 事件；不会删除任何历史产物。</div>"
            "<div class='form-actions'><button type='submit'>归档并隐藏</button></div>"
            "</form>"
            "</article>"
        )

    def _standard_task_create_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        defaults = dict(payload.get("operation_defaults", {}) or {})
        selected_template = str(defaults.get("template_type", "") or "cold_start_loop")
        template_schema = get_template_form_schema(selected_template)
        template_options = self._task_template_options(selected_template)
        device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=True,
        )
        metric_selector = self._task_metric_selector(default_selected=tuple(template_schema["metrics"]["default"]))
        return (
            "<article class='card stack task-create-card'>"
            "<h3>创建任务 <span class='heading-hint'>定义要测什么 App、用什么模板、可选哪些设备。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-task', current_actor=current_actor), quote=True)}' class='stack task-create-form'>"
            "<section class='task-form-section task-form-section-basic'>"
            "<div class='task-form-section-title'>基础信息</div>"
            "<div class='form-grid-three task-basic-grid'>"
            "<label>任务名<input type='text' name='task_name' value='' placeholder='例如 首页冷启动回归' required /></label>"
            "<label>包名<input type='text' name='package_name' value='' placeholder='com.example.app' required /></label>"
            f"<label>模板<select name='template_type' required>{template_options}</select></label>"
            "</div>"
            f"{self._task_template_risk_notice(template_schema)}"
            "</section>"
            "<div class='task-create-layout'>"
            "<section class='task-form-section task-create-target'>"
            "<div class='task-form-section-title'>执行目标</div>"
            f"{device_selector}"
            "<div class='task-target-controls'>"
            "<label class='sampling-field'>采样间隔(秒)<input type='number' name='sampling_interval' value='5' min='0' /></label>"
            "<div class='meta'>和设备选择放在一起，便于一次确认调度范围与采样频率。</div>"
            "</div>"
            "</section>"
            "<section class='task-form-section task-create-metrics'>"
            "<div class='task-form-section-title'>监控指标</div>"
            f"{metric_selector}"
            "</section>"
            "</div>"
            "<section class='task-form-section task-form-section-params'>"
            "<div class='task-form-section-title'>参数表单</div>"
            "<div class='form-grid-three task-params-grid'>"
            f"{self._task_params_builder(managed_apks=list(payload.get('managed_apks', []) or []), upload_url=self._actor_scoped_path('/tasks/actions/upload-apk', current_actor=current_actor), delete_url=self._actor_scoped_path('/tasks/actions/delete-apk', current_actor=current_actor))}"
            f"{self._json_textarea_with_help('task_params(JSON)', 'task_params', '例如 {\"loop_count\": 10}', self._task_params_help())}"
            f"{self._json_textarea_with_help('metadata(JSON)', 'metadata', '例如 {\"source\":\"web\"}', self._metadata_help())}"
            "</div>"
            "</section>"
            "<div class='form-actions'><button type='submit'>创建任务</button></div>"
            "</form></article>"
        )

    def _long_run_task_create_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        defaults = dict(payload.get("operation_defaults", {}) or {})
        long_run_template_key = str(defaults.get("long_run_template_key", "") or "")
        long_run_template_name = str(defaults.get("long_run_template_name", "") or "")
        selected_task_name = str(defaults.get("task_name", "") or "")
        selected_package_name = str(defaults.get("package_name", "") or "")
        selected_runtime_hours = max(int(defaults.get("runtime_hours", 12) or 12), 1)
        selected_interval_minutes = max(int(defaults.get("interval_minutes", 60) or 60), 1)
        selected_retry_count = max(int(defaults.get("retry_count", 1) or 1), 0)
        selected_device_count = max(int(defaults.get("desired_device_count", 1) or 1), 1)
        selected_failure_threshold = max(int(defaults.get("failure_threshold", 3) or 3), 1)
        selected_rotation_strategy = str(defaults.get("rotation_strategy", "") or "round_robin")
        selected_rotation_advance_policy = str(defaults.get("rotation_advance_policy", "") or "every_round")
        selected_start_now = str(defaults.get("start_now", "1") or "1")
        selected_monitoring_backend = str(defaults.get("monitoring_backend", "") or "default")
        selected_primary_devices = tuple(str(item) for item in list(defaults.get("primary_device_ids", []) or []) if str(item or "").strip())
        selected_backup_devices = tuple(str(item) for item in list(defaults.get("backup_device_ids", []) or []) if str(item or "").strip())
        selected_metadata = defaults.get("metadata", {})
        metadata_value = (
            json.dumps(selected_metadata, ensure_ascii=False, indent=2)
            if isinstance(selected_metadata, Mapping) and selected_metadata
            else ""
        )
        selected_template = str(defaults.get("template_type", "") or "monkey")
        template_schema = get_template_form_schema(selected_template)
        template_options = self._task_template_options(selected_template)
        primary_device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=True,
            label="指定设备 / 自动调度",
            field_name="devices",
            empty_title="自动调度",
            empty_hint="不绑定设备；无人值守轮次按设备池挑选",
            selected_values=selected_primary_devices,
        )
        backup_device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=True,
            label="候补设备",
            field_name="backup_devices",
            empty_title="不指定候补设备",
            empty_hint="主设备不可用时才尝试补位",
            selected_values=selected_backup_devices,
        )
        metric_selector = self._task_metric_selector(default_selected=tuple(template_schema["metrics"]["default"]))
        template_notice = ""
        if long_run_template_key:
            template_notice = self._notice(
                "已套用长稳模板："
                + (long_run_template_name or long_run_template_key)
                + "。已预填运行时长、轮转间隔、期望设备数和轮转策略；只需补包名、设备和监控策略即可创建。",
                tone="ok",
            )
        return (
            "<article class='card stack task-create-card long-run-task-create-card'>"
            "<h3>创建长稳任务 <span class='heading-hint'>一次提交创建普通 Task，并写入 runner 可见的无人值守配置。</span></h3>"
            + template_notice
            + f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-task', current_actor=current_actor), quote=True)}' class='stack task-create-form long-run-task-create-form'>"
            "<input type='hidden' name='configure_unattended' value='1' />"
            f"<input type='hidden' name='long_run_template_key' value='{escape(long_run_template_key, quote=True)}' />"
            f"<input type='hidden' name='long_run_template_name' value='{escape(long_run_template_name, quote=True)}' />"
            "<section class='task-form-section task-form-section-basic'>"
            "<div class='task-form-section-title'>测试目标</div>"
            "<div class='form-grid-three task-basic-grid'>"
            f"<label>任务名<input type='text' name='task_name' value='{escape(selected_task_name, quote=True)}' placeholder='例如 直播间 overnight 长稳' required /></label>"
            f"<label>包名<input type='text' name='package_name' value='{escape(selected_package_name, quote=True)}' placeholder='com.example.app' required /></label>"
            f"<label>长稳模板<select name='template_type' required>{template_options}</select></label>"
            "</div>"
            f"{self._task_template_risk_notice(template_schema)}"
            "<div class='meta'>模板覆盖前后台切换、Monkey、冷启动、安装卸载、重启、待机唤醒；这里只做最小长稳闭环，不做复杂排班平台。</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>运行策略</div>"
            "<div class='form-grid-three'>"
            f"<label>运行时长(小时)<input type='number' name='runtime_hours' value='{selected_runtime_hours}' min='1' /></label>"
            f"<label>轮转间隔(分钟)<input type='number' name='interval_minutes' value='{selected_interval_minutes}' min='1' /></label>"
            f"<label>失败重试<input type='number' name='retry_count' value='{selected_retry_count}' min='0' /></label>"
            f"<label>期望设备数<input type='number' name='desired_device_count' value='{selected_device_count}' min='1' /></label>"
            f"<label>失败阈值<input type='number' name='failure_threshold' value='{selected_failure_threshold}' min='1' /></label>"
            "<label>自动补位<select name='auto_backfill'><option value='1'>开启</option><option value='0'>关闭</option></select></label>"
            "<label>轮转策略<select name='rotation_strategy'>"
            f"<option value='round_robin'{' selected' if selected_rotation_strategy == 'round_robin' else ''}>round_robin</option>"
            f"<option value='fixed'{' selected' if selected_rotation_strategy == 'fixed' else ''}>fixed</option>"
            "</select></label>"
            "<label>轮转推进<select name='rotation_advance_policy'>"
            f"<option value='every_round'{' selected' if selected_rotation_advance_policy == 'every_round' else ''}>every_round</option>"
            f"<option value='failure_only'{' selected' if selected_rotation_advance_policy == 'failure_only' else ''}>failure_only</option>"
            "</select></label>"
            "<label>立即开始<select name='start_now'>"
            f"<option value='1'{' selected' if selected_start_now == '1' else ''}>是</option>"
            f"<option value='0'{' selected' if selected_start_now == '0' else ''}>否</option>"
            "</select></label>"
            "</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>设备策略</div>"
            "<div class='unattended-device-grid'>"
            f"<div class='unattended-device-slot'>{primary_device_selector}</div>"
            f"<div class='unattended-device-slot'>{backup_device_selector}</div>"
            "</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>监控策略</div>"
            "<div class='long-run-monitoring-grid'>"
            "<div class='long-run-monitoring-controls'>"
            "<label>Monitoring Backend<select name='monitoring_backend'>"
            f"<option value='default'{' selected' if selected_monitoring_backend == 'default' else ''}>default - 基础 ADB 快照</option>"
            f"<option value='solox'{' selected' if selected_monitoring_backend == 'solox' else ''}>solox - 实时性能采样</option>"
            f"<option value='perfetto'{' selected' if selected_monitoring_backend == 'perfetto' else ''}>perfetto - 系统 Trace</option>"
            f"<option value='solox_perfetto'{' selected' if selected_monitoring_backend == 'solox_perfetto' else ''}>solox_perfetto - SoloX + Perfetto</option>"
            "</select></label>"
            "<label>采样间隔(秒)<input type='number' name='sampling_interval' value='5' min='0' /></label>"
            "<div class='meta'>先选采集方式和频率，再勾选这条长稳任务要沉淀的指标。</div>"
            "</div>"
            f"{metric_selector}"
            "</div>"
            "</section>"
            "<section class='task-form-section'>"
            "<div class='task-form-section-title'>输出</div>"
            "<div class='form-grid-three'>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='daily_report' checked /><span>日报<small>runner daily report</small></span></label>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='weekly_report' checked /><span>周报<small>runner weekly report</small></span></label>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='exception_summary' checked /><span>异常摘要<small>失败/掉线/隔离摘要</small></span></label>"
            "<label class='task-param-builder-check'><input type='checkbox' name='outputs' value='admission_assist' checked /><span>准入辅助结果说明<small>供准入/提测决策参考</small></span></label>"
            "</div>"
            "<label>结果说明<textarea name='output_note' rows='2' placeholder='例如 每天早上看日报，异常摘要同步到准入辅助说明。'></textarea></label>"
            "</section>"
            "<section class='task-form-section task-form-section-params'>"
            "<div class='task-form-section-title'>模板参数</div>"
            "<div class='form-grid-three task-params-grid'>"
            f"{self._task_params_builder(managed_apks=list(payload.get('managed_apks', []) or []), upload_url=self._actor_scoped_path('/tasks/actions/upload-apk', current_actor=current_actor), delete_url=self._actor_scoped_path('/tasks/actions/delete-apk', current_actor=current_actor))}"
            f"{self._json_textarea_with_help('task_params(JSON)', 'task_params', '例如 {\"event_count\": 5000, \"throttle_ms\": 300}', self._task_params_help())}"
            f"{self._json_textarea_with_help('metadata(JSON)', 'metadata', '例如 {\"owner_team\":\"android-client\"}', self._metadata_help(), value=metadata_value)}"
            "</div>"
            "</section>"
            "<div class='form-actions'>"
            "<button type='submit'>创建长稳任务并配置无人值守</button>"
            "<a href='/runner'>查看 runner 页面</a>"
            "</div>"
            "</form></article>"
        )

    def _run_create_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        device_selector = self._task_device_selector(
            list(payload.get("schedulable_devices", []) or []),
            allow_empty=False,
        )
        options = "".join(
            self._task_option(item)
            for item in list(payload.get("tasks", []) or [])
            if str(item.get("task_id", "") or "").strip()
        )
        return (
            "<article class='card stack'>"
            "<h3>创建 Run <span class='heading-hint'>基于某个任务生成一次具体执行批次。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/create-run', current_actor=current_actor), quote=True)}' class='stack'>"
            "<div class='form-grid-three'>"
            "<label>任务<select name='task_id' required>" + options + "</select></label>"
            f"{device_selector}"
            "<label>metadata(JSON)<textarea name='metadata' rows='2' placeholder='例如 {\"source\":\"web\"}'></textarea></label>"
            "</div>"
            "<div class='form-actions'><button type='submit'>创建 Run</button></div>"
            "</form></article>"
        )

    def _run_execute_form(self, payload: Mapping[str, Any]) -> str:
        current_actor = dict(payload.get("current_actor", {}) or {})
        defaults = dict(payload.get("operation_defaults", {}) or {})
        options = "".join(
            f"<option value='{escape(str(item.get('run_id', '') or ''), quote=True)}'>{escape(str(item.get('run_id', '') or ''))} / {escape(str(item.get('task_name', '') or ''))}</option>"
            for item in list(payload.get("runs", []) or [])
            if str(item.get("run_id", "") or "").strip()
        )
        selected_backend = str(defaults.get("monitoring_backend", "default") or "default")
        return (
            "<article class='card stack'>"
            "<h3>执行 Run <span class='heading-hint'>真正开始跑，并选择 monitoring backend、并发、重试等执行参数。</span></h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/tasks/actions/execute-run', current_actor=current_actor), quote=True)}' class='stack'>"
            "<div class='form-grid-three'>"
            "<label>Run<select name='run_id' required>" + options + "</select></label>"
            f"<label>Monitoring Backend<select name='monitoring_backend'><option value='default'{' selected' if selected_backend == 'default' else ''}>default - 基础 ADB 快照</option><option value='solox'{' selected' if selected_backend == 'solox' else ''}>solox - 实时性能采样</option><option value='perfetto'{' selected' if selected_backend == 'perfetto' else ''}>perfetto - 系统 Trace</option></select></label>"
            "<label>重试次数<input type='number' name='retry_count' value='0' min='0' /></label>"
            "</div>"
            "<div class='form-grid-three'>"
            "<label>并发数<input type='number' name='max_concurrency' value='1' min='1' /></label>"
            "<label>停止于失败<select name='stop_on_failure'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "</div>"
            "<div class='form-actions'><button type='submit'>执行 Run</button></div>"
            "</form></article>"
        )

    @staticmethod
    def _task_option(item: Mapping[str, Any]) -> str:
        task_id = str(item.get("task_id", "") or "").strip()
        task_name = str(item.get("task_name", "") or task_id).strip()
        template_type = str(item.get("template_type", "") or "").strip()
        package_name = str(item.get("package_name", "") or "").strip()
        created_at = str(item.get("created_at", "") or "").strip().replace("T", " ", 1)
        short_id = task_id[-8:] if len(task_id) > 8 else task_id
        template_label = TaskFormsMixin._task_template_plain_label(template_type)
        detail_parts = [part for part in [template_label, package_name, f"id:{short_id}", created_at[:16]] if part]
        label = task_name + (" / " + " / ".join(detail_parts) if detail_parts else "")
        return f"<option value='{escape(task_id, quote=True)}'>{escape(label)}</option>"

    @classmethod
    def _json_textarea_with_help(
        cls,
        label: str,
        name: str,
        placeholder: str,
        help_html: str,
        *,
        wide: bool = True,
        rows: int = 2,
        value: str = "",
    ) -> str:
        class_name = "json-field-with-help"
        if wide:
            class_name += " form-field-wide"
        return (
            f"<div class='{class_name}'>"
            "<div class='json-field-header'>"
            f"<span>{escape(label)}</span>"
            "<details class='json-param-help'>"
            "<summary>查看参数</summary>"
            f"<div class='json-param-help-body'>{help_html}</div>"
            "</details>"
            "</div>"
            f"<textarea name='{escape(name, quote=True)}' rows='{int(rows)}' placeholder='{escape(placeholder, quote=True)}'>{escape(value)}</textarea>"
            "</div>"
        )

    @classmethod
    def _task_params_builder(
        cls,
        *,
        wide: bool = True,
        managed_apks: Sequence[Mapping[str, Any]] = (),
        upload_url: str = "/tasks/actions/upload-apk",
        delete_url: str = "/tasks/actions/delete-apk",
    ) -> str:
        class_name = "task-param-builder"
        if wide:
            class_name += " form-field-wide"
        section_html = []
        for section in get_param_sections_for_web():
            is_general_section = set(section.template_scopes) == {"all"}
            field_html = "".join(
                cls._task_param_builder_input(
                    field.key,
                    field.input_type,
                    field.label,
                    field.placeholder,
                    default=field.default,
                    managed_apks=managed_apks,
                    upload_url=upload_url,
                    delete_url=delete_url,
                )
                for field in section.fields
            )
            open_attr = " open" if is_general_section else ""
            section_html.append(
                f"<details{open_attr} class='task-param-builder-section task-param-builder-drawer' "
                f"data-template-scope='{escape(' '.join(section.template_scopes), quote=True)}'>"
                f"<summary><strong>{escape(section.title)}</strong><span>{len(section.fields)} 个参数</span></summary>"
                "<div class='task-param-builder-grid'>"
                + field_html
                + "</div>"
                "</details>"
            )
        return (
            f"<div class='{class_name}' data-task-param-builder='1'>"
            "<div class='json-field-header'>"
            "<span>参数表单</span>"
            "<span class='meta'>默认只展开通用参数；按需展开当前模板参数，填写后自动生成 task_params(JSON)。</span>"
            "</div>"
            + "".join(section_html)
            + "</div>"
        )

    @staticmethod
    def _task_param_builder_input(
        key: str,
        kind: str,
        label: str,
        placeholder: str,
        *,
        default: object | None = None,
        managed_apks: Sequence[Mapping[str, Any]] = (),
        upload_url: str = "/tasks/actions/upload-apk",
        delete_url: str = "/tasks/actions/delete-apk",
    ) -> str:
        escaped_key = escape(key, quote=True)
        escaped_label = escape(label)
        escaped_placeholder = escape(placeholder, quote=True)
        default_attr = "" if default in (None, "") else f" value='{escape(str(default), quote=True)}'"
        if kind == "apk_manager":
            options = "".join(
                f"<option value='{escape(str(item.get('path', '') or ''), quote=True)}'>"
                f"{escape(str(item.get('name', '') or item.get('path', '') or 'APK'))}"
                "</option>"
                for item in managed_apks
                if str(item.get("path", "") or "").strip()
            )
            return (
                "<div class='task-param-builder-input task-apk-manager' data-apk-manager='1' "
                f"data-apk-upload-url='{escape(upload_url, quote=True)}' "
                f"data-apk-delete-url='{escape(delete_url, quote=True)}'>"
                "<div class='task-apk-manager-head'>"
                f"<span>{escaped_label}<small>上传、删除并选择安装卸载循环使用的 APK</small></span>"
                "<button type='button' class='secondary' data-apk-upload-button='1'>上传 APK</button>"
                "<button type='button' class='secondary danger' data-apk-delete-button='1'>删除</button>"
                "</div>"
                "<input type='file' accept='.apk,application/vnd.android.package-archive' data-apk-upload-input='1' hidden />"
                "<label class='task-apk-select-label'>"
                "已管理 APK"
                "<select data-apk-select='1'>"
                "<option value=''>请选择已上传 APK</option>"
                + options +
                "</select>"
                "</label>"
                "<div class='meta' data-apk-manager-status='1'>上传后会加入下拉列表；选择后自动写入下方 apk_path。</div>"
                "</div>"
            )
        input_type = "number" if kind == "number" else "text"
        if kind == "checkbox":
            return (
                "<label class='task-param-builder-check'>"
                f"<input type='checkbox' data-task-param-key='{escaped_key}' data-task-param-type='boolean' />"
                f"<span>{escaped_label}<small>{escape(key)}</small></span>"
                "</label>"
            )
        return (
            "<label class='task-param-builder-input'>"
            f"<span>{escaped_label}<small>{escape(key)}</small></span>"
            f"<input type='{input_type}' data-task-param-key='{escaped_key}' data-task-param-type='{escape(kind, quote=True)}' placeholder='{escaped_placeholder}'{default_attr} />"
            "</label>"
        )

    @staticmethod
    def _task_params_help() -> str:
        groups = []
        for section in get_param_sections_for_web():
            groups.append(
                (
                    section.title,
                    section.template_scopes,
                    tuple(
                        (
                            " / ".join((field.key, *field.aliases)),
                            field.description,
                        )
                        for field in section.fields
                    ),
                )
            )
        return TaskFormsMixin._help_group_html(groups)

    @staticmethod
    def _metadata_help() -> str:
        groups = [
            (
                "常用字段",
                [
                    ("source", "来源，例如 web、codex、release-center。"),
                    ("branch", "代码分支或测试分支。"),
                    ("build_id", "构建 ID，方便和 CI / 提测系统对齐。"),
                    ("version_name / version_code", "版本名和版本号。"),
                    ("release_channel", "发布通道，例如 beta、gray、store。"),
                    ("owner_team", "责任团队。"),
                    ("note", "补充说明，便于后续排查。"),
                ],
            ),
            (
                "联动建议",
                [
                    ("ticket_id / ci_run_id", "外部缺陷或 CI 流水线编号。"),
                    ("baseline_key", "需要关联准入基线时填写。"),
                    ("tags", "自定义标签；建议用数组或逗号字符串。"),
                ],
            ),
        ]
        return TaskFormsMixin._help_group_html(groups)

    @staticmethod
    def _help_group_html(groups: Sequence[tuple[Any, ...]]) -> str:
        sections = []
        for group in groups:
            if len(group) == 3:
                title, templates, items = group
            else:
                title, items = group
                templates = ("all",)
            template_attr = " ".join(str(item) for item in templates if str(item).strip()) or "all"
            rows = "".join(
                "<tr>"
                f"<td class='mono'>{escape(str(key))}</td>"
                f"<td>{escape(str(description))}</td>"
                "</tr>"
                for key, description in items
            )
            sections.append(
                f"<div class='json-param-help-section' data-template-scope='{escape(template_attr, quote=True)}'>"
                f"<strong>{escape(str(title))}</strong>"
                "<table class='compact-table'><tbody>"
                + rows
                + "</tbody></table>"
                "</div>"
            )
        return "".join(sections)

    @staticmethod
    def _task_metric_selector(*, default_selected: Sequence[str] = ("cpu", "memory")) -> str:
        selected = {str(item or "").strip().lower() for item in default_selected}
        cards = []
        for value, metric in METRIC_REGISTRY.items():
            checked = " checked" if value in selected else ""
            scopes = " ".join(metric_template_scopes(value))
            default_scopes = " ".join(default_metric_template_scopes(value))
            cards.append(
                "<label class='device-choice-card metric-choice-card' "
                f"data-template-scope='{escape(scopes, quote=True)}' "
                f"data-default-template-scope='{escape(default_scopes, quote=True)}'>"
                f"<input type='checkbox' name='metrics' value='{escape(value, quote=True)}'{checked} />"
                "<span>"
                f"<strong>{escape(metric.title)}</strong>"
                f"<small>{escape(value)} / {escape(metric.description)}</small>"
                "</span>"
                "</label>"
            )
        return (
            "<div class='device-checkbox-field metric-checkbox-field'>"
            "<div class='meta'>指标</div>"
            "<div class='device-choice-grid metric-choice-grid'>"
            + "".join(cards)
            + "</div>"
            "<span class='meta'>可多选；默认 CPU + Memory，SoloX 可采 network / battery / fps / gpu，Perfetto 可辅助 trace/network。</span>"
            "</div>"
        )

    @staticmethod
    def _task_device_selector(
        devices: list[Mapping[str, Any]],
        *,
        allow_empty: bool,
        label: str = "设备",
        field_name: str = "devices",
        empty_title: str = "自动调度（不指定设备）",
        empty_hint: str = "执行时按设备池选择",
        selected_values: Sequence[str] = (),
    ) -> str:
        selected = {str(item or "").strip() for item in selected_values if str(item or "").strip()}
        help_text = (
            "可勾选一台或多台；选择“自动调度”则任务不绑定具体设备。"
            if allow_empty
            else "必须勾选至少一台可调度设备。"
        )
        required_attrs = "" if allow_empty else " data-required-group='1' data-required-message='请至少选择一台设备。'"
        if not devices:
            message = "当前没有可调度设备，请先到设备池刷新或连接设备"
            empty_required_attrs = (
                "" if allow_empty else " data-required-group='1' data-required-message='当前没有可调度设备，请先到设备池刷新或连接设备。'"
            )
            return (
                f"<div class='device-checkbox-field'{empty_required_attrs}>"
                f"<div class='meta'>{escape(label)}</div>"
                f"<div class='empty-state'>{escape(message)}</div>"
                f"<span class='meta'>{escape(message)}</span>"
                "</div>"
            )
        cards = []
        if allow_empty:
            checked = " checked" if not selected else ""
            cards.append(
                "<label class='device-choice-card device-choice-auto'>"
                f"<input type='checkbox' name='{escape(field_name, quote=True)}' value=''{checked} />"
                f"<span><strong>{escape(empty_title)}</strong><small>{escape(empty_hint)}</small></span>"
                "</label>"
            )
        for item in devices:
            device_id = str(item.get("device_id", "") or item.get("serial", "") or "").strip()
            if not device_id:
                continue
            model = str(item.get("model", "") or item.get("display_name", "") or "").strip()
            group_name = str(item.get("group_name", "") or "").strip() or "未分组"
            team_name = str(item.get("team_name", "") or item.get("team", "") or "").strip() or "未分配"
            checked = " checked" if device_id in selected else ""
            cards.append(
                "<label class='device-choice-card'>"
                f"<input type='checkbox' name='{escape(field_name, quote=True)}' value='{escape(device_id, quote=True)}'{checked} />"
                "<span>"
                f"<strong>{escape(device_id)}</strong>"
                f"<small>{escape(' / '.join(part for part in [model, group_name, team_name] if part))}</small>"
                "</span>"
                "</label>"
            )
        return (
            f"<div class='device-checkbox-field'{required_attrs}>"
            f"<div class='meta'>{escape(label)}</div>"
            "<div class='device-choice-grid'>"
            + "".join(cards)
            + "</div>"
            f"<span class='meta'>{escape(help_text)}</span>"
            "</div>"
        )

    @staticmethod
    def _task_template_options(selected: str) -> str:
        return "".join(
            f"<option value='{escape(item.value, quote=True)}'{' selected' if selected == item.value else ''}>{escape(item.option_label)}</option>"
            for item in list_scenario_definitions()
        )

    @staticmethod
    def _task_template_risk_notice(schema: Mapping[str, Any]) -> str:
        risk = dict(schema.get("risk", {}) or {})
        level = str(risk.get("risk_level", "") or "low")
        notes = []
        if risk.get("requires_apk"):
            notes.append("需要 APK")
        if risk.get("changes_device_state"):
            notes.append("会改变设备状态")
        risk_note = str(risk.get("risk_note", "") or "").strip()
        summary = "；".join(notes) if notes else "常规执行模板"
        if risk_note:
            summary = f"{summary}；{risk_note}"
        tone = "warning" if level in {"medium", "high"} else "ok"
        return (
            f"<div class='notice {tone} task-template-risk' data-template-risk='1'>"
            f"当前模板风险：<strong>{escape(level)}</strong>，{escape(summary)}"
            "</div>"
        )

    @staticmethod
    def _task_template_plain_label(template_type: str) -> str:
        template = str(template_type or "").strip()
        if not template:
            return ""
        try:
            return get_scenario_definition(template).plain_label
        except KeyError:
            pass
        return template

    @staticmethod
    def _task_template_definitions() -> tuple[tuple[str, str, str], ...]:
        return tuple((item.value, item.chinese_name, item.description) for item in list_scenario_definitions())
