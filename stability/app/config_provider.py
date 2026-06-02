from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from stability.app.evidence_retention import EvidenceRetentionPolicy
from stability.app.platform_health_service import PlatformHealthThresholds
from stability.app.quality_gate_service import QualityGatePolicy
from stability.infrastructure import (
    FileBackedMonitoringSettingsProvider,
    FileBackedPerformanceRiskThresholdProvider,
    MonitoringBackendSettings,
)


@dataclass(frozen=True)
class RuntimePathsConfig:
    root: Path
    analysis_snapshots: Path
    analysis_review_reports: Path
    admission_cases: Path
    collaboration: Path
    integration_outbox: Path
    quality_gates: Path
    release_submissions: Path
    unattended_runner: Path
    apks: Path


@dataclass(frozen=True)
class OutboxConfig:
    root_dir: Path
    retry_delay_seconds: int
    delivery_interval_seconds: int | None
    max_retry_delay_seconds: int
    dead_letter_threshold: int
    retry_alert_threshold: int


@dataclass(frozen=True)
class WebConfig:
    host: str
    port: int
    allow_remote_access: bool
    portal_mode: str
    public_base_url: str
    deployment_label: str
    sync_devices_on_start: bool


@dataclass(frozen=True)
class DeviceConfig:
    adb_timeout_seconds: int
    adb_retry_count: int
    max_parallel_commands: int
    sync_on_web_start: bool


@dataclass(frozen=True)
class ThresholdsConfig:
    performance_risk_config_path: Path
    monitoring_thresholds: Mapping[str, Any]


