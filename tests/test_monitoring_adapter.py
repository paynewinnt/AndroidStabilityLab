from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.infrastructure.monitoring_adapter import (
    ADBCollectorMonitoringAdapter,
    ConfiguredMonitoringAdapter,
    MonitoringAdapterFactory,
    MonitoringBackendSettings,
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
    PerfettoTraceCaptureAdapter,
    SoloXMonitoringAdapter,
    build_monitoring_adapter,
    normalize_monitoring_backend_name,
)
from stability.infrastructure.monitoring_legacy_storage import LegacyStorageMixin


class _FakePerfettoProcess:
    def __init__(self, *, stdout: str = "", stderr: str = "") -> None:
        self._stdout = stdout
        self._stderr = stderr

    def wait(self, timeout: float | None = None) -> None:
        return None

    def communicate(self, timeout: float | None = None):
        return self._stdout, self._stderr


class _FakeSoloXClient:
    def collectCpu(self, **kwargs):
        return [12.5, 44.0]

    def collectMemory(self, **kwargs):
        return [256.0]

    def collectMemoryDetail(self, **kwargs):
        return {
            "java_heap": 64.0,
            "native_heap": 128.0,
            "graphics": 32.0,
        }

    def collectNetwork(self, **kwargs):
        return [1.5, 2.0]

    def collectFps(self, **kwargs):
        return [57.0, 3.0]

    def collectBattery(self, **kwargs):
        return [82.0, 31.5, 450.0, 4100.0, None]

    def collectGpu(self, **kwargs):
        return [71.0]


class _FakeSoloXDictClient:
    def collectCpu(self, **kwargs):
        return {"appCpuRate": 1.0, "systemCpuRate": 8.0}

    def collectMemory(self, **kwargs):
        return {"total": 43.34, "swap": 0.32}

    def collectMemoryDetail(self, **kwargs):
        return {}

    def collectNetwork(self, **kwargs):
        return {"send": 0.5, "recv": 1.25}

    def collectFps(self, **kwargs):
        return {"fps": 55, "jank": 2}

    def collectBattery(self, **kwargs):
        return {"level": 99, "temperature": 28.1}

    def collectGpu(self, **kwargs):
        return None


class _RecordingAdapter:
    def __init__(self, *, backend: str) -> None:
        self.backend = backend
        self.started_configs: list[MonitoringSessionConfig] = []

    def start_session(self, device_id: str, config: MonitoringSessionConfig | None = None, session_name: str | None = None):
        resolved_config = config or MonitoringSessionConfig()
        self.started_configs.append(resolved_config)
        return MonitoringSessionHandle(
            device_id=device_id,
            session_name=session_name or f"{self.backend}-session",
            config=resolved_config,
            collector=None,
            backend_name=self.backend,
        )

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        return MonitoringSnapshot(
            timestamp=handle.started_at,
            system=None,
            apps=[],
            metadata={"backend": self.backend},
        )

    def persist_snapshot(self, handle: MonitoringSessionHandle, snapshot: MonitoringSnapshot) -> bool:
        return True

    def stop_session(self, handle: MonitoringSessionHandle, status: str = "completed") -> None:
        return None


class _SnapshotAdapter(_RecordingAdapter):
    def __init__(self, *, backend: str, system=None, apps=None) -> None:
        super().__init__(backend=backend)
        self._system = system
        self._apps = apps or []

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        return MonitoringSnapshot(
            timestamp=handle.started_at,
            system=self._system,
            apps=list(self._apps),
            metadata={"backend": self.backend},
        )


def _successful_command_runner():
    def runner(command):
        normalized = tuple(str(item) for item in command)
        if "pull" in normalized:
            local_path = Path(normalized[-1])
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(b"trace-data")
            return 0, "pulled", ""
        return 0, "", ""

    return runner


