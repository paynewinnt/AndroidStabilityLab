from __future__ import annotations

from stability.application import DevicePoolQuery, list_device_pools as list_device_pools_use_case
from stability.time_utils import now_beijing_string

from ...application_common import *


def _generated_at_now() -> str:
    return now_beijing_string()


class DevicesPayloadMixin:
    def _device_pools_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        device_sync = self._maybe_sync_devices(query)
        device_service = getattr(self._bundle, "device_service", None)
        group_filter = self._str_query(query, "group")
        team_filter = self._str_query(query, "team")
        tag_filters = self._query_values(query, "tag")
        payload = list_device_pools_use_case(
            device_service,
            DevicePoolQuery(group=group_filter, team=team_filter, tags=tag_filters),
        )
        payload.update(
            {
                "page": "device_pools",
                "title": "设备池",
                "generated_at": _generated_at_now(),
                "current_actor": dict(request_context or {}).get("current_actor", {}),
                "device_sync": device_sync,
                "device_marking": {
                    "supported": hasattr(device_service, "update_device_profile"),
                    "action_path": "/device-pools/actions/update-profile",
                    "api_action_path": "/api/device-pools/actions/update-profile",
                    "fields": {
                        "group_name": "Device.group_name",
                        "team_name": "Device.metadata.team",
                        "tags": "Device.tags",
                    },
                },
                "device_actions": {
                    "refresh_supported": hasattr(device_service, "sync_devices"),
                    "connect_supported": hasattr(device_service, "connect_device"),
                    "refresh_path": "/device-pools/actions/refresh",
                    "connect_path": "/device-pools/actions/connect",
                    "pair_connect_path": "/device-pools/actions/pair-connect",
                    "api_refresh_path": "/api/device-pools/actions/refresh",
                    "api_connect_path": "/api/device-pools/actions/connect",
                    "api_pair_connect_path": "/api/device-pools/actions/pair-connect",
                },
            }
        )
        return payload

    def _aggregate_device_pools(
        self,
        devices: list[dict[str, Any]],
        *,
        group: str = "",
        team: str = "",
        tags: Sequence[str] = (),
    ) -> dict[str, Any]:
        group_filter = str(group or "").strip()
        team_filter = str(team or "").strip()
        tag_filters = tuple(str(item).strip() for item in tags if str(item).strip())
        scoped_devices = [dict(item) for item in devices]
        if group_filter:
            scoped_devices = [item for item in scoped_devices if str(item.get("group_name", "") or "ungrouped") == group_filter]
        if team_filter:
            scoped_devices = [item for item in scoped_devices if self._device_team(item) == team_filter]
        if tag_filters:
            required_tags = set(tag_filters)
            scoped_devices = [item for item in scoped_devices if required_tags.issubset(set(self._device_tags(item)))]

        pools_by_key: dict[str, dict[str, Any]] = {}
        group_counts: dict[str, int] = {}
        team_counts: dict[str, int] = {}
        tag_counts: dict[str, int] = {}
        reason_counts: dict[str, int] = {}
        for device in scoped_devices:
            group_name = str(device.get("group_name", "") or "ungrouped")
            owning_team = self._device_team(device)
            pool_key = f"group:{group_name}|team:{owning_team}"
            pool = pools_by_key.setdefault(
                pool_key,
                {
                    "pool_key": pool_key,
                    "group_name": group_name,
                    "team": owning_team,
                    "device_count": 0,
                    "online_device_count": 0,
                    "schedulable_device_count": 0,
                    "unschedulable_device_count": 0,
                    "schedulable_devices": [],
                    "unschedulable_devices": [],
                    "tags": [],
                    "tag_counts": {},
                    "unschedulable_reason_counts": {},
                },
            )
            device_tags = self._device_tags(device)
            reasons = self._unschedulable_reasons(device)
            pool["device_count"] = int(pool["device_count"]) + 1
            if bool(device.get("is_online", False)):
                pool["online_device_count"] = int(pool["online_device_count"]) + 1
            if reasons:
                pool["unschedulable_device_count"] = int(pool["unschedulable_device_count"]) + 1
                pool["unschedulable_devices"].append({**device, "unschedulable_reasons": reasons})
                for reason in reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    pool["unschedulable_reason_counts"][reason] = pool["unschedulable_reason_counts"].get(reason, 0) + 1
            else:
                pool["schedulable_device_count"] = int(pool["schedulable_device_count"]) + 1
                pool["schedulable_devices"].append(device)
            group_counts[group_name] = group_counts.get(group_name, 0) + 1
            team_counts[owning_team] = team_counts.get(owning_team, 0) + 1
            for tag in device_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                pool["tag_counts"][tag] = pool["tag_counts"].get(tag, 0) + 1
                pool["tags"] = sorted(pool["tag_counts"])

        pools = sorted(pools_by_key.values(), key=lambda item: (str(item.get("group_name", "")), str(item.get("team", ""))))
        return {
            "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
            "summary": {
                "pool_count": len(pools),
                "device_count": len(scoped_devices),
                "online_device_count": sum(1 for item in scoped_devices if bool(item.get("is_online", False))),
                "schedulable_device_count": sum(1 for item in scoped_devices if not self._unschedulable_reasons(item)),
                "unschedulable_device_count": sum(1 for item in scoped_devices if self._unschedulable_reasons(item)),
                "group_counts": dict(sorted(group_counts.items())),
                "team_counts": dict(sorted(team_counts.items())),
                "tag_counts": dict(sorted(tag_counts.items())),
                "unschedulable_reason_counts": dict(sorted(reason_counts.items())),
            },
            "pools": pools,
        }

    def _formal_device_pools_payload(
        self,
        device_service: object,
        *,
        group: str = "",
        team: str = "",
        tags: Sequence[str] = (),
    ) -> dict[str, Any]:
        summaries = {
            dimension: [
                self._object_payload(item)
                for item in device_service.summarize_device_pools(group_by=dimension)  # type: ignore[attr-defined]
            ]
            for dimension in ("group", "team", "tag")
        }
        plan = self._object_payload(
            device_service.suggest_device_candidates(  # type: ignore[attr-defined]
                group_name=str(group or "").strip(),
                team_name=str(team or "").strip(),
                tags=tuple(str(item).strip() for item in tags if str(item).strip()),
                requested_count=0,
            )
        )
        candidates = [
            self._candidate_device_payload(item, schedulable=True)
            for item in list(plan.get("candidates", []) or [])
        ]
        rejected = [
            self._candidate_device_payload(item, schedulable=False)
            for item in list(plan.get("rejected_candidates", []) or [])
        ]
        return self._device_pools_payload_from_candidates(
            candidates=candidates,
            rejected=rejected,
            summaries=summaries,
            group=group,
            team=team,
            tags=tags,
        )

    def _device_pools_payload_from_candidates(
        self,
        *,
        candidates: Sequence[Mapping[str, Any]],
        rejected: Sequence[Mapping[str, Any]],
        summaries: Mapping[str, Sequence[Mapping[str, Any]]],
        group: str = "",
        team: str = "",
        tags: Sequence[str] = (),
    ) -> dict[str, Any]:
        group_filter = str(group or "").strip()
        team_filter = str(team or "").strip()
        tag_filters = tuple(str(item).strip() for item in tags if str(item).strip())
        devices = [dict(item) for item in candidates] + [dict(item) for item in rejected]
        pools_by_key: dict[str, dict[str, Any]] = {}
        reason_counts: dict[str, int] = {}
        for device in devices:
            group_name = str(device.get("group_name", "") or "ungrouped")
            owning_team = self._device_team(device)
            pool_key = f"group:{group_name}|team:{owning_team}"
            pool = pools_by_key.setdefault(
                pool_key,
                {
                    "pool_key": pool_key,
                    "group_name": group_name,
                    "team": owning_team,
                    "device_count": 0,
                    "online_device_count": 0,
                    "schedulable_device_count": 0,
                    "unschedulable_device_count": 0,
                    "schedulable_devices": [],
                    "unschedulable_devices": [],
                    "tags": [],
                    "tag_counts": {},
                    "unschedulable_reason_counts": {},
                },
            )
            pool["device_count"] = int(pool["device_count"]) + 1
            if bool(device.get("is_online", False)):
                pool["online_device_count"] = int(pool["online_device_count"]) + 1
            if bool(device.get("is_schedulable", False)):
                pool["schedulable_device_count"] = int(pool["schedulable_device_count"]) + 1
                pool["schedulable_devices"].append(device)
            else:
                reasons = list(device.get("unschedulable_reasons", []) or ["not_schedulable"])
                pool["unschedulable_device_count"] = int(pool["unschedulable_device_count"]) + 1
                pool["unschedulable_devices"].append({**device, "unschedulable_reasons": reasons})
                for reason in reasons:
                    reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
                    pool["unschedulable_reason_counts"][str(reason)] = pool["unschedulable_reason_counts"].get(str(reason), 0) + 1
            for tag in self._device_tags(device):
                pool["tag_counts"][tag] = pool["tag_counts"].get(tag, 0) + 1
                pool["tags"] = sorted(pool["tag_counts"])

        pools = sorted(pools_by_key.values(), key=lambda item: (str(item.get("group_name", "")), str(item.get("team", ""))))
        return {
            "filters": {"group": group_filter, "team": team_filter, "tags": list(tag_filters)},
            "service_summary": {
                "groups": list(summaries.get("group", []) or []),
                "teams": list(summaries.get("team", []) or []),
                "tags": list(summaries.get("tag", []) or []),
            },
            "summary": {
                "pool_count": len(pools),
                "device_count": len(devices),
                "online_device_count": sum(int(item.get("online_count", 0) or 0) for item in summaries.get("group", []) or []) if not any([group_filter, team_filter, tag_filters]) else sum(1 for item in devices if bool(item.get("is_online", False))),
                "schedulable_device_count": len(candidates),
                "unschedulable_device_count": len(rejected),
                "group_counts": self._summary_counts(summaries.get("group", []) or []),
                "team_counts": self._summary_counts(summaries.get("team", []) or []),
                "tag_counts": self._summary_counts(summaries.get("tag", []) or []),
                "unschedulable_reason_counts": dict(sorted(reason_counts.items())),
            },
            "pools": pools,
        }

__all__ = ["DevicesPayloadMixin"]
