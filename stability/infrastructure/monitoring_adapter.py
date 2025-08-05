"""Compatibility facade for monitoring adapters.

The implementation is split across focused ``monitoring_*`` modules, while this
module keeps the original import contract intact.
"""

from __future__ import annotations

from stability.infrastructure.monitoring_adb_adapter import ADBCollectorMonitoringAdapter
from stability.infrastructure.monitoring_base import MonitoringAdapter
from stability.infrastructure.monitoring_config import (
    SUPPORTED_MONITORING_BACKENDS,
    _DEFAULT_MONITORING_PROFILES,
    _MONITORING_BACKEND_ALIASES,
    _backend_to_profile,
    _profile_for_backend,
    _profile_name_to_backend_name,
    _profile_to_backend,
    FileBackedMonitoringSettingsProvider,
    MonitoringBackendSettings,
    backend_to_profile,
    load_monitoring_profile_registry,
    normalize_monitoring_backend_name,
    profile_for_backend,
    profile_name_to_backend_name,
    profile_to_backend,
)
from stability.infrastructure.monitoring_configured_adapter import ConfiguredMonitoringAdapter
from stability.infrastructure.monitoring_factory import (
    MonitoringAdapterFactory,
    build_configured_monitoring_adapter,
    build_monitoring_adapter,
)
from stability.infrastructure.monitoring_legacy_storage import (
    _LegacyStorageMixin,
    LegacyStorageMixin,
    PersistedMonitoringDataProvider,
    default_data_storage,
)
from stability.infrastructure.monitoring_models import (
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
)
from stability.infrastructure.monitoring_perfetto_adapter import PerfettoTraceCaptureAdapter
from stability.infrastructure.monitoring_solox_adapter import SoloXMonitoringAdapter
from stability.infrastructure.monitoring_utils import (
    _deep_merge_mapping,
    _mapping_number,
    _metric_enabled,
    _safe_float,
    _tail_text,
    _utcnow,
    deep_merge_mapping,
    mapping_number,
    metric_enabled,
    safe_float,
    tail_text,
    utcnow,
)

__all__ = [
    "ADBCollectorMonitoringAdapter",
    "ConfiguredMonitoringAdapter",
    "FileBackedMonitoringSettingsProvider",
    "LegacyStorageMixin",
    "MonitoringAdapter",
    "MonitoringAdapterFactory",
    "MonitoringBackendSettings",
    "MonitoringSessionConfig",
    "MonitoringSessionHandle",
    "MonitoringSnapshot",
    "PerfettoTraceCaptureAdapter",
    "PersistedMonitoringDataProvider",
    "SoloXMonitoringAdapter",
    "SUPPORTED_MONITORING_BACKENDS",
    "backend_to_profile",
    "build_configured_monitoring_adapter",
    "build_monitoring_adapter",
    "deep_merge_mapping",
    "default_data_storage",
    "load_monitoring_profile_registry",
    "mapping_number",
    "metric_enabled",
    "normalize_monitoring_backend_name",
    "profile_for_backend",
    "profile_name_to_backend_name",
    "profile_to_backend",
    "safe_float",
    "tail_text",
    "utcnow",
    "_DEFAULT_MONITORING_PROFILES",
    "_LegacyStorageMixin",
    "_MONITORING_BACKEND_ALIASES",
    "_backend_to_profile",
    "_deep_merge_mapping",
    "_mapping_number",
    "_metric_enabled",
    "_profile_for_backend",
    "_profile_name_to_backend_name",
    "_profile_to_backend",
    "_safe_float",
    "_tail_text",
    "_utcnow",
]
