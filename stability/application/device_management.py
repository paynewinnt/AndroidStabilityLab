from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class DevicePoolQuery:
    group: str = ""
    team: str = ""
    tags: Sequence[str] = ()


@dataclass(frozen=True)
class UpdateDeviceProfileCommand:
    device_id: str
    group_name: str = ""
    team_name: str = ""
    tags: Sequence[str] = ()
    actor: str = "system"


@dataclass(frozen=True)
class RefreshDevicesCommand:
    device_id: str = ""


@dataclass(frozen=True)
class ConnectDeviceCommand:
    device_id: str


@dataclass(frozen=True)
class PairConnectDeviceCommand:
    pair_device_id: str
    pairing_code: str
    connect_device_id: str


def list_device_pools(device_service: object | None, query: DevicePoolQuery | None = None) -> dict[str, Any]:
    """Build the shared device-pool view used by CLI and Web."""
    query = query or DevicePoolQuery()
    if device_service is None:
        return _empty_device_pools_payload(query)
    if hasattr(device_service, "summarize_device_pools") and hasattr(device_service, "suggest_device_candidates"):
        return _formal_device_pools_payload(device_service, query=query)
    if hasattr(device_service, "list_device_pools"):
        payload = _call_device_pool_service_method(
            device_service.list_device_pools,  # type: ignore[attr-defined]
            query=query,
        )
        return _normalize_device_pools_payload(payload)
    if hasattr(device_service, "describe_device_pools"):
        payload = _call_device_pool_service_method(
            device_service.describe_device_pools,  # type: ignore[attr-defined]
            query=query,
        )
        return _normalize_device_pools_payload(payload)
    if not hasattr(device_service, "list_device_summaries"):
        return _empty_device_pools_payload(query)
    return _aggregate_device_pools(
        [dict(item) for item in device_service.list_device_summaries()],  # type: ignore[attr-defined]
        query=query,
    )


def update_device_profile(device_service: object | None, command: UpdateDeviceProfileCommand) -> dict[str, Any]:
    if device_service is None or not hasattr(device_service, "update_device_profile"):
        raise ValueError("Device profile marking is unavailable.")
    device = device_service.update_device_profile(  # type: ignore[attr-defined]
        str(command.device_id or "").strip(),
        group_name=command.group_name,
        team_name=command.team_name,
        tags=tuple(command.tags),
        actor=str(command.actor or "system").strip() or "system",
    )
    if hasattr(device_service, "describe_device"):
        device_payload = dict(device_service.describe_device(device))  # type: ignore[attr-defined]
    else:
        device_payload = _object_payload(device)
    return {
        "storage_mode": "persistent",
        "device": device_payload,
        "device_id": str(device_payload.get("device_id", "") or ""),
        "group_name": str(device_payload.get("group_name", "") or ""),
        "team_name": str(device_payload.get("team_name", device_payload.get("team", "")) or ""),
        "tags": list(device_payload.get("tags", []) or []),
        "updated_by": str(command.actor or "system").strip() or "system",
    }


def refresh_devices(device_service: object | None, command: RefreshDevicesCommand | None = None) -> dict[str, Any]:
    if device_service is None:
        raise ValueError("Device registry refresh is unavailable.")
    command = command or RefreshDevicesCommand()
    target = str(command.device_id or "").strip()
    if target and hasattr(device_service, "sync_device"):
        device = device_service.sync_device(target)  # type: ignore[attr-defined]
        return {
            "storage_mode": "persistent",
            "mode": "target_device",
            "target_device_id": target,
            "found": device is not None,
            "updated_device_id": str(getattr(device, "device_id", "") or ""),
        }
    if not hasattr(device_service, "sync_devices"):
        raise ValueError("Device registry refresh is unavailable.")
    result = device_service.sync_devices(include_unavailable=True, mark_missing_offline=True)  # type: ignore[attr-defined]
    return {
        "storage_mode": "persistent",
        "mode": "full_registry",
        "scanned_count": int(getattr(result, "scanned_count", 0) or 0),
        "created_count": len(getattr(result, "created", ()) or ()),
        "updated_count": len(getattr(result, "updated", ()) or ()),
        "refreshed_count": len(getattr(result, "refreshed", ()) or ()),
        "marked_offline_count": len(getattr(result, "marked_offline", ()) or ()),
    }


