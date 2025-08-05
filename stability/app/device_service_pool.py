from __future__ import annotations

from typing import Sequence

from stability.domain import Device, DeviceAvailabilityState, DeviceConnectionState

from .device_service_helpers import normalize_strings
from .device_service_models import DevicePoolSummary, DeviceSchedulingCandidate, DeviceTeamProfile


def describe_device_profile(device: Device) -> DeviceTeamProfile:
    return DeviceTeamProfile(
        device_id=device.device_id,
        group_name=str(device.group_name or "").strip(),
        team_name=device.team_name,
        tags=tuple(normalize_strings(device.tags)),
        capabilities=tuple(device.capabilities),
        owner=device.owner,
        priority=device.priority,
        maintenance=device.is_under_maintenance(),
        maintenance_reason=device.maintenance_reason,
        reserved_by=str(device.metadata.get("reserved_by") or "").strip(),
        quarantine_reason=str(device.metadata.get("quarantine_reason") or "").strip(),
    )


def evaluate_scheduling_candidate(
    device: Device,
    *,
    group_name: str,
    team_name: str,
    tags: Sequence[str],
    capabilities: Sequence[str],
    owner: str,
    min_priority: int | None,
) -> DeviceSchedulingCandidate:
    profile = describe_device_profile(device)
    reasons: list[str] = []
    if device.connection_state != DeviceConnectionState.ONLINE:
        reasons.append("offline")
    if device.availability_state == DeviceAvailabilityState.QUARANTINED:
        reasons.append("quarantined")
    elif device.availability_state == DeviceAvailabilityState.RESERVED:
        reasons.append("reserved")
    elif device.availability_state == DeviceAvailabilityState.RUNNING:
        reasons.append("running")
    elif device.availability_state != DeviceAvailabilityState.IDLE:
        reasons.append(device.availability_state.value)
    if profile.maintenance:
        reasons.append("maintenance")

    expected_group = str(group_name or "").strip()
    expected_team = str(team_name or "").strip()
    expected_owner = str(owner or "").strip()
    if expected_group and profile.group_name != expected_group:
        reasons.append("group_mismatch")
    if expected_team and profile.team_name != expected_team:
        reasons.append("team_mismatch")
    if expected_owner and profile.owner != expected_owner:
        reasons.append("owner_mismatch")

    expected_tags = set(normalize_strings(tags))
    device_tags = set(profile.tags)
    if expected_tags and not expected_tags.issubset(device_tags):
        reasons.append("tag_mismatch")

    expected_capabilities = set(normalize_strings(capabilities))
    device_capabilities = set(profile.capabilities)
    if expected_capabilities and not expected_capabilities.issubset(device_capabilities):
        reasons.append("capability_mismatch")

    if min_priority is not None and profile.priority < int(min_priority):
        reasons.append("priority_below_minimum")

    score = profile.priority
    if not reasons:
        score += 1000
    return DeviceSchedulingCandidate(
        device_id=device.device_id,
        serial=device.serial,
        display_name=device.display_name,
        schedulable=not reasons,
        reasons=tuple(reasons),
        score=score,
        profile=profile,
    )


def build_pool_summary(key: str, dimension: str, devices: Sequence[Device]) -> DevicePoolSummary:
    device_ids: list[str] = []
    schedulable_ids: list[str] = []
    risk_ids: list[str] = []
    online_count = 0
    idle_count = 0
    running_count = 0
    reserved_count = 0
    quarantined_count = 0
    maintenance_count = 0
    for device in devices:
        device_ids.append(device.device_id)
        profile = describe_device_profile(device)
        if device.connection_state == DeviceConnectionState.ONLINE:
            online_count += 1
        if device.availability_state == DeviceAvailabilityState.IDLE:
            idle_count += 1
        elif device.availability_state == DeviceAvailabilityState.RUNNING:
            running_count += 1
        elif device.availability_state == DeviceAvailabilityState.RESERVED:
            reserved_count += 1
        elif device.availability_state == DeviceAvailabilityState.QUARANTINED:
            quarantined_count += 1
        if profile.maintenance:
            maintenance_count += 1
        if device.is_schedulable():
            schedulable_ids.append(device.device_id)
        if is_risk_device(device):
            risk_ids.append(device.device_id)
    return DevicePoolSummary(
        key=key,
        dimension=dimension,
        total_count=len(devices),
        online_count=online_count,
        idle_count=idle_count,
        running_count=running_count,
        reserved_count=reserved_count,
        quarantined_count=quarantined_count,
        maintenance_count=maintenance_count,
        schedulable_count=len(schedulable_ids),
        risk_count=len(risk_ids),
        device_ids=tuple(sorted(device_ids)),
        schedulable_device_ids=tuple(sorted(schedulable_ids)),
        risk_device_ids=tuple(sorted(risk_ids)),
    )


def pool_keys(device: Device, dimension: str) -> tuple[str, ...]:
    profile = describe_device_profile(device)
    if dimension == "team":
        return (profile.team_name or "unteamed",)
    if dimension == "tag":
        return profile.tags or ("untagged",)
    return (profile.group_name or "ungrouped",)


def normalize_pool_dimension(group_by: str) -> str:
    normalized = str(group_by or "group").strip().lower()
    aliases = {"group_name": "group", "team_name": "team", "tags": "tag"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"group", "team", "tag"}:
        raise ValueError("group_by must be one of: group, team, tag")
    return normalized


def is_risk_device(device: Device) -> bool:
    if device.connection_state != DeviceConnectionState.ONLINE:
        return True
    if device.availability_state in {DeviceAvailabilityState.ERROR, DeviceAvailabilityState.QUARANTINED}:
        return True
    if device.is_under_maintenance():
        return True
    health = device.metadata.get("automation_health")
    if isinstance(health, dict) and int(health.get("failure_streak", 0) or 0) > 0:
        return True
    return False
