from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


LONG_RUN_OVERRIDABLE_PARAMETERS: tuple[str, ...] = (
    "interval_minutes",
    "max_rounds",
    "desired_device_count",
    "primary_device_ids",
    "backup_device_ids",
    "failure_threshold",
    "max_round_history",
    "max_device_window_history",
    "rotation_strategy",
    "rotation_advance_policy",
    "enabled",
    "start_now",
    "tags",
)


LONG_RUN_TEMPLATE_CHINESE_GUIDANCE: dict[str, dict[str, str]] = {
    "smoke_long_run": {
        "explanation": "短时冒烟长稳，用来确认无人值守链路、设备选择、轮转和报告保留是否跑通。",
        "purpose": "适合版本提测前或改动后快速自检，不追求覆盖深度，重点是发现配置/调度/报告链路断点。",
    },
    "overnight_long_run": {
        "explanation": "夜间均衡长稳，用较低人工成本持续观察崩溃、ANR、设备离线和自动恢复表现。",
        "purpose": "适合下班后到次日上午的稳定性守夜，帮助团队在早会前拿到异常设备、失败轮次和风险提示。",
    },
    "weekly_soak": {
        "explanation": "周级耐久长稳，覆盖更长时间窗口和更多设备轮转，用来捕捉低频、累积型稳定性问题。",
        "purpose": "适合周末、发布前耐久验证或重点版本 soak，重点观察设备池消耗、隔离策略和历史保留成本。",
    },
    "custom_long_run": {
        "explanation": "自定义长稳模板，保留标准长稳字段，但允许团队按业务节奏覆盖间隔、轮次和设备数量。",
        "purpose": "适合已有明确实验目标的场景，比如指定 App、指定设备池、特殊时长或专项稳定性排查。",
    },
    "soak_2h": {
        "explanation": "两小时快速长稳，用较短持续时间验证基础稳定性和无人值守闭环。",
        "purpose": "适合提测前快速冒烟，优先确认任务创建、执行、采样和报告链路是否可用。",
    },
    "soak_8h": {
        "explanation": "八小时工作日长稳，覆盖一个完整工作时段内的持续运行和周期性采样。",
        "purpose": "适合白天值班观察，能在不占用整晚资源的情况下沉淀较完整的稳定性信号。",
    },
    "endurance_24h": {
        "explanation": "二十四小时耐久长稳，用较长窗口观察低频异常、资源累积和设备恢复能力。",
        "purpose": "适合夜间或周末耐久验证，重点服务发布前稳定性把关和日报/周报分析。",
    },
}


def normalize_long_run_template_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize service/fallback long-run template payloads for Web and CLI."""
    template = dict(value)
    template_key = str(
        template.get("template_key", "")
        or template.get("template_id", "")
        or template.get("key", "")
        or ""
    )
    if template_key:
        template["template_key"] = template_key
        template.setdefault("template_id", template_key)
        template.setdefault("key", template_key)
    guidance = LONG_RUN_TEMPLATE_CHINESE_GUIDANCE.get(template_key, {})
    if guidance:
        template.setdefault("chinese_explanation", guidance["explanation"])
        template.setdefault("chinese_purpose", guidance["purpose"])

    template_type = str(
        template.get("template_type", "")
        or template.get("default_template_type", "")
        or ""
    )
    if template_type:
        template["template_type"] = template_type

    defaults = dict(template.get("defaults", {}) or {})
    _set_default(defaults, "template_type", template_type)
    _set_default(defaults, "interval_minutes", template.get("default_interval_minutes"))
    _set_default(defaults, "max_rounds", template.get("default_max_rounds"))
    _set_default(defaults, "desired_device_count", template.get("recommended_device_count"))
    _set_default(defaults, "rotation_strategy", template.get("recommended_rotation_strategy"))
    tags = _string_list(template.get("default_tags", template.get("tags", ())))
    if tags and "tags" not in defaults:
        defaults["tags"] = tags
    template["defaults"] = defaults

    overridable = template.get("overridable_parameters")
    if not isinstance(overridable, Sequence) or isinstance(overridable, (str, bytes, bytearray)):
        overridable = LONG_RUN_OVERRIDABLE_PARAMETERS
    template["overridable_parameters"] = _string_list(overridable)
    template["default_tags"] = tags
    template["risk_notes"] = _string_list(template.get("risk_notes", ()))
    return template


def normalize_long_run_templates(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_long_run_template_mapping(item) for item in values]


def find_long_run_template(
    templates: Sequence[Mapping[str, Any]],
    template_key: str,
) -> dict[str, Any] | None:
    expected = str(template_key or "")
    for item in templates:
        if _template_identity(item) == expected:
            return normalize_long_run_template_mapping(item)
    return None


def normalize_long_run_plan_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    plan = dict(value)
    template = plan.get("template")
    if isinstance(template, Mapping):
        normalized_template = normalize_long_run_template_mapping(template)
        plan["template"] = normalized_template
        plan.setdefault("template_key", normalized_template.get("template_key", ""))
    return plan


def sanitize_actor_for_public_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep actor context useful without echoing session/token material."""
    allowed_keys = ("actor_id", "display_name", "role_key", "permissions")
    return {key: value[key] for key in allowed_keys if key in value}


def _template_identity(item: Mapping[str, Any]) -> str:
    return str(item.get("template_key", "") or item.get("template_id", "") or item.get("key", "") or "")


def _set_default(defaults: dict[str, Any], key: str, value: Any) -> None:
    if key not in defaults and value not in (None, ""):
        defaults[key] = value


def _string_list(value: object) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)):
        items: Sequence[object] = (value,)
    elif isinstance(value, Sequence):
        items = value
    else:
        items = ()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result
