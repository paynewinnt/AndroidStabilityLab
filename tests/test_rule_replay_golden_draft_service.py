from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import RuleReplayGoldenDraftService
from stability.domain import (
    DeviceSnapshot,
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


class RuleReplayGoldenDraftServiceTest(unittest.TestCase):
    def test_create_draft_exports_case_from_real_run(self) -> None:
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        instance_repository = InMemoryInstanceRepository()

        task = TaskDefinition(
            task_id="task-real",
            task_name="Real Crash Task",
            template_type=TaskTemplateType.MONKEY,
            target_app=TaskTargetApp(package_name="com.example.real"),
        )
        run = TaskRun(
            run_id="run-real",
            task_definition_id=task.task_id,
            task_name=task.task_name,
            status=TaskRunStatus.FAILED,
            created_at=datetime(2025, 7, 22, 10, 0, 0),
        )
        task_repository.add(task)
        run_repository.add(run)
        instance_repository.add_many(
            (
                ExecutionInstance(
                    instance_id="instance-a",
                    run_id=run.run_id,
                    task_definition_id=task.task_id,
                    device_id="device-a",
                    device_snapshot=DeviceSnapshot(device_id="device-a", serial="device-a"),
                    template_type=TaskTemplateType.MONKEY,
                    target_app_package="com.example.real",
                    status=ExecutionStatus.FAILED,
                    exit_reason=ExitReason.EXECUTION_ERROR,
                    result_level=ResultLevel.FAILED,
                    metadata={
                        "report_path": "runtime/real-a/report.md",
                        "execution_log_path": "runtime/real-a/execution.log",
                    },
                    issues=[
                        IssueRecord(
                            issue_id="issue-a",
                            instance_id="instance-a",
                            task_run_id=run.run_id,
                            device_id="device-a",
                            issue_type=IssueType.CRASH,
                            issue_title="检测到 Crash",
                            severity=SeverityLevel.CRITICAL,
                            detected_at=datetime(2025, 7, 22, 10, 1, 0),
                            process_name="com.example.real",
                            package_name="com.example.real",
                            raw_key="crash:stack-a",
                            summary="Crash stack A",
                        )
                    ],
                ),
                ExecutionInstance(
                    instance_id="instance-b",
                    run_id=run.run_id,
                    task_definition_id=task.task_id,
                    device_id="device-b",
                    device_snapshot=DeviceSnapshot(device_id="device-b", serial="device-b"),
                    template_type=TaskTemplateType.MONKEY,
                    target_app_package="com.example.real",
                    status=ExecutionStatus.FAILED,
                    exit_reason=ExitReason.EXECUTION_ERROR,
                    result_level=ResultLevel.FAILED,
                    metadata={
                        "report_path": "runtime/real-b/report.md",
                        "execution_log_path": "runtime/real-b/execution.log",
                    },
                    issues=[
                        IssueRecord(
                            issue_id="issue-b",
                            instance_id="instance-b",
                            task_run_id=run.run_id,
                            device_id="device-b",
                            issue_type=IssueType.CRASH,
                            issue_title="检测到 Crash",
                            severity=SeverityLevel.CRITICAL,
                            detected_at=datetime(2025, 7, 22, 10, 2, 0),
                            process_name="com.example.real",
                            package_name="com.example.real",
                            raw_key="crash:stack-b",
                            summary="Crash stack B",
                        )
                    ],
                ),
            )
        )
        service = RuleReplayGoldenDraftService(
            task_repository=task_repository,
            run_repository=run_repository,
            instance_repository=instance_repository,
        )

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "golden_draft.json"

            result = service.create_draft(
                run_id=run.run_id,
                issue_ids=("issue-a", "issue-b"),
                output_path=str(output_path),
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result.case_id, "crash_run-real_draft")
        self.assertEqual(result.issue_type, "crash")
        self.assertEqual(result.layer, "merge_semantics")
        self.assertEqual(result.expectation, "unchanged")
        self.assertEqual(result.issue_count, 2)
        self.assertEqual(result.expected["family_count"], 1)
        self.assertEqual(result.expected["change_summary"], {"unchanged": 1})
        self.assertEqual(payload["suite_version"], "v2")
        self.assertEqual(len(payload["cases"]), 1)
        self.assertEqual(payload["cases"][0]["filters"]["package_name"], "com.example.real")
        self.assertTrue(payload["cases"][0]["include_unchanged"])
        self.assertEqual(payload["cases"][0]["draft_metadata"]["selected_issue_ids"], ["issue-a", "issue-b"])
        self.assertEqual(len(payload["cases"][0]["dataset"]["instances"]), 2)

    def test_create_draft_selects_issues_by_issue_type(self) -> None:
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        instance_repository = InMemoryInstanceRepository()

        task = TaskDefinition(
            task_id="task-offline",
            task_name="Offline Task",
            template_type=TaskTemplateType.MONKEY,
            target_app=TaskTargetApp(package_name="com.example.real"),
        )
        run = TaskRun(
            run_id="run-offline",
            task_definition_id=task.task_id,
            task_name=task.task_name,
            status=TaskRunStatus.FAILED,
            created_at=datetime(2025, 7, 22, 11, 0, 0),
        )
        task_repository.add(task)
        run_repository.add(run)
        instance_repository.add_many(
            (
                ExecutionInstance(
                    instance_id="instance-offline-a",
                    run_id=run.run_id,
                    task_definition_id=task.task_id,
                    device_id="device-a",
                    template_type=TaskTemplateType.MONKEY,
                    target_app_package="com.example.real",
                    issues=[
                        IssueRecord(
                            issue_id="issue-offline-a",
                            instance_id="instance-offline-a",
                            task_run_id=run.run_id,
                            device_id="device-a",
                            issue_type=IssueType.DEVICE_OFFLINE,
                            issue_title="设备离线",
                            severity=SeverityLevel.HIGH,
                            detected_at=datetime(2025, 7, 22, 11, 1, 0),
                            package_name="com.example.real",
                            raw_key="transport:offline-a",
                        )
                    ],
                ),
                ExecutionInstance(
                    instance_id="instance-offline-b",
                    run_id=run.run_id,
                    task_definition_id=task.task_id,
                    device_id="device-b",
                    template_type=TaskTemplateType.MONKEY,
                    target_app_package="com.example.real",
                    issues=[
                        IssueRecord(
                            issue_id="issue-offline-b",
                            instance_id="instance-offline-b",
                            task_run_id=run.run_id,
                            device_id="device-b",
                            issue_type=IssueType.DEVICE_OFFLINE,
                            issue_title="设备离线",
                            severity=SeverityLevel.HIGH,
                            detected_at=datetime(2025, 7, 22, 11, 2, 0),
                            package_name="com.example.real",
                            raw_key="transport:offline-b",
                        )
                    ],
                ),
            )
        )
        service = RuleReplayGoldenDraftService(
            task_repository=task_repository,
            run_repository=run_repository,
            instance_repository=instance_repository,
        )

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "offline_draft.json"
            result = service.create_draft(
                run_id=run.run_id,
                issue_type="device_offline",
                limit=1,
                output_path=str(output_path),
            )

        self.assertEqual(result.issue_count, 1)
        self.assertEqual(result.issue_type, "device_offline")
        self.assertEqual(result.layer, "identity_semantics")
        self.assertEqual(result.selected_issue_ids, ("issue-offline-a",))


if __name__ == "__main__":
    unittest.main()
