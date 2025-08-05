"""SoloX-backed monitoring adapter."""

from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, Optional

from stability.infrastructure.monitoring_base import MonitoringAdapter
from stability.infrastructure.monitoring_legacy_storage import LegacyStorageMixin, default_data_storage
from stability.infrastructure.monitoring_models import (
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
)
from stability.infrastructure.monitoring_utils import mapping_number, metric_enabled, safe_float, utcnow

logger = logging.getLogger(__name__)


class SoloXMonitoringAdapter(LegacyStorageMixin, MonitoringAdapter):
    """Collect normalized monitoring samples through SoloX Python APIs."""

    def __init__(
        self,
        client_factory: Callable[..., Any] | None = None,
        data_storage_service: Any = default_data_storage,
    ) -> None:
        super().__init__(data_storage_service=data_storage_service)
        self._client_factory = client_factory or self._default_client_factory

    def start_session(
        self,
        device_id: str,
        config: Optional[MonitoringSessionConfig] = None,
        session_name: Optional[str] = None,
    ) -> MonitoringSessionHandle:
        session_config = config or MonitoringSessionConfig()
        package_name = self._package_name(session_config)
        if not package_name:
            raise RuntimeError("SoloX monitoring requires one target package_name.")

        handle = MonitoringSessionHandle(
            device_id=device_id,
            session_name=session_name or f"solox_{device_id}_{utcnow().strftime('%Y%m%d_%H%M%S')}",
            config=session_config,
            collector=None,
            state={
                "package_name": package_name,
                "client": self._client_factory(
                    device_id=device_id,
                    package_name=package_name,
                    config=session_config,
                ),
            },
            backend_name="solox",
        )
        if session_config.persist_to_database and not session_config.demo_mode:
            handle.session_id = self._create_legacy_session(handle)
            handle.persisted = handle.session_id is not None
        return handle

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        client = handle.state.get("client")
        package_name = str(handle.state.get("package_name", "") or "")
        if client is None or not package_name:
            raise RuntimeError("SoloX monitoring session was not initialized correctly.")
        metrics = dict(handle.config.metrics)
        enabled_targets = {
            str(item or "").strip().lower()
            for item in list(handle.config.extra.get("solox_enabled_metrics", []) or [])
            if str(item or "").strip()
        }
        timestamp = utcnow()
        target_enabled = lambda name, *keys: (not enabled_targets or name in enabled_targets) and metric_enabled(
            metrics,
            *keys,
        )

        raw_cpu = self._collect_metric(
            client,
            "collectCpu",
            package_name=package_name,
        ) if target_enabled("cpu", "cpu", "apps") else None
        raw_memory = self._collect_metric(
            client,
            "collectMemory",
            package_name=package_name,
        ) if target_enabled("memory", "memory", "apps") else None
        raw_memory_detail = self._collect_metric(
            client,
            "collectMemoryDetail",
            package_name=package_name,
        ) if target_enabled("memory_detail", "memory", "apps") else None
        raw_network = self._collect_metric(
            client,
            "collectNetwork",
            package_name=package_name,
            wifi=bool(handle.config.extra.get("solox_wifi", True)),
        ) if target_enabled("network", "network", "apps") else None
        raw_fps = self._collect_metric(
            client,
            "collectFps",
            package_name=package_name,
        ) if target_enabled("fps", "fps", "apps") else None
        raw_battery = self._collect_metric(
            client,
            "collectBattery",
            package_name=package_name,
        ) if target_enabled("battery", "battery", "system") else None
        raw_gpu = self._collect_metric(
            client,
            "collectGpu",
            package_name=package_name,
        ) if target_enabled("gpu", "gpu", "apps") else None

        app_sample = {
            "package_name": package_name,
            "timestamp": timestamp,
            "cpu_usage": self._solox_cpu(raw_cpu).get("app_cpu_usage"),
            "memory_pss": self._solox_memory(raw_memory).get("memory_pss"),
            "memory_java": self._solox_memory_detail(raw_memory_detail).get("memory_java"),
            "memory_native": self._solox_memory_detail(raw_memory_detail).get("memory_native"),
            "memory_graphics": self._solox_memory_detail(raw_memory_detail).get("memory_graphics"),
            "rx_bytes": self._solox_network(raw_network).get("rx_bytes"),
            "tx_bytes": self._solox_network(raw_network).get("tx_bytes"),
            "fps": self._solox_fps(raw_fps).get("fps"),
            "jank_frames": self._solox_fps(raw_fps).get("jank_frames"),
            "gpu_usage": self._solox_gpu(raw_gpu).get("gpu_usage"),
            "power_usage": self._solox_battery(raw_battery).get("power_usage"),
        }
        app_sample = {
            key: value
            for key, value in app_sample.items()
            if value is not None or key in {"package_name", "timestamp"}
        }
        system_sample = {
            "timestamp": timestamp,
            "cpu_usage": self._solox_cpu(raw_cpu).get("system_cpu_usage"),
            "battery_level": self._solox_battery(raw_battery).get("battery_level"),
            "battery_temperature": self._solox_battery(raw_battery).get("battery_temperature"),
            "battery_voltage": self._solox_battery(raw_battery).get("battery_voltage"),
        }
        system_sample = {key: value for key, value in system_sample.items() if value is not None}
        return MonitoringSnapshot(
            timestamp=timestamp,
            system=system_sample or None,
            apps=[app_sample],
            metadata={
                "backend": "solox",
                "profile_name": handle.config.profile_name,
                "raw_targets": [
                    target
                    for target, raw_value in (
                        ("cpu", raw_cpu),
                        ("memory", raw_memory),
                        ("memory_detail", raw_memory_detail),
                        ("network", raw_network),
                        ("fps", raw_fps),
                        ("battery", raw_battery),
                        ("gpu", raw_gpu),
                    )
                    if raw_value is not None
                ],
            },
        )

    @staticmethod
    def _collect_metric(client: Any, method_name: str, *, package_name: str, **kwargs: Any) -> Any:
        method = getattr(client, method_name, None)
        if method is None:
            logger.warning("SoloX client for %s does not expose %s.", package_name, method_name)
            return None
        try:
            return method(**kwargs)
        except Exception as exc:
            logger.warning("SoloX metric %s failed for %s: %s", method_name, package_name, exc)
            return None

    @staticmethod
    def _default_client_factory(
        *,
        device_id: str,
        package_name: str,
        config: MonitoringSessionConfig,
    ) -> Any:
        try:
            from solox.public.apm import AppPerformanceMonitor
        except Exception as exc:  # pragma: no cover - depends on optional dependency
            raise RuntimeError("SoloX Python package is unavailable. Install it with `pip install -U solox`.") from exc

        return AppPerformanceMonitor(
            pkgName=package_name,
            platform="Android",
            deviceId=device_id,
            surfaceview=bool(config.extra.get("solox_surfaceview", True)),
            noLog=bool(config.extra.get("solox_no_log", True)),
            pid=config.extra.get("solox_pid"),
            record=bool(config.extra.get("solox_record", False)),
            collect_all=False,
            duration=int(config.extra.get("solox_duration_seconds", 0) or 0),
        )

    @staticmethod
    def _package_name(config: MonitoringSessionConfig) -> str:
        for app in config.selected_apps:
            package_name = str(dict(app).get("package_name", "") or "")
            if package_name:
                return package_name
        return ""

    @staticmethod
    def _solox_cpu(payload: Any) -> dict[str, float | None]:
        if isinstance(payload, Mapping):
            return {
                "app_cpu_usage": mapping_number(payload, "app_cpu_usage", "app_cpu", "appCpuRate", "cpu_usage"),
                "system_cpu_usage": mapping_number(
                    payload,
                    "system_cpu_usage",
                    "system_cpu",
                    "systemCpuRate",
                    "totalCpuRate",
                    "total_cpu_usage",
                ),
            }
        if isinstance(payload, (list, tuple)):
            app_cpu = safe_float(payload[0]) if len(payload) > 0 else None
            system_cpu = safe_float(payload[1]) if len(payload) > 1 else None
            return {"app_cpu_usage": app_cpu, "system_cpu_usage": system_cpu}
        return {"app_cpu_usage": safe_float(payload), "system_cpu_usage": None}

    @staticmethod
    def _solox_memory(payload: Any) -> dict[str, float | None]:
        if isinstance(payload, Mapping):
            return {
                "memory_pss": mapping_number(payload, "memory_pss", "pss", "totalPss", "memory", "total"),
            }
        if isinstance(payload, (list, tuple)) and payload:
            return {"memory_pss": safe_float(payload[0])}
        return {"memory_pss": safe_float(payload)}

    @staticmethod
    def _solox_memory_detail(payload: Any) -> dict[str, float | None]:
        if not isinstance(payload, Mapping):
            return {
                "memory_java": None,
                "memory_native": None,
                "memory_graphics": None,
            }
        return {
            "memory_java": mapping_number(payload, "memory_java", "java_heap", "javaHeap", "java"),
            "memory_native": mapping_number(payload, "memory_native", "native_heap", "nativeHeap", "native"),
            "memory_graphics": mapping_number(payload, "memory_graphics", "graphics", "graphics_heap", "graphicsHeap"),
        }

    @staticmethod
    def _solox_network(payload: Any) -> dict[str, float | None]:
        if isinstance(payload, Mapping):
            rx_bytes = mapping_number(payload, "rx_bytes", "download_bytes")
            tx_bytes = mapping_number(payload, "tx_bytes", "upload_bytes")
            if rx_bytes is None:
                rx_kb = mapping_number(payload, "rx", "recv", "receive", "download")
                rx_bytes = rx_kb * 1024 if rx_kb is not None else None
            if tx_bytes is None:
                tx_kb = mapping_number(payload, "tx", "send", "upload")
                tx_bytes = tx_kb * 1024 if tx_kb is not None else None
            return {"rx_bytes": rx_bytes, "tx_bytes": tx_bytes}
        if isinstance(payload, (list, tuple)):
            rx_kb = safe_float(payload[0]) if len(payload) > 0 else None
            tx_kb = safe_float(payload[1]) if len(payload) > 1 else None
            return {
                "rx_bytes": rx_kb * 1024 if rx_kb is not None else None,
                "tx_bytes": tx_kb * 1024 if tx_kb is not None else None,
            }
        return {"rx_bytes": None, "tx_bytes": None}

    @staticmethod
    def _solox_fps(payload: Any) -> dict[str, float | None]:
        if isinstance(payload, Mapping):
            return {
                "fps": mapping_number(payload, "fps", "FPS"),
                "jank_frames": mapping_number(payload, "jank", "jank_frames", "jankFrames"),
            }
        if isinstance(payload, (list, tuple)):
            fps = safe_float(payload[0]) if len(payload) > 0 else None
            jank_frames = safe_float(payload[1]) if len(payload) > 1 else None
            return {"fps": fps, "jank_frames": jank_frames}
        return {"fps": safe_float(payload), "jank_frames": None}

    @staticmethod
    def _solox_battery(payload: Any) -> dict[str, float | None]:
        if isinstance(payload, Mapping):
            current = mapping_number(payload, "current", "battery_current")
            voltage = mapping_number(payload, "voltage", "battery_voltage")
            power_usage = mapping_number(payload, "power", "power_usage")
            if power_usage is None and current is not None and voltage is not None:
                power_usage = abs(current) * abs(voltage) / 1_000_000.0
            return {
                "battery_level": mapping_number(payload, "level", "battery_level"),
                "battery_temperature": mapping_number(payload, "temperature", "battery_temperature"),
                "battery_voltage": voltage,
                "power_usage": power_usage,
            }
        if isinstance(payload, (list, tuple)):
            level = safe_float(payload[0]) if len(payload) > 0 else None
            temperature = safe_float(payload[1]) if len(payload) > 1 else None
            current = safe_float(payload[2]) if len(payload) > 2 else None
            voltage = safe_float(payload[3]) if len(payload) > 3 else None
            power_usage = safe_float(payload[4]) if len(payload) > 4 else None
            if power_usage is None and current is not None and voltage is not None:
                power_usage = abs(current) * abs(voltage) / 1_000_000.0
            return {
                "battery_level": level,
                "battery_temperature": temperature,
                "battery_voltage": voltage,
                "power_usage": power_usage,
            }
        return {
            "battery_level": None,
            "battery_temperature": None,
            "battery_voltage": None,
            "power_usage": None,
        }

    @staticmethod
    def _solox_gpu(payload: Any) -> dict[str, float | None]:
        if isinstance(payload, Mapping):
            return {"gpu_usage": mapping_number(payload, "gpu_usage", "gpu", "usage")}
        if isinstance(payload, (list, tuple)) and payload:
            return {"gpu_usage": safe_float(payload[0])}
        return {"gpu_usage": safe_float(payload)}