def connect_device(device_service: object | None, command: ConnectDeviceCommand) -> dict[str, Any]:
    if device_service is None or not hasattr(device_service, "connect_device"):
        raise ValueError("Device TCP connect is unavailable.")
    result = device_service.connect_device(str(command.device_id or "").strip())  # type: ignore[attr-defined]
    return {"storage_mode": "persistent", **_result_payload(result)}


def pair_connect_device(device_service: object | None, command: PairConnectDeviceCommand) -> dict[str, Any]:
    if device_service is None or not hasattr(device_service, "pair_and_connect_device"):
        raise ValueError("Device wireless pairing is unavailable.")
    result = device_service.pair_and_connect_device(  # type: ignore[attr-defined]
        pair_serial=str(command.pair_device_id or "").strip(),
        pairing_code=str(command.pairing_code or "").strip(),
        connect_serial=str(command.connect_device_id or "").strip(),
    )
    return {"storage_mode": "persistent", **_result_payload(result)}


def _formal_device_pools_payload(device_service: object, *, query: DevicePoolQuery) -> dict[str, Any]:
    summaries = {
        dimension: [
            _object_payload(item)
            for item in device_service.summarize_device_pools(group_by=dimension)  # type: ignore[attr-defined]
        ]
        for dimension in ("group", "team", "tag")
    }
    plan = _object_payload(
        device_service.suggest_device_candidates(  # type: ignore[attr-defined]
            group_name=str(query.group or "").strip(),
            team_name=str(query.team or "").strip(),
            tags=tuple(str(item).strip() for item in query.tags if str(item).strip()),
            requested_count=0,
        )
    )
    candidates = [_candidate_device_payload(item, schedulable=True) for item in list(plan.get("candidates", []) or [])]
    rejected = [_candidate_device_payload(item, schedulable=False) for item in list(plan.get("rejected_candidates", []) or [])]
    return _device_pools_payload_from_candidates(
        candidates=candidates,
        rejected=rejected,
        summaries=summaries,
        query=query,
    )


def _aggregate_device_pools(devices: Sequence[Mapping[str, Any]], *, query: DevicePoolQuery) -> dict[str, Any]:
    group_filter, team_filter, tag_filters = _normalized_filters(query)
    scoped_devices = [dict(item) for item in devices]
    if group_filter:
        scoped_devices = [item for item in scoped_devices if str(item.get("group_name", "") or "ungrouped") == group_filter]
    if team_filter:
        scoped_devices = [item for item in scoped_devices if _device_team(item) == team_filter]
    if tag_filters:
        required_tags = set(tag_filters)
        scoped_devices = [item for item in scoped_devices if required_tags.issubset(set(_device_tags(item)))]

    pools_by_key: dict[str, dict[str, Any]] = {}
    group_counts: dict[str, int] = {}
    team_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for device in scoped_devices:
        group_name = str(device.get("group_name", "") or "ungrouped")
        owning_team = _device_team(device)
        pool = pools_by_key.setdefault(
            f"group:{group_name}|team:{owning_team}",
            _empty_pool(group_name=group_name, team=owning_team),
        )
        _append_device_to_pool(pool, device, reason_counts=reason_counts)
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
        team_counts[owning_team] = team_counts.get(owning_team, 0) + 1
        for tag in _device_tags(device):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    pools = _sorted_pools(pools_by_key)
    return {
        "storage_mode": "persistent",
        "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
        "summary": {
            "pool_count": len(pools),
            "device_count": len(scoped_devices),
            "online_device_count": sum(1 for item in scoped_devices if bool(item.get("is_online", False))),
            "schedulable_device_count": sum(1 for item in scoped_devices if not _unschedulable_reasons(item)),
            "unschedulable_device_count": sum(1 for item in scoped_devices if _unschedulable_reasons(item)),
            "group_counts": dict(sorted(group_counts.items())),
            "team_counts": dict(sorted(team_counts.items())),
            "tag_counts": dict(sorted(tag_counts.items())),
            "unschedulable_reason_counts": dict(sorted(reason_counts.items())),
        },
        "pools": pools,
    }


