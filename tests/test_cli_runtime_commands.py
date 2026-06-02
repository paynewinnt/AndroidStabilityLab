from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability.cli import task_create
from stability.app.doctor_service import DoctorCheck, DoctorReport


class CliRuntimeCommandsTest(unittest.TestCase):
    def test_doctor_command_outputs_platform_diagnostics(self) -> None:
        fake_report = DoctorReport(
            generated_at="2025-07-29 10:00:00",
            ok=True,
            checks=(DoctorCheck(name="python", status="ok", summary="ok"),),
            summary={"total": 1, "ok": 1, "warn": 0, "fail": 0, "skipped": 0},
        )
        stdout = io.StringIO()

        with patch("stability.cli.task_create.DoctorService") as service_class:
            service_class.return_value.run.return_value = fake_report
            with redirect_stdout(stdout):
                exit_code = task_create.main(
                    [
                        "doctor",
                        "--runtime-root",
                        "runtime",
                        "--device-id",
                        "192.168.31.99:5555",
                        "--package-name",
                        "com.example.app",
                    ]
                )

        self.assertEqual(exit_code, 0)
        service_class.assert_called_once()
        self.assertEqual(service_class.call_args.kwargs["device_id"], "192.168.31.99:5555")
        self.assertEqual(service_class.call_args.kwargs["package_name"], "com.example.app")
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["checks"][0]["name"], "python")

    def test_runtime_doctor_command_outputs_runtime_summary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            (root / "tasks").mkdir(parents=True)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = task_create.main(["runtime-doctor", "--runtime-root", str(root)])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["root_dir"], str(root))
        self.assertIn("summaries", payload)

    def test_export_runtime_command_writes_archive(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            (root / "tasks" / "task-a").mkdir(parents=True)
            (root / "tasks" / "task-a" / "run.json").write_text("{}", encoding="utf-8")
            output = Path(temp_dir) / "runtime.zip"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = task_create.main(
                    ["export-runtime", "--runtime-root", str(root), "--category", "tasks", "--output", str(output)]
                )
            output_exists = output.exists()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["output_path"], str(output))
        self.assertTrue(output_exists)

    def test_platform_health_publish_alert_outputs_delivery_status(self) -> None:
        class _FakeAlert:
            def to_payload(self):
                return {"contract_version": "asl.platform_health_alert.v1", "fired": True, "severity": "fail"}

        class _FakePlatformHealthService:
            def __init__(self) -> None:
                self.snapshot_record_values = []
                self.published = False

            def snapshot(self, *, record: bool = True):
                self.snapshot_record_values.append(record)
                return SimpleNamespace(ok=False, severity="fail")

            def snapshot_payload(self, snapshot):
                return {"contract_version": "asl.platform_health.v1", "ok": snapshot.ok, "severity": snapshot.severity}

            def publish_alert(self, snapshot):
                self.published = True
                return _FakeAlert()

        fake_service = _FakePlatformHealthService()
        stdout = io.StringIO()

        with patch("stability.bootstrap.create_v1_persistent_bootstrap") as factory:
            factory.return_value = SimpleNamespace(platform_health_service=fake_service)
            with redirect_stdout(stdout):
                exit_code = task_create.main(["platform-health", "--no-record", "--publish-alert"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(fake_service.snapshot_record_values, [False])
        self.assertTrue(fake_service.published)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["published_alert"]["published"])
        self.assertEqual(payload["published_alert"]["alert"]["contract_version"], "asl.platform_health_alert.v1")


if __name__ == "__main__":
    unittest.main()
