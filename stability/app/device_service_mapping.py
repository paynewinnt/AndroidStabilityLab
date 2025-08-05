from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from stability.domain import Device, DeviceAvailabilityState, DeviceConnectionState
from stability.infrastructure.device_adapter import DeviceDescriptor


def find_device_by_serial(devices: Sequence[Device], serial: str) -> Optional[Device]:
    for device in devices:
        if device.serial == serial:
            return device
    return None


def build_device(descriptor: DeviceDescriptor) -> Device:
    connection_state = map_connection_state(descriptor.status)
    device = Device(
        device_id=descriptor.device_id,
        serial=descriptor.serial,
        brand=descriptor.brand or descriptor.manufacturer or "",
        model=descriptor.model or descriptor.device_name or "",
        android_version=descriptor.android_version or "",
        rom_version=descriptor.build_id or "",
        abi=descriptor.cpu_abi or "",
        connection_state=connection_state,
        availability_state=derive_availability_state(
            current_state=None,
            connection_state=connection_state,
            current_instance_id=None,
        ),
        metadata=build_metadata(descriptor),
    )
    device.touch_heartbeat()
    return device


def merge_descriptor(device: Device, descriptor: DeviceDescriptor) -> bool:
    before = comparison_snapshot(device)
    connection_state = map_connection_state(descriptor.status)

    device.device_id = descriptor.device_id
    device.serial = descriptor.serial
    device.brand = descriptor.brand or descriptor.manufacturer or ""
    device.model = descriptor.model or descriptor.device_name or ""
    device.android_version = descriptor.android_version or ""
    device.rom_version = descriptor.build_id or ""
    device.abi = descriptor.cpu_abi or ""
    device.connection_state = connection_state
    device.availability_state = derive_availability_state(
        current_state=device.availability_state,
        connection_state=connection_state,
        current_instance_id=device.current_instance_id,
    )
    device.metadata = build_metadata(descriptor, current=device.metadata)
    device.touch_heartbeat()

    return comparison_snapshot(device) != before


def map_connection_state(status: str) -> DeviceConnectionState:
    normalized = (status or "").strip().lower()
    if normalized == "device":
        return DeviceConnectionState.ONLINE
    if normalized == "offline":
        return DeviceConnectionState.OFFLINE
    if normalized == "unauthorized":
        return DeviceConnectionState.UNAUTHORIZED
    return DeviceConnectionState.UNKNOWN


def derive_availability_state(
    current_state: Optional[DeviceAvailabilityState],
    connection_state: DeviceConnectionState,
    current_instance_id: Optional[str],
) -> DeviceAvailabilityState:
    if current_state == DeviceAvailabilityState.QUARANTINED:
        return DeviceAvailabilityState.QUARANTINED
    if connection_state != DeviceConnectionState.ONLINE:
        return DeviceAvailabilityState.ERROR
    if current_state in {DeviceAvailabilityState.RESERVED, DeviceAvailabilityState.RUNNING}:
        return current_state
    if current_instance_id:
        return DeviceAvailabilityState.RESERVED
    return DeviceAvailabilityState.IDLE


def build_metadata(
    descriptor: DeviceDescriptor,
    current: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(current or {})
    metadata.update(
        {
            "manufacturer": descriptor.manufacturer,
            "api_level": descriptor.api_level,
            "screen_size": descriptor.screen_size,
            "screen_density": descriptor.screen_density,
            "transport_id": descriptor.transport_id,
            "usb": descriptor.usb,
            "product": descriptor.product,
            "device_name": descriptor.device_name,
            "model_code": descriptor.model_code,
            "raw": dict(descriptor.raw),
        }
    )
    return metadata


def comparison_snapshot(device: Device) -> tuple[Any, ...]:
    return (
        device.device_id,
        device.serial,
        device.brand,
        device.model,
        device.android_version,
        device.rom_version,
        device.abi,
        device.connection_state,
        device.availability_state,
        device.current_instance_id,
        device.group_name,
        tuple(device.tags),
        tuple(sorted(device.metadata.items())),
    )


def mark_missing_device_offline(device: Device) -> bool:
    if (
        device.connection_state == DeviceConnectionState.OFFLINE
        and device.availability_state in {DeviceAvailabilityState.ERROR, DeviceAvailabilityState.QUARANTINED}
    ):
        return False
    device.connection_state = DeviceConnectionState.OFFLINE
    if device.availability_state != DeviceAvailabilityState.QUARANTINED:
        device.availability_state = DeviceAvailabilityState.ERROR
    return True
