from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from stability.app.platform_health_service import PlatformHealthService, PlatformHealthThresholds
from stability.time_utils import now_beijing_string


class _ListRepo:
    def __init__(self, items):
        self._items = list(items)

    def list(self):
        return list(self._items)


class _InstanceRepo(_ListRepo):
    def list_by_run(self, run_id):
        return list(self._items)


class _OutboxRecorder:
    def __init__(self) -> None:
        self.events = []

    def publish_event(self, **kwargs):
        self.events.append(dict(kwargs))
        return SimpleNamespace(**kwargs)


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

    def test_alert_detects_sla_breach_and_publishes_outbox_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            device = SimpleNamespace(
                device_id="device-1",
                availability_state="error",
                is_online=lambda: False,
                is_schedulable=lambda: False,
            )
            outbox = _OutboxRecorder()
            service = PlatformHealthService(
                root_dir=tmp_dir,
                device_service=SimpleNamespace(list_devices=lambda: [device]),
                integration_outbox_service=outbox,
                thresholds=PlatformHealthThresholds(alert_min_severity="fail", device_online_rate_min=0.9),
            )

            snapshot = service.snapshot(record=False)
            alert = service.evaluate_alert(snapshot)
            published = service.publish_alert(snapshot)

        self.assertTrue(alert.fired)
        self.assertEqual(alert.severity, "fail")
        self.assertIn("device_online_rate", {item["metric"] for item in alert.sla_breaches})
        self.assertIsNotNone(published)
        self.assertEqual(outbox.events[0]["event_type"], "asl.platform_health_alert.v1")
        self.assertEqual(outbox.events[0]["target_type"], "platform_health")

    def test_alert_fires_for_sla_breach_even_when_component_status_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            online_device = SimpleNamespace(
                device_id="device-online",
                availability_state="idle",
                is_online=lambda: True,
                is_schedulable=lambda: True,
            )
            offline_device = SimpleNamespace(
                device_id="device-offline",
                availability_state="offline",
                is_online=lambda: False,
                is_schedulable=lambda: False,
            )
            service = PlatformHealthService(
                root_dir=tmp_dir,
                device_service=SimpleNamespace(list_devices=lambda: [online_device, offline_device]),
                thresholds=PlatformHealthThresholds(alert_min_severity="fail", device_online_rate_min=0.9),
            )

            snapshot = service.snapshot(record=False)
            alert = service.evaluate_alert(snapshot)

        device_check = next(item for item in snapshot.checks if item.category == "device_adb")
        self.assertEqual(device_check.status, "ok")
        self.assertEqual(snapshot.severity, "warn")
        self.assertTrue(alert.fired)
        self.assertEqual(alert.sla_breaches[0]["metric"], "device_online_rate")

    def test_trend_payload_uses_configured_24h_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            root.mkdir(parents=True, exist_ok=True)
            (root / "snapshots.json").write_text(
                json.dumps(
                    {
                        "contract_version": "asl.platform_health.v1",
                        "updated_at": now_beijing_string(),
                        "snapshots": [
                            {
                                "contract_version": "asl.platform_health.v1",
                                "generated_at": "2020-01-01 00:00:00.000000",
                                "status": "blocked",
                                "severity": "fail",
                                "summary": {},
                                "checks": [],
                                "readiness": {},
                                "trends": {},
                            },
                            {
                                "contract_version": "asl.platform_health.v1",
                                "generated_at": now_beijing_string(),
                                "status": "degraded",
                                "severity": "warn",
                                "summary": {},
                                "checks": [],
                                "readiness": {},
                                "trends": {},
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = PlatformHealthService(
                root_dir=root,
                thresholds=PlatformHealthThresholds(trend_window_hours=24),
            )

            payload = service.snapshot_payload(service.snapshot(record=False))

        trends = payload["trends"]
        self.assertEqual(trends["history_count"], 2)
        self.assertEqual(trends["window_hours"], 24)
        self.assertEqual(trends["window_snapshot_count"], 1)
        self.assertEqual(trends["window_warn_count"], 1)
        self.assertEqual(trends["window_fail_count"], 0)


if __name__ == "__main__":
    unittest.main()
