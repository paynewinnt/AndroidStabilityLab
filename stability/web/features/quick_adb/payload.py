from __future__ import annotations

from typing import Any, Mapping

from stability.time_utils import now_beijing_string

from .catalog import QUICK_ADB_COMMANDS, QUICK_ADB_LAYERS


class QuickAdbPayloadMixin:
    def _quick_adb_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        layer_filter = self._str_query(query, "layer")
        commands = [command for command in QUICK_ADB_COMMANDS if not layer_filter or command.layer == layer_filter]
        device_choices = self._quick_adb_device_choices(query, request_context=request_context)
        return {
            "page": "quick_adb",
            "title": "快捷 ADB",
            "generated_at": now_beijing_string(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "filters": {"layer": layer_filter},
            "layers": list(QUICK_ADB_LAYERS),
            "device_choices": device_choices,
            "commands": [
                {
                    "command_id": command.command_id,
                    "title": command.title,
                    "description": command.description,
                    "layer": command.layer,
                    "group": command.group,
                    "args": list(command.args),
                    "params": list(command.params),
                    "timeout_seconds": command.timeout_seconds,
                    "risk": command.risk,
                }
                for command in commands
            ],
            "summary": {
                "layer_count": len(QUICK_ADB_LAYERS),
                "command_count": len(commands),
                "total_command_count": len(QUICK_ADB_COMMANDS),
                "available_device_count": len(device_choices),
            },
        }

    def _quick_adb_device_choices(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            device_payload = self._device_pools_payload(query, request_context=request_context)
        except Exception:
            return []
        choices: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pool in list(device_payload.get("pools", []) or []):
            pool_map = dict(pool or {})
            group_name = str(pool_map.get("group_name", "") or "ungrouped")
            team = str(pool_map.get("team", "") or "unassigned")
            for device in list(pool_map.get("schedulable_devices", []) or []):
                item = dict(device or {})
                device_id = str(item.get("device_id") or item.get("serial") or "").strip()
                if not device_id or device_id in seen:
                    continue
                seen.add(device_id)
                tags = [str(tag) for tag in list(item.get("tags", []) or []) if str(tag).strip()]
                display_name = str(item.get("display_name", "") or item.get("serial", "") or device_id)
                choices.append(
                    {
                        "device_id": device_id,
                        "label": display_name,
                        "group_name": group_name,
                        "team": team,
                        "tags": tags,
                    }
                )
        return sorted(choices, key=lambda item: (str(item.get("group_name", "")), str(item.get("team", "")), str(item.get("label", ""))))