def _device_pools_payload_from_candidates(
    *,
    candidates: Sequence[Mapping[str, Any]],
    rejected: Sequence[Mapping[str, Any]],
    summaries: Mapping[str, Sequence[Mapping[str, Any]]],
    query: DevicePoolQuery,
) -> dict[str, Any]:
    group_filter, team_filter, tag_filters = _normalized_filters(query)
    devices = [dict(item) for item in candidates] + [dict(item) for item in rejected]
    pools_by_key: dict[str, dict[str, Any]] = {}
    reason_counts: dict[str, int] = {}
    for device in devices:
        group_name = str(device.get("group_name", "") or "ungrouped")
        owning_team = _device_team(device)
        pool = pools_by_key.setdefault(
            f"group:{group_name}|team:{owning_team}",
            _empty_pool(group_name=group_name, team=owning_team),
        )
        _append_device_to_pool(pool, device, reason_counts=reason_counts)

    pools = _sorted_pools(pools_by_key)
    return {
        "storage_mode": "persistent",
        "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
        "service_summary": {
            "groups": list(summaries.get("group", []) or []),
            "teams": list(summaries.get("team", []) or []),
            "tags": list(summaries.get("tag", []) or []),
        },
        "summary": {
            "pool_count": len(pools),
            "device_count": len(devices),
            "online_device_count": (
                sum(int(item.get("online_count", 0) or 0) for item in summaries.get("group", []) or [])
                if not any([group_filter, team_filter, tag_filters])
                else sum(1 for item in devices if bool(item.get("is_online", False)))
            ),
            "schedulable_device_count": len(candidates),
            "unschedulable_device_count": len(rejected),
            "group_counts": _summary_counts(summaries.get("group", []) or []),
            "team_counts": _summary_counts(summaries.get("team", []) or []),
            "tag_counts": _summary_counts(summaries.get("tag", []) or []),
            "unschedulable_reason_counts": dict(sorted(reason_counts.items())),
        },
        "pools": pools,
    }


def _append_device_to_pool(pool: dict[str, Any], device: Mapping[str, Any], *, reason_counts: dict[str, int]) -> None:
    pool["device_count"] = int(pool["device_count"]) + 1
    if bool(device.get("is_online", False)):
        pool["online_device_count"] = int(pool["online_device_count"]) + 1
    reasons = _unschedulable_reasons(device)
    if reasons:
        pool["unschedulable_device_count"] = int(pool["unschedulable_device_count"]) + 1
        pool["unschedulable_devices"].append({**dict(device), "unschedulable_reasons": reasons})
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            pool["unschedulable_reason_counts"][reason] = pool["unschedulable_reason_counts"].get(reason, 0) + 1
    else:
        pool["schedulable_device_count"] = int(pool["schedulable_device_count"]) + 1
        pool["schedulable_devices"].append(dict(device))
    for tag in _device_tags(device):
        pool["tag_counts"][tag] = pool["tag_counts"].get(tag, 0) + 1
        pool["tags"] = sorted(pool["tag_counts"])


def _call_device_pool_service_method(method: object, *, query: DevicePoolQuery) -> object:
    try:
        return method(group=query.group, team=query.team, tags=tuple(query.tags))  # type: ignore[misc]
    except TypeError:
        return method()  # type: ignore[misc]


def _normalize_device_pools_payload(payload: object) -> dict[str, Any]:
    result = dict(payload) if isinstance(payload, Mapping) else {"pools": list(payload or [])}
    result.setdefault("storage_mode", "persistent")
    result.setdefault("summary", {})
    result.setdefault("pools", [])
    return result


