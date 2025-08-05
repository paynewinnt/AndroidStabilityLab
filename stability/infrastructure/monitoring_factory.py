"""Factory helpers for monitoring adapter wiring."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from stability.infrastructure.adb import ADBCollector
from stability.infrastructure.monitoring_adb_adapter import ADBCollectorMonitoringAdapter
from stability.infrastructure.monitoring_base import MonitoringAdapter
from stability.infrastructure.monitoring_config import (
    _DEFAULT_MONITORING_PROFILES,
    MonitoringBackendSettings,
    load_monitoring_profile_registry,
    normalize_monitoring_backend_name,
    profile_for_backend,
)
from stability.infrastructure.monitoring_configured_adapter import ConfiguredMonitoringAdapter
from stability.infrastructure.monitoring_legacy_storage import default_data_storage
from stability.infrastructure.monitoring_perfetto_adapter import PerfettoTraceCaptureAdapter
from stability.infrastructure.monitoring_solox_adapter import SoloXMonitoringAdapter
from stability.infrastructure.monitoring_utils import deep_merge_mapping

logger = logging.getLogger(__name__)


def build_configured_monitoring_adapter(
    config_path: str | Path = "config/monitoring.json",
) -> ConfiguredMonitoringAdapter:
    """Build the repo-default configured monitoring adapter."""

    registry = load_monitoring_profile_registry(config_path)
    return ConfiguredMonitoringAdapter(
        default_profile=str(registry.get("default_profile", "adb") or "adb"),
        profiles=dict(registry.get("profiles", {}) or {}),
    )


def build_monitoring_adapter(
    *,
    requested_backend: str | None = None,
    settings: MonitoringBackendSettings | None = None,
    data_storage_service: Any = default_data_storage,
    adb_collector_factory: Callable[[], ADBCollector] | None = None,
    solox_monitor_factory: Callable[..., Any] | None = None,
) -> tuple[MonitoringAdapter | None, str]:
    """Build one monitoring adapter for bootstrap wiring and CLI overrides."""

    resolved_settings = settings or MonitoringBackendSettings()
    requested_backend_name = normalize_monitoring_backend_name(requested_backend, "")
    configured_backend = normalize_monitoring_backend_name(
        resolved_settings.backend,
        "adb_collector",
    )
    resolved_backend = configured_backend if requested_backend_name in {"", "auto"} else requested_backend_name
    if resolved_backend == "disabled":
        return None, "disabled"

    registry = dict(resolved_settings.registry or load_monitoring_profile_registry(resolved_settings.config_path))
    profiles = dict(registry.get("profiles", {}) or _DEFAULT_MONITORING_PROFILES)
    preferred_profile = str(registry.get("default_profile", "adb") or "adb")
    forced_profile_name = profile_for_backend(
        resolved_backend,
        preferred_profile=preferred_profile,
        profiles=profiles,
    )
    if resolved_settings.solox:
        solox_metadata: dict[str, Any] = {}
        if "surfaceview" in resolved_settings.solox:
            solox_metadata["solox_surfaceview"] = bool(resolved_settings.solox.get("surfaceview"))
        if "network_wifi" in resolved_settings.solox:
            solox_metadata["solox_wifi"] = bool(resolved_settings.solox.get("network_wifi"))
        if "no_log" in resolved_settings.solox:
            solox_metadata["solox_no_log"] = bool(resolved_settings.solox.get("no_log"))
        if "record" in resolved_settings.solox:
            solox_metadata["solox_record"] = bool(resolved_settings.solox.get("record"))
        enabled_metrics = list(resolved_settings.solox.get("enabled_metrics", []) or [])
        if enabled_metrics:
            solox_metadata["solox_enabled_metrics"] = tuple(
                str(item).strip().lower()
                for item in enabled_metrics
                if str(item or "").strip()
            )
        if solox_metadata:
            for profile_name in ("solox", "solox_perfetto"):
                profile = dict(profiles.get(profile_name, _DEFAULT_MONITORING_PROFILES.get(profile_name, {})))
                profile["metadata"] = deep_merge_mapping(profile.get("metadata", {}), solox_metadata)
                profiles[profile_name] = profile

    if resolved_backend == "adb_collector":
        return (
            ADBCollectorMonitoringAdapter(
                collector_factory=adb_collector_factory,
                data_storage_service=data_storage_service,
            ),
            "adb_collector",
        )

    if resolved_backend == "solox":
        solox_adapter = SoloXMonitoringAdapter(
            client_factory=solox_monitor_factory,
            data_storage_service=data_storage_service,
        )
        fallback_backend = normalize_monitoring_backend_name(
            resolved_settings.fallback_backend,
            "adb_collector",
        )
        if fallback_backend == "disabled":
            return solox_adapter, "solox"
        return (
            ConfiguredMonitoringAdapter(
                default_profile=forced_profile_name,
                profiles=profiles,
                legacy_adapter=ADBCollectorMonitoringAdapter(
                    collector_factory=adb_collector_factory,
                    data_storage_service=data_storage_service,
                ),
                solox_adapter=solox_adapter,
                forced_profile_name=forced_profile_name,
            ),
            "solox",
        )

    if resolved_backend == "perfetto":
        return (
            ConfiguredMonitoringAdapter(
                default_profile=forced_profile_name,
                profiles=profiles,
                legacy_adapter=ADBCollectorMonitoringAdapter(
                    collector_factory=adb_collector_factory,
                    data_storage_service=data_storage_service,
                ),
                solox_adapter=SoloXMonitoringAdapter(
                    client_factory=solox_monitor_factory,
                    data_storage_service=data_storage_service,
                ),
                perfetto_adapter=PerfettoTraceCaptureAdapter(),
                forced_profile_name=forced_profile_name,
            ),
            "perfetto",
        )

    logger.warning(
        "Unsupported monitoring backend '%s'; falling back to adb_collector.",
        resolved_backend,
    )
    return (
        ADBCollectorMonitoringAdapter(
            collector_factory=adb_collector_factory,
            data_storage_service=data_storage_service,
        ),
        "adb_collector",
    )


class MonitoringAdapterFactory:
    """Compatibility wrapper for class-based factory imports."""

    build_configured_monitoring_adapter = staticmethod(build_configured_monitoring_adapter)
    build_monitoring_adapter = staticmethod(build_monitoring_adapter)
