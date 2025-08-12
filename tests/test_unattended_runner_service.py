from __future__ import annotations

from datetime import timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app.unattended_runner_service import (
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedPatrolRunnerService,
)
from stability.domain.value_objects import utcnow


class _FakeUnattendedService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.daily_report_calls: list[dict[str, object]] = []
        self.weekly_report_calls: list[dict[str, object]] = []

    def run_due_tasks(self, **kwargs):
        self.calls.append(dict(kwargs))
        return type(
            "PatrolResult",
            (),
            {
                "generated_at": utcnow(),
                "task_count": 1,
                "enabled_task_count": 1,
                "due_task_count": 1,
                "executed_task_count": 1,
                "skipped_task_count": 0,
                "failed_rate": 0.0,
                "offline_rate": 0.0,
                "recovery_success_rate": 1.0,
                "quarantined_device_count": 0,
                "quarantined_device_ids": (),
                "quarantine_probe_attempt_count": 0,
                "quarantine_probe_skipped_count": 0,
                "quarantine_probe_recovered_count": 0,
                "recovered_device_ids": (),
                "quarantine_probe_results": (),
                "metrics": {"instance_count": 1},
                "executed_rounds": ({"round_id": f"round-{len(self.calls)}"},),
                "task_records": (),
            },
        )()

    def build_daily_report(self, *, report_date: str = "", task_id: str = ""):
        self.daily_report_calls.append({"report_date": report_date, "task_id": task_id})
        return type(
            "DailyReport",
            (),
            {
                "report_date": utcnow().date().isoformat(),
                "generated_at": utcnow(),
                "task_count": 1,
                "active_task_count": 1,
                "round_count": len(self.calls),
                "executed_round_count": len(self.calls),
                "skipped_round_count": 0,
                "failed_round_count": 0,
                "total_runtime_seconds": 30,
                "total_runtime_hours": 0.008,
                "device_online_rate": 1.0,
                "failed_rate": 0.0,
                "offline_rate": 0.0,
                "recovery_success_rate": 1.0,
                "quarantined_device_count": 0,
                "quarantined_device_ids": (),
                "issue_type_distribution": {},
                "top_issue_types": (),
                "interruption_rounds": (),
                "task_summaries": (),
                "metrics": {"instance_count": len(self.calls)},
            },
        )()

    def build_weekly_report(self, *, report_date: str = "", task_id: str = ""):
        self.weekly_report_calls.append({"report_date": report_date, "task_id": task_id})
        anchor = utcnow().date()
        return type(
            "WeeklyReport",
            (),
            {
                "week_key": "2025-W30",
                "anchor_date": anchor.isoformat(),
                "week_start_date": (anchor - timedelta(days=anchor.weekday())).isoformat(),
                "week_end_date": (anchor - timedelta(days=anchor.weekday()) + timedelta(days=6)).isoformat(),
                "generated_at": utcnow(),
                "task_count": 1,
                "active_task_count": 1,
                "active_day_count": 2,
                "round_count": len(self.calls),
                "executed_round_count": len(self.calls),
                "skipped_round_count": 0,
                "failed_round_count": 0,
                "total_runtime_seconds": 60,
                "total_runtime_hours": 0.017,
                "device_online_rate": 1.0,
                "failed_rate": 0.0,
                "offline_rate": 0.0,
                "recovery_success_rate": 1.0,
                "quarantined_device_count": 0,
                "quarantined_device_ids": (),
                "issue_type_distribution": {},
                "top_issue_types": (),
                "interruption_rounds": (),
                "task_summaries": (),
                "daily_summaries": (
                    {"report_date": anchor.isoformat(), "round_count": len(self.calls), "failed_round_count": 0},
                ),
                "metrics": {"instance_count": len(self.calls)},
            },
        )()


