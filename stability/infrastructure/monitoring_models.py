"""Monitoring adapter data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from stability.infrastructure.monitoring_utils import utcnow


@dataclass(frozen=True)
class MonitoringSessionConfig:
    """Configuration normalized for the monitoring adapter contract."""

    selected_apps: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    metrics: Mapping[str, bool] = field(
        default_factory=lambda: {
            "system": True,
            "apps": True,
        }
    )
    sample_interval: float = 3.0
    persist_to_database: bool = True
    demo_mode: bool = False
    profile_name: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_legacy_config(self, device_id: str) -> Dict[str, Any]:
        config = {
            "device_id": device_id,
            "selected_apps": [dict(app) for app in self.selected_apps],
            "metrics": dict(self.metrics),
            "sample_interval": self.sample_interval,
            "demo_mode": self.demo_mode,
            "monitoring_profile": self.profile_name,
        }
        config.update(dict(self.extra))
        return config


@dataclass
class MonitoringSessionHandle:
    """Runtime handle for one monitoring session managed by an adapter."""

    device_id: str
    session_name: str
    config: MonitoringSessionConfig
    collector: Any = field(repr=False, default=None)
    session_id: Optional[int] = None
    started_at: datetime = field(default_factory=utcnow)
    persisted: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    backend_name: str = ""


@dataclass(frozen=True)
class MonitoringSnapshot:
    """A single monitoring sample in a format compatible with legacy storage."""

    timestamp: datetime
    system: Optional[Dict[str, Any]]
    apps: List[Dict[str, Any]]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_legacy_payload(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "system": self.system,
            "apps": self.apps,
        }
