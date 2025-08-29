"""Legacy monitoring storage compatibility helpers."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from stability.infrastructure.monitoring_models import MonitoringSessionHandle, MonitoringSnapshot

# database.data_storage has been removed — legacy storage adapter is no longer available.
default_data_storage = None

logger = logging.getLogger(__name__)


class PersistedMonitoringDataProvider:
    """Read-only adapter for querying persisted monitoring session history."""

    def __init__(self, data_storage_service: Any = default_data_storage) -> None:
        self._data_storage = data_storage_service

    def get_monitoring_data(
        self,
        session_id: int,
        start_time=None,
        end_time=None,
        data_types=None,
        package_names=None,
    ) -> Mapping[str, Any]:
        if self._data_storage is None:
            return {}
        try:
            payload = self._data_storage.get_monitoring_data(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                data_types=data_types,
                package_names=package_names,
            )
        except Exception as exc:
            logger.warning("Failed to load monitoring history for session %s: %s", session_id, exc)
            return {}
        return payload or {}


class LegacyStorageMixin:
    """Shared legacy session and persistence helpers."""

    def __init__(self, *, data_storage_service: Any = default_data_storage) -> None:
        self._data_storage = data_storage_service

    def _create_legacy_session(self, handle: MonitoringSessionHandle) -> Optional[int]:
        if self._data_storage is None:
            return None
        try:
            session_id = self._data_storage.create_monitoring_session(
                session_name=handle.session_name,
                device_id=handle.device_id,
                config=handle.config.to_legacy_config(handle.device_id),
                selected_apps=[dict(app) for app in handle.config.selected_apps],
            )
            return int(session_id) if session_id else None
        except Exception as exc:
            logger.warning("Failed to create monitoring session for %s: %s", handle.device_id, exc)
            return None

    def persist_snapshot(self, handle: MonitoringSessionHandle, snapshot: MonitoringSnapshot) -> bool:
        if not handle.session_id or self._data_storage is None:
            return False
        try:
            return bool(self._data_storage.store_monitoring_data(handle.session_id, snapshot.to_legacy_payload()))
        except Exception as exc:
            logger.warning(
                "Failed to persist monitoring snapshot for session %s: %s",
                handle.session_id,
                exc,
            )
            return False

    def stop_session(self, handle: MonitoringSessionHandle, status: str = "completed") -> None:
        if not handle.session_id or self._data_storage is None:
            return
        try:
            if hasattr(self._data_storage, "flush_all_buffers"):
                self._data_storage.flush_all_buffers()
            self._data_storage.end_monitoring_session(handle.session_id, status=self._legacy_session_status(status))
        except Exception as exc:
            logger.warning(
                "Failed to stop monitoring session %s: %s",
                handle.session_id,
                exc,
            )

    @staticmethod
    def _legacy_session_status(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized in {"success", "completed", "passed"}:
            return "completed"
        if normalized in {"failed", "failure", "error"}:
            return "error"
        if normalized in {"cancelled", "canceled", "interrupted"}:
            return "cancelled"
        return "completed"


_LegacyStorageMixin = LegacyStorageMixin
