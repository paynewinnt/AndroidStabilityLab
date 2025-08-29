from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from stability.app import DoctorService
from stability.infrastructure.command_runner import CommandResult


class FakeCommandRunner:
    def __init__(self, results: dict[tuple[str, ...], CommandResult]) -> None:
        self.results = results

    def run(self, command, *, timeout_seconds=None, timeout=None):  # noqa: ANN001
        del timeout_seconds, timeout
        return self.results.get(tuple(command), CommandResult(returncode=127, stderr="missing command"))


class DoctorServiceTest(unittest.TestCase):
    def test_run_reports_core_environment_checks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "monitoring.json").write_text("{}", encoding="utf-8")
            runner = FakeCommandRunner(
                {
                    ("adb", "version"): CommandResult(returncode=0, stdout="Android Debug Bridge version 1.0.41"),
                    ("adb", "devices", "-l"): CommandResult(
                        returncode=0,
                        stdout="List of devices attached\n192.168.31.99:5555 device product:test\n",
                    ),
                    ("adb", "devices"): CommandResult(
                        returncode=0,
                        stdout="List of devices attached\n192.168.31.99:5555 device\n",
                    ),
                }
            )

            with patch.object(DoctorService, "_python_dependency_status", return_value=[]):
                report = DoctorService(
                    runtime_root=root / "runtime",
                    config_dir=config_dir,
                    outbox_root=root / "runtime" / "integration_outbox",
                    web_port=1,
                    command_runner=runner,
                ).run()

        names = {item.name: item for item in report.checks}
        self.assertTrue(report.ok)
        self.assertEqual(names["python"].status, "ok")
        self.assertEqual(names["adb_available"].status, "ok")
        self.assertEqual(names["adb_devices"].status, "ok")
        self.assertIn(names["tcp_devices"].status, {"ok", "warn"})
        self.assertEqual(names["runtime_permissions"].status, "ok")
        self.assertEqual(names["config_json"].status, "ok")

    def test_invalid_config_json_is_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "broken.json").write_text("{", encoding="utf-8")
            runner = FakeCommandRunner(
                {
                    ("adb", "version"): CommandResult(returncode=0, stdout="adb"),
                    ("adb", "devices", "-l"): CommandResult(returncode=0, stdout="List of devices attached\n"),
                    ("adb", "devices"): CommandResult(returncode=0, stdout="List of devices attached\n"),
                }
            )

            report = DoctorService(
                runtime_root=root / "runtime",
                config_dir=config_dir,
                outbox_root=root / "runtime" / "integration_outbox",
                command_runner=runner,
            ).run()

        config_check = next(item for item in report.checks if item.name == "config_json")
        self.assertFalse(report.ok)
        self.assertEqual(config_check.status, "fail")
        self.assertEqual(len(config_check.details["invalid"]), 1)

    def test_device_id_adds_target_device_deep_checks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            device_id = "192.168.31.99:5555"
            runner = FakeCommandRunner(
                {
                    ("adb", "version"): CommandResult(returncode=0, stdout="adb"),
                    ("adb", "devices", "-l"): CommandResult(
                        returncode=0,
                        stdout=f"List of devices attached\n{device_id} device product:test model:Demo\n",
                    ),
                    ("adb", "devices"): CommandResult(
                        returncode=0,
                        stdout=f"List of devices attached\n{device_id} device\n",
                    ),
                    ("adb", "-s", device_id, "get-state"): CommandResult(returncode=0, stdout="device\n"),
                    ("adb", "-s", device_id, "shell", "getprop", "ro.product.model"): CommandResult(
                        returncode=0,
                        stdout="DemoPhone\n",
                    ),
                    ("adb", "-s", device_id, "shell", "pm", "path", "com.example.app"): CommandResult(
                        returncode=0,
                        stdout="package:/data/app/base.apk\n",
                    ),
                    ("adb", "-s", device_id, "shell", "dumpsys", "package", "com.example.app"): CommandResult(
                        returncode=0,
                        stdout="versionName=1.2.3\nversionCode=123\n",
                    ),
                    ("adb", "-s", device_id, "shell", "command", "-v", "perfetto"): CommandResult(
                        returncode=0,
                        stdout="/system/bin/perfetto\n",
                    ),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "perfetto",
                        "-o",
                        "/data/misc/perfetto-traces/asl_doctor_192_168_31_99_5555.perfetto-trace",
                        "-t",
                        "1s",
                        "sched",
                    ): CommandResult(returncode=0),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "ls",
                        "-l",
                        "/data/misc/perfetto-traces/asl_doctor_192_168_31_99_5555.perfetto-trace",
                    ): CommandResult(returncode=0, stdout="-rw-rw---- probe\n"),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "rm",
                        "-f",
                        "/data/misc/perfetto-traces/asl_doctor_192_168_31_99_5555.perfetto-trace",
                    ): CommandResult(returncode=0),
                }
            )

            with patch.object(DoctorService, "_python_dependency_status", return_value=[]):
                with patch.object(DoctorService, "_probe_tcp", return_value=(True, "")):
                    report = DoctorService(
                        runtime_root=root / "runtime",
                        config_dir=config_dir,
                        outbox_root=root / "runtime" / "integration_outbox",
                        command_runner=runner,
                        device_id=device_id,
                        package_name="com.example.app",
                    ).run()

        checks = {item.name: item for item in report.checks}
        self.assertTrue(report.ok)
        self.assertEqual(checks["target_device_authorization"].status, "ok")
        self.assertEqual(checks["target_device_shell"].status, "ok")
        self.assertEqual(checks["target_package"].status, "ok")
        self.assertEqual(checks["target_perfetto_available"].status, "ok")
        self.assertEqual(checks["target_perfetto_write_permission"].status, "ok")
        self.assertEqual(checks["target_wireless_adb"].status, "ok")

    def test_usb_serial_reports_wireless_check_as_not_required_when_adb_is_ready(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            device_id = "AFQJVB2211008014"
            runner = FakeCommandRunner(
                {
                    ("adb", "version"): CommandResult(returncode=0, stdout="adb"),
                    ("adb", "devices", "-l"): CommandResult(
                        returncode=0,
                        stdout=f"List of devices attached\n{device_id} device usb:2-1 model:Demo\n",
                    ),
                    ("adb", "devices"): CommandResult(
                        returncode=0,
                        stdout=f"List of devices attached\n{device_id} device\n",
                    ),
                    ("adb", "-s", device_id, "get-state"): CommandResult(returncode=0, stdout="device\n"),
                    ("adb", "-s", device_id, "shell", "getprop", "ro.product.model"): CommandResult(
                        returncode=0,
                        stdout="DemoPhone\n",
                    ),
                    ("adb", "-s", device_id, "shell", "command", "-v", "perfetto"): CommandResult(
                        returncode=0,
                        stdout="/system/bin/perfetto\n",
                    ),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "perfetto",
                        "-o",
                        "/data/misc/perfetto-traces/asl_doctor_AFQJVB2211008014.perfetto-trace",
                        "-t",
                        "1s",
                        "sched",
                    ): CommandResult(returncode=0),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "ls",
                        "-l",
                        "/data/misc/perfetto-traces/asl_doctor_AFQJVB2211008014.perfetto-trace",
                    ): CommandResult(returncode=0, stdout="-rw-rw---- probe\n"),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "rm",
                        "-f",
                        "/data/misc/perfetto-traces/asl_doctor_AFQJVB2211008014.perfetto-trace",
                    ): CommandResult(returncode=0),
                    (
                        "adb",
                        "-s",
                        device_id,
                        "shell",
                        "getprop",
                        "service.adb.tcp.port",
                    ): CommandResult(returncode=0, stdout=""),
                }
            )

            with patch.object(DoctorService, "_python_dependency_status", return_value=[]):
                report = DoctorService(
                    runtime_root=root / "runtime",
                    config_dir=config_dir,
                    outbox_root=root / "runtime" / "integration_outbox",
                    command_runner=runner,
                    device_id=device_id,
                ).run()

        checks = {item.name: item for item in report.checks}
        self.assertTrue(report.ok)
        self.assertEqual(checks["target_package"].status, "skipped")
        self.assertEqual(checks["target_wireless_adb"].status, "ok")
        self.assertEqual(checks["target_wireless_adb"].details["connection_type"], "usb_serial")

    def test_report_is_json_serializable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            runner = FakeCommandRunner(
                {
                    ("adb", "version"): CommandResult(returncode=0, stdout="adb"),
                    ("adb", "devices", "-l"): CommandResult(returncode=0, stdout="List of devices attached\n"),
                    ("adb", "devices"): CommandResult(returncode=0, stdout="List of devices attached\n"),
                }
            )
            report = DoctorService(
                runtime_root=Path(temp_dir) / "runtime",
                config_dir=Path(temp_dir) / "config",
                outbox_root=Path(temp_dir) / "runtime" / "integration_outbox",
                command_runner=runner,
            ).run()

        payload = json.dumps(report, default=lambda value: getattr(value, "__dict__", str(value)), ensure_ascii=False)
        self.assertIn("runtime_permissions", payload)


if __name__ == "__main__":
    unittest.main()
