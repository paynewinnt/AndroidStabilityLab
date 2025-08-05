"""Adapters that expose existing ADBCollector capabilities behind stable interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from stability.infrastructure.adb import ADBCollector
from stability.infrastructure.command_runner import ADBCommandRunner, CommandRunner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceDescriptor:
    """Normalized device metadata for the V1 device registry."""

    serial: str
    status: str
    model: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    android_version: Optional[str] = None
    api_level: Optional[str] = None
    cpu_abi: Optional[str] = None
    build_id: Optional[str] = None
    screen_size: Optional[str] = None
    screen_density: Optional[str] = None
    transport_id: Optional[str] = None
    usb: Optional[str] = None
    product: Optional[str] = None
    device_name: Optional[str] = None
    model_code: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def device_id(self) -> str:
        return self.serial

    @property
    def is_available(self) -> bool:
        return self.status == "device"


class DeviceDiscoveryAdapter(ABC):
    """Stable contract for device discovery and metadata lookup."""

    @abstractmethod
    def list_devices(self, include_unavailable: bool = False) -> List[DeviceDescriptor]:
        raise NotImplementedError

    @abstractmethod
    def get_device(self, serial: str) -> Optional[DeviceDescriptor]:
        raise NotImplementedError

    def connect_device(self, serial: str) -> Dict[str, Any]:
        """Best-effort connection hook for TCP/IP ADB targets."""
        return {"attempted": False, "serial": serial, "success": False, "message": "connect_device is not supported"}

    def pair_device(self, serial: str, pairing_code: str) -> Dict[str, Any]:
        """Best-effort pairing hook for Android wireless debugging targets."""
        return {"attempted": False, "serial": serial, "success": False, "message": "pair_device is not supported"}


class ADBCollectorDeviceAdapter(DeviceDiscoveryAdapter):
    """Thin adapter over the ADBCollector device APIs."""

    def __init__(
        self,
        collector_factory: Optional[Callable[[], ADBCollector]] = None,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self._collector_factory = collector_factory or ADBCollector
        self._command_runner = command_runner

    def list_devices(self, include_unavailable: bool = False) -> List[DeviceDescriptor]:
        devices = []
        for serial, parsed in self._list_raw_devices().items():
            status = parsed.get("status", "unknown")
            if not include_unavailable and status != "device":
                continue
            devices.append(self._build_descriptor(serial=serial, status=status, raw_entry=parsed))
        return devices

    def get_device(self, serial: str) -> Optional[DeviceDescriptor]:
        raw_devices = self._list_raw_devices()
        parsed = raw_devices.get(serial)
        if parsed is None:
            return None
        return self._build_descriptor(
            serial=serial,
            status=parsed.get("status", "unknown"),
            raw_entry=parsed,
        )

    def connect_device(self, serial: str) -> Dict[str, Any]:
        target = str(serial or "").strip()
        if not target:
            return {"attempted": False, "serial": "", "success": False, "message": "serial is required"}
        result = ADBCommandRunner(command_runner=self._command_runner).run_adb(["connect", target], timeout_seconds=10)
        output = result.stdout or result.stderr or ""
        normalized = output.lower()
        success = result.returncode == 0 and ("connected" in normalized or "already connected" in normalized)
        return {
            "attempted": True,
            "serial": target,
            "success": success,
            "message": output.strip() or "adb connect returned no output",
        }

    def pair_device(self, serial: str, pairing_code: str) -> Dict[str, Any]:
        target = str(serial or "").strip()
        code = str(pairing_code or "").strip()
        if not target or not code:
            return {"attempted": False, "serial": target, "success": False, "message": "pair serial and pairing code are required"}
        result = ADBCommandRunner(command_runner=self._command_runner).run_adb(["pair", target, code], timeout_seconds=30)
        output = result.stdout or result.stderr or ""
        normalized = output.lower()
        success = result.returncode == 0 and ("successfully paired" in normalized or "already paired" in normalized)
        return {
            "attempted": True,
            "serial": target,
            "success": success,
            "message": output.strip() or "adb pair returned no output",
        }

    def _build_descriptor(
        self,
        serial: str,
        status: str,
        raw_entry: Mapping[str, Any],
    ) -> DeviceDescriptor:
        info: Dict[str, Any] = {}
        if status == "device":
            info = self._load_device_info(serial)

        return DeviceDescriptor(
            serial=serial,
            status=status,
            model=info.get("model"),
            brand=info.get("brand"),
            manufacturer=info.get("manufacturer"),
            android_version=info.get("android_version"),
            api_level=info.get("api_level"),
            cpu_abi=info.get("cpu_abi"),
            build_id=info.get("build_id"),
            screen_size=info.get("screen_size"),
            screen_density=info.get("screen_density"),
            transport_id=self._string_or_none(raw_entry.get("transport_id")),
            usb=self._string_or_none(raw_entry.get("usb")),
            product=self._string_or_none(raw_entry.get("product")),
            device_name=self._string_or_none(raw_entry.get("device")),
            model_code=self._string_or_none(raw_entry.get("model")),
            raw={**dict(raw_entry), "device_info": info},
        )

    def _load_device_info(self, serial: str) -> Dict[str, Any]:
        collector = self._create_collector(device_id=serial)
        info = collector.get_device_info() or {}
        if "error" in info:
            logger.warning("Failed to load device info for %s: %s", serial, info["error"])
        return info

    def _list_raw_devices(self) -> Dict[str, Dict[str, str]]:
        result = ADBCommandRunner(command_runner=self._command_runner).run_adb(["devices", "-l"], timeout_seconds=10)
        output = result.stdout if result.returncode == 0 else ""
        if not output:
            return {}
        return self._parse_adb_devices(output)

    def _create_collector(self, device_id: Optional[str] = None) -> ADBCollector:
        collector = self._collector_factory()
        if device_id:
            collector.device_id = device_id
        return collector

    @staticmethod
    def _parse_adb_devices(output: str) -> Dict[str, Dict[str, str]]:
        devices: Dict[str, Dict[str, str]] = {}
        lines = output.splitlines()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("List of devices attached"):
                continue

            tokens = stripped.split()
            if len(tokens) < 2:
                continue

            serial = tokens[0]
            status = tokens[1]
            details: Dict[str, str] = {"status": status, "raw_line": stripped}
            for token in tokens[2:]:
                if ":" not in token:
                    continue
                key, value = token.split(":", 1)
                details[key] = value
            devices[serial] = details

        return devices

    @staticmethod
    def _string_or_none(value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


def iter_available_devices(adapter: DeviceDiscoveryAdapter) -> Iterable[DeviceDescriptor]:
    """Helper for callers that only care about schedulable devices."""

    return (device for device in adapter.list_devices(include_unavailable=False) if device.is_available)