class SoloXMonitoringAdapterTest(unittest.TestCase):
    def test_collect_snapshot_normalizes_solox_metrics(self) -> None:
        adapter = SoloXMonitoringAdapter(
            client_factory=lambda **kwargs: _FakeSoloXClient(),
        )
        config = MonitoringSessionConfig(
            selected_apps=(
                {
                    "package_name": "com.example.app",
                    "app_name": "Example App",
                },
            ),
            extra={
                "solox_enabled_metrics": (
                    "cpu",
                    "memory",
                    "memory_detail",
                    "network",
                    "fps",
                    "battery",
                    "gpu",
                )
            },
        )

        handle = adapter.start_session("device-1", config=config, session_name="solox-session")
        snapshot = adapter.collect_snapshot(handle)

        self.assertEqual(snapshot.metadata["backend"], "solox")
        self.assertEqual(snapshot.system["cpu_usage"], 44.0)
        self.assertEqual(snapshot.system["battery_level"], 82.0)
        self.assertEqual(snapshot.apps[0]["package_name"], "com.example.app")
        self.assertEqual(snapshot.apps[0]["cpu_usage"], 12.5)
        self.assertEqual(snapshot.apps[0]["memory_pss"], 256.0)
        self.assertEqual(snapshot.apps[0]["memory_java"], 64.0)
        self.assertEqual(snapshot.apps[0]["memory_native"], 128.0)
        self.assertEqual(snapshot.apps[0]["memory_graphics"], 32.0)
        self.assertEqual(snapshot.apps[0]["rx_bytes"], 1536.0)
        self.assertEqual(snapshot.apps[0]["tx_bytes"], 2048.0)
        self.assertEqual(snapshot.apps[0]["fps"], 57.0)
        self.assertEqual(snapshot.apps[0]["jank_frames"], 3.0)
        self.assertEqual(snapshot.apps[0]["gpu_usage"], 71.0)
        self.assertIsNotNone(snapshot.apps[0]["power_usage"])

    def test_collect_snapshot_normalizes_real_solox_dict_keys(self) -> None:
        adapter = SoloXMonitoringAdapter(
            client_factory=lambda **kwargs: _FakeSoloXDictClient(),
        )
        config = MonitoringSessionConfig(
            selected_apps=({"package_name": "com.example.app"},),
            extra={"solox_enabled_metrics": ("cpu", "memory", "network", "fps", "battery")},
        )

        handle = adapter.start_session("device-1", config=config, session_name="solox-dict-session")
        snapshot = adapter.collect_snapshot(handle)

        self.assertEqual(snapshot.metadata["backend"], "solox")
        self.assertEqual(snapshot.apps[0]["memory_pss"], 43.34)
        self.assertEqual(snapshot.apps[0]["rx_bytes"], 1280.0)
        self.assertEqual(snapshot.apps[0]["tx_bytes"], 512.0)
        self.assertEqual(snapshot.apps[0]["fps"], 55.0)
        self.assertEqual(snapshot.apps[0]["jank_frames"], 2.0)
        self.assertEqual(snapshot.system["battery_level"], 99.0)


