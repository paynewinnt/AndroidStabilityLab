from __future__ import annotations

from .application_common import *
from stability.app.unattended.template_payloads import LONG_RUN_OVERRIDABLE_PARAMETERS, find_long_run_template
from stability.time_utils import format_beijing_datetime_or_original


class ApplicationIntegrationHelpersMixin:
    @staticmethod
    def _release_submission_payload(record: object) -> dict[str, Any]:
        submission_id = str(getattr(record, "submission_id", "") or "")
        return {
            "submission_id": submission_id,
            "source_platform": str(getattr(record, "source_platform", "") or ""),
            "source_request_id": str(getattr(record, "source_request_id", "") or ""),
            "submission_title": str(getattr(record, "submission_title", "") or ""),
            "submission_status": str(getattr(record, "submission_status", "") or ""),
            "package_name": str(getattr(record, "package_name", "") or ""),
            "version_name": str(getattr(record, "version_name", "") or ""),
            "version_code": str(getattr(record, "version_code", "") or ""),
            "build_id": str(getattr(record, "build_id", "") or ""),
            "release_channel": str(getattr(record, "release_channel", "") or ""),
            "owner_team": str(getattr(record, "owner_team", "") or ""),
            "template_type": str(getattr(record, "template_type", "") or ""),
            "selected_device_ids": list(getattr(record, "selected_device_ids", ()) or ()),
            "enabled_metrics": list(getattr(record, "enabled_metrics", ()) or ()),
            "sampling_interval_seconds": int(getattr(record, "sampling_interval_seconds", 0) or 0),
            "monitoring_backend": str(getattr(record, "monitoring_backend", "") or ""),
            "execute_immediately": bool(getattr(record, "execute_immediately", False)),
            "task_id": str(getattr(record, "task_id", "") or ""),
            "task_name": str(getattr(record, "task_name", "") or ""),
            "run_id": str(getattr(record, "run_id", "") or ""),
            "run_status": str(getattr(record, "run_status", "") or ""),
            "report_paths": dict(getattr(record, "report_paths", {}) or {}),
            "baseline_key": str(getattr(record, "baseline_key", "") or ""),
            "admission_case_id": str(getattr(record, "admission_case_id", "") or ""),
            "admission_status": str(getattr(record, "admission_status", "") or ""),
            "admission_final_decision": str(getattr(record, "admission_final_decision", "") or ""),
            "admission_error_code": str(getattr(record, "admission_error_code", "") or ""),
            "created_at": WebPortalApplication._isoformat_or_none(getattr(record, "created_at", None)),
            "created_by": str(getattr(record, "created_by", "") or ""),
            "updated_at": WebPortalApplication._isoformat_or_none(getattr(record, "updated_at", None)),
            "updated_by": str(getattr(record, "updated_by", "") or ""),
            "metadata": dict(getattr(record, "metadata", {}) or {}),
            "detail_path": f"/api/release-submissions/{quote(submission_id, safe='')}" if submission_id else "",
            "api_path": f"/api/release-submissions/{quote(submission_id, safe='')}" if submission_id else "",
        }

    @staticmethod
    def _describe_task_payload(task: object) -> dict[str, Any]:
        target_app = getattr(task, "target_app", None)
        sampling_config = getattr(task, "sampling_config", None)
        template_type = getattr(task, "template_type", None)
        metadata = dict(getattr(task, "metadata", {}) or {})
        lifecycle = dict(metadata.get("lifecycle", {}) or {})
        return {
            "task_id": str(getattr(task, "task_id", "") or ""),
            "task_name": str(getattr(task, "task_name", "") or ""),
            "template_type": str(getattr(template_type, "value", template_type) or ""),
            "package_name": str(getattr(target_app, "package_name", "") or ""),
            "target_app": {
                "package_name": str(getattr(target_app, "package_name", "") or ""),
                "app_label": str(getattr(target_app, "app_label", "") or ""),
                "version_name": str(getattr(target_app, "version_name", "") or ""),
                "version_code": str(getattr(target_app, "version_code", "") or ""),
                "launch_activity": str(getattr(target_app, "launch_activity", "") or ""),
            },
            "selected_device_ids": list(getattr(task, "selected_device_ids", ()) or ()),
            "planned_device_count": int(getattr(task, "planned_device_count", lambda: 0)() or 0),
            "task_params": dict(getattr(task, "task_params", {}) or {}),
            "sampling_config": {
                "interval_seconds": int(getattr(sampling_config, "interval_seconds", 0) or 0),
                "enabled_metrics": list(getattr(sampling_config, "enabled_metrics", ()) or ()),
            },
            "duration_seconds": int(getattr(task, "duration_seconds", 0) or 0),
            "timeout_seconds": int(getattr(task, "timeout_seconds", 0) or 0),
            "created_by": str(getattr(task, "created_by", "") or ""),
            "created_at": WebPortalApplication._isoformat_or_none(getattr(task, "created_at", None)),
            "updated_at": WebPortalApplication._isoformat_or_none(getattr(task, "updated_at", None)),
            "notes": str(getattr(task, "notes", "") or ""),
            "metadata": metadata,
            "archived": bool(metadata.get("archived") or lifecycle.get("archived") or lifecycle.get("state") == "archived"),
            "hidden": bool(metadata.get("hidden") or lifecycle.get("hidden") or lifecycle.get("state") == "archived"),
            "archived_at": WebPortalApplication._isoformat_or_none(metadata.get("archived_at")),
            "archived_by": str(metadata.get("archived_by", "") or ""),
            "archive_reason": str(metadata.get("archive_reason", "") or ""),
        }

    @staticmethod
    def _unattended_task_payload(item: object) -> dict[str, Any]:
        return {
            "task_id": str(getattr(item, "task_id", "") or ""),
            "task_name": str(getattr(item, "task_name", "") or ""),
            "configured": bool(getattr(item, "configured", False)),
            "enabled": bool(getattr(item, "enabled", False)),
            "interval_minutes": int(getattr(item, "interval_minutes", 0) or 0),
            "desired_device_count": int(getattr(item, "desired_device_count", 0) or 0),
            "failure_threshold": int(getattr(item, "failure_threshold", 0) or 0),
            "rotation_strategy": str(getattr(item, "rotation_strategy", "") or ""),
            "rotation_advance_policy": str(getattr(item, "rotation_advance_policy", "") or ""),
            "rotation_cursor": int(getattr(item, "rotation_cursor", 0) or 0),
            "rotation_advance_count": int(getattr(item, "rotation_advance_count", 0) or 0),
            "primary_device_ids": list(getattr(item, "primary_device_ids", ()) or ()),
            "backup_device_ids": list(getattr(item, "backup_device_ids", ()) or ()),
            "next_run_at": WebPortalApplication._isoformat_or_none(getattr(item, "next_run_at", None)),
            "last_run_at": WebPortalApplication._isoformat_or_none(getattr(item, "last_run_at", None)),
            "last_run_id": str(getattr(item, "last_run_id", "") or ""),
            "due": bool(getattr(item, "due", False)),
            "latest_summary": dict(getattr(item, "latest_summary", {}) or {}),
            "long_run_summary": dict(getattr(item, "long_run_summary", {}) or {}),
            "recent_device_windows": [dict(entry) for entry in (getattr(item, "recent_device_windows", ()) or ())],
            "recent_rounds": [dict(entry) for entry in (getattr(item, "recent_rounds", ()) or ())],
        }

    @staticmethod
    def _unattended_round_execution_payload(item: object) -> dict[str, Any]:
        return {
            "executed": bool(getattr(item, "executed", False)),
            "reason": str(getattr(item, "reason", "") or ""),
            "round": dict(getattr(item, "round_record", {}) or {}),
        }

    @staticmethod
    def _unattended_patrol_payload(item: object) -> dict[str, Any]:
        return {
            "generated_at": WebPortalApplication._isoformat_or_none(getattr(item, "generated_at", None)),
            "task_count": int(getattr(item, "task_count", 0) or 0),
            "enabled_task_count": int(getattr(item, "enabled_task_count", 0) or 0),
            "due_task_count": int(getattr(item, "due_task_count", 0) or 0),
            "executed_task_count": int(getattr(item, "executed_task_count", 0) or 0),
            "skipped_task_count": int(getattr(item, "skipped_task_count", 0) or 0),
            "failed_rate": float(getattr(item, "failed_rate", 0.0) or 0.0),
            "offline_rate": float(getattr(item, "offline_rate", 0.0) or 0.0),
            "recovery_success_rate": float(getattr(item, "recovery_success_rate", 0.0) or 0.0),
            "quarantined_device_count": int(getattr(item, "quarantined_device_count", 0) or 0),
            "quarantined_device_ids": list(getattr(item, "quarantined_device_ids", ()) or ()),
            "quarantine_probe_attempt_count": int(getattr(item, "quarantine_probe_attempt_count", 0) or 0),
            "quarantine_probe_skipped_count": int(getattr(item, "quarantine_probe_skipped_count", 0) or 0),
            "quarantine_probe_recovered_count": int(getattr(item, "quarantine_probe_recovered_count", 0) or 0),
            "recovered_device_ids": list(getattr(item, "recovered_device_ids", ()) or ()),
            "metrics": dict(getattr(item, "metrics", {}) or {}),
            "executed_rounds": [dict(entry) for entry in (getattr(item, "executed_rounds", ()) or ())],
            "tasks": [WebPortalApplication._unattended_task_payload(record) for record in (getattr(item, "task_records", ()) or ())],
        }

    @staticmethod
    def _unattended_daily_report_payload(item: object) -> dict[str, Any]:
        return {
            "report_date": str(getattr(item, "report_date", "") or ""),
            "generated_at": WebPortalApplication._isoformat_or_none(getattr(item, "generated_at", None)),
            "round_count": int(getattr(item, "round_count", 0) or 0),
            "executed_round_count": int(getattr(item, "executed_round_count", 0) or 0),
            "failed_round_count": int(getattr(item, "failed_round_count", 0) or 0),
            "device_online_rate": float(getattr(item, "device_online_rate", 0.0) or 0.0),
            "failed_rate": float(getattr(item, "failed_rate", 0.0) or 0.0),
            "offline_rate": float(getattr(item, "offline_rate", 0.0) or 0.0),
            "recovery_success_rate": float(getattr(item, "recovery_success_rate", 0.0) or 0.0),
            "quarantined_device_count": int(getattr(item, "quarantined_device_count", 0) or 0),
            "metrics": dict(getattr(item, "metrics", {}) or {}),
            "task_summaries": [dict(entry) for entry in (getattr(item, "task_summaries", ()) or ())],
        }

    @staticmethod
    def _unattended_weekly_report_payload(item: object) -> dict[str, Any]:
        return {
            "week_key": str(getattr(item, "week_key", "") or ""),
            "anchor_date": str(getattr(item, "anchor_date", "") or ""),
            "week_start_date": str(getattr(item, "week_start_date", "") or ""),
            "week_end_date": str(getattr(item, "week_end_date", "") or ""),
            "generated_at": WebPortalApplication._isoformat_or_none(getattr(item, "generated_at", None)),
            "round_count": int(getattr(item, "round_count", 0) or 0),
            "executed_round_count": int(getattr(item, "executed_round_count", 0) or 0),
            "failed_round_count": int(getattr(item, "failed_round_count", 0) or 0),
            "active_day_count": int(getattr(item, "active_day_count", 0) or 0),
            "device_online_rate": float(getattr(item, "device_online_rate", 0.0) or 0.0),
            "failed_rate": float(getattr(item, "failed_rate", 0.0) or 0.0),
            "offline_rate": float(getattr(item, "offline_rate", 0.0) or 0.0),
            "recovery_success_rate": float(getattr(item, "recovery_success_rate", 0.0) or 0.0),
            "quarantined_device_count": int(getattr(item, "quarantined_device_count", 0) or 0),
            "metrics": dict(getattr(item, "metrics", {}) or {}),
            "task_summaries": [dict(entry) for entry in (getattr(item, "task_summaries", ()) or ())],
            "daily_summaries": [dict(entry) for entry in (getattr(item, "daily_summaries", ()) or ())],
        }

    @staticmethod
    def _instance_payload(instance: object) -> dict[str, Any]:
        payload = {
            "instance_id": str(getattr(instance, "instance_id", "") or ""),
            "device_id": str(getattr(instance, "device_id", "") or ""),
            "status": str(getattr(instance, "instance_status", getattr(instance, "status", "")) or ""),
        }
        metadata = dict(getattr(instance, "metadata", {}) or {})
        monitoring_backend = str(metadata.get("monitoring_backend", "") or getattr(instance, "monitoring_backend", "") or "").strip()
        if monitoring_backend:
            payload["monitoring_backend"] = monitoring_backend
        monitoring_trace_path = str(metadata.get("monitoring_trace_path", "") or getattr(instance, "monitoring_trace_path", "") or "").strip()
        if monitoring_trace_path:
            payload["monitoring_trace_path"] = monitoring_trace_path
        monitoring_snapshot_path = str(metadata.get("monitoring_snapshot_path", "") or getattr(instance, "monitoring_snapshot_path", "") or "").strip()
        if monitoring_snapshot_path:
            payload["monitoring_snapshot_path"] = monitoring_snapshot_path
        return payload

    @staticmethod
    def _count_instance_statuses(instances: Sequence[object]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for instance in instances:
            status = str(getattr(instance, "instance_status", getattr(instance, "status", "unknown")) or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _json_safe_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
        if hasattr(value, "__dict__"):
            return {
                str(key): item
                for key, item in dict(getattr(value, "__dict__", {}) or {}).items()
                if not str(key).startswith("_")
            }
        return {}

    @staticmethod
    def _fallback_long_run_templates() -> list[dict[str, Any]]:
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

    @staticmethod
    def _find_long_run_template(templates: Sequence[Mapping[str, Any]], template_key: str) -> dict[str, Any] | None:
        return find_long_run_template(templates, template_key)

    @staticmethod
    def _service_long_run_template(service: object | None, template_key: str) -> dict[str, Any] | None:
        if service is None:
            return None
        for method_name in ("get_long_run_template", "show_long_run_template"):
            method = getattr(service, method_name, None)
            if method is None:
                continue
            try:
                result = method(template_key)
            except Exception:
                continue
            if result is not None:
                return WebPortalApplication._jsonable_mapping(result)
        return None

    @staticmethod
    def _service_long_run_template_plan(
        service: object | None,
        template_key: str,
        overrides: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if service is None:
            return None
        build_method = getattr(service, "build_long_run_plan", None)
        if build_method is not None:
            build_overrides = {
                key: value for key, value in dict(overrides).items() if key in LONG_RUN_OVERRIDABLE_PARAMETERS
            }
            result = WebPortalApplication._call_long_run_template_plan_method(
                build_method,
                template_key,
                (((), build_overrides), ((), {})),
            )
            if result is not None:
                return result

        plan_method = getattr(service, "plan_long_run_template", None)
        if plan_method is None:
            return None
        return WebPortalApplication._call_long_run_template_plan_method(
            plan_method,
            template_key,
            (
                ((), {"overrides": dict(overrides)}),
                ((dict(overrides),), {}),
                ((), dict(overrides)),
                ((), {}),
            ),
        )

    @staticmethod
    def _call_long_run_template_plan_method(
        method: Any,
        template_key: str,
        attempts: Sequence[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> dict[str, Any] | None:
        for args, kwargs in attempts:
            try:
                result = method(template_key, *args, **kwargs)
            except TypeError:
                continue
            except Exception:
                return None
            return WebPortalApplication._jsonable_mapping(result)
        return None

    @staticmethod
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

    @staticmethod
    def _jsonable_mapping(value: object) -> dict[str, Any]:
        normalized = WebPortalApplication._jsonable_value(value)
        return dict(normalized) if isinstance(normalized, Mapping) else {"value": normalized}

    @staticmethod
    def _jsonable_value(value: object) -> object:
        if isinstance(value, Mapping):
            return {str(key): WebPortalApplication._jsonable_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [WebPortalApplication._jsonable_value(item) for item in value]
        enum_value = getattr(value, "value", None)
        if enum_value is not None and value.__class__.__module__ != "builtins":
            return enum_value
        if hasattr(value, "isoformat"):
            return format_beijing_datetime_or_original(value)
        if hasattr(value, "__dict__") and value.__class__.__module__ != "builtins":
            return {
                str(key): WebPortalApplication._jsonable_value(item)
                for key, item in vars(value).items()
                if not str(key).startswith("_")
            }
        return value
