from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability.app import DeviceRecordNotFound
from stability.app.analysis_service import AggregatedIssueNotFound
from stability.app.task_service import TaskRecordNotFound
from stability.cli import task_create
from tests.helpers.cli import run_main_with_bundle


class CLIUnattendedCommandsTest(unittest.TestCase):
    def test_configure_unattended_task_outputs_config(self) -> None:
        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                configure_task=lambda *args, **kwargs: SimpleNamespace(
                    task_id="task-1",
                    task_name="Task 1",
                    enabled=True,
                    interval_minutes=30,
                    desired_device_count=1,
                    failure_threshold=3,
                    rotation_strategy="round_robin",
                    rotation_advance_policy="every_round",
                    rotation_cursor=0,
                    rotation_advance_count=0,
                    primary_device_ids=("device-1",),
                    backup_device_ids=("device-2",),
                    next_run_at=None,
                    last_run_at=None,
                    last_run_id="",
                    due=False,
                    latest_summary={},
                    long_run_summary={"round_count": 0},
                    recent_device_windows=(),
                    recent_rounds=(),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "configure-unattended-task",
                "--task-id",
                "task-1",
                "--interval-minutes",
                "30",
                "--device",
                "device-1",
                "--backup-device",
                "device-2",
            ],
            bundle,
        )

        self.assertEqual(payload["unattended_task"]["task_id"], "task-1")
        self.assertEqual(payload["unattended_task"]["primary_device_ids"], ["device-1"])
        self.assertEqual(payload["unattended_task"]["backup_device_ids"], ["device-2"])
        self.assertEqual(payload["unattended_task"]["rotation_strategy"], "round_robin")

    def test_run_unattended_round_outputs_round_result(self) -> None:
        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                run_task_round=lambda *args, **kwargs: SimpleNamespace(
                    task=SimpleNamespace(
                        task_id="task-1",
                        task_name="Task 1",
                        enabled=True,
                        interval_minutes=30,
                        desired_device_count=1,
                        failure_threshold=3,
                        rotation_strategy="round_robin",
                        rotation_advance_policy="every_round",
                        rotation_cursor=1,
                        rotation_advance_count=1,
                        primary_device_ids=("device-1",),
                        backup_device_ids=("device-2",),
                        next_run_at=None,
                        last_run_at=None,
                        last_run_id="run-1",
                        due=False,
                        latest_summary={"run_id": "run-1"},
                        long_run_summary={"round_count": 1},
                        recent_device_windows=(),
                        recent_rounds=(),
                    ),
                    executed=True,
                    reason="executed",
                    round_record={"round_id": "round-1", "run_id": "run-1", "assigned_device_ids": ["device-2"]},
                )
            )
        )

        payload = self._run_main_with_bundle(
            ["run-unattended-round", "--task-id", "task-1"],
            bundle,
        )

        self.assertTrue(payload["execution"]["executed"])
        self.assertEqual(payload["execution"]["round"]["run_id"], "run-1")
        self.assertEqual(payload["execution"]["round"]["assigned_device_ids"], ["device-2"])

    def test_patrol_unattended_tasks_outputs_summary(self) -> None:
        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                run_due_tasks=lambda *args, **kwargs: SimpleNamespace(
                    generated_at=None,
                    task_count=2,
                    enabled_task_count=2,
                    due_task_count=1,
                    executed_task_count=1,
                    skipped_task_count=1,
                    failed_rate=0.5,
                    offline_rate=0.25,
                    recovery_success_rate=1.0,
                    quarantined_device_count=1,
                    quarantined_device_ids=("device-3",),
                    quarantine_probe_attempt_count=1,
                    quarantine_probe_skipped_count=0,
                    quarantine_probe_recovered_count=1,
                    recovered_device_ids=("device-4",),
                    quarantine_probe_results=(
                        {
                            "device_id": "device-4",
                            "attempted": True,
                            "recovered": True,
                            "skipped": False,
                            "reason": "recovered",
                        },
                    ),
                    metrics={"instance_count": 2, "quarantine_probe_attempt_count": 1},
                    executed_rounds=({"round_id": "round-1"},),
                    task_records=(),
                )
            )
        )

        payload = self._run_main_with_bundle(["patrol-unattended-tasks"], bundle)

        self.assertEqual(payload["patrol"]["executed_task_count"], 1)
        self.assertEqual(payload["patrol"]["quarantined_device_count"], 1)
        self.assertEqual(payload["patrol"]["metrics"]["instance_count"], 2)
        self.assertEqual(payload["patrol"]["quarantine_probe_attempt_count"], 1)
        self.assertEqual(payload["patrol"]["quarantine_probe_recovered_count"], 1)
        self.assertEqual(payload["patrol"]["recovered_device_ids"], ["device-4"])

    def test_run_unattended_patrol_runner_outputs_runner_summary(self) -> None:
        bundle = SimpleNamespace(
            unattended_runner_service=SimpleNamespace(
                run=lambda *args, **kwargs: SimpleNamespace(
                    started_at=None,
                    finished_at=None,
                    interval_seconds=60,
                    max_iterations=2,
                    cycle_count=2,
                    stopped_reason="max_iterations_reached",
                    task_id="task-1",
                    force=True,
                    paths=SimpleNamespace(
                        root_dir="runtime/unattended_runner",
                        lock_path="runtime/unattended_runner/runner.lock",
                        heartbeat_path="runtime/unattended_runner/runner_status.json",
                        daily_reports_dir="runtime/unattended_runner/daily_reports",
                        weekly_reports_dir="runtime/unattended_runner/weekly_reports",
                    ),
                    latest_daily_report={"report_date": "2025-07-22", "round_count": 2},
                    daily_report_paths={"report_json_path": "runtime/unattended_runner/daily_reports/2025-07-22/report.json"},
                    latest_weekly_report={"week_key": "2025-W30", "round_count": 7},
                    weekly_report_paths={"report_json_path": "runtime/unattended_runner/weekly_reports/2025-W30/report.json"},
                    patrols=(
                        SimpleNamespace(
                            cycle_index=1,
                            started_at=None,
                            finished_at=None,
                            patrol=SimpleNamespace(
                                generated_at=None,
                                task_count=1,
                                enabled_task_count=1,
                                due_task_count=1,
                                executed_task_count=1,
                                skipped_task_count=0,
                                failed_rate=0.0,
                                offline_rate=0.0,
                                recovery_success_rate=1.0,
                                quarantined_device_count=0,
                                quarantined_device_ids=(),
                                quarantine_probe_attempt_count=1,
                                quarantine_probe_skipped_count=0,
                                quarantine_probe_recovered_count=1,
                                recovered_device_ids=("device-1",),
                                quarantine_probe_results=(),
                                metrics={"instance_count": 1},
                                executed_rounds=({"round_id": "round-1"},),
                                task_records=(),
                            ),
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            ["run-unattended-patrol-runner", "--task-id", "task-1", "--max-iterations", "2", "--force"],
            bundle,
        )

        self.assertEqual(payload["runner"]["cycle_count"], 2)
        self.assertEqual(payload["runner"]["stopped_reason"], "max_iterations_reached")
        self.assertEqual(payload["runner"]["task_id"], "task-1")
        self.assertEqual(
            payload["runner"]["paths"]["heartbeat_path"],
            "runtime/unattended_runner/runner_status.json",
        )
        self.assertEqual(
            payload["runner"]["paths"]["daily_reports_dir"],
            "runtime/unattended_runner/daily_reports",
        )
        self.assertEqual(
            payload["runner"]["paths"]["weekly_reports_dir"],
            "runtime/unattended_runner/weekly_reports",
        )
        self.assertEqual(payload["runner"]["latest_daily_report"]["round_count"], 2)
        self.assertEqual(payload["runner"]["latest_weekly_report"]["week_key"], "2025-W30")
        self.assertEqual(payload["runner"]["patrols"][0]["patrol"]["quarantine_probe_recovered_count"], 1)

    def test_build_unattended_daily_report_outputs_summary(self) -> None:
        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                build_daily_report=lambda *args, **kwargs: SimpleNamespace(
                    report_date="2025-07-22",
                    generated_at=None,
                    task_count=2,
                    active_task_count=2,
                    round_count=4,
                    executed_round_count=3,
                    skipped_round_count=1,
                    failed_round_count=1,
                    total_runtime_seconds=600,
                    total_runtime_hours=0.167,
                    device_online_rate=0.75,
                    failed_rate=0.25,
                    offline_rate=0.25,
                    recovery_success_rate=1.0,
                    quarantined_device_count=1,
                    quarantined_device_ids=("device-3",),
                    issue_type_distribution={"device_offline": 1},
                    top_issue_types=({"issue_type": "device_offline", "count": 1},),
                    interruption_rounds=({"round_id": "round-1", "status": "no_schedulable_devices"},),
                    task_summaries=({"task_id": "task-1", "round_count": 2},),
                    metrics={"instance_count": 4},
                )
            )
        )

        payload = self._run_main_with_bundle(["build-unattended-daily-report"], bundle)

        self.assertEqual(payload["daily_report"]["report_date"], "2025-07-22")
        self.assertEqual(payload["daily_report"]["round_count"], 4)
        self.assertEqual(payload["daily_report"]["top_issue_types"][0]["issue_type"], "device_offline")

    def test_build_unattended_weekly_report_outputs_summary(self) -> None:
        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                build_weekly_report=lambda *args, **kwargs: SimpleNamespace(
                    week_key="2025-W30",
                    anchor_date="2025-07-22",
                    week_start_date="2025-07-20",
                    week_end_date="2025-07-26",
                    generated_at=None,
                    task_count=2,
                    active_task_count=2,
                    active_day_count=3,
                    round_count=8,
                    executed_round_count=7,
                    skipped_round_count=1,
                    failed_round_count=2,
                    total_runtime_seconds=1800,
                    total_runtime_hours=0.5,
                    device_online_rate=0.8,
                    failed_rate=0.25,
                    offline_rate=0.125,
                    recovery_success_rate=0.5,
                    quarantined_device_count=1,
                    quarantined_device_ids=("device-3",),
                    issue_type_distribution={"device_offline": 2},
                    top_issue_types=({"issue_type": "device_offline", "count": 2},),
                    interruption_rounds=({"round_id": "round-1", "status": "failed"},),
                    task_summaries=({"task_id": "task-1", "round_count": 4},),
                    daily_summaries=({"report_date": "2025-07-22", "round_count": 3},),
                    metrics={"instance_count": 8},
                )
            )
        )

        payload = self._run_main_with_bundle(["build-unattended-weekly-report"], bundle)

        self.assertEqual(payload["weekly_report"]["week_key"], "2025-W30")
        self.assertEqual(payload["weekly_report"]["round_count"], 8)
        self.assertEqual(payload["weekly_report"]["daily_summaries"][0]["report_date"], "2025-07-22")

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