class PerfettoTraceCaptureAdapterTest(unittest.TestCase):
    def test_collect_snapshot_returns_trace_artifact_and_normalized_stats(self) -> None:
        with TemporaryDirectory() as tempdir:
            adapter = PerfettoTraceCaptureAdapter(
                process_factory=lambda command, config_text: _FakePerfettoProcess(),
                command_runner=_successful_command_runner(),
            )
            config = MonitoringSessionConfig(
                sample_interval=1.0,
                extra={
                    "runtime_monitoring_dir": tempdir,
                    "perfetto_duration_ms": 5000,
                },
            )

            handle = adapter.start_session("device-1", config=config, session_name="session-a")
            snapshot = adapter.collect_snapshot(handle)

            self.assertEqual(snapshot.metadata["backend"], "perfetto")
            self.assertEqual(snapshot.metadata["perfetto"]["trace_status"], "captured")
            self.assertEqual(snapshot.metadata["perfetto"]["capture_mode"], "remote_file")
            self.assertFalse(snapshot.metadata["best_effort_degraded"])
            self.assertTrue(snapshot.metadata["trace_artifact_path"].endswith("session-a.perfetto-trace"))
            self.assertEqual(
                snapshot.metadata["normalized_stats"]["trace_size_bytes"],
                len(b"trace-data"),
            )
            self.assertEqual(snapshot.system["perfetto_duration_ms"], 5000)

    def test_collect_snapshot_marks_missing_binary_as_best_effort_degraded(self) -> None:
        with TemporaryDirectory() as tempdir:
            adapter = PerfettoTraceCaptureAdapter(
                process_factory=lambda command, config_text: _FakePerfettoProcess(
                    stderr="/system/bin/sh: perfetto: not found",
                ),
                command_runner=lambda command: (1, "", "remote trace missing"),
            )
            config = MonitoringSessionConfig(
                extra={
                    "runtime_monitoring_dir": tempdir,
                    "perfetto_duration_ms": 3000,
                },
            )

            handle = adapter.start_session("device-1", config=config, session_name="session-b")
            snapshot = adapter.collect_snapshot(handle)

            self.assertEqual(snapshot.metadata["perfetto"]["trace_status"], "binary_missing")
            self.assertTrue(snapshot.metadata["best_effort_degraded"])
            self.assertEqual(snapshot.metadata["trace_artifact_path"], "")
            self.assertEqual(snapshot.metadata["normalized_stats"]["trace_size_bytes"], None)

    def test_collect_snapshot_uses_stdout_fallback_when_remote_pull_fails(self) -> None:
        with TemporaryDirectory() as tempdir:
            adapter = PerfettoTraceCaptureAdapter(
                process_factory=lambda command, config_text: _FakePerfettoProcess(
                    stdout=b"\x0a\x08trace-bytes-from-stdout".decode("latin-1"),
                    stderr="",
                ),
                command_runner=lambda command: (1, "", "remote object missing"),
            )
            config = MonitoringSessionConfig(
                extra={
                    "runtime_monitoring_dir": tempdir,
                    "perfetto_duration_ms": 3000,
                },
            )

            handle = adapter.start_session("device-1", config=config, session_name="session-stdout")
            snapshot = adapter.collect_snapshot(handle)

            self.assertEqual(snapshot.metadata["perfetto"]["trace_status"], "captured")
            self.assertEqual(snapshot.metadata["perfetto"]["capture_mode"], "stdout_fallback")
            self.assertFalse(snapshot.metadata["best_effort_degraded"])
            trace_path = Path(snapshot.metadata["trace_artifact_path"])
            self.assertTrue(trace_path.exists())
            self.assertEqual(trace_path.read_bytes(), b"\x0a\x08trace-bytes-from-stdout")

    def test_collect_snapshot_recaptures_stdout_when_remote_file_output_is_blocked(self) -> None:
        with TemporaryDirectory() as tempdir:
            started_commands = []

            def process_factory(command, config_text):
                started_commands.append(tuple(command))
                if len(started_commands) == 1:
                    return _FakePerfettoProcess(stderr="Failed to open remote trace file")
                return _FakePerfettoProcess(stdout=b"\x0a\x08recaptured-trace".decode("latin-1"))

            adapter = PerfettoTraceCaptureAdapter(
                process_factory=process_factory,
                command_runner=lambda command: (1, "", "remote object missing"),
            )
            config = MonitoringSessionConfig(
                extra={
                    "runtime_monitoring_dir": tempdir,
                    "perfetto_duration_ms": 3000,
                },
            )

            handle = adapter.start_session("device-1", config=config, session_name="session-recapture")
            snapshot = adapter.collect_snapshot(handle)

            self.assertEqual(len(started_commands), 2)
            self.assertEqual(started_commands[0][-1], "/data/misc/perfetto-traces/session-recapture.perfetto-trace")
            self.assertEqual(started_commands[1][-1], "-")
            self.assertEqual(snapshot.metadata["perfetto"]["trace_status"], "captured")
            self.assertEqual(snapshot.metadata["perfetto"]["capture_mode"], "stdout_fallback")
            trace_path = Path(snapshot.metadata["trace_artifact_path"])
            self.assertEqual(trace_path.read_bytes(), b"\x0a\x08recaptured-trace")

    def test_build_monitoring_adapter_supports_perfetto_backend_name(self) -> None:
        adapter, resolved_backend = build_monitoring_adapter(requested_backend="perfetto")

        self.assertIsInstance(adapter, ConfiguredMonitoringAdapter)
        self.assertEqual(resolved_backend, "perfetto")
        self.assertEqual(normalize_monitoring_backend_name("trace"), "perfetto")

    def test_default_trace_config_can_enable_android_network_packets(self) -> None:
        config_text = PerfettoTraceCaptureAdapter._default_trace_config(
            device_id="device-1",
            session_name="trace-session",
            config=MonitoringSessionConfig(
                selected_apps=({"package_name": "com.example.app"},),
                sample_interval=2.0,
                extra={
                    "perfetto_duration_ms": 4000,
                    "perfetto_enable_network_packets": True,
                },
            ),
        )

        self.assertIn('name: "android.network_packets"', config_text)
        self.assertIn("network_packet_trace_config", config_text)
        self.assertIn("poll_ms: 2000", config_text)
        self.assertNotIn("cpufreq_period_ms", config_text)


