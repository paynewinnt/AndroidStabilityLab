"""Infrastructure adapters for the V1 execution backbone."""

from .adb import ADBCollector
from .artifact_paths import ArtifactLayout, ArtifactPathPlanner, ArtifactScope
from .command_runner import ADBCommandRunner, CommandResult, CommandRunner, SubprocessCommandRunner
from .device_adapter import (
    ADBCollectorDeviceAdapter,
    DeviceDescriptor,
    DeviceDiscoveryAdapter,
)
from .monitoring_adapter import (
    ADBCollectorMonitoringAdapter,
    build_configured_monitoring_adapter,
    build_monitoring_adapter,
    ConfiguredMonitoringAdapter,
    FileBackedMonitoringSettingsProvider,
    MonitoringAdapter,
    MonitoringBackendSettings,
    PersistedMonitoringDataProvider,
    PerfettoTraceCaptureAdapter,
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
    normalize_monitoring_backend_name,
    SoloXMonitoringAdapter,
    SUPPORTED_MONITORING_BACKENDS,
)
from .performance_thresholds import FileBackedPerformanceRiskThresholdProvider
from .rule_config import FileBackedRuleConfigProvider, default_analysis_rule_config

__all__ = [
    "ADBCollectorDeviceAdapter",
    "ADBCollectorMonitoringAdapter",
    "ADBCollector",
    "ArtifactLayout",
    "ArtifactPathPlanner",
    "ArtifactScope",
    "ADBCommandRunner",
    "build_configured_monitoring_adapter",
    "build_monitoring_adapter",
    "CommandResult",
    "CommandRunner",
    "ConfiguredMonitoringAdapter",
    "DeviceDescriptor",
    "DeviceDiscoveryAdapter",
    "FileBackedMonitoringSettingsProvider",
    "FileBackedPerformanceRiskThresholdProvider",
    "MonitoringAdapter",
    "MonitoringBackendSettings",
    "PerfettoTraceCaptureAdapter",
    "PersistedMonitoringDataProvider",
    "MonitoringSessionConfig",
    "MonitoringSessionHandle",
    "MonitoringSnapshot",
    "normalize_monitoring_backend_name",
    "SoloXMonitoringAdapter",
    "SubprocessCommandRunner",
    "SUPPORTED_MONITORING_BACKENDS",
    "FileBackedRuleConfigProvider",
    "default_analysis_rule_config",
]
