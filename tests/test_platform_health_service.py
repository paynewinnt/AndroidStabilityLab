from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace

from stability.app.platform_health_service import PlatformHealthService


class _ListRepo:
    def __init__(self, items):
        self._items = list(items)

    def list(self):
        return list(self._items)


class _InstanceRepo(_ListRepo):
    def list_by_run(self, run_id):
        return list(self._items)


class PlatformHealthServiceTest(unittest.TestCase):
    def test_records_continuous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            device = SimpleNamespace(
                device_id="device-1",
                availability_state="idle",
                is_online=lambda: True,
                is_schedulable=lambda: True,
            )
            runner_status = SimpleNamespace(
                status="running",
                heartbeat_age_seconds=12,
                is_stale=False,
                cycle_count=3,
                last_patrol={"failed_rate": 0.0, "offline_rate": 0.0, "quarantined_device_count": 0},
                last_heartbeat_at="2025-07-29 10:00:00.000000",
                started_at="2025-07-29 09:00:00.000000",
                stopped_reason="",
                lock_state="held",
            )
            outbox = SimpleNamespace(
                list_events=lambda limit=200: [SimpleNamespace(delivery_status="delivered", dead_lettered_at=None)],
                get_worker_status=lambda: SimpleNamespace(status="idle", failed_count=0),
            )
            instance = SimpleNamespace(
                status="success",
                exit_reason="completed",
                artifacts=[SimpleNamespace(capture_status="success")],
                summary={"analysis_ready": {"report": {"markdown_path": "report.md"}}},
            )
            service = PlatformHealthService(
                root_dir=tmp_dir,
                device_service=SimpleNamespace(list_devices=lambda: [device]),
                task_repository=_ListRepo([SimpleNamespace(task_id="task-1")]),
                run_repository=_ListRepo([SimpleNamespace(run_id="run-1", status="success")]),
                instance_repository=_InstanceRepo([instance]),
                unattended_runner_service=SimpleNamespace(show_status=lambda: runner_status),
                integration_outbox_service=outbox,
            )

            snapshot = service.snapshot(record=True)
            payload = service.snapshot_payload(snapshot)

            self.assertTrue(snapshot.ok)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["summary"]["ok_count"], 5)
            self.assertTrue(payload["storage"]["snapshot_path"].endswith("snapshots.json"))
            self.assertEqual(service.history(limit=1)[0]["contract_version"], "asl.platform_health.v1")

    def test_marks_blocked_when_no_schedulable_device(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            device = SimpleNamespace(
                device_id="device-1",
                availability_state="error",
                is_online=lambda: False,
                is_schedulable=lambda: False,
            )
            service = PlatformHealthService(
                root_dir=tmp_dir,
                device_service=SimpleNamespace(list_devices=lambda: [device]),
            )

            payload = service.snapshot_payload(service.snapshot(record=False))

            device_check = next(item for item in payload["checks"] if item["category"] == "device_adb")
            self.assertEqual(device_check["status"], "fail")
            self.assertEqual(payload["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
