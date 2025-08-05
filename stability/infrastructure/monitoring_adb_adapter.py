"""ADBCollector-backed monitoring adapter."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from stability.infrastructure.adb import ADBCollector
from stability.infrastructure.monitoring_base import MonitoringAdapter
from stability.infrastructure.monitoring_legacy_storage import LegacyStorageMixin, default_data_storage
from stability.infrastructure.monitoring_models import (
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
)
from stability.infrastructure.monitoring_utils import utcnow


class ADBCollectorMonitoringAdapter(LegacyStorageMixin, MonitoringAdapter):
    """Wrap the existing collector + data_storage flow behind a reusable API."""

    def __init__(
        self,
        collector_factory: Optional[Callable[[], ADBCollector]] = None,
        data_storage_service: Any = default_data_storage,
    ) -> None:
        super().__init__(data_storage_service=data_storage_service)
        self._collector_factory = collector_factory or ADBCollector

    def start_session(
        self,
        device_id: str,
        config: Optional[MonitoringSessionConfig] = None,
        session_name: Optional[str] = None,
    ) -> MonitoringSessionHandle:
        session_config = config or MonitoringSessionConfig()
        collector = self._collector_factory()
        collector.device_id = device_id

        resolved_session_name = session_name or self._build_session_name(device_id)
        handle = MonitoringSessionHandle(
            device_id=device_id,
            session_name=resolved_session_name,
            config=session_config,
            collector=collector,
            backend_name="adb_collector",
        )
        if session_config.persist_to_database and not session_config.demo_mode:
            handle.session_id = self._create_legacy_session(handle)
            handle.persisted = handle.session_id is not None
        return handle

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        system = None
        metrics = dict(handle.config.metrics)

        if metrics.get("system", True):
            system = handle.collector.get_system_performance()

        apps = self._collect_app_samples(handle)
        return MonitoringSnapshot(
            timestamp=utcnow(),
            system=system,
            apps=apps,
            metadata={"backend": "adb_collector"},
        )

    def _collect_app_samples(self, handle: MonitoringSessionHandle) -> List[Dict[str, Any]]:
        if not handle.config.metrics.get("apps", True):
            return []

        selected_apps = [dict(app) for app in handle.config.selected_apps]
        if not selected_apps:
            return []

        package_names = [app["package_name"] for app in selected_apps if app.get("package_name")]
        if not package_names:
            return []

        samples: List[Dict[str, Any]] = []
        if hasattr(handle.collector, "get_multiple_app_performance"):
            batch_data = handle.collector.get_multiple_app_performance(package_names)
            for app in selected_apps:
                package_name = app.get("package_name")
                if not package_name or package_name not in batch_data:
                    continue
                sample = dict(batch_data[package_name])
                sample["app_info"] = app
                sample.setdefault("package_name", package_name)
                samples.append(sample)
            return samples

        for app in selected_apps:
            package_name = app.get("package_name")
            if not package_name:
                continue
            sample = handle.collector.get_app_performance(package_name)
            sample["app_info"] = app
            sample.setdefault("package_name", package_name)
            samples.append(sample)
        return samples

    @staticmethod
    def _build_session_name(device_id: str) -> str:
        return f"monitor_{device_id}_{utcnow().strftime('%Y%m%d_%H%M%S')}"