class UnattendedPatrolRunnerServiceTest(unittest.TestCase):
    def test_run_executes_bounded_cycles_and_sleeps_between_cycles(self) -> None:
        service = _FakeUnattendedService()
        sleep_calls: list[float] = []
        ticks = [utcnow() + timedelta(seconds=index) for index in range(16)]

        def _clock():
            return ticks.pop(0)

        with TemporaryDirectory() as tempdir:
            runner = UnattendedPatrolRunnerService(
                unattended_service=service,
                root_dir=tempdir,
                sleep_func=lambda seconds: sleep_calls.append(seconds),
                clock_func=_clock,
            )

            result = runner.run(
                interval_seconds=30,
                max_iterations=2,
                task_id="task-1",
                force=True,
                requested_by="runner",
            )

            self.assertEqual(result.cycle_count, 2)
            self.assertEqual(result.stopped_reason, "max_iterations_reached")
            self.assertEqual(len(result.patrols), 2)
            self.assertEqual(len(service.calls), 2)
            self.assertEqual(service.calls[0]["task_id"], "task-1")
            self.assertEqual(service.calls[0]["force"], True)
            self.assertEqual(service.calls[0]["requested_by"], "runner")
            self.assertEqual(sleep_calls, [30.0])
            self.assertFalse(Path(result.paths.lock_path).exists())
            heartbeat = json.loads(Path(result.paths.heartbeat_path).read_text(encoding="utf-8"))
            self.assertEqual(heartbeat["status"], "stopped")
            self.assertEqual(heartbeat["cycle_count"], 2)
            self.assertEqual(heartbeat["task_id"], "task-1")
            self.assertEqual(heartbeat["last_patrol"]["executed_task_count"], 1)
            self.assertEqual(len(heartbeat["recent_patrols"]), 2)
            self.assertEqual(heartbeat["recent_patrols"][-1]["cycle_index"], 2)
            self.assertEqual(heartbeat["latest_daily_report"]["round_count"], 2)
            self.assertEqual(heartbeat["latest_weekly_report"]["week_key"], "2025-W30")
            self.assertTrue(Path(result.daily_report_paths["report_json_path"]).exists())
            self.assertTrue(Path(result.weekly_report_paths["report_json_path"]).exists())
            self.assertEqual(len(service.daily_report_calls), 2)
            self.assertEqual(len(service.weekly_report_calls), 2)

    def test_run_returns_interrupted_when_sleep_is_cancelled(self) -> None:
        service = _FakeUnattendedService()
        ticks = [utcnow() + timedelta(seconds=index) for index in range(12)]

        def _clock():
            return ticks.pop(0)

        def _sleep(_seconds: float) -> None:
            raise KeyboardInterrupt()

        with TemporaryDirectory() as tempdir:
            runner = UnattendedPatrolRunnerService(
                unattended_service=service,
                root_dir=tempdir,
                sleep_func=_sleep,
                clock_func=_clock,
            )

            result = runner.run(interval_seconds=30, max_iterations=0)

            self.assertEqual(result.cycle_count, 1)
            self.assertEqual(result.stopped_reason, "interrupted")
            self.assertEqual(len(service.calls), 1)
            heartbeat = json.loads(Path(result.paths.heartbeat_path).read_text(encoding="utf-8"))
            self.assertEqual(heartbeat["stopped_reason"], "interrupted")

    def test_run_rejects_second_active_runner_when_lock_is_fresh(self) -> None:
        service = _FakeUnattendedService()
        now = utcnow()
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "runner.lock").write_text("{}", encoding="utf-8")
            (root / "runner_status.json").write_text(
                json.dumps(
                    {
                        "status": "running",
                        "last_heartbeat_at": now.isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            runner = UnattendedPatrolRunnerService(
                unattended_service=service,
                root_dir=tempdir,
                sleep_func=lambda _seconds: None,
                clock_func=lambda: now,
            )

            with self.assertRaises(UnattendedPatrolRunnerAlreadyRunning):
                runner.run(interval_seconds=30, max_iterations=1)

    def test_run_can_take_over_stale_lock(self) -> None:
        service = _FakeUnattendedService()
        base = utcnow()
        ticks = [base + timedelta(seconds=index) for index in range(10, 24)]

        def _clock():
            return ticks.pop(0)

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "runner.lock").write_text("{}", encoding="utf-8")
            (root / "runner_status.json").write_text(
                json.dumps(
                    {
                        "status": "running",
                        "last_heartbeat_at": (base - timedelta(minutes=10)).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            runner = UnattendedPatrolRunnerService(
                unattended_service=service,
                root_dir=tempdir,
                sleep_func=lambda _seconds: None,
                clock_func=_clock,
            )

            result = runner.run(interval_seconds=30, max_iterations=1)

            self.assertEqual(result.cycle_count, 1)
            self.assertEqual(result.stopped_reason, "max_iterations_reached")
            self.assertFalse((root / "runner.lock").exists())

    def test_show_status_reports_active_runner_heartbeat(self) -> None:
        service = _FakeUnattendedService()
        now = utcnow()
        now_aware = now.replace(tzinfo=timezone.utc)
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "runner.lock").write_text(
                json.dumps({"pid": 321, "started_at": now_aware.isoformat()}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "runner_status.json").write_text(
                json.dumps(
                    {
                        "pid": 321,
                        "status": "running",
                        "started_at": now_aware.isoformat(),
                        "last_heartbeat_at": now_aware.isoformat(),
                        "interval_seconds": 30,
                        "cycle_count": 4,
                        "active_cycle_index": 5,
                        "task_id": "task-1",
                        "latest_daily_report": {"report_date": now.date().isoformat(), "round_count": 4},
                        "daily_report_paths": {"report_json_path": "runtime/report.json"},
                        "latest_weekly_report": {"week_key": "2025-W30", "round_count": 6},
                        "weekly_report_paths": {"report_json_path": "runtime/weekly-report.json"},
                        "last_patrol": {"executed_task_count": 2},
                        "recent_patrols": [
                            {"cycle_index": 3, "executed_task_count": 1},
                            {"cycle_index": 4, "executed_task_count": 2},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            runner = UnattendedPatrolRunnerService(
                unattended_service=service,
                root_dir=tempdir,
                sleep_func=lambda _seconds: None,
                clock_func=lambda: now,
            )

            status = runner.show_status()

            self.assertTrue(status.lock_present)
            self.assertTrue(status.heartbeat_present)
            self.assertEqual(status.lock_state, "active")
            self.assertEqual(status.status, "running")
            self.assertEqual(status.pid, 321)
            self.assertEqual(status.task_id, "task-1")
            self.assertEqual(status.cycle_count, 4)
            self.assertEqual(status.last_patrol["executed_task_count"], 2)
            self.assertEqual(len(status.recent_patrols), 2)
            self.assertEqual(status.recent_patrols[-1]["cycle_index"], 4)
            self.assertEqual(status.latest_daily_report["round_count"], 4)
            self.assertEqual(status.daily_report_paths["report_json_path"], "runtime/report.json")
            self.assertEqual(status.latest_weekly_report["week_key"], "2025-W30")
            self.assertEqual(status.weekly_report_paths["report_json_path"], "runtime/weekly-report.json")
            self.assertFalse(status.is_stale)

    def test_show_status_marks_lock_stale_when_heartbeat_is_too_old(self) -> None:
        service = _FakeUnattendedService()
        now = utcnow()
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "runner.lock").write_text(
                json.dumps({"pid": 999, "started_at": now.isoformat()}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "runner_status.json").write_text(
                json.dumps(
                    {
                        "pid": 999,
                        "status": "running",
                        "started_at": (now - timedelta(minutes=30)).isoformat(),
                        "last_heartbeat_at": (now - timedelta(minutes=20)).isoformat(),
                        "interval_seconds": 60,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            runner = UnattendedPatrolRunnerService(
                unattended_service=service,
                root_dir=tempdir,
                sleep_func=lambda _seconds: None,
                clock_func=lambda: now,
            )

            status = runner.show_status()

            self.assertTrue(status.lock_present)
            self.assertTrue(status.heartbeat_present)
            self.assertTrue(status.is_stale)
            self.assertEqual(status.lock_state, "stale")
            self.assertEqual(status.status, "running")
            self.assertGreater(status.heartbeat_age_seconds or 0, status.stale_after_seconds)


if __name__ == "__main__":
    unittest.main()
