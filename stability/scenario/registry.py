from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from stability.domain import AppError, AppErrorCode, MetricType, TaskTemplateType


@dataclass(frozen=True)
class ScenarioParamField:
    """One user-facing template parameter exposed by Web/CLI help."""

    key: str
    input_type: str
    label: str
    description: str
    placeholder: str = ""
    default: object | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioParamSection:
    """A group of parameters shown together in task forms."""

    title: str
    template_scopes: tuple[str, ...]
    fields: tuple[ScenarioParamField, ...]


@dataclass(frozen=True)
class ScenarioMetric:
    """One supported monitoring metric."""

    key: str
    title: str
    description: str
    supported_backends: tuple[str, ...] = ("adb_collector", "solox", "perfetto")


@dataclass(frozen=True)
class ScenarioDefinition:
    """Registry entry for one executable task template."""

    template_type: TaskTemplateType
    chinese_name: str
    description: str
    parameter_sections: tuple[ScenarioParamSection, ...] = ()
    supported_metrics: tuple[str, ...] = (MetricType.CPU.value, MetricType.MEMORY.value)
    default_metrics: tuple[str, ...] = (MetricType.CPU.value, MetricType.MEMORY.value)
    risk_level: str = "low"
    requires_device: bool = True
    requires_apk: bool = False
    changes_device_state: bool = False
    risk_note: str = ""

    @property
    def value(self) -> str:
        return self.template_type.value

    @property
    def option_label(self) -> str:
        return f"{self.value} - {self.chinese_name}：{self.description}"

    @property
    def plain_label(self) -> str:
        return f"{self.value} - {self.chinese_name}"


METRIC_REGISTRY: Mapping[str, ScenarioMetric] = {
    MetricType.CPU.value: ScenarioMetric(MetricType.CPU.value, "CPU", "应用/系统 CPU 使用率"),
    MetricType.MEMORY.value: ScenarioMetric(MetricType.MEMORY.value, "Memory", "应用 PSS / 内存占用"),
    MetricType.NETWORK.value: ScenarioMetric(
        MetricType.NETWORK.value,
        "Network",
        "上下行流量与速率",
        supported_backends=("solox", "perfetto"),
    ),
    MetricType.BATTERY.value: ScenarioMetric(
        MetricType.BATTERY.value,
        "Battery",
        "电量、温度、电压",
        supported_backends=("solox",),
    ),
    MetricType.FPS.value: ScenarioMetric(
        MetricType.FPS.value,
        "FPS",
        "帧率与卡顿辅助判断",
        supported_backends=("solox",),
    ),
    "gpu": ScenarioMetric("gpu", "GPU", "GPU 使用率", supported_backends=("solox",)),
    "trace": ScenarioMetric("trace", "Trace", "Perfetto / 系统 Trace 辅助采集", supported_backends=("perfetto",)),
    MetricType.POWER.value: ScenarioMetric(
        MetricType.POWER.value,
        "Power",
        "功耗/电流电压换算",
        supported_backends=("solox", "perfetto"),
    ),
    "jank": ScenarioMetric("jank", "Jank", "卡顿帧辅助指标", supported_backends=("solox",)),
    MetricType.STARTUP.value: ScenarioMetric(
        MetricType.STARTUP.value,
        "Startup",
        "启动耗时与启动成功率",
        supported_backends=("adb_collector", "perfetto"),
    ),
}


COMMON_PARAM_SECTION = ScenarioParamSection(
    title="通用参数",
    template_scopes=("all",),
    fields=(
        ScenarioParamField("loop_count", "number", "循环次数", "多数循环模板支持；不填则走模板默认值。", "例如 3"),
    ),
)


