from __future__ import annotations

from stability.application import (
    ConnectDeviceCommand,
    PairConnectDeviceCommand,
    RefreshDevicesCommand,
    UpdateDeviceProfileCommand,
    connect_device as connect_device_use_case,
    pair_connect_device as pair_connect_device_use_case,
    refresh_devices as refresh_devices_use_case,
    update_device_profile as update_device_profile_use_case,
)

from typing import Any, Mapping


class DevicesActionsMixin:
    def _handle_device_profile_update(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        actor = dict(request_context.get("current_actor", {}) or {})
        return update_device_profile_use_case(
            getattr(self._bundle, "device_service", None),
            UpdateDeviceProfileCommand(
                device_id=self._required_form_value(dict(payload), "device_id"),
                group_name=self._form_value(dict(payload), "group_name"),
                team_name=self._form_value(dict(payload), "team_name"),
                tags=self._expand_form_values(payload, "tags"),
                actor=str(actor.get("actor_id", "") or "web"),
            ),
        )

    def _handle_device_registry_refresh(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        return refresh_devices_use_case(
            getattr(self._bundle, "device_service", None),
            RefreshDevicesCommand(device_id=self._form_value(dict(payload), "device_id")),
        )

    def _handle_device_connect(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        return connect_device_use_case(
            getattr(self._bundle, "device_service", None),
            ConnectDeviceCommand(device_id=self._required_form_value(dict(payload), "device_id")),
        )

    def _handle_device_pair_connect(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        return pair_connect_device_use_case(
            getattr(self._bundle, "device_service", None),
            PairConnectDeviceCommand(
                pair_device_id=self._required_form_value(dict(payload), "pair_device_id"),
                pairing_code=self._required_form_value(dict(payload), "pairing_code"),
                connect_device_id=self._required_form_value(dict(payload), "connect_device_id"),
            ),
        )

__all__ = ["DevicesActionsMixin"]
