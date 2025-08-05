from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from stability.domain.value_objects import utcnow

from .models import TaskDefinitionLike, UnattendedTaskRecord, _UnattendedConfig


class UnattendedConfigMixin:
    def _update_state_after_round(
        self,
        task: TaskDefinitionLike,
        config: _UnattendedConfig,
        round_record: dict[str, Any],
        *,
        occurred_at: datetime,
        run_id: str = "",
    ) -> None:
        config.last_run_at = occurred_at
        config.next_run_at = occurred_at + timedelta(minutes=config.interval_minutes)
        config.last_run_id = run_id or str(round_record.get("run_id", "") or "")
        self._advance_rotation_state(config, round_record)
        config.latest_summary = {
            "status": round_record.get("status", ""),
            "run_id": round_record.get("run_id", ""),
            "run_status": round_record.get("run_status", ""),
            "triggered_at": round_record.get("triggered_at", ""),
            "instance_count": round_record.get("instance_count", 0),
            "failed_instance_count": round_record.get("failed_instance_count", 0),
            "offline_event_count": round_record.get("offline_event_count", 0),
            "recovery_attempt_count": round_record.get("recovery_attempt_count", 0),
            "recovery_success_count": round_record.get("recovery_success_count", 0),
            "rotation_cursor": config.rotation_cursor,
            "rotation_advance_count": config.rotation_advance_count,
        }
        config.recent_rounds.insert(0, dict(round_record))
        del config.recent_rounds[config.max_round_history :]
        config.recent_device_windows.insert(
            0,
            {
                "round_id": str(round_record.get("round_id", "") or ""),
                "status": str(round_record.get("status", "") or ""),
                "triggered_at": str(round_record.get("triggered_at", "") or ""),
                "assigned_device_ids": list(round_record.get("assigned_device_ids", []) or []),
                "preferred_device_ids": list(round_record.get("preferred_device_ids", []) or []),
                "unavailable_device_ids": list(round_record.get("unavailable_device_ids", []) or []),
                "rotation": dict(round_record.get("rotation", {}) or {}),
            },
        )
        del config.recent_device_windows[config.max_device_window_history :]
        config.long_run_summary = self._build_long_run_summary(config)
        self._save_config(task, config)

    def _build_task_record(self, task: TaskDefinitionLike, config: _UnattendedConfig) -> UnattendedTaskRecord:
        now = utcnow()
        return UnattendedTaskRecord(
            task_id=task.task_id,
            task_name=task.task_name,
            configured=config.configured,
            enabled=config.enabled,
            interval_minutes=config.interval_minutes,
            desired_device_count=config.desired_device_count,
            failure_threshold=config.failure_threshold,
            rotation_strategy=config.rotation_strategy,
            rotation_advance_policy=config.rotation_advance_policy,
            rotation_cursor=config.rotation_cursor,
            rotation_advance_count=config.rotation_advance_count,
            primary_device_ids=tuple(config.primary_device_ids),
            backup_device_ids=tuple(config.backup_device_ids),
            next_run_at=config.next_run_at,
            last_run_at=config.last_run_at,
            last_run_id=config.last_run_id,
            due=bool(config.enabled and config.next_run_at is not None and config.next_run_at <= now),
            latest_summary=dict(config.latest_summary),
            long_run_summary=dict(config.long_run_summary),
            recent_device_windows=tuple(dict(item) for item in config.recent_device_windows),
            recent_rounds=tuple(dict(item) for item in config.recent_rounds),
        )

    def _load_config(self, task: TaskDefinitionLike) -> _UnattendedConfig:
        metadata = dict(getattr(task, "metadata", {}) or {})
        root = metadata.get(self.ROOT_KEY)
        if not isinstance(root, dict):
            return _UnattendedConfig(
                configured=False,
                primary_device_ids=list(getattr(task, "selected_device_ids", ()) or ()),
                desired_device_count=max(1, len(getattr(task, "selected_device_ids", ()) or ()) or 1),
            )
        config_payload = root.get("config")
        if not isinstance(config_payload, dict):
            config_payload = {}
        state_payload = root.get("state")
        if not isinstance(state_payload, dict):
            state_payload = {}
        primary_device_ids = config_payload.get("primary_device_ids")
        backup_device_ids = config_payload.get("backup_device_ids")
        recent_rounds = state_payload.get("recent_rounds")
        recent_device_windows = state_payload.get("recent_device_windows")
        return _UnattendedConfig(
            configured=True,
            enabled=bool(config_payload.get("enabled", False)),
            interval_minutes=max(1, int(config_payload.get("interval_minutes", 60) or 60)),
            desired_device_count=max(
                1,
                int(
                    config_payload.get(
                        "desired_device_count",
                        len(primary_device_ids) if isinstance(primary_device_ids, list) and primary_device_ids else 1,
                    )
                    or 1
                ),
            ),
            failure_threshold=max(1, int(config_payload.get("failure_threshold", 3) or 3)),
            rotation_strategy=self._normalize_rotation_strategy(config_payload.get("rotation_strategy", "round_robin")),
            rotation_advance_policy=self._normalize_rotation_advance_policy(
                config_payload.get("rotation_advance_policy", "every_round")
            ),
            rotation_cursor=max(0, int(state_payload.get("rotation_cursor", 0) or 0)),
            rotation_advance_count=max(0, int(state_payload.get("rotation_advance_count", 0) or 0)),
            primary_device_ids=[str(item) for item in (primary_device_ids or list(getattr(task, "selected_device_ids", ()) or ()))],
            backup_device_ids=[str(item) for item in (backup_device_ids or [])],
            max_round_history=max(1, int(config_payload.get("max_round_history", 10) or 10)),
            max_device_window_history=max(1, int(config_payload.get("max_device_window_history", 10) or 10)),
            next_run_at=self._parse_datetime(state_payload.get("next_run_at")),
            last_run_at=self._parse_datetime(state_payload.get("last_run_at")),
            last_run_id=str(state_payload.get("last_run_id", "") or ""),
            latest_summary=dict(state_payload.get("latest_summary", {}) or {}),
            long_run_summary=dict(state_payload.get("long_run_summary", {}) or {}),
            recent_device_windows=[
                dict(item) for item in (recent_device_windows or []) if isinstance(item, dict)
            ],
            recent_rounds=[dict(item) for item in (recent_rounds or []) if isinstance(item, dict)],
        )

    def _save_config(self, task: TaskDefinitionLike, config: _UnattendedConfig) -> TaskDefinitionLike:
        metadata = dict(getattr(task, "metadata", {}) or {})
        metadata[self.ROOT_KEY] = {
            "config": {
                "enabled": config.enabled,
                "interval_minutes": config.interval_minutes,
                "desired_device_count": config.desired_device_count,
                "failure_threshold": config.failure_threshold,
                "rotation_strategy": config.rotation_strategy,
                "rotation_advance_policy": config.rotation_advance_policy,
                "primary_device_ids": list(config.primary_device_ids),
                "backup_device_ids": list(config.backup_device_ids),
                "max_round_history": config.max_round_history,
                "max_device_window_history": config.max_device_window_history,
            },
            "state": {
                "next_run_at": self._isoformat(config.next_run_at),
                "last_run_at": self._isoformat(config.last_run_at),
                "last_run_id": config.last_run_id,
                "rotation_cursor": config.rotation_cursor,
                "rotation_advance_count": config.rotation_advance_count,
                "latest_summary": dict(config.latest_summary),
                "long_run_summary": dict(config.long_run_summary),
                "recent_device_windows": [dict(item) for item in config.recent_device_windows],
                "recent_rounds": [dict(item) for item in config.recent_rounds],
            },
        }
        task.metadata = metadata
        task.updated_at = utcnow()
        return self._task_repository.save(task)

    def _build_long_run_summary(self, config: _UnattendedConfig) -> dict[str, Any]:
        recent_rounds = list(config.recent_rounds)
        executed_round_count = sum(1 for item in recent_rounds if self._round_is_executed(item))
        failed_round_count = sum(1 for item in recent_rounds if self._round_is_failed(item))
        replacement_round_count = sum(
            1 for item in recent_rounds if list(item.get("replacement_events", []) or [])
        )
        unique_assigned_device_ids = sorted(
            {
                str(device_id)
                for item in recent_rounds
                for device_id in list(item.get("assigned_device_ids", []) or [])
                if str(device_id).strip()
            }
        )
        next_primary_order = self._ordered_primary_device_ids(
            config.primary_device_ids,
            config.rotation_cursor,
            config.rotation_strategy,
        )
        return {
            "rotation_strategy": config.rotation_strategy,
            "rotation_advance_policy": config.rotation_advance_policy,
            "rotation_cursor": config.rotation_cursor,
            "rotation_advance_count": config.rotation_advance_count,
            "rotation_loop_count": (
                config.rotation_advance_count // max(1, len(config.primary_device_ids))
                if config.primary_device_ids
                else 0
            ),
            "round_count": len(recent_rounds),
            "executed_round_count": executed_round_count,
            "skipped_round_count": max(0, len(recent_rounds) - executed_round_count),
            "failed_round_count": failed_round_count,
            "replacement_round_count": replacement_round_count,
            "unique_assigned_device_count": len(unique_assigned_device_ids),
            "unique_assigned_device_ids": unique_assigned_device_ids,
            "next_primary_order": list(next_primary_order),
            "last_assigned_device_ids": list(recent_rounds[0].get("assigned_device_ids", []) or [])
            if recent_rounds
            else [],
            "last_status": str(recent_rounds[0].get("status", "") or "") if recent_rounds else "",
        }