SCENARIO_REGISTRY: Mapping[str, ScenarioDefinition] = {
    TaskTemplateType.COLD_START_LOOP.value: ScenarioDefinition(
        template_type=TaskTemplateType.COLD_START_LOOP,
        chinese_name="冷启动循环",
        description="重复启动 App，观察启动耗时/崩溃",
        supported_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.STARTUP.value, "trace", MetricType.NETWORK.value),
        default_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.STARTUP.value),
        risk_level="low",
        parameter_sections=(
            ScenarioParamSection(
                "cold_start_loop 冷启动",
                (TaskTemplateType.COLD_START_LOOP.value,),
                (
                    ScenarioParamField("launch_wait_ms", "number", "启动后等待(ms)", "启动成功后等待稳定时间。", "默认 1000"),
                    ScenarioParamField("interval_ms", "number", "轮次间隔(ms)", "两轮启动之间的等待时间。", "默认 1000"),
                    ScenarioParamField("startup_timeout_ms", "number", "启动超时(ms)", "单轮启动判定超时。", "默认 10000"),
                    ScenarioParamField("launch_timeout_seconds", "number", "命令超时(s)", "am start 命令执行超时。", "默认 20"),
                    ScenarioParamField("target_activity", "text", "指定 Activity", "留空则使用包默认启动入口。", "可留空"),
                    ScenarioParamField("kill_before_launch", "checkbox", "启动前 force-stop", "每轮启动前停止目标 App。"),
                ),
            ),
        ),
    ),
    TaskTemplateType.MONKEY.value: ScenarioDefinition(
        template_type=TaskTemplateType.MONKEY,
        chinese_name="Monkey 稳定性",
        description="随机事件压测，发现崩溃/ANR/卡死",
        supported_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.NETWORK.value, MetricType.BATTERY.value, MetricType.FPS.value, "gpu", "jank"),
        default_metrics=(MetricType.CPU.value, MetricType.MEMORY.value),
        risk_level="medium",
        parameter_sections=(
            ScenarioParamSection(
                "monkey 稳定性",
                (TaskTemplateType.MONKEY.value,),
                (
                    ScenarioParamField("event_count", "number", "事件数", "随机事件数量。", "默认 100"),
                    ScenarioParamField("throttle_ms", "number", "事件间隔(ms)", "两次事件之间的节流时间。", "默认 300"),
                    ScenarioParamField("seed", "number", "随机种子", "复现问题时填写。", "复现问题时填写"),
                    ScenarioParamField("timeout_seconds", "number", "执行超时(s)", "Monkey 进程最长执行时间。", "默认 180"),
                    ScenarioParamField("verbosity", "number", "日志级别", "Monkey 日志详细级别。", "默认 1"),
                    ScenarioParamField("ignore_crashes", "checkbox", "忽略 crash 继续执行", "让 Monkey 忽略 crash。"),
                    ScenarioParamField("ignore_timeouts", "checkbox", "忽略 timeout 继续执行", "让 Monkey 忽略 ANR/timeout。"),
                    ScenarioParamField("ignore_security_exceptions", "checkbox", "忽略安全异常继续执行", "让 Monkey 忽略安全异常。"),
                    ScenarioParamField("force_stop_before_start", "checkbox", "执行前 force-stop", "执行前停止目标 App。"),
                    ScenarioParamField("recover_inject_events", "checkbox", "INJECT_EVENTS 自动恢复", "触发 INJECT_EVENTS 后停止并重新打开目标 App。", default=True),
                    ScenarioParamField("inject_events_retry_count", "number", "INJECT_EVENTS 恢复上限", "广告/外跳导致 INJECT_EVENTS 后的最大恢复次数。", "默认 50"),
                    ScenarioParamField("block_notification_shade", "checkbox", "禁止下拉通知栏/快捷设置", "开启后将 Monkey motion 事件转为 tap，避免下拉通知栏或快捷设置页后继续点击。", default=True),
                    ScenarioParamField("foreground_guard_enabled", "checkbox", "前台包守护", "执行中发现前台不是目标 App 时立即中止本轮 Monkey 并拉回目标 App。", default=True),
                    ScenarioParamField("foreground_drift_retry_count", "number", "外跳恢复上限", "前台跳到其他 App 后的最大恢复次数。", "默认 50"),
                    ScenarioParamField("foreground_guard_interval_seconds", "number", "前台检查间隔(s)", "Monkey 执行中检查当前前台包的频率。", "默认 1"),
                    ScenarioParamField("foreground_guard_grace_seconds", "number", "前台守护宽限(s)", "启动初期允许目标 App 拉起的宽限时间。", "默认 5"),
                    ScenarioParamField("foreground_guard_stop_foreign_app", "checkbox", "停止外跳 App", "外跳到第三方 App 时尝试 force-stop 该 App，系统包和桌面会跳过。", default=True),
                    ScenarioParamField("foreground_guard_allowed_packages", "text", "允许前台包", "逗号分隔；仅用于确实需要短暂进入可信辅助包的场景。", "例如 com.android.settings"),
                ),
            ),
        ),
    ),
    TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value: ScenarioDefinition(
        template_type=TaskTemplateType.FOREGROUND_BACKGROUND_LOOP,
        chinese_name="前后台切换",
        description="反复切后台再回前台，检查恢复能力",
        supported_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.FPS.value, "jank", "trace"),
        risk_level="low",
        parameter_sections=(
            ScenarioParamSection(
                "foreground_background_loop 前后台切换",
                (TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value,),
                (
                    ScenarioParamField("foreground_wait_ms", "number", "前台停留(ms)", "每轮回到前台后的停留时间。", "默认 1000"),
                    ScenarioParamField("background_wait_ms", "number", "后台停留(ms)", "每轮回到桌面后的停留时间。", "默认 1000"),
                    ScenarioParamField("launch_timeout_seconds", "number", "启动超时(s)", "拉起 App 命令超时。", "默认 20"),
                    ScenarioParamField("home_timeout_seconds", "number", "返回桌面超时(s)", "返回桌面命令超时。", "默认 10"),
                ),
            ),
        ),
    ),
    TaskTemplateType.INSTALL_UNINSTALL_LOOP.value: ScenarioDefinition(
        template_type=TaskTemplateType.INSTALL_UNINSTALL_LOOP,
        chinese_name="安装卸载循环",
        description="反复安装/卸载，检查包管理稳定性",
        supported_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.POWER.value),
        risk_level="high",
        requires_apk=True,
        changes_device_state=True,
        risk_note="会安装和卸载目标 App，只建议用于可安全重装的测试包。",
        parameter_sections=(
            ScenarioParamSection(
                "install_uninstall_loop 安装卸载",
                (TaskTemplateType.INSTALL_UNINSTALL_LOOP.value,),
                (
                    ScenarioParamField("apk_manager", "apk_manager", "应用管理", "上传、删除并选择安装卸载循环使用的 APK。"),
                    ScenarioParamField("apk_path", "text", "APK 路径", "安装卸载循环使用的 APK 文件路径。", "/path/app.apk", required=True),
                    ScenarioParamField("install_timeout_seconds", "number", "安装超时(s)", "adb install 命令超时。", "默认 180"),
                    ScenarioParamField("uninstall_timeout_seconds", "number", "卸载超时(s)", "adb uninstall 命令超时。", "默认 60"),
                    ScenarioParamField("settle_ms", "number", "稳定等待(ms)", "安装或卸载后等待稳定时间。", "默认 1000"),
                ),
            ),
        ),
    ),
    TaskTemplateType.REBOOT_LOOP.value: ScenarioDefinition(
        template_type=TaskTemplateType.REBOOT_LOOP,
        chinese_name="重启循环",
        description="重启后拉起和恢复检查",
        supported_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.POWER.value, MetricType.BATTERY.value),
        risk_level="high",
        changes_device_state=True,
        risk_note="会真实重启设备，只应在可安全重启的设备上运行。",
        parameter_sections=(
            ScenarioParamSection(
                "reboot_loop 重启",
                (TaskTemplateType.REBOOT_LOOP.value,),
                (
                    ScenarioParamField("reboot_timeout_seconds", "number", "重启命令超时(s)", "adb reboot 命令超时。", "默认 15"),
                    ScenarioParamField("boot_wait_timeout_seconds", "number", "等待开机超时(s)", "等待设备重新上线的最长时间。", "默认 120"),
                    ScenarioParamField("poll_interval_seconds", "number", "轮询间隔(s)", "等待开机时的轮询间隔。", "默认 5"),
                    ScenarioParamField("settle_ms", "number", "开机后等待(ms)", "设备上线后的稳定等待时间。", "默认 3000"),
                ),
            ),
        ),
    ),
    TaskTemplateType.STANDBY_WAKE_LOOP.value: ScenarioDefinition(
        template_type=TaskTemplateType.STANDBY_WAKE_LOOP,
        chinese_name="息屏唤醒循环",
        description="待机/唤醒后可用性检查",
        supported_metrics=(MetricType.CPU.value, MetricType.MEMORY.value, MetricType.POWER.value, MetricType.BATTERY.value, "trace"),
        risk_level="medium",
        changes_device_state=True,
        risk_note="会反复发送息屏、唤醒和可选解锁命令。",
        parameter_sections=(
            ScenarioParamSection(
                "standby_wake_loop 息屏唤醒",
                (TaskTemplateType.STANDBY_WAKE_LOOP.value,),
                (
                    ScenarioParamField("standby_wait_ms", "number", "息屏停留(ms)", "息屏后的停留时间。", "默认 1000"),
                    ScenarioParamField("wake_wait_ms", "number", "唤醒等待(ms)", "唤醒后的等待时间。", "默认 1000"),
                    ScenarioParamField("command_timeout_seconds", "number", "命令超时(s)", "电源键/解锁命令超时。", "默认 10"),
                    ScenarioParamField("unlock_after_wake", "checkbox", "唤醒后尝试解锁", "唤醒后发送解锁命令。"),
                ),
            ),
        ),
    ),
    TaskTemplateType.CUSTOM.value: ScenarioDefinition(
        template_type=TaskTemplateType.CUSTOM,
        chinese_name="自定义自动化",
        description="接入自定义脚本或自动化流程",
        supported_metrics=tuple(METRIC_REGISTRY.keys()),
        risk_level="high",
        changes_device_state=True,
        risk_note="可执行自定义脚本或 ADB 命令，需要使用者自行确认影响范围。",
        parameter_sections=(
            ScenarioParamSection(
                "custom 自定义自动化",
                (TaskTemplateType.CUSTOM.value,),
                (
                    ScenarioParamField(
                        "automation_mode",
                        "text",
                        "执行模式",
                        "uiautomator2、adb_script 或 external_script。",
                        "uiautomator2 / adb_script / external_script",
                        required=True,
                        aliases=("execution_mode",),
                    ),
                    ScenarioParamField("scenario_name", "text", "场景名称", "自定义场景名称。", "例如 login_journey"),
                    ScenarioParamField("entry_name", "text", "入口名称", "自定义入口名称。", "例如 smoke_login"),
                    ScenarioParamField("script_path", "text", "外部脚本路径", "external_script 模式下的脚本路径。", "/path/to/script.py"),
                    ScenarioParamField("script_timeout_seconds", "number", "脚本超时(s)", "外部脚本执行超时。", "默认 300"),
                ),
            ),
        ),
    ),
}


