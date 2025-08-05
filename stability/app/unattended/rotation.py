from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from stability.domain import Device, DeviceAvailabilityState, DeviceConnectionState

from .models import TaskDefinitionLike, _UnattendedConfig


class UnattendedRotationMixin:
    def _select_devices(self, task: TaskDefinitionLike, config: _UnattendedConfig, *, occurred_at: datetime) -> dict[str, Any]:
        devices = {device.device_id: device for device in self._device_service.list_devices()}
        preferred_device_ids = self._ordered_primary_device_ids(
            config.primary_device_ids or task.selected_device_ids,
            config.rotation_cursor,
            config.rotation_strategy,
        )
        desired_device_count = max(1, config.desired_device_count or len(preferred_device_ids) or 1)
        assigned_device_ids: list[str] = []
        unavailable_device_ids: list[str] = []
        replacement_events: list[dict[str, Any]] = []

        for device_id in preferred_device_ids:
            if len(assigned_device_ids) >= desired_device_count:
                break
            device = devices.get(device_id)
            if device is not None and self._is_schedulable_device(device):
                assigned_device_ids.append(device_id)
            else:
                unavailable_device_ids.append(device_id)

        backup_pool = list(config.backup_device_ids)
        backup_pool.extend(
            device_id
            for device_id, device in devices.items()
            if device_id not in backup_pool and device_id not in preferred_device_ids and self._is_schedulable_device(device)
        )
        shortage = max(0, desired_device_count - len(assigned_device_ids))
        unavailable_queue = list(unavailable_device_ids)
        for device_id in backup_pool:
            if shortage <= 0:
                break
            if device_id in assigned_device_ids:
                continue
            device = devices.get(device_id)
            if device is None or not self._is_schedulable_device(device):
                continue
            assigned_device_ids.append(device_id)
            shortage -= 1
            replaced_device_id = unavailable_queue.pop(0) if unavailable_queue else ""
            replacement_events.append(
                {
                    "replaced_device_id": replaced_device_id,
                    "replacement_device_id": device_id,
                    "occurred_at": occurred_at.isoformat(),
                    "reason": "preferred_device_unavailable" if replaced_device_id else "pool_backfill",
                }
            )

        return {
            "preferred_device_ids": preferred_device_ids,
            "assigned_device_ids": assigned_device_ids,
            "unavailable_device_ids": unavailable_device_ids,
            "replacement_events": replacement_events,
            "rotation": {
                "strategy": config.rotation_strategy,
                "advance_policy": config.rotation_advance_policy,
                "cursor_before": config.rotation_cursor,
                "window_device_ids": list(preferred_device_ids[:desired_device_count]),
                "step": self._rotation_step(preferred_device_ids, desired_device_count),
            },
        }

    def _advance_rotation_state(self, config: _UnattendedConfig, round_record: dict[str, Any]) -> None:
        primary_device_ids = list(config.primary_device_ids)
        if not primary_device_ids or config.rotation_strategy != "round_robin":
            config.rotation_cursor = 0
            return
        if not self._should_advance_rotation(config, round_record):
            config.rotation_cursor = self._normalize_rotation_cursor(
                config.rotation_cursor,
                primary_device_ids,
                config.rotation_strategy,
            )
            return
        step = self._rotation_step(primary_device_ids, config.desired_device_count)
        config.rotation_cursor = (config.rotation_cursor + step) % len(primary_device_ids)
        config.rotation_advance_count += 1

    def _should_advance_rotation(self, config: _UnattendedConfig, round_record: dict[str, Any]) -> bool:
        policy = self._normalize_rotation_advance_policy(config.rotation_advance_policy)
        if policy == "failure_only":
            return self._round_is_failed(round_record)
        return True

    @staticmethod
    def _ordered_primary_device_ids(
        primary_device_ids: Sequence[str],
        rotation_cursor: int,
        rotation_strategy: str,
    ) -> list[str]:
        ordered = [str(item) for item in primary_device_ids if str(item).strip()]
        if not ordered:
            return []
        if rotation_strategy != "round_robin":
            return ordered
        cursor = rotation_cursor % len(ordered)
        return ordered[cursor:] + ordered[:cursor]

    @staticmethod
    def _rotation_step(primary_device_ids: Sequence[str], desired_device_count: int) -> int:
        if not primary_device_ids:
            return 0
        return max(1, min(len(primary_device_ids), int(desired_device_count or 1)))

    @classmethod
    def _normalize_rotation_cursor(
        cls,
        rotation_cursor: int,
        primary_device_ids: Sequence[str],
        rotation_strategy: str,
    ) -> int:
        if rotation_strategy != "round_robin" or not primary_device_ids:
            return 0
        return max(0, int(rotation_cursor or 0)) % len(primary_device_ids)

    @staticmethod
    def _normalize_rotation_strategy(value: Any) -> str:
        normalized = str(value or "round_robin").strip().lower()
        if normalized not in {"fixed", "round_robin"}:
            return "round_robin"
        return normalized

    @staticmethod
    def _normalize_rotation_advance_policy(value: Any) -> str:
        normalized = str(value or "every_round").strip().lower()
        if normalized not in {"every_round", "failure_only"}:
            return "every_round"
        return normalized

    @staticmethod
    def _is_schedulable_device(device: Device) -> bool:
        return (
            device.connection_state == DeviceConnectionState.ONLINE
            and device.availability_state == DeviceAvailabilityState.IDLE
        )