class ConfigProvider:
    """Central config reader with explicit override > env > file > default priority."""

    def __init__(
        self,
        *,
        config_dir: str | Path = "config",
        env: Mapping[str, str] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        self._env = dict(os.environ if env is None else env)
        self._overrides = dict(overrides or {})
        resolved_config_dir = self._overrides.get(
            "config.dir",
            self._env.get("ASL_CONFIG_DIR", config_dir),
        )
        self._config_dir = Path(str(resolved_config_dir or "config"))
        self._platform_payload = self._load_json(self._config_dir / "platform.json")
        self._monitoring_payload = self._load_json(self._config_dir / "monitoring.json")
        self._performance_payload = self._load_json(self._config_dir / "performance.json")

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    def runtime_paths(self) -> RuntimePathsConfig:
        root = self._path_value(
            "runtime.root",
            "ASL_RUNTIME_ROOT",
            self._from_platform("runtime", "root"),
            Path("runtime"),
        )

        def child(key: str, default_name: str) -> Path:
            configured = self._path_value(
                f"runtime.{key}",
                f"ASL_RUNTIME_{key.upper()}",
                self._from_platform("runtime", key),
                root / default_name,
            )
            return configured if configured.is_absolute() else configured

        return RuntimePathsConfig(
            root=root,
            analysis_snapshots=child("analysis_snapshots", "analysis_snapshots"),
            analysis_review_reports=child("analysis_review_reports", "analysis_review_reports"),
            admission_cases=child("admission_cases", "admission_cases"),
            collaboration=child("collaboration", "collaboration"),
            integration_outbox=child("integration_outbox", "integration_outbox"),
            quality_gates=child("quality_gates", "quality_gates"),
            release_submissions=child("release_submissions", "release_submissions"),
            unattended_runner=child("unattended_runner", "unattended_runner"),
            apks=child("apks", "apks"),
        )

    def monitoring_settings(
        self,
        *,
        requested_backend: str | None = None,
        config_path: str | Path | None = None,
    ) -> MonitoringBackendSettings:
        path = self.monitoring_config_path(config_path)
        settings = FileBackedMonitoringSettingsProvider(path).load()
        configured_backend = None if config_path is not None else self._from_monitoring("monitoring", "backend")
        configured_fallback_backend = (
            None if config_path is not None else self._from_monitoring("monitoring", "fallback_backend")
        )
        requested_backend_default = settings.backend
        if requested_backend and str(requested_backend).strip().lower() != "auto":
            requested_backend_default = requested_backend
        backend = self._string_value(
            "monitoring.backend",
            "ASL_MONITORING_BACKEND",
            configured_backend,
            requested_backend_default,
        )
        fallback_backend = self._string_value(
            "monitoring.fallback_backend",
            "ASL_MONITORING_FALLBACK_BACKEND",
            configured_fallback_backend,
            settings.fallback_backend,
        )
        return MonitoringBackendSettings(
            backend=backend,
            fallback_backend=fallback_backend,
            config_path=str(path),
            registry=settings.registry,
            solox=settings.solox,
        )

    def monitoring_config_path(self, explicit: str | Path | None = None) -> Path:
        return self._path_value(
            "monitoring.config_path",
            "ASL_MONITORING_CONFIG",
            explicit or self._from_platform("monitoring", "config_path"),
            self._config_dir / "monitoring.json",
        )

    def performance_risk_thresholds(self, *, config_path: str | Path | None = None):
        path = self.thresholds(config_path=config_path).performance_risk_config_path
        return FileBackedPerformanceRiskThresholdProvider(path).load()

    def thresholds(self, *, config_path: str | Path | None = None) -> ThresholdsConfig:
        path = self._path_value(
            "thresholds.performance_risk_config_path",
            "ASL_PERFORMANCE_RISK_THRESHOLDS_CONFIG",
            config_path or self._from_platform("thresholds", "performance_risk_config_path"),
            self._config_dir / "performance_risk_thresholds.json",
        )
        return ThresholdsConfig(
            performance_risk_config_path=path,
            monitoring_thresholds=dict(self._monitoring_payload.get("thresholds", {}) or {}),
        )

    def platform_health(self) -> PlatformHealthThresholds:
        """平台健康 SLA 阈值，从 ``platform.json`` 的 ``platform_health`` 段叠加到默认值上。"""
        section = self._platform_payload.get("platform_health", {})
        if not isinstance(section, Mapping):
            section = {}
        payload = dict(section)
        env_keys = {
            "alert_min_severity": "ASL_PLATFORM_HEALTH_ALERT_MIN_SEVERITY",
            "trend_window_hours": "ASL_PLATFORM_HEALTH_TREND_WINDOW_HOURS",
            "device_online_rate_min": "ASL_PLATFORM_HEALTH_DEVICE_ONLINE_RATE_MIN",
            "run_failure_rate_max": "ASL_PLATFORM_HEALTH_RUN_FAILURE_RATE_MAX",
            "instance_failure_rate_max": "ASL_PLATFORM_HEALTH_INSTANCE_FAILURE_RATE_MAX",
            "artifact_failure_rate_max": "ASL_PLATFORM_HEALTH_ARTIFACT_FAILURE_RATE_MAX",
            "outbox_dead_letter_max": "ASL_PLATFORM_HEALTH_OUTBOX_DEAD_LETTER_MAX",
        }
        for key, env_key in env_keys.items():
            override_key = f"platform_health.{key}"
            if override_key in self._overrides:
                payload[key] = self._overrides[override_key]
            elif env_key in self._env:
                payload[key] = self._env[env_key]
        return PlatformHealthThresholds.from_mapping(payload)

    def quality_gate_policy(self) -> QualityGatePolicy:
        """质量门禁策略，从 ``platform.json`` 的 ``quality_gate`` 段叠加到默认值上。"""
        section = self._platform_payload.get("quality_gate", {})
        if not isinstance(section, Mapping):
            section = {}
        payload = dict(section)
        env_keys = {
            "review_failures_max": "ASL_QUALITY_GATE_REVIEW_FAILURES_MAX",
            "golden_suite_failures_max": "ASL_QUALITY_GATE_GOLDEN_SUITE_FAILURES_MAX",
            "review_warnings_max": "ASL_QUALITY_GATE_REVIEW_WARNINGS_MAX",
            "high_risk_family_max": "ASL_QUALITY_GATE_HIGH_RISK_FAMILY_MAX",
            "high_risk_family_high_severity_min": "ASL_QUALITY_GATE_HIGH_RISK_FAMILY_HIGH_SEVERITY_MIN",
            "min_review_snapshot_count": "ASL_QUALITY_GATE_MIN_REVIEW_SNAPSHOT_COUNT",
            "min_golden_suite_case_count": "ASL_QUALITY_GATE_MIN_GOLDEN_SUITE_CASE_COUNT",
            "performance_risk_max": "ASL_QUALITY_GATE_PERFORMANCE_RISK_MAX",
            "performance_worsened_high_count": "ASL_QUALITY_GATE_PERFORMANCE_WORSENED_HIGH_COUNT",
        }
        for key, env_key in env_keys.items():
            override_key = f"quality_gate.{key}"
            if override_key in self._overrides:
                payload[key] = self._overrides[override_key]
            elif env_key in self._env:
                payload[key] = self._env[env_key]
        if "quality_gate.rule_version" in self._overrides:
            payload["rule_version"] = self._overrides["quality_gate.rule_version"]
        elif "ASL_QUALITY_GATE_RULE_VERSION" in self._env:
            payload["rule_version"] = self._env["ASL_QUALITY_GATE_RULE_VERSION"]
        return QualityGatePolicy.from_mapping(payload)

    def evidence_retention(self) -> EvidenceRetentionPolicy:
        """证据保留策略，从 ``platform.json`` 的 ``evidence_retention`` 段叠加到默认策略上。"""
        section = self._platform_payload.get("evidence_retention", {})
        if not isinstance(section, Mapping):
            section = {}
        return EvidenceRetentionPolicy.from_mapping(section)

    def outbox(self) -> OutboxConfig:
        runtime = self.runtime_paths()
        return OutboxConfig(
            root_dir=self._path_value(
                "outbox.root_dir",
                "ASL_OUTBOX_ROOT",
                self._from_platform("outbox", "root_dir"),
                runtime.integration_outbox,
            ),
            retry_delay_seconds=self._int_value(
                "outbox.retry_delay_seconds",
                "ASL_OUTBOX_RETRY_DELAY_SECONDS",
                self._from_platform("outbox", "retry_delay_seconds"),
                300,
            ),
            delivery_interval_seconds=self._optional_int_value(
                "outbox.delivery_interval_seconds",
                "ASL_OUTBOX_DELIVERY_INTERVAL_SECONDS",
                self._from_platform("outbox", "delivery_interval_seconds"),
            ),
            max_retry_delay_seconds=self._int_value(
                "outbox.max_retry_delay_seconds",
                "ASL_OUTBOX_MAX_RETRY_DELAY_SECONDS",
                self._from_platform("outbox", "max_retry_delay_seconds"),
                3600,
            ),
            dead_letter_threshold=self._int_value(
                "outbox.dead_letter_threshold",
                "ASL_OUTBOX_DEAD_LETTER_THRESHOLD",
                self._from_platform("outbox", "dead_letter_threshold"),
                5,
            ),
            retry_alert_threshold=self._int_value(
                "outbox.retry_alert_threshold",
                "ASL_OUTBOX_RETRY_ALERT_THRESHOLD",
                self._from_platform("outbox", "retry_alert_threshold"),
                3,
            ),
        )

    def web(self) -> WebConfig:
        return WebConfig(
            host=self._string_value("web.host", "ASL_WEB_HOST", self._from_platform("web", "host"), "127.0.0.1"),
            port=self._int_value("web.port", "ASL_WEB_PORT", self._from_platform("web", "port"), 8030),
            allow_remote_access=self._bool_value(
                "web.allow_remote_access",
                "ASL_WEB_ALLOW_REMOTE_ACCESS",
                self._from_platform("web", "allow_remote_access"),
                False,
            ),
            portal_mode=self._string_value(
                "web.portal_mode",
                "ASL_WEB_PORTAL_MODE",
                self._from_platform("web", "portal_mode"),
                "local_ops_console",
            ),
            public_base_url=self._string_value(
                "web.public_base_url",
                "ASL_WEB_PUBLIC_BASE_URL",
                self._from_platform("web", "public_base_url"),
                "",
            ),
            deployment_label=self._string_value(
                "web.deployment_label",
                "ASL_WEB_DEPLOYMENT_LABEL",
                self._from_platform("web", "deployment_label"),
                "",
            ),
            sync_devices_on_start=self._bool_value(
                "web.sync_devices_on_start",
                "ASL_WEB_SYNC_DEVICES_ON_START",
                self._from_platform("web", "sync_devices_on_start"),
                False,
            ),
        )

    def device(self) -> DeviceConfig:
        monitoring_adb = dict(self._monitoring_payload.get("adb", {}) or {})
        return DeviceConfig(
            adb_timeout_seconds=self._int_value(
                "device.adb_timeout_seconds",
                "ASL_DEVICE_ADB_TIMEOUT_SECONDS",
                self._from_platform("device", "adb_timeout_seconds"),
                int(self._performance_payload.get("adb_timeout", monitoring_adb.get("timeout", 10)) or 10),
            ),
            adb_retry_count=self._int_value(
                "device.adb_retry_count",
                "ASL_DEVICE_ADB_RETRY_COUNT",
                self._from_platform("device", "adb_retry_count"),
                int(self._performance_payload.get("adb_retry_count", monitoring_adb.get("retry_count", 3)) or 3),
            ),
            max_parallel_commands=self._int_value(
                "device.max_parallel_commands",
                "ASL_DEVICE_MAX_PARALLEL_COMMANDS",
                self._from_platform("device", "max_parallel_commands"),
                int(self._performance_payload.get("max_parallel_commands", 6) or 6),
            ),
            sync_on_web_start=self._bool_value(
                "device.sync_on_web_start",
                "ASL_DEVICE_SYNC_ON_WEB_START",
                self._from_platform("device", "sync_on_web_start"),
                False,
            ),
        )

    def _from_platform(self, section: str, key: str) -> Any:
        return self._nested_get(self._platform_payload, section, key)

    def _from_monitoring(self, section: str, key: str) -> Any:
        return self._nested_get(self._monitoring_payload, section, key)

    def _raw_value(self, override_key: str, env_key: str, configured: Any, default: Any) -> Any:
        if override_key in self._overrides:
            return self._overrides[override_key]
        if env_key in self._env:
            return self._env[env_key]
        if configured not in (None, ""):
            return configured
        return default

    def _string_value(self, override_key: str, env_key: str, configured: Any, default: str) -> str:
        return str(self._raw_value(override_key, env_key, configured, default) or "").strip()

    def _int_value(self, override_key: str, env_key: str, configured: Any, default: int) -> int:
        raw = self._raw_value(override_key, env_key, configured, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return int(default)

    def _optional_int_value(self, override_key: str, env_key: str, configured: Any) -> int | None:
        raw = self._raw_value(override_key, env_key, configured, None)
        if raw in (None, ""):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _bool_value(self, override_key: str, env_key: str, configured: Any, default: bool) -> bool:
        raw = self._raw_value(override_key, env_key, configured, default)
        if isinstance(raw, bool):
            return raw
        value = str(raw or "").strip().lower()
        if value in {"1", "true", "yes", "y", "on"}:
            return True
        if value in {"0", "false", "no", "n", "off"}:
            return False
        return bool(default)

    def _path_value(self, override_key: str, env_key: str, configured: Any, default: str | Path) -> Path:
        raw = self._raw_value(override_key, env_key, configured, default)
        return Path(str(raw or default))

    @staticmethod
    def _nested_get(payload: Mapping[str, Any], section: str, key: str) -> Any:
        section_payload = payload.get(section, {})
        if not isinstance(section_payload, Mapping):
            return None
        return section_payload.get(key)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}