def list_scenario_definitions() -> tuple[ScenarioDefinition, ...]:
    """Return scenario definitions in user-facing order."""

    return tuple(SCENARIO_REGISTRY[item.value] for item in TaskTemplateType)


def get_scenario_definition(template_type: str | TaskTemplateType) -> ScenarioDefinition:
    """Resolve one scenario definition or raise KeyError."""

    key = template_type.value if isinstance(template_type, TaskTemplateType) else str(template_type or "").strip()
    return SCENARIO_REGISTRY[key]


def resolve_scenario_definition(template_type: str | TaskTemplateType) -> ScenarioDefinition:
    """Resolve a scenario definition or raise the shared application error."""

    key = template_type.value if isinstance(template_type, TaskTemplateType) else str(template_type or "").strip()
    try:
        return SCENARIO_REGISTRY[key]
    except KeyError as exc:
        raise AppError.validation(
            f"Unsupported template_type: {key}",
            code=AppErrorCode.UNSUPPORTED_TEMPLATE,
            hint="请使用 ScenarioRegistry 中已经声明的任务模板。",
            details={"template_type": key, "supported_templates": list(get_supported_template_values())},
        ) from exc


def get_supported_template_values() -> tuple[str, ...]:
    return tuple(item.value for item in list_scenario_definitions())


