from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from stability.domain import Device, DeviceAvailabilityState, DeviceConnectionState
from stability.domain.value_objects import utcnow
from stability.infrastructure.device_adapter import DeviceDiscoveryAdapter

from .device_service_helpers import health_metadata, isoformat_or_none, normalize_strings, parse_datetime
from .device_service_mapping import (
    build_device,
    find_device_by_serial,
    mark_missing_device_offline,
    merge_descriptor,
)
from .device_service_models import (
    DeviceConnectionAttemptResult,
    DevicePoolSummary,
    DeviceQuarantineProbeResult,
    DeviceRecordNotFound,
    DeviceRepository,
    DeviceSchedulingCandidate,
    DeviceSchedulingPlan,
    DeviceSyncResult,
    DeviceTeamProfile,
)
from .device_service_pool import (
    build_pool_summary,
    describe_device_profile,
    evaluate_scheduling_candidate,
    normalize_pool_dimension,
    pool_keys,
)


class DeviceService:
    """Application service for V1 device discovery and registry synchronization."""

    def __init__(
        self,
        repository: DeviceRepository,
        discovery_adapter: DeviceDiscoveryAdapter,
    ) -> None:
        self._repository = repository
        self._discovery_adapter = discovery_adapter

    def sync_devices(
        self,
        include_unavailable: bool = True,
        mark_missing_offline: bool = True,
    ) -> DeviceSyncResult:
        existing_devices = list(self._repository.list())
        existing_by_id = {device.device_id: device for device in existing_devices}
        existing_by_serial = {device.serial: device for device in existing_devices if device.serial}

        descriptors = self._discovery_adapter.list_devices(include_unavailable=include_unavailable)
        seen_ids = {descriptor.device_id for descriptor in descriptors}
        seen_serials = {descriptor.serial for descriptor in descriptors}

        created: List[Device] = []
        updated: List[Device] = []
        refreshed: List[Device] = []
        marked_offline: List[Device] = []

        for descriptor in descriptors:
            existing = existing_by_id.get(descriptor.device_id) or existing_by_serial.get(descriptor.serial)
            if existing is None:
                device = build_device(descriptor)
                created.append(self._repository.add(device))
                continue

            changed = merge_descriptor(existing, descriptor)
            persisted = self._repository.save(existing)
            if changed:
                updated.append(persisted)
            else:
                refreshed.append(persisted)

        if mark_missing_offline:
            for device in existing_devices:
                if device.device_id in seen_ids or device.serial in seen_serials:
                    continue
                if mark_missing_device_offline(device):
                    marked_offline.append(self._repository.save(device))

        return DeviceSyncResult(
            scanned_count=len(descriptors),
            created=tuple(created),
            updated=tuple(updated),
            refreshed=tuple(refreshed),
            marked_offline=tuple(marked_offline),
        )

    def sync_device(self, serial: str) -> Optional[Device]:
        descriptor = self._discovery_adapter.get_device(serial)
        if descriptor is None:
            return None

        existing = self._repository.get(descriptor.device_id)
        if existing is None:
            existing = find_device_by_serial(self._repository.list(), serial)

        if existing is None:
            return self._repository.add(build_device(descriptor))

        merge_descriptor(existing, descriptor)
        return self._repository.save(existing)

    def connect_device(self, serial: str) -> DeviceConnectionAttemptResult:
        target = str(serial or "").strip()
        if not target:
            raise ValueError("device serial is required.")
        raw_result: Dict[str, Any] = {}
        if hasattr(self._discovery_adapter, "connect_device"):
            raw_result = dict(self._discovery_adapter.connect_device(target) or {})
        device = self.sync_device(target)
        connected = bool(raw_result.get("success", False))
        if device is not None and device.connection_state == DeviceConnectionState.ONLINE:
            connected = True
        return DeviceConnectionAttemptResult(
            serial=target,
            attempted=bool(raw_result.get("attempted", False)),
            connected=connected,
            message=str(raw_result.get("message", "") or ""),
            device=device,
        )

    def pair_and_connect_device(
        self,
        *,
        pair_serial: str,
        pairing_code: str,
        connect_serial: str,
    ) -> DeviceConnectionAttemptResult:
        pair_target = str(pair_serial or "").strip()
        code = str(pairing_code or "").strip()
        connect_target = str(connect_serial or "").strip()
        if not pair_target or not code or not connect_target:
            raise ValueError("pair_serial, pairing_code and connect_serial are required.")
        pair_result: Dict[str, Any] = {}
        if hasattr(self._discovery_adapter, "pair_device"):
            pair_result = dict(self._discovery_adapter.pair_device(pair_target, code) or {})
        connect_result = self.connect_device(connect_target)
        return DeviceConnectionAttemptResult(
            serial=connect_result.serial,
            attempted=connect_result.attempted,
            connected=connect_result.connected,
            message=connect_result.message,
            device=connect_result.device,
            paired=bool(pair_result.get("success", False)),
            pair_serial=pair_target,
            pair_message=str(pair_result.get("message", "") or ""),
        )

    def list_devices(self) -> List[Device]:
        return sorted(
            self._repository.list(),
            key=lambda device: (
                device.device_id or "",
                device.serial or "",
            ),
        )

    def get_device(self, device_id: str) -> Optional[Device]:
        return self._repository.get(device_id)

    def require_device(self, device_id: str) -> Device:
        device = self.get_device(device_id)
        if device is None:
            raise DeviceRecordNotFound(f"Device '{device_id}' was not found.")
        return device

    def describe_device(self, device: Device, *, include_metadata: bool = True) -> Dict[str, Any]:
        profile = self.describe_device_profile(device)
        payload = {
            "device_id": device.device_id,
            "serial": device.serial,
            "display_name": device.display_name,
            "brand": device.brand,
            "model": device.model,
            "android_version": device.android_version,
            "rom_version": device.rom_version,
            "abi": device.abi,
            "connection_state": device.connection_state.value,
            "availability_state": device.availability_state.value,
            "is_online": device.is_online(),
            "is_schedulable": device.is_schedulable(),
            "group_name": device.group_name,
            "tags": list(device.tags),
            "team_name": profile.team_name,
            "owner": profile.owner,
            "priority": profile.priority,
            "capabilities": list(profile.capabilities),
            "maintenance": profile.maintenance,
            "maintenance_reason": profile.maintenance_reason,
            "reserved_by": profile.reserved_by,
            "quarantine_reason": profile.quarantine_reason,
            "current_instance_id": device.current_instance_id,
            "last_heartbeat_at": isoformat_or_none(device.last_heartbeat_at),
        }
        if include_metadata:
            payload["metadata"] = dict(device.metadata)
        return payload

    def list_device_summaries(self) -> List[Dict[str, Any]]:
        return [self.describe_device(device, include_metadata=False) for device in self.list_devices()]

    def update_device_profile(
        self,
        device_id: str,
        *,
        group_name: str | None = None,
        team_name: str | None = None,
        tags: Sequence[str] | str | None = None,
        actor: str = "system",
        occurred_at: datetime | None = None,
    ) -> Device:
        device = self.require_device(str(device_id or "").strip())
        if group_name is not None:
            device.group_name = str(group_name or "").strip()
        if tags is not None:
            device.tags = normalize_strings(tags)
        if team_name is not None:
            team = str(team_name or "").strip()
            if team:
                device.metadata["team"] = team
                device.metadata["team_name"] = team
            else:
                device.metadata.pop("team", None)
                device.metadata.pop("team_name", None)
        updated_at = occurred_at or utcnow()
        device.metadata["profile_updated_by"] = str(actor or "system").strip() or "system"
        device.metadata["profile_updated_at"] = updated_at.isoformat()
        device.touch_heartbeat(updated_at)
        return self._repository.save(device)

    def list_quarantined_devices(self) -> List[Device]:
        return [device for device in self.list_devices() if device.availability_state == DeviceAvailabilityState.QUARANTINED]

    def describe_device_profile(self, device: Device) -> DeviceTeamProfile:
        return describe_device_profile(device)

    def summarize_device_pools(self, *, group_by: str = "group") -> List[DevicePoolSummary]:
        dimension = normalize_pool_dimension(group_by)
        buckets: Dict[str, List[Device]] = {}
        for device in self.list_devices():
            for key in pool_keys(device, dimension):
                buckets.setdefault(key, []).append(device)
        return [
            build_pool_summary(key, dimension, devices)
            for key, devices in sorted(buckets.items(), key=lambda item: item[0])
        ]

    def list_schedulable_devices(
        self,
        *,
        group_name: str = "",
        team_name: str = "",
        tags: Sequence[str] = (),
        capabilities: Sequence[str] = (),
        owner: str = "",
        min_priority: int | None = None,
    ) -> List[Device]:
        plan = self.suggest_device_candidates(
            group_name=group_name,
            team_name=team_name,
            tags=tags,
            capabilities=capabilities,
            owner=owner,
            min_priority=min_priority,
            requested_count=0,
        )
        devices = {device.device_id: device for device in self.list_devices()}
        return [devices[candidate.device_id] for candidate in plan.candidates if candidate.device_id in devices]

    def suggest_device_candidates(
        self,
        *,
        group_name: str = "",
        team_name: str = "",
        tags: Sequence[str] = (),
        capabilities: Sequence[str] = (),
        owner: str = "",
        min_priority: int | None = None,
        requested_count: int = 1,
        device_ids: Sequence[str] = (),
    ) -> DeviceSchedulingPlan:
        requested_count = max(0, int(requested_count or 0))
        scoped_ids = {str(item).strip() for item in device_ids if str(item).strip()}
        candidates: list[DeviceSchedulingCandidate] = []
        rejected: list[DeviceSchedulingCandidate] = []
        for device in self.list_devices():
            if scoped_ids and device.device_id not in scoped_ids:
                continue
            candidate = evaluate_scheduling_candidate(
                device,
                group_name=group_name,
                team_name=team_name,
                tags=tags,
                capabilities=capabilities,
                owner=owner,
                min_priority=min_priority,
            )
            if candidate.schedulable:
                candidates.append(candidate)
            else:
                rejected.append(candidate)

        candidates.sort(key=lambda item: (-item.score, item.device_id))
        rejected.sort(key=lambda item: (item.device_id, item.reasons))
        selected = tuple(candidate.device_id for candidate in candidates[:requested_count] if requested_count > 0)
        return DeviceSchedulingPlan(
            requested_count=requested_count,
            selected_device_ids=selected,
            candidates=tuple(candidates),
            rejected_candidates=tuple(rejected),
        )

    def probe_quarantined_devices(
        self,
        *,
        device_ids: Sequence[str] = (),
        actor: str = "system",
        probe_interval_minutes: int = 15,
        occurred_at: datetime | None = None,
    ) -> List[DeviceQuarantineProbeResult]:
        occurred_at = occurred_at or utcnow()
        scoped_ids = {str(item).strip() for item in device_ids if str(item).strip()}
        results: List[DeviceQuarantineProbeResult] = []
        for device in self.list_quarantined_devices():
            if scoped_ids and device.device_id not in scoped_ids:
                continue
            results.append(
                self._probe_quarantined_device(
                    device.device_id,
                    actor=actor,
                    probe_interval_minutes=probe_interval_minutes,
                    occurred_at=occurred_at,
                )
            )
        return results

    def record_device_failure(
        self,
        device_id: str,
        *,
        reason: str,
        actor: str = "system",
        quarantine_threshold: int | None = None,
        occurred_at: datetime | None = None,
    ) -> Device:
        device = self.require_device(device_id)
        occurred_at = occurred_at or utcnow()
        health = health_metadata(device)
        failure_streak = int(health.get("failure_streak", 0) or 0) + 1
        health.update(
            {
                "failure_streak": failure_streak,
                "last_failure_at": occurred_at.isoformat(),
                "last_failure_reason": reason,
                "last_updated_by": actor,
            }
        )
        if quarantine_threshold is not None and quarantine_threshold > 0 and failure_streak >= quarantine_threshold:
            health["quarantine_count"] = int(health.get("quarantine_count", 0) or 0) + 1
            health["quarantined_at"] = occurred_at.isoformat()
            health["quarantine_reason"] = reason
            health["quarantined_by"] = actor
            device.mark_quarantined(reason=reason, quarantined_at=occurred_at)
        else:
            device.touch_heartbeat(occurred_at)
        return self._repository.save(device)

    def record_device_success(
        self,
        device_id: str,
        *,
        actor: str = "system",
        occurred_at: datetime | None = None,
    ) -> Device:
        device = self.require_device(device_id)
        occurred_at = occurred_at or utcnow()
        health = health_metadata(device)
        health.update(
            {
                "failure_streak": 0,
                "last_success_at": occurred_at.isoformat(),
                "last_updated_by": actor,
            }
        )
        if device.availability_state not in {
            DeviceAvailabilityState.RESERVED,
            DeviceAvailabilityState.RUNNING,
            DeviceAvailabilityState.QUARANTINED,
        }:
            device.availability_state = (
                DeviceAvailabilityState.IDLE
                if device.connection_state == DeviceConnectionState.ONLINE
                else DeviceAvailabilityState.ERROR
            )
        device.touch_heartbeat(occurred_at)
        return self._repository.save(device)

    def clear_device_quarantine(
        self,
        device_id: str,
        *,
        actor: str = "system",
        note: str = "",
        occurred_at: datetime | None = None,
    ) -> Device:
        device = self.require_device(device_id)
        occurred_at = occurred_at or utcnow()
        health = health_metadata(device)
        health.update(
            {
                "failure_streak": 0,
                "last_recovered_at": occurred_at.isoformat(),
                "last_updated_by": actor,
            }
        )
        if note:
            health["recovery_note"] = note
        health.pop("quarantined_at", None)
        health.pop("quarantine_reason", None)
        health.pop("quarantined_by", None)
        device.clear_quarantine(released_at=occurred_at)
        return self._repository.save(device)

    def _probe_quarantined_device(
        self,
        device_id: str,
        *,
        actor: str,
        probe_interval_minutes: int,
        occurred_at: datetime,
    ) -> DeviceQuarantineProbeResult:
        device = self.require_device(device_id)
        health = health_metadata(device)
        interval_minutes = max(1, int(probe_interval_minutes or 15))
        next_probe_at: datetime | None = None

        if device.availability_state != DeviceAvailabilityState.QUARANTINED:
            return DeviceQuarantineProbeResult(
                device_id=device.device_id,
                serial=device.serial,
                attempted=False,
                recovered=False,
                skipped=True,
                reason="not_quarantined",
                probed_at=occurred_at,
            )

        last_probe_at = parse_datetime(health.get("last_probe_at"))
        if last_probe_at is not None:
            next_probe_at = last_probe_at + timedelta(minutes=interval_minutes)
            if next_probe_at > occurred_at:
                health["next_probe_at"] = next_probe_at.isoformat()
                self._repository.save(device)
                return DeviceQuarantineProbeResult(
                    device_id=device.device_id,
                    serial=device.serial,
                    attempted=False,
                    recovered=False,
                    skipped=True,
                    reason="probe_cooldown",
                    probed_at=occurred_at,
                    next_probe_at=next_probe_at,
                )

        health["last_probe_at"] = occurred_at.isoformat()
        health["last_probe_actor"] = actor
        health["probe_attempt_count"] = int(health.get("probe_attempt_count", 0) or 0) + 1
        next_probe_at = occurred_at + timedelta(minutes=interval_minutes)
        health["next_probe_at"] = next_probe_at.isoformat()

        refreshed = self.sync_device(device.serial or device.device_id)
        if refreshed is None:
            health["last_probe_result"] = "device_not_found"
            self._repository.save(device)
            return DeviceQuarantineProbeResult(
                device_id=device.device_id,
                serial=device.serial,
                attempted=True,
                recovered=False,
                skipped=False,
                reason="device_not_found",
                probed_at=occurred_at,
                next_probe_at=next_probe_at,
            )

        device = refreshed
        health = health_metadata(device)
        health["last_probe_at"] = occurred_at.isoformat()
        health["last_probe_actor"] = actor
        health["next_probe_at"] = next_probe_at.isoformat()

        if device.connection_state == DeviceConnectionState.ONLINE:
            health["probe_recovery_count"] = int(health.get("probe_recovery_count", 0) or 0) + 1
            health["last_probe_result"] = "recovered"
            device = self.clear_device_quarantine(
                device.device_id,
                actor=actor,
                note="automatic_probe_recovered",
                occurred_at=occurred_at,
            )
            health = health_metadata(device)
            health["last_probe_at"] = occurred_at.isoformat()
            health["last_probe_actor"] = actor
            health["last_probe_result"] = "recovered"
            health["next_probe_at"] = next_probe_at.isoformat()
            self._repository.save(device)
            return DeviceQuarantineProbeResult(
                device_id=device.device_id,
                serial=device.serial,
                attempted=True,
                recovered=True,
                skipped=False,
                reason="recovered",
                probed_at=occurred_at,
                next_probe_at=next_probe_at,
            )

        health["last_probe_result"] = f"still_{device.connection_state.value}"
        self._repository.save(device)
        return DeviceQuarantineProbeResult(
            device_id=device.device_id,
            serial=device.serial,
            attempted=True,
            recovered=False,
            skipped=False,
            reason=f"still_{device.connection_state.value}",
            probed_at=occurred_at,
            next_probe_at=next_probe_at,
        )
