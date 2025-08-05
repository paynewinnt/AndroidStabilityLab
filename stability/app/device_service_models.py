from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Sequence

from stability.domain import Device
from stability.domain.value_objects import utcnow


class DeviceRepository(Protocol):
    """Persistence contract for the V1 device registry."""

    def add(self, device: Device) -> Device:
        ...

    def get(self, device_id: str) -> Optional[Device]:
        ...

    def list(self) -> Sequence[Device]:
        ...

    def save(self, device: Device) -> Device:
        ...


@dataclass(frozen=True)
class DeviceSyncResult:
    """Summary of one device-registry synchronization pass."""

    scanned_count: int
    created: Sequence[Device] = field(default_factory=tuple)
    updated: Sequence[Device] = field(default_factory=tuple)
    refreshed: Sequence[Device] = field(default_factory=tuple)
    marked_offline: Sequence[Device] = field(default_factory=tuple)
    synced_at: datetime = field(default_factory=utcnow)

    @property
    def changed_count(self) -> int:
        return len(self.created) + len(self.updated) + len(self.marked_offline)

    @property
    def total_persisted(self) -> int:
        return len(self.created) + len(self.updated) + len(self.refreshed) + len(self.marked_offline)


@dataclass(frozen=True)
class DeviceQuarantineProbeResult:
    """Summary of one quarantined-device recovery probe."""

    device_id: str
    serial: str
    attempted: bool
    recovered: bool
    skipped: bool
    reason: str
    probed_at: datetime
    next_probe_at: datetime | None = None


@dataclass(frozen=True)
class DeviceConnectionAttemptResult:
    """Result of a user-triggered ADB connect + registry refresh action."""

    serial: str
    attempted: bool
    connected: bool
    message: str = ""
    device: Device | None = None
    paired: bool = False
    pair_serial: str = ""
    pair_message: str = ""
    synced_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial": self.serial,
            "attempted": self.attempted,
            "connected": self.connected,
            "message": self.message,
            "paired": self.paired,
            "pair_serial": self.pair_serial,
            "pair_message": self.pair_message,
            "device_id": self.device.device_id if self.device is not None else "",
            "connection_state": self.device.connection_state.value if self.device is not None else "",
            "availability_state": self.device.availability_state.value if self.device is not None else "",
            "is_schedulable": self.device.is_schedulable() if self.device is not None else False,
            "synced_at": self.synced_at.isoformat(),
        }


@dataclass(frozen=True)
class DeviceTeamProfile:
    """Normalized scheduling profile read from Device fields and metadata."""

    device_id: str
    group_name: str = ""
    team_name: str = ""
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    owner: str = ""
    priority: int = 0
    maintenance: bool = False
    maintenance_reason: str = ""
    reserved_by: str = ""
    quarantine_reason: str = ""


@dataclass(frozen=True)
class DevicePoolSummary:
    """Read-only pool health counters for one group/team/tag bucket."""

    key: str
    dimension: str
    total_count: int = 0
    online_count: int = 0
    idle_count: int = 0
    running_count: int = 0
    reserved_count: int = 0
    quarantined_count: int = 0
    maintenance_count: int = 0
    schedulable_count: int = 0
    risk_count: int = 0
    device_ids: tuple[str, ...] = ()
    schedulable_device_ids: tuple[str, ...] = ()
    risk_device_ids: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "dimension": self.dimension,
            "total_count": self.total_count,
            "online_count": self.online_count,
            "idle_count": self.idle_count,
            "running_count": self.running_count,
            "reserved_count": self.reserved_count,
            "quarantined_count": self.quarantined_count,
            "maintenance_count": self.maintenance_count,
            "schedulable_count": self.schedulable_count,
            "risk_count": self.risk_count,
            "device_ids": list(self.device_ids),
            "schedulable_device_ids": list(self.schedulable_device_ids),
            "risk_device_ids": list(self.risk_device_ids),
        }


@dataclass(frozen=True)
class DeviceSchedulingCandidate:
    """Per-device scheduling decision with human-readable blockers."""

    device_id: str
    serial: str
    display_name: str
    schedulable: bool
    reasons: tuple[str, ...] = ()
    score: int = 0
    profile: DeviceTeamProfile | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "serial": self.serial,
            "display_name": self.display_name,
            "schedulable": self.schedulable,
            "reasons": list(self.reasons),
            "score": self.score,
            "profile": self.profile.__dict__ if self.profile is not None else None,
        }


@dataclass(frozen=True)
class DeviceSchedulingPlan:
    """Candidate pool returned by the device service for team-level dispatch."""

    requested_count: int
    selected_device_ids: tuple[str, ...] = ()
    candidates: tuple[DeviceSchedulingCandidate, ...] = ()
    rejected_candidates: tuple[DeviceSchedulingCandidate, ...] = ()

    @property
    def has_capacity(self) -> bool:
        return len(self.selected_device_ids) >= self.requested_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_count": self.requested_count,
            "selected_device_ids": list(self.selected_device_ids),
            "has_capacity": self.has_capacity,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "rejected_candidates": [candidate.to_dict() for candidate in self.rejected_candidates],
        }


class DeviceRecordNotFound(LookupError):
    """Raised when a requested device does not exist in the registry."""
