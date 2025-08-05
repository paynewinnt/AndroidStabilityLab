from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from collections.abc import Iterable, Mapping as MappingABC
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.app import (
    AggregatedIssueNotFound,
    DeviceRecordNotFound,
    RunRecordNotFound,
    SnapshotRecordNotFound,
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedTaskRecordNotFound,
)
from stability.app.task_service import TaskRecordNotFound
from stability.domain import (
    AggregatedIssue,
    AnalysisSnapshotRecord,
    AnalysisSnapshotSummary,
    ComparedMetricTrend,
    ComparedIssue,
    ComparisonResult,
    IssueEventReference,
    IssueAttribution,
    MetricTrendSummary,
    PerformanceTrendComparison,
    RegressedIssue,
    RegressedMetric,
    RegressionResult,
    SamplingConfig,
    TaskDefinition,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.app.unattended.template_payloads import (
    LONG_RUN_OVERRIDABLE_PARAMETERS,
    find_long_run_template,
    normalize_long_run_plan_mapping,
    normalize_long_run_template_mapping,
    normalize_long_run_templates,
)
from stability.cli.handlers.web import handle_serve_web as _web_handle_serve_web
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; payloads_longrun.py owns this command/payload group.

def _fallback_long_run_templates() -> list[dict[str, object]]:
    """Return stable CLI/Web defaults until the service layer exposes template methods."""
    return [
        {
            "template_key": "soak_2h",
            "name": "2 小时冒烟长稳",
            "description": "适合版本提测前快速确认无人值守链路、设备轮转和报告产出。",
            "template_type": TaskTemplateType.MONKEY.value,
            "defaults": {
                "duration_seconds": 7200,
                "timeout_seconds": 7800,
                "interval_minutes": 30,
                "desired_device_count": 1,
                "failure_threshold": 2,
                "max_round_history": 8,
                "rotation_strategy": "round_robin",
                "rotation_advance_policy": "every_round",
                "max_device_window_history": 8,
                "sampling_interval": 5,
                "enabled_metrics": ["cpu", "memory", "fps"],
            },
            "overridable_parameters": [
                "duration_seconds",
                "timeout_seconds",
                "interval_minutes",
                "desired_device_count",
                "failure_threshold",
                "rotation_strategy",
                "rotation_advance_policy",
                "enabled_metrics",
            ],
        },
        {
            "template_key": "soak_8h",
            "name": "8 小时工作日长稳",
            "description": "覆盖一个工作日内的持续运行、掉线恢复和周期性日报素材沉淀。",
            "template_type": TaskTemplateType.MONKEY.value,
            "defaults": {
                "duration_seconds": 28800,
                "timeout_seconds": 30000,
                "interval_minutes": 60,
                "desired_device_count": 2,
                "failure_threshold": 3,
                "max_round_history": 16,
                "rotation_strategy": "round_robin",
                "rotation_advance_policy": "every_round",
                "max_device_window_history": 16,
                "sampling_interval": 10,
                "enabled_metrics": ["cpu", "memory", "fps", "power"],
            },
            "overridable_parameters": [
                "duration_seconds",
                "timeout_seconds",
                "interval_minutes",
                "desired_device_count",
                "failure_threshold",
                "rotation_strategy",
                "rotation_advance_policy",
                "enabled_metrics",
            ],
        },
        {
            "template_key": "endurance_24h",
            "name": "24 小时耐久长稳",
            "description": "面向夜间或周末持续巡检，默认保留更长轮次历史用于日报/周报分析。",
            "template_type": TaskTemplateType.MONKEY.value,
            "defaults": {
                "duration_seconds": 86400,
                "timeout_seconds": 90000,
                "interval_minutes": 120,
                "desired_device_count": 2,
                "failure_threshold": 3,
                "max_round_history": 32,
                "rotation_strategy": "round_robin",
                "rotation_advance_policy": "failure_only",
                "max_device_window_history": 32,
                "sampling_interval": 15,
                "enabled_metrics": ["cpu", "memory", "fps", "power"],
            },
            "overridable_parameters": [
                "duration_seconds",
                "timeout_seconds",
                "interval_minutes",
                "desired_device_count",
                "failure_threshold",
                "rotation_strategy",
                "rotation_advance_policy",
                "enabled_metrics",
            ],
        },
    ]


def _long_run_templates_payload(
    unattended_service: object | None,
    *,
    template_key: str = "",
    overrides: Mapping[str, object] | None = None,
    include_plan: bool = False,
) -> dict[str, object]:
    source = "fallback"
    templates: list[dict[str, object]] = []
    if unattended_service is not None and hasattr(unattended_service, "list_long_run_templates"):
        try:
            templates = normalize_long_run_templates(
                [
                    _jsonable_mapping(item)
                    for item in _long_run_template_items(unattended_service.list_long_run_templates())
                ]
            )
            source = "service"
        except Exception:
            templates = []
    if not templates:
        templates = normalize_long_run_templates(_fallback_long_run_templates())

    selected = find_long_run_template(templates, template_key) if template_key else None
    payload: dict[str, object] = {
        "storage_mode": "persistent",
        "source": source,
        "template_count": len(templates),
        "templates": templates,
    }
    if template_key:
        if selected is None and source == "service":
            selected = _service_long_run_template(unattended_service, template_key)
            if selected is not None:
                selected = normalize_long_run_template_mapping(selected)
        payload["template_key"] = template_key
        payload["template"] = selected
    if include_plan:
        normalized_overrides = dict(overrides or {})
        payload["overrides"] = normalized_overrides
        payload["plan"] = _service_long_run_template_plan(
            unattended_service,
            template_key,
            normalized_overrides,
        )
        if isinstance(payload["plan"], MappingABC):
            payload["plan"] = normalize_long_run_plan_mapping(payload["plan"])
        if payload["plan"] is None and selected is not None:
            defaults = dict(selected.get("defaults", {}) or {})
            payload["plan"] = {
                "template_key": template_key,
                "effective_defaults": {**defaults, **normalized_overrides},
                "overrides": normalized_overrides,
            }
    return payload


def _service_long_run_template(unattended_service: object | None, template_key: str) -> dict[str, object] | None:
    if unattended_service is None:
        return None
    for method_name in ("get_long_run_template", "show_long_run_template"):
        method = getattr(unattended_service, method_name, None)
        if method is None:
            continue
        try:
            result = method(template_key)
        except Exception:
            continue
        if result is not None:
            return _jsonable_mapping(result)
    return None


def _service_long_run_template_plan(
    unattended_service: object | None,
    template_key: str,
    overrides: Mapping[str, object],
) -> dict[str, object] | None:
    if unattended_service is None:
        return None
    build_method = getattr(unattended_service, "build_long_run_plan", None)
    if build_method is not None:
        build_overrides = {
            key: value for key, value in dict(overrides).items() if key in LONG_RUN_OVERRIDABLE_PARAMETERS
        }
        result = _call_long_run_template_plan_method(
            build_method,
            template_key,
            (((), build_overrides), ((), {})),
        )
        if result is not None:
            return result

    plan_method = getattr(unattended_service, "plan_long_run_template", None)
    if plan_method is None:
        return None
    return _call_long_run_template_plan_method(
        plan_method,
        template_key,
        (
            ((), {"overrides": dict(overrides)}),
            ((dict(overrides),), {}),
            ((), dict(overrides)),
            ((), {}),
        ),
    )


def _call_long_run_template_plan_method(
    method: object,
    template_key: str,
    attempts: Sequence[tuple[tuple[object, ...], dict[str, object]]],
) -> dict[str, object] | None:
    for args, kwargs in attempts:
        try:
            result = method(template_key, *args, **kwargs)  # type: ignore[misc]
        except TypeError:
            continue
        except Exception:
            return None
        return _jsonable_mapping(result)
    return None


def _long_run_template_items(value: object) -> Sequence[object]:
    if isinstance(value, Mapping):
        for key in ("templates", "items", "entries"):
            items = value.get(key)
            if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)):
                return items
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _find_long_run_template(templates: Sequence[Mapping[str, object]], template_key: str) -> dict[str, object] | None:
    return find_long_run_template(templates, template_key)


def _parse_key_value_overrides(values: Sequence[str]) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for raw_item in values:
        if "=" not in raw_item:
            raise SystemExit(f"Invalid override '{raw_item}'. Expected key=value.")
        key, raw_value = raw_item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit("Override key must not be empty.")
        overrides[key] = _parse_scalar_override(raw_value.strip())
    return overrides


def _parse_scalar_override(value: str) -> object:
    if value == "":
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _jsonable_mapping(value: object) -> dict[str, object]:
    normalized = _jsonable_value(value)
    return dict(normalized) if isinstance(normalized, Mapping) else {"value": normalized}


def _jsonable_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable_value(item) for item in value]
    enum_value = getattr(value, "value", None)
    if enum_value is not None and value.__class__.__module__ != "builtins":
        return enum_value
    if hasattr(value, "isoformat"):
        return format_beijing_datetime_or_original(value)
    if hasattr(value, "__dict__") and value.__class__.__module__ != "builtins":
        return {
            str(key): _jsonable_value(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return value


def _isoformat_or_none(value: object) -> str | None:
    """Return a Beijing display string when the object looks like a datetime."""
    return format_beijing_datetime_or_original(value)