def get_param_sections_for_web() -> tuple[ScenarioParamSection, ...]:
    sections: list[ScenarioParamSection] = [COMMON_PARAM_SECTION]
    for definition in list_scenario_definitions():
        sections.extend(definition.parameter_sections)
    return tuple(sections)


def get_template_form_schema(template_type: str | TaskTemplateType) -> dict[str, Any]:
    """Return one JSON-ready template schema shared by Web and CLI."""

    definition = resolve_scenario_definition(template_type)
    fields = _fields_for_definition(definition)
    return {
        "contract": "scenario_template_schema.v1",
        "template_type": definition.value,
        "chinese_name": definition.chinese_name,
        "description": definition.description,
        "option_label": definition.option_label,
        "risk": {
            "risk_level": definition.risk_level,
            "requires_device": definition.requires_device,
            "requires_apk": definition.requires_apk,
            "changes_device_state": definition.changes_device_state,
            "risk_note": definition.risk_note,
        },
        "metrics": {
            "default": list(definition.default_metrics),
            "supported": [
                _metric_payload(metric_key)
                for metric_key in definition.supported_metrics
                if metric_key in METRIC_REGISTRY
            ],
        },
        "parameter_sections": [
            {
                "title": section.title,
                "template_scopes": list(section.template_scopes),
                "fields": [
                    _field_payload(field)
                    for field in section.fields
                    if field in fields
                ],
            }
            for section in (COMMON_PARAM_SECTION, *definition.parameter_sections)
        ],
    }


def list_template_form_schemas() -> tuple[dict[str, Any], ...]:
    """Return JSON-ready schemas for every supported template."""

    return tuple(get_template_form_schema(item.template_type) for item in list_scenario_definitions())


