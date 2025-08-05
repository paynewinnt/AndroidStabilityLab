"""Profile-aware monitoring adapter composition."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Mapping, Optional

from stability.infrastructure.monitoring_adb_adapter import ADBCollectorMonitoringAdapter
from stability.infrastructure.monitoring_base import MonitoringAdapter
from stability.infrastructure.monitoring_config import _DEFAULT_MONITORING_PROFILES
from stability.infrastructure.monitoring_models import (
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
)
from stability.infrastructure.monitoring_perfetto_adapter import PerfettoTraceCaptureAdapter
from stability.infrastructure.monitoring_solox_adapter import SoloXMonitoringAdapter
from stability.infrastructure.monitoring_utils import deep_merge_mapping, utcnow

logger = logging.getLogger(__name__)


class ConfiguredMonitoringAdapter(MonitoringAdapter):
    """Route task monitoring profiles to one metrics backend plus optional Perfetto sidecar."""

    def __init__(
        self,
        *,
        default_profile: str = "adb",
        profiles: Mapping[str, Mapping[str, Any]] | None = None,
        legacy_adapter: MonitoringAdapter | None = None,
        solox_adapter: MonitoringAdapter | None = None,
        perfetto_adapter: MonitoringAdapter | None = None,
        forced_profile_name: str = "",
    ) -> None:
        self._default_profile = default_profile or "adb"
        self._profiles = {
            key: dict(value)
            for key, value in (profiles or _DEFAULT_MONITORING_PROFILES).items()
        }
        self._legacy_adapter = legacy_adapter or ADBCollectorMonitoringAdapter()
        self._solox_adapter = solox_adapter or SoloXMonitoringAdapter()
        self._perfetto_adapter = perfetto_adapter or PerfettoTraceCaptureAdapter()
        self._forced_profile_name = str(forced_profile_name or "").strip()

    def start_session(
        self,
        device_id: str,
        config: Optional[MonitoringSessionConfig] = None,
        session_name: Optional[str] = None,
    ) -> MonitoringSessionHandle:
        session_config = config or MonitoringSessionConfig()
        resolved_profile = self._resolve_profile_name(session_config)
        profile = dict(self._profiles.get(resolved_profile, self._profiles.get(self._default_profile, {})))
        resolved_extra = deep_merge_mapping(profile.get("metadata", {}), session_config.extra)
        resolved_config = replace(
            session_config,
            profile_name=resolved_profile,
            extra=resolved_extra,
        )
        metrics_backend = str(profile.get("metrics_backend", "adb_collector") or "adb_collector")
        trace_backend = str(profile.get("trace_backend", "") or "")
        warnings: list[str] = []

        primary_adapter = self._adapter_for_backend(metrics_backend)
        metrics_handle = None
        if primary_adapter is not None:
            try:
                metrics_handle = primary_adapter.start_session(
                    device_id=device_id,
                    config=resolved_config,
                    session_name=session_name,
                )
            except Exception as exc:
                warnings.append(
                    f"metrics backend '{metrics_backend}' unavailable, falling back to adb_collector: {exc}"
                )
                primary_adapter = self._legacy_adapter
                metrics_backend = "adb_collector"
                metrics_handle = primary_adapter.start_session(
                    device_id=device_id,
                    config=resolved_config,
                    session_name=session_name,
                )

        fallback_adapter = None
        fallback_handle = None
        if metrics_backend != "adb_collector":
            try:
                fallback_adapter = self._legacy_adapter
                fallback_handle = fallback_adapter.start_session(
                    device_id=device_id,
                    config=replace(resolved_config, persist_to_database=False),
                    session_name=session_name,
                )
            except Exception as exc:
                warnings.append(f"adb_collector fallback monitoring backend unavailable: {exc}")

        trace_adapter = None
        trace_handle = None
        if trace_backend:
            trace_adapter = self._adapter_for_backend(trace_backend)
            if trace_adapter is not None:
                try:
                    trace_handle = trace_adapter.start_session(
                        device_id=device_id,
                        config=resolved_config,
                        session_name=session_name or (metrics_handle.session_name if metrics_handle is not None else None),
                    )
                except Exception as exc:
                    warnings.append(f"trace backend '{trace_backend}' unavailable: {exc}")

        resolved_session_name = (
            metrics_handle.session_name
            if metrics_handle is not None
            else (trace_handle.session_name if trace_handle is not None else (session_name or f"monitor_{device_id}"))
        )
        return MonitoringSessionHandle(
            device_id=device_id,
            session_name=resolved_session_name,
            config=resolved_config,
            collector=None,
            session_id=getattr(metrics_handle, "session_id", None),
            started_at=getattr(metrics_handle, "started_at", utcnow()),
            persisted=bool(getattr(metrics_handle, "persisted", False)),
            state={
                "profile_name": resolved_profile,
                "metrics_backend": metrics_backend,
                "metrics_adapter": primary_adapter,
                "metrics_handle": metrics_handle,
                "fallback_adapter": fallback_adapter,
                "fallback_handle": fallback_handle,
                "trace_backend": trace_backend,
                "trace_adapter": trace_adapter,
                "trace_handle": trace_handle,
                "warnings": warnings,
            },
            backend_name=metrics_backend,
        )

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        metrics_adapter = handle.state.get("metrics_adapter")
        metrics_handle = handle.state.get("metrics_handle")
        fallback_adapter = handle.state.get("fallback_adapter")
        fallback_handle = handle.state.get("fallback_handle")
        warnings = list(handle.state.get("warnings", []) or [])
        if metrics_adapter is None or metrics_handle is None:
            snapshot = MonitoringSnapshot(timestamp=utcnow(), system=None, apps=[], metadata={})
        else:
            try:
                snapshot = metrics_adapter.collect_snapshot(metrics_handle)
            except Exception as exc:
                if fallback_adapter is None or fallback_handle is None:
                    raise
                warnings.append(
                    f"metrics backend '{handle.state.get('metrics_backend', 'unknown')}' snapshot failed; used adb_collector fallback: {exc}"
                )
                snapshot = fallback_adapter.collect_snapshot(fallback_handle)

        system_payload = dict(snapshot.system or {})
        metadata_payload = dict(snapshot.metadata or {})
        metadata_payload.setdefault("backend", str(handle.state.get("metrics_backend", "") or "adb_collector"))
        metadata_payload["profile_name"] = str(handle.state.get("profile_name", "") or handle.config.profile_name)
        trace_adapter = handle.state.get("trace_adapter")
        trace_handle = handle.state.get("trace_handle")
        if trace_adapter is not None and trace_handle is not None:
            try:
                trace_snapshot = trace_adapter.collect_snapshot(trace_handle)
                system_payload.update(dict(trace_snapshot.system or {}))
                artifacts = list(metadata_payload.get("artifacts", []) or [])
                artifacts.extend(list(dict(trace_snapshot.metadata or {}).get("artifacts", []) or []))
                metadata_payload = deep_merge_mapping(metadata_payload, dict(trace_snapshot.metadata or {}))
                if artifacts:
                    metadata_payload["artifacts"] = artifacts
            except Exception as exc:
                warnings.append(f"trace backend '{handle.state.get('trace_backend', 'unknown')}' snapshot failed: {exc}")
        if warnings:
            metadata_payload["warnings"] = warnings
        return MonitoringSnapshot(
            timestamp=snapshot.timestamp,
            system=system_payload or None,
            apps=list(snapshot.apps),
            metadata=metadata_payload,
        )

    def persist_snapshot(self, handle: MonitoringSessionHandle, snapshot: MonitoringSnapshot) -> bool:
        metrics_adapter = handle.state.get("metrics_adapter")
        metrics_handle = handle.state.get("metrics_handle")
        if metrics_adapter is None or metrics_handle is None:
            return False
        return bool(metrics_adapter.persist_snapshot(metrics_handle, snapshot))

    def stop_session(self, handle: MonitoringSessionHandle, status: str = "completed") -> None:
        for adapter_key, handle_key in (
            ("metrics_adapter", "metrics_handle"),
            ("fallback_adapter", "fallback_handle"),
            ("trace_adapter", "trace_handle"),
        ):
            adapter = handle.state.get(adapter_key)
            child_handle = handle.state.get(handle_key)
            if adapter is None or child_handle is None:
                continue
            try:
                adapter.stop_session(child_handle, status=status)
            except Exception as exc:
                logger.warning("Failed to stop %s for %s: %s", adapter_key, handle.device_id, exc)

    def _resolve_profile_name(self, config: MonitoringSessionConfig) -> str:
        if self._forced_profile_name and self._forced_profile_name in self._profiles:
            return self._forced_profile_name
        requested = str(config.profile_name or dict(config.extra).get("monitoring_profile", "") or "").strip()
        if requested and requested in self._profiles:
            return requested
        return self._default_profile

    def _adapter_for_backend(self, backend_name: str) -> MonitoringAdapter | None:
        normalized = str(backend_name or "").strip().lower()
        if normalized in {"", "none"}:
            return None
        if normalized in {"legacy", "legacy_adb", "adb", "adb_collector"}:
            return self._legacy_adapter
        if normalized == "solox":
            return self._solox_adapter
        if normalized == "perfetto":
            return self._perfetto_adapter
        raise ValueError(f"Unsupported monitoring backend: {backend_name}")
