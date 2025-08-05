"""Base monitoring adapter protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from stability.infrastructure.monitoring_models import (
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
)


class MonitoringAdapter(ABC):
    """Stable interface for monitoring session lifecycle and sampling."""

    @abstractmethod
    def start_session(
        self,
        device_id: str,
        config: Optional[MonitoringSessionConfig] = None,
        session_name: Optional[str] = None,
    ) -> MonitoringSessionHandle:
        raise NotImplementedError

    @abstractmethod
    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        raise NotImplementedError

    @abstractmethod
    def persist_snapshot(self, handle: MonitoringSessionHandle, snapshot: MonitoringSnapshot) -> bool:
        raise NotImplementedError

    @abstractmethod
    def stop_session(self, handle: MonitoringSessionHandle, status: str = "completed") -> None:
        raise NotImplementedError
