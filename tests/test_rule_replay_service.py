from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app.rule_replay_service import RuleReplayService
from stability.domain import (
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    ExecutionInstance,
    ExecutionStatus,
    ExitReason,
    IssueRecord,
    IssueType,
    ResultLevel,
    SeverityLevel,
    TaskDefinition,
    TaskRun,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.repositories import InMemoryInstanceRepository, InMemoryRunRepository, InMemoryTaskRepository


class RuleReplayServiceTest(unittest.TestCase):
    def test_replay_top_issues_reports_regrouped_family_when_candidate_ignores_crash_raw_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            baseline_path.write_text("{}", encoding="utf-8")
            candidate_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "v2",
                            "ignore_raw_key_issue_types": ["crash"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = build_rule_replay_fixture(default_rule_path=str(baseline_path))

            result = service.replay_top_issues(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
                include_unchanged=True,
            )

            self.assertEqual(result.family_count, 1)
            self.assertEqual(result.changed_family_count, 1)
            self.assertEqual(result.change_summary["regrouped"], 1)
            family = result.families[0]
            self.assertEqual(family.change_type, "regrouped")
            self.assertEqual(family.left_group_count, 2)
            self.assertEqual(family.right_group_count, 1)
            self.assertEqual(result.baseline.fingerprint_rule_version, "v1")
            self.assertEqual(result.candidate.fingerprint_rule_version, "v2")

    def test_replay_top_issues_reports_fingerprint_changed_when_family_stays_grouped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "v1",
                            "ignore_raw_key_issue_types": [],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            candidate_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "v2",
                            "ignore_raw_key_issue_types": ["device_offline"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = build_rule_replay_fingerprint_fixture(default_rule_path=str(baseline_path))

            result = service.replay_top_issues(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
                include_unchanged=True,
            )

            self.assertEqual(result.family_count, 1)
            self.assertEqual(result.changed_family_count, 1)
            self.assertEqual(result.change_summary["fingerprint_changed"], 1)
            family = result.families[0]
            self.assertEqual(family.change_type, "fingerprint_changed")
            self.assertEqual(family.left_group_count, 1)
            self.assertEqual(family.right_group_count, 1)
            self.assertNotEqual(family.left_fingerprints, family.right_fingerprints)


def build_rule_replay_fixture(*, default_rule_path: str) -> RuleReplayService:
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()

    task = TaskDefinition(
        task_id="task-1",
        task_name="Replay Task",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(package_name="com.example.app"),
    )
    task_repository.add(task)

    run = TaskRun(
        run_id="run-1",
        task_definition_id=task.task_id,
        task_name=task.task_name,
        status=TaskRunStatus.FAILED,
        created_at=datetime(2025, 7, 20, 9, 0, 0),
    )
    run_repository.add(run)

    issue_a = IssueRecord(
        issue_id="issue-a",
        instance_id="instance-a",
        task_run_id=run.run_id,
        device_id="device-a",
        issue_type=IssueType.CRASH,
        issue_title="检测到 Crash",
        severity=SeverityLevel.CRITICAL,
        detected_at=datetime(2025, 7, 20, 9, 1, 0),
        process_name="com.example.app",
        package_name="com.example.app",
        raw_key="crash:stack-a",
        summary="Crash A",
    )
    issue_b = IssueRecord(
        issue_id="issue-b",
        instance_id="instance-b",
        task_run_id=run.run_id,
        device_id="device-b",
        issue_type=IssueType.CRASH,
        issue_title="检测到 Crash",
        severity=SeverityLevel.CRITICAL,
        detected_at=datetime(2025, 7, 20, 9, 2, 0),
        process_name="com.example.app",
        package_name="com.example.app",
        raw_key="crash:stack-b",
        summary="Crash B",
    )

    instance_repository.add_many(
        [
            ExecutionInstance(
                instance_id="instance-a",
                run_id=run.run_id,
                task_definition_id=task.task_id,
                device_id="device-a",
                device_snapshot=Device(
                    device_id="device-a",
                    serial="device-a",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ).snapshot(),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.EXECUTION_ERROR,
                result_level=ResultLevel.FAILED,
                issues=[issue_a],
                metadata={
                    "report_path": "runtime/run-1/instance-a/report.md",
                    "execution_log_path": "runtime/run-1/instance-a/execution.log",
                },
            ),
            ExecutionInstance(
                instance_id="instance-b",
                run_id=run.run_id,
                task_definition_id=task.task_id,
                device_id="device-b",
                device_snapshot=Device(
                    device_id="device-b",
                    serial="device-b",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ).snapshot(),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.EXECUTION_ERROR,
                result_level=ResultLevel.FAILED,
                issues=[issue_b],
                metadata={
                    "report_path": "runtime/run-1/instance-b/report.md",
                    "execution_log_path": "runtime/run-1/instance-b/execution.log",
                },
            ),
        ]
    )

    return RuleReplayService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        default_rule_path=default_rule_path,
    )


def build_rule_replay_fingerprint_fixture(*, default_rule_path: str) -> RuleReplayService:
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()

    task = TaskDefinition(
        task_id="task-fp",
        task_name="Replay Fingerprint Task",
        template_type=TaskTemplateType.COLD_START_LOOP,
        target_app=TaskTargetApp(package_name="com.example.app"),
    )
    task_repository.add(task)

    run = TaskRun(
        run_id="run-fp",
        task_definition_id=task.task_id,
        task_name=task.task_name,
        status=TaskRunStatus.FAILED,
        created_at=datetime(2025, 7, 20, 10, 0, 0),
    )
    run_repository.add(run)

    issue = IssueRecord(
        issue_id="issue-fp",
        instance_id="instance-fp",
        task_run_id=run.run_id,
        device_id="device-fp",
        issue_type=IssueType.DEVICE_OFFLINE,
        issue_title="设备离线",
        severity=SeverityLevel.HIGH,
        detected_at=datetime(2025, 7, 20, 10, 1, 0),
        process_name="com.example.app",
        package_name="com.example.app",
        raw_key="transport:offline",
        summary="Device offline",
    )

    instance_repository.add_many(
        [
            ExecutionInstance(
                instance_id="instance-fp",
                run_id=run.run_id,
                task_definition_id=task.task_id,
                device_id="device-fp",
                device_snapshot=Device(
                    device_id="device-fp",
                    serial="device-fp",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ).snapshot(),
                template_type=TaskTemplateType.COLD_START_LOOP,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.DEVICE_OFFLINE,
                result_level=ResultLevel.FAILED,
                issues=[issue],
                metadata={
                    "report_path": "runtime/run-fp/instance-fp/report.md",
                    "execution_log_path": "runtime/run-fp/instance-fp/execution.log",
                },
            ),
        ]
    )

    return RuleReplayService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        default_rule_path=default_rule_path,
    )


if __name__ == "__main__":
    unittest.main()
