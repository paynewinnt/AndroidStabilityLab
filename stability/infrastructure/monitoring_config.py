"""Monitoring backend and profile configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

from stability.infrastructure.monitoring_utils import deep_merge_mapping

SUPPORTED_MONITORING_BACKENDS = ("adb_collector", "solox", "perfetto", "auto", "disabled")
DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE = "/data/misc/perfetto-traces/{session_name}.perfetto-trace"
_MONITORING_BACKEND_ALIASES = {
    "adb": "adb_collector",
    "legacy": "adb_collector",
    "legacy_adb": "adb_collector",
    "trace": "perfetto",
    "perfetto_trace": "perfetto",
    "none": "disabled",
    "off": "disabled",
}

_DEFAULT_MONITORING_PROFILES: dict[str, dict[str, Any]] = {
    "adb": {
        "metrics_backend": "adb_collector",
        "trace_backend": "",
        "metadata": {},
    },
    "solox": {
        "metrics_backend": "solox",
        "trace_backend": "",
        "metadata": {
            "solox_surfaceview": True,
            "solox_wifi": True,
        },
    },
    "perfetto": {
        "metrics_backend": "adb_collector",
        "trace_backend": "perfetto",
        "metadata": {
            "perfetto_buffer_size_kb": 32768,
            "perfetto_remote_path_template": DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE,
        },
    },
    "solox_perfetto": {
        "metrics_backend": "solox",
        "trace_backend": "perfetto",
        "metadata": {
            "solox_surfaceview": True,
            "solox_wifi": True,
            "perfetto_buffer_size_kb": 32768,
            "perfetto_remote_path_template": DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE,
        },
    },
}


def normalize_monitoring_backend_name(value: Any, default: str = "adb_collector") -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return default
    normalized = _MONITORING_BACKEND_ALIASES.get(candidate, candidate)
    if normalized not in SUPPORTED_MONITORING_BACKENDS:
        return default
    return normalized


def backend_to_profile(backend_name: str) -> str:
    normalized = normalize_monitoring_backend_name(backend_name, "adb_collector")
    if normalized == "solox":
        return "solox"
    if normalized == "perfetto":
        return "perfetto"
    return "adb"


def profile_name_to_backend_name(profile_name: str) -> str:
    normalized = str(profile_name or "").strip().lower()
    if normalized in {"solox", "solox_perfetto"}:
        return "solox"
    if normalized in {"", "adb", "legacy", "perfetto"}:
        return "adb_collector"
    return "adb_collector"


@dataclass(frozen=True)
class MonitoringBackendSettings:
    """Minimal monitoring backend settings used by bootstrap wiring."""

    backend: str = "adb_collector"
    fallback_backend: str = "adb_collector"
    config_path: str = "config/monitoring.json"
    registry: Mapping[str, Any] = field(default_factory=dict)
    solox: Mapping[str, Any] = field(default_factory=dict)


class FileBackedMonitoringSettingsProvider:
    """Load backend selection settings from the monitoring repo config."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> MonitoringBackendSettings:
        raw_payload: Mapping[str, Any] = {}
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, Mapping):
                raw_payload = loaded

        monitoring_payload = dict(raw_payload.get("monitoring", {}) or {})
        registry = load_monitoring_profile_registry(self._path)
        backend = normalize_monitoring_backend_name(
            monitoring_payload.get("backend"),
            profile_name_to_backend_name(str(registry.get("default_profile", "adb") or "adb")),
        )
        fallback_backend = normalize_monitoring_backend_name(
            monitoring_payload.get("fallback_backend"),
            "adb_collector",
        )
        return MonitoringBackendSettings(
            backend=backend,
            fallback_backend=fallback_backend,
            config_path=str(self._path),
            registry=registry,
            solox=dict(monitoring_payload.get("solox", {}) or {}),
        )


def load_monitoring_profile_registry(config_path: str | Path = "config/monitoring.json") -> dict[str, Any]:
    """Load the optional monitoring profile registry from the repo config file."""

    payload = {
        "default_profile": "adb",
        "profiles": dict(_DEFAULT_MONITORING_PROFILES),
    }
    path = Path(config_path)
    if not path.exists():
        return payload
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return payload
    integration = dict(raw.get("integration_backends", {}) or {})
    payload["default_profile"] = str(integration.get("default_profile", payload["default_profile"]) or "adb")
    configured_profiles = dict(integration.get("profiles", {}) or {})
    merged_profiles = dict(_DEFAULT_MONITORING_PROFILES)
    for key, value in configured_profiles.items():
        if not isinstance(value, Mapping):
            continue
        merged_profiles[str(key)] = deep_merge_mapping(merged_profiles.get(str(key), {}), value)
    payload["profiles"] = merged_profiles
    return payload


def profile_to_backend(profile_name: str, profiles: Mapping[str, Mapping[str, Any]]) -> str:
    profile = dict(profiles.get(profile_name, {}) or {})
    trace_backend = normalize_monitoring_backend_name(profile.get("trace_backend"), "")
    if trace_backend == "perfetto":
        return "perfetto"
    metrics_backend = str(profile.get("metrics_backend", "") or "").strip().lower()
    if metrics_backend == "solox":
        return "solox"
    return "adb_collector"


def profile_for_backend(
    backend_name: str,
    *,
    preferred_profile: str,
    profiles: Mapping[str, Mapping[str, Any]],
) -> str:
    normalized_backend = normalize_monitoring_backend_name(backend_name)
    if preferred_profile in profiles and profile_to_backend(preferred_profile, profiles) == normalized_backend:
        return preferred_profile
    candidates = {
        "adb_collector": ("adb", "legacy"),
        "solox": ("solox",),
        "perfetto": ("perfetto", "solox_perfetto"),
    }.get(normalized_backend, ())
    for candidate in candidates:
        if candidate in profiles:
            return candidate
    return preferred_profile if preferred_profile in profiles else "adb"


_backend_to_profile = backend_to_profile
_profile_name_to_backend_name = profile_name_to_backend_name
_profile_to_backend = profile_to_backend
_profile_for_backend = profile_for_backend