def _empty_device_pools_payload(query: DevicePoolQuery) -> dict[str, Any]:
    group_filter, team_filter, tag_filters = _normalized_filters(query)
    return {
        "storage_mode": "persistent",
        "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
        "summary": {
            "pool_count": 0,
            "device_count": 0,
            "online_device_count": 0,
            "schedulable_device_count": 0,
            "unschedulable_device_count": 0,
            "group_counts": {},
            "team_counts": {},
            "tag_counts": {},
            "unschedulable_reason_counts": {},
        },
        "pools": [],
    }


def _empty_pool(*, group_name: str, team: str) -> dict[str, Any]:
    pool_key = f"group:{group_name}|team:{team}"
    return {
        "pool_key": pool_key,
        "group_name": group_name,
        "team": team,
        "device_count": 0,
        "online_device_count": 0,
        "schedulable_device_count": 0,
        "unschedulable_device_count": 0,
        "schedulable_devices": [],
        "unschedulable_devices": [],
        "tags": [],
        "tag_counts": {},
        "unschedulable_reason_counts": {},
    }


def _sorted_pools(pools_by_key: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(item) for item in pools_by_key.values()],
        key=lambda item: (str(item.get("group_name", "")), str(item.get("team", ""))),
    )


def _object_payload(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())  # type: ignore[no-any-return, attr-defined]
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _result_payload(value: object) -> dict[str, Any]:
    return _object_payload(value)


def _candidate_device_payload(value: object, *, schedulable: bool) -> dict[str, Any]:
    payload = _object_payload(value)
    profile = _object_payload(payload.get("profile", {}) or {})
    tags = profile.get("tags", ()) or ()
    reasons = list(payload.get("reasons", []) or [])
    return {
        "device_id": str(payload.get("device_id", "") or ""),
        "serial": str(payload.get("serial", "") or ""),
        "display_name": str(payload.get("display_name", "") or ""),
        "group_name": str(profile.get("group_name", "") or "ungrouped"),
        "team": str(profile.get("team_name", "") or "unassigned"),
        "tags": sorted({str(item).strip() for item in tags if str(item).strip()}),
        "is_online": "offline" not in reasons,
        "is_schedulable": bool(payload.get("schedulable", schedulable)),
        "score": int(payload.get("score", 0) or 0),
        "unschedulable_reasons": reasons,
        "profile": profile,
    }


def _summary_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("key", "") or "").strip()
        if key:
            counts[key] = int(item.get("total_count", item.get("device_count", 0)) or 0)
    return dict(sorted(counts.items()))


def _device_team(device: Mapping[str, Any]) -> str:
    metadata = dict(device.get("metadata", {}) or {})
    return str(
        device.get("team")
        or device.get("team_id")
        or device.get("team_name")
        or device.get("owner_team")
        or metadata.get("team")
        or metadata.get("team_id")
        or metadata.get("team_name")
        or metadata.get("owner_team")
        or "unassigned"
    )


def _device_tags(device: Mapping[str, Any]) -> list[str]:
    raw_tags = device.get("tags", ()) or ()
    return sorted({str(item).strip() for item in raw_tags if str(item).strip()})


def _unschedulable_reasons(device: Mapping[str, Any]) -> list[str]:
    if bool(device.get("is_schedulable", False)):
        return []
    explicit = [str(item).strip() for item in (device.get("unschedulable_reasons", ()) or ()) if str(item).strip()]
    if explicit:
        return sorted(set(explicit))
    reasons: list[str] = []
    if not bool(device.get("is_online", False)):
        reasons.append("offline")
    availability = str(device.get("availability_state", "") or "").strip()
    if availability and availability not in {"idle", "available"}:
        reasons.append(f"availability:{availability}")
    connection = str(device.get("connection_state", "") or "").strip()
    if connection and connection not in {"connected", "online"}:
        reasons.append(f"connection:{connection}")
    if str(device.get("current_instance_id", "") or "").strip():
        reasons.append("busy")
    if not reasons:
        reasons.append("not_schedulable")
    return sorted(set(reasons))


def _normalized_filters(query: DevicePoolQuery) -> tuple[str, str, tuple[str, ...]]:
    return (
        str(query.group or "").strip(),
        str(query.team or "").strip(),
        tuple(str(item).strip() for item in query.tags if str(item).strip()),
    )
