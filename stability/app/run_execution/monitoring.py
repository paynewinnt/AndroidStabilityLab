from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Sequence, TYPE_CHECKING

from stability.infrastructure import MonitoringSessionConfig

if TYPE_CHECKING:
    from ..execution_service import ExecutionInstanceLike, TaskDefinitionLike


class MonitoringHelpersMixin:
    """Monitoring session and snapshot metadata helpers."""

    def _start_monitoring_session(
        self,
        task: "TaskDefinitionLike",
        instance: "ExecutionInstanceLike",
        *,
        layout,
        persist_monitoring: bool,
    ):
        """Translate task sampling settings into a monitoring session handle."""
        if self._monitoring_adapter is None:
            return None
        target_app = getattr(task, "target_app", None)
        selected_apps = []
        package_name = getattr(target_app, "package_name", "") if target_app is not None else ""
        app_label = getattr(target_app, "app_label", "") if target_app is not None else ""
        if package_name:
            selected_apps.append(
                {
                    "package_name": package_name,
                    "app_name": app_label or package_name,
                }
            )
        sampling_config = getattr(task, "sampling_config", None)
        interval_seconds = getattr(sampling_config, "interval_seconds", 3) if sampling_config else 3
        extra = dict(getattr(sampling_config, "metadata", {}) or {}) if sampling_config is not None else {}
        enabled_metrics = self._normalize_enabled_metrics(
            getattr(sampling_config, "enabled_metrics", ()) if sampling_config is not None else ()
        )
        extra.setdefault("runtime_monitoring_dir", str(layout.monitoring_dir))
        extra.setdefault("task_timeout_seconds", getattr(task, "timeout_seconds", 0) or 0)
        extra.setdefault("task_duration_seconds", getattr(task, "duration_seconds", 0) or 0)
        if enabled_metrics and "solox_enabled_metrics" not in extra:
            extra["solox_enabled_metrics"] = tuple(enabled_metrics)
        config = MonitoringSessionConfig(
            selected_apps=tuple(selected_apps),
            metrics=self._monitoring_metric_scope(enabled_metrics),
            sample_interval=float(interval_seconds or 3),
            persist_to_database=persist_monitoring,
            profile_name=str(getattr(sampling_config, "monitoring_profile", "") or ""),
            extra=extra,
        )
        return self._monitoring_adapter.start_session(
            device_id=getattr(instance, "device_id", ""),
            config=config,
            session_name=f"{getattr(task, 'task_id', 'task')}_{getattr(instance, 'instance_id', 'instance')}",
        )

    @staticmethod
    def _normalize_enabled_metrics(values: Sequence[object] | None) -> tuple[str, ...]:
        normalized = []
        for value in values or ():
            item = str(value or "").strip().lower()
            if item:
                normalized.append(item)
        return tuple(normalized)

    @classmethod
    def _monitoring_metric_scope(cls, enabled_metrics: Sequence[str]) -> Dict[str, bool]:
        normalized = {str(item or "").strip().lower() for item in enabled_metrics if str(item or "").strip()}
        if not normalized:
            return {"system": True, "apps": True}

        app_targets = {
            "app",
            "apps",
            "cpu",
            "memory",
            "memory_detail",
            "network",
            "fps",
            "gpu",
            "jank",
        }
        system_targets = {
            "system",
            "cpu",
            "battery",
            "power",
            "power_usage",
        }
        apps_enabled = bool(normalized & app_targets)
        system_enabled = bool(normalized & system_targets)
        if not apps_enabled and not system_enabled:
            return {"system": True, "apps": True}
        return {"system": system_enabled, "apps": apps_enabled}

    @staticmethod
    def _snapshot_payload(snapshot, *, persisted: bool) -> Dict[str, Any]:
        """Normalize one monitoring snapshot into a JSON-serializable payload."""
        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "persisted": persisted,
            "system": MonitoringHelpersMixin._jsonable_snapshot_value(snapshot.system),
            "apps": MonitoringHelpersMixin._jsonable_snapshot_value(snapshot.apps),
            "metadata": MonitoringHelpersMixin._jsonable_snapshot_value(dict(getattr(snapshot, "metadata", {}) or {})),
        }

    @staticmethod
    def _jsonable_snapshot_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): MonitoringHelpersMixin._jsonable_snapshot_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [MonitoringHelpersMixin._jsonable_snapshot_value(item) for item in value]
        return value

    @staticmethod
    def _monitoring_trace_path(snapshot_payload: Dict[str, Any] | None) -> str:
        metadata = dict((snapshot_payload or {}).get("metadata", {}) or {})
        explicit = str(metadata.get("trace_artifact_path", "") or "").strip()
        if explicit:
            return explicit
        for artifact in metadata.get("artifacts", ()) or ():
            if not isinstance(artifact, dict):
                continue
            artifact_type = str(artifact.get("artifact_type", "") or artifact.get("type", "") or "").strip().lower()
            if artifact_type != "perfetto_trace":
                continue
            file_path = str(artifact.get("file_path", "") or artifact.get("path", "") or "").strip()
            if file_path:
                return file_path
        return ""