class MonitoringAdapterBuildTest(unittest.TestCase):
    def test_legacy_storage_status_mapping_accepts_execution_statuses(self) -> None:
        self.assertEqual(LegacyStorageMixin._legacy_session_status("success"), "completed")
        self.assertEqual(LegacyStorageMixin._legacy_session_status("failed"), "error")
        self.assertEqual(LegacyStorageMixin._legacy_session_status("cancelled"), "cancelled")

    def test_legacy_monitoring_adapter_factory_import_contract(self) -> None:
        self.assertIs(MonitoringAdapterFactory.build_monitoring_adapter, build_monitoring_adapter)

    def test_build_monitoring_adapter_auto_uses_configured_backend(self) -> None:
        adapter, resolved_backend = build_monitoring_adapter(
            requested_backend="auto",
            settings=MonitoringBackendSettings(backend="adb_collector"),
        )

        self.assertIsInstance(adapter, ADBCollectorMonitoringAdapter)
        self.assertEqual(resolved_backend, "adb_collector")

    def test_build_monitoring_adapter_solox_uses_configured_wrapper_when_fallback_enabled(self) -> None:
        adapter, resolved_backend = build_monitoring_adapter(
            requested_backend="solox",
            settings=MonitoringBackendSettings(
                backend="solox",
                fallback_backend="adb_collector",
            ),
        )

        self.assertIsInstance(adapter, ConfiguredMonitoringAdapter)
        self.assertEqual(resolved_backend, "solox")

    def test_configured_adapter_can_force_backend_profile_over_task_profile(self) -> None:
        adb_adapter = _RecordingAdapter(backend="adb_collector")
        solox_adapter = _RecordingAdapter(backend="solox")
        perfetto_adapter = _RecordingAdapter(backend="perfetto")
        adapter = ConfiguredMonitoringAdapter(
            default_profile="adb",
            profiles={
                "adb": {
                    "metrics_backend": "adb_collector",
                    "trace_backend": "",
                    "metadata": {},
                },
                "solox": {
                    "metrics_backend": "solox",
                    "trace_backend": "",
                    "metadata": {},
                },
                "perfetto": {
                    "metrics_backend": "adb_collector",
                    "trace_backend": "perfetto",
                    "metadata": {},
                },
            },
            legacy_adapter=adb_adapter,
            solox_adapter=solox_adapter,
            perfetto_adapter=perfetto_adapter,
            forced_profile_name="perfetto",
        )

        handle = adapter.start_session(
            "device-1",
            config=MonitoringSessionConfig(profile_name="solox"),
            session_name="forced-profile",
        )

        self.assertEqual(handle.state["profile_name"], "perfetto")
        self.assertEqual(handle.state["metrics_backend"], "adb_collector")
        self.assertEqual(handle.state["trace_backend"], "perfetto")
        self.assertEqual(len(solox_adapter.started_configs), 0)
        self.assertEqual(len(adb_adapter.started_configs), 1)
        self.assertEqual(len(perfetto_adapter.started_configs), 1)

    def test_configured_adapter_can_skip_trace_snapshot_for_periodic_samples(self) -> None:
        adb_adapter = _RecordingAdapter(backend="adb_collector")
        perfetto_adapter = _RecordingAdapter(backend="perfetto")
        adapter = ConfiguredMonitoringAdapter(
            default_profile="perfetto",
            profiles={
                "perfetto": {
                    "metrics_backend": "adb_collector",
                    "trace_backend": "perfetto",
                    "metadata": {},
                },
            },
            legacy_adapter=adb_adapter,
            perfetto_adapter=perfetto_adapter,
        )

        handle = adapter.start_session("device-1", session_name="periodic-sample")
        handle.state["skip_trace_snapshot"] = True
        periodic_snapshot = adapter.collect_snapshot(handle)
        handle.state.pop("skip_trace_snapshot", None)
        final_snapshot = adapter.collect_snapshot(handle)

        self.assertEqual(periodic_snapshot.metadata["backend"], "adb_collector")
        self.assertEqual(final_snapshot.metadata["backend"], "perfetto")

    def test_configured_adapter_enriches_solox_with_adb_fallback_metrics(self) -> None:
        solox_adapter = _SnapshotAdapter(
            backend="solox",
            system={"cpu_usage": 12.0},
            apps=[{"package_name": "com.example.app", "cpu_usage": 3.0, "memory_pss": 100.0}],
        )
        adb_adapter = _SnapshotAdapter(
            backend="adb_collector",
            system={"cpu_usage": 80.0, "battery_level": 90.0},
            apps=[
                {
                    "package_name": "com.example.app",
                    "cpu_usage": 99.0,
                    "memory_java": 20.0,
                    "memory_native": 30.0,
                    "gpu_p95_ms": 6.0,
                    "gpu_p99_ms": 9.0,
                    "jank_percent": 4.0,
                }
            ],
        )
        adapter = ConfiguredMonitoringAdapter(
            default_profile="solox",
            profiles={"solox": {"metrics_backend": "solox", "trace_backend": "", "metadata": {}}},
            legacy_adapter=adb_adapter,
            solox_adapter=solox_adapter,
        )

        handle = adapter.start_session(
            "device-1",
            config=MonitoringSessionConfig(selected_apps=({"package_name": "com.example.app"},)),
            session_name="solox-with-fallback",
        )
        snapshot = adapter.collect_snapshot(handle)

        self.assertEqual(snapshot.metadata["backend"], "solox")
        self.assertTrue(snapshot.metadata["fallback_metric_enriched"])
        self.assertEqual(snapshot.system["cpu_usage"], 12.0)
        self.assertEqual(snapshot.system["battery_level"], 90.0)
        self.assertEqual(snapshot.apps[0]["cpu_usage"], 3.0)
        self.assertEqual(snapshot.apps[0]["memory_pss"], 100.0)
        self.assertEqual(snapshot.apps[0]["memory_java"], 20.0)
        self.assertEqual(snapshot.apps[0]["memory_native"], 30.0)
        self.assertEqual(snapshot.apps[0]["gpu_p95_ms"], 6.0)
        self.assertEqual(snapshot.apps[0]["gpu_p99_ms"], 9.0)
        self.assertEqual(snapshot.apps[0]["jank_percent"], 4.0)


if __name__ == "__main__":
    unittest.main()
