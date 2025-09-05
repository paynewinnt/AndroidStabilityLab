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
        filters = self._quick_adb_filters(query)
        layer_filter = str(filters.get("layer", "") or "")
        commands = [
            command
            for command in QUICK_ADB_COMMANDS
            if self._quick_adb_command_matches_filters(command, filters)
        ]
        total_count_for_layer = sum(1 for command in QUICK_ADB_COMMANDS if not layer_filter or command.layer == layer_filter)
        paged_commands = self._page_slice(
            [self._quick_adb_command_payload(command) for command in commands],
            page=int(filters["page"]),
            page_size=int(filters["page_size"]),
        )
        device_choices = self._quick_adb_device_choices(query, request_context=request_context)
        return {
            "page": "quick_adb",
            "title": "快捷 ADB",
            "generated_at": now_beijing_string(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "filters": filters,
            "pagination": {
                "page": int(filters["page"]),
                "page_size": int(filters["page_size"]),
                "total": len(commands),
            },
            "layers": list(QUICK_ADB_LAYERS),
            "group_options": sorted({command.group for command in QUICK_ADB_COMMANDS}),
            "risk_options": sorted({command.risk for command in QUICK_ADB_COMMANDS}),
            "param_options": sorted({param for command in QUICK_ADB_COMMANDS for param in command.params}),
            "device_choices": device_choices,
            "commands": paged_commands,
            "summary": {
                "layer_count": len(QUICK_ADB_LAYERS),
                "command_count": len(commands),
                "layer_command_count": total_count_for_layer,
                "total_command_count": len(QUICK_ADB_COMMANDS),
                "available_device_count": len(device_choices),
            },
        }

    def _quick_adb_filters(self, query: dict[str, list[str]]) -> dict[str, Any]:
        return {
            "layer": self._str_query(query, "layer"),
            "keyword": self._str_query(query, "keyword"),
            "group": self._str_query(query, "group"),
            "risk": self._str_query(query, "risk"),
            "param": self._str_query(query, "param"),
            "page": max(self._int_query(query, "page", default=1), 1),
            "page_size": min(max(self._int_query(query, "page_size", default=20), 1), 100),
        }

    @staticmethod
    def _quick_adb_command_payload(command: Any) -> dict[str, Any]:
        return {
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

    @staticmethod
    def _quick_adb_command_matches_filters(command: Any, filters: Mapping[str, Any]) -> bool:
        layer = str(filters.get("layer", "") or "")
        if layer and command.layer != layer:
            return False
        keyword = str(filters.get("keyword", "") or "").lower()
        if keyword:
            haystack = " ".join(
                str(value or "")
                for value in (
                    command.command_id,
                    command.title,
                    command.description,
                    command.layer,
                    command.group,
                    command.risk,
                    " ".join(command.args),
                    " ".join(command.params),
                )
            ).lower()
            if keyword not in haystack:
                return False
        group = str(filters.get("group", "") or "")
        if group and command.group != group:
            return False
        risk = str(filters.get("risk", "") or "")
        if risk and command.risk != risk:
            return False
        param = str(filters.get("param", "") or "")
        if param and param not in set(command.params):
            return False
        return True

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