def metric_template_scopes(metric_key: str) -> tuple[str, ...]:
    scopes = [
        definition.value
        for definition in list_scenario_definitions()
        if metric_key in definition.supported_metrics
    ]
    return tuple(scopes) or ("all",)


def default_metric_template_scopes(metric_key: str) -> tuple[str, ...]:
    scopes = [
        definition.value
        for definition in list_scenario_definitions()
        if metric_key in definition.default_metrics
    ]
    return tuple(scopes)


def _metric_payload(metric_key: str) -> dict[str, Any]:
    metric = METRIC_REGISTRY[metric_key]
    return {
        "key": metric.key,
        "title": metric.title,
        "description": metric.description,
        "supported_backends": list(metric.supported_backends),
    }


def _field_payload(field: ScenarioParamField) -> dict[str, Any]:
    return {
        "key": field.key,
        "input_type": field.input_type,
        "label": field.label,
        "description": field.description,
        "placeholder": field.placeholder,
        "default": field.default,
        "required": field.required,
        "aliases": list(field.aliases),
    }


def validate_scenario_task_contract(
    *,
    template_type: str | TaskTemplateType,
    task_params: Mapping[str, Any] | None = None,
    enabled_metrics: Sequence[str] | None = None,
) -> None:
    """Validate task params and metrics against ScenarioRegistry."""

    definition = resolve_scenario_definition(template_type)
    params = dict(task_params or {})
    _validate_param_fields(definition, params)
    _validate_metrics(definition, enabled_metrics or ())


def _validate_param_fields(definition: ScenarioDefinition, params: Mapping[str, Any]) -> None:
    errors: list[dict[str, Any]] = []
    for field in _fields_for_definition(definition):
        value = _first_param_value(params, (field.key, *field.aliases))
        if field.required and _is_blank(value):
            errors.append(
                {
                    "field": field.key,
                    "code": "required",
                    "message": f"{field.label} 是必填项。",
                    "aliases": list(field.aliases),
                }
            )
            continue
        if _is_blank(value):
            continue
        if field.input_type == "number" and not _is_number(value):
            errors.append(
                {
                    "field": field.key,
                    "code": "invalid_number",
                    "message": f"{field.label} 必须是数字。",
                    "value": value,
                }
            )
        if field.input_type == "checkbox" and not _is_bool_like(value):
            errors.append(
                {
                    "field": field.key,
                    "code": "invalid_boolean",
                    "message": f"{field.label} 必须是布尔值。",
                    "value": value,
                }
            )
    if definition.template_type == TaskTemplateType.CUSTOM:
        mode = str(_first_param_value(params, ("automation_mode", "execution_mode")) or "").strip()
        if mode and mode not in {"uiautomator2", "adb_script", "external_script"}:
            errors.append(
                {
                    "field": "automation_mode",
                    "code": "unsupported_value",
                    "message": "执行模式必须是 uiautomator2、adb_script 或 external_script。",
                    "value": mode,
                    "supported_values": ["uiautomator2", "adb_script", "external_script"],
                }
            )
    if errors:
        raise AppError.validation(
            f"{definition.value} task_params 校验失败。",
            code=AppErrorCode.INVALID_TASK_PARAMS,
            hint="请按当前模板的参数表单填写；如果使用 JSON 模式，请检查字段名和值类型。",
            details={"template_type": definition.value, "errors": errors},
        )


def _validate_metrics(definition: ScenarioDefinition, enabled_metrics: Sequence[str]) -> None:
    requested = [str(metric or "").strip() for metric in enabled_metrics if str(metric or "").strip()]
    unsupported = [metric for metric in requested if metric not in definition.supported_metrics]
    unknown = [metric for metric in requested if metric not in METRIC_REGISTRY]
    if not unsupported and not unknown:
        return
    raise AppError.validation(
        f"{definition.value} 不支持部分指标。",
        code=AppErrorCode.UNSUPPORTED_METRIC,
        hint="请只选择当前模板支持的指标；Web 表单会按模板自动过滤。",
        details={
            "template_type": definition.value,
            "unsupported_metrics": unsupported,
            "unknown_metrics": unknown,
            "supported_metrics": list(definition.supported_metrics),
        },
    )


def _fields_for_definition(definition: ScenarioDefinition) -> tuple[ScenarioParamField, ...]:
    fields: list[ScenarioParamField] = list(COMMON_PARAM_SECTION.fields)
    for section in definition.parameter_sections:
        fields.extend(section.fields)
    return tuple(fields)


def _first_param_value(params: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in params:
            return params[key]
    return None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.strip())
        except ValueError:
            return False
        return True
    return False


def _is_bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "false", "1", "0", "yes", "no", "on", "off"}
    return False
