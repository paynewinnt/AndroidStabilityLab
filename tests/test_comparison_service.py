from __future__ import annotations

from datetime import datetime
import unittest

from stability.app import AnalysisService, ComparisonService
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


class ComparisonServiceTest(unittest.TestCase):
    def test_compare_versions_reports_changed_gone_and_unchanged(self) -> None:
        service = build_comparison_service_fixture()

        result = service.compare_issues(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        self.assertEqual(result.dimension, "version")
        self.assertEqual(result.issue_change_summary["changed_count"], 1)
        self.assertEqual(result.issue_change_summary["gone_count"], 1)
        self.assertEqual(result.issue_change_summary["unchanged_count"], 1)
        self.assertEqual(result.sample_summary["left_issue_group_count"], 3)
        self.assertEqual(result.sample_summary["right_issue_group_count"], 2)

        changes = {item.issue_type: item for item in result.issues}
        self.assertEqual(changes["crash"].change_type, "changed")
        self.assertEqual(changes["crash"].left_occurrence_count, 3)
        self.assertEqual(changes["crash"].right_occurrence_count, 1)
        self.assertEqual(changes["device_offline"].change_type, "gone")
        self.assertEqual(changes["startup_timeout"].change_type, "unchanged")

    def test_compare_devices_uses_device_scope(self) -> None:
        service = build_comparison_service_fixture()

        result = service.compare_issues(
            dimension="device",
            left_value="device-a",
            right_value="device-b",
            template_type="monkey",
            version="1.0.0(100)",
            package_name="com.example.app",
        )

        changes = {item.issue_type: item for item in result.issues}
        self.assertEqual(changes["crash"].change_type, "changed")
        self.assertEqual(changes["crash"].occurrence_delta, 1)
        self.assertEqual(changes["startup_timeout"].change_type, "new")
        self.assertEqual(changes["device_offline"].change_type, "gone")
        self.assertIn("single device_id scopes", " ".join(result.comparability_notes))

    def test_compare_scenarios_aligns_same_issue_without_scenario_name(self) -> None:
        service = build_comparison_service_fixture()

        result = service.compare_issues(
            dimension="scenario",
            left_value="monkey",
            right_value="cold_start_loop",
            version="1.0.0(100)",
            package_name="com.example.app",
        )

        changes = {item.issue_type: item for item in result.issues}
        self.assertEqual(changes["crash"].change_type, "changed")
        self.assertTrue(changes["crash"].left_fingerprint)
        self.assertTrue(changes["crash"].right_fingerprint)
        self.assertEqual(changes["reboot"].change_type, "new")
        self.assertEqual(changes["startup_timeout"].change_type, "gone")
        self.assertEqual(result.issue_change_summary["new_count"], 1)
        self.assertEqual(result.issue_change_summary["gone_count"], 2)


def build_comparison_service_fixture() -> ComparisonService:
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()

    task_monkey_v1 = TaskDefinition(
        task_id="task-monkey-v1",
        task_name="Monkey V1",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(
            package_name="com.example.app",
            version_name="1.0.0",
            version_code="100",
        ),
    )
    task_monkey_v2 = TaskDefinition(
        task_id="task-monkey-v2",
        task_name="Monkey V2",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(
            package_name="com.example.app",
            version_name="2.0.0",
            version_code="200",
        ),
    )
    task_cold_v1 = TaskDefinition(
        task_id="task-cold-v1",
        task_name="Cold Start V1",
        template_type=TaskTemplateType.COLD_START_LOOP,
        target_app=TaskTargetApp(
            package_name="com.example.app",
            version_name="1.0.0",
            version_code="100",
        ),
    )
    for task in (task_monkey_v1, task_monkey_v2, task_cold_v1):
        task_repository.add(task)

    run_v1_a = TaskRun(
        run_id="run-v1-a",
        task_definition_id=task_monkey_v1.task_id,
        task_name=task_monkey_v1.task_name,
        status=TaskRunStatus.FAILED,
        created_at=datetime(2025, 7, 20, 9, 0, 0),
    )
    run_v1_b = TaskRun(
        run_id="run-v1-b",
        task_definition_id=task_monkey_v1.task_id,
        task_name=task_monkey_v1.task_name,
        status=TaskRunStatus.FAILED,
        created_at=datetime(2025, 7, 20, 9, 10, 0),
    )
    run_v2_a = TaskRun(
        run_id="run-v2-a",
        task_definition_id=task_monkey_v2.task_id,
        task_name=task_monkey_v2.task_name,
        status=TaskRunStatus.FAILED,
        created_at=datetime(2025, 7, 20, 9, 20, 0),
    )
    run_cold_v1 = TaskRun(
        run_id="run-cold-v1",
        task_definition_id=task_cold_v1.task_id,
        task_name=task_cold_v1.task_name,
        status=TaskRunStatus.FAILED,
        created_at=datetime(2025, 7, 20, 9, 30, 0),
    )
    for run in (run_v1_a, run_v1_b, run_v2_a, run_cold_v1):
        run_repository.add(run)

    instance_repository.add_many(
        [
            ExecutionInstance(
                instance_id="instance-v1-a",
                run_id=run_v1_a.run_id,
                task_definition_id=task_monkey_v1.task_id,
                device_id="device-a",
                device_snapshot=_device("device-a"),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.EXECUTION_ERROR,
                result_level=ResultLevel.FAILED,
                issues=[
                    _issue(
                        issue_id="issue-crash-v1-a",
                        run_id=run_v1_a.run_id,
                        instance_id="instance-v1-a",
                        device_id="device-a",
                        issue_type=IssueType.CRASH,
                        detected_at=datetime(2025, 7, 20, 9, 1, 0),
                        raw_key="crash:com.example.app",
                    ),
                    _issue(
                        issue_id="issue-offline-v1-a",
                        run_id=run_v1_a.run_id,
                        instance_id="instance-v1-a",
                        device_id="device-a",
                        issue_type=IssueType.DEVICE_OFFLINE,
                        detected_at=datetime(2025, 7, 20, 9, 2, 0),
                        raw_key="device_offline:device-a",
                        severity=SeverityLevel.HIGH,
                        title="执行期间设备离线",
                    ),
                ],
                metadata={"report_path": "runtime/run-v1-a/report.md"},
            ),
            ExecutionInstance(
                instance_id="instance-v1-b",
                run_id=run_v1_b.run_id,
                task_definition_id=task_monkey_v1.task_id,
                device_id="device-b",
                device_snapshot=_device("device-b"),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.EXECUTION_ERROR,
                result_level=ResultLevel.FAILED,
                issues=[
                    _issue(
                        issue_id="issue-crash-v1-b-1",
                        run_id=run_v1_b.run_id,
                        instance_id="instance-v1-b",
                        device_id="device-b",
                        issue_type=IssueType.CRASH,
                        detected_at=datetime(2025, 7, 20, 9, 11, 0),
                        raw_key="crash:com.example.app",
                    ),
                    _issue(
                        issue_id="issue-crash-v1-b-2",
                        run_id=run_v1_b.run_id,
                        instance_id="instance-v1-b",
                        device_id="device-b",
                        issue_type=IssueType.CRASH,
                        detected_at=datetime(2025, 7, 20, 9, 12, 0),
                        raw_key="crash:com.example.app",
                    ),
                    _issue(
                        issue_id="issue-timeout-v1-b",
                        run_id=run_v1_b.run_id,
                        instance_id="instance-v1-b",
                        device_id="device-b",
                        issue_type=IssueType.STARTUP_TIMEOUT,
                        detected_at=datetime(2025, 7, 20, 9, 13, 0),
                        raw_key="startup_timeout:device-b",
                        severity=SeverityLevel.HIGH,
                        title="冷启动超时",
                    ),
                ],
                metadata={"report_path": "runtime/run-v1-b/report.md"},
            ),
            ExecutionInstance(
                instance_id="instance-v2-a",
                run_id=run_v2_a.run_id,
                task_definition_id=task_monkey_v2.task_id,
                device_id="device-a",
                device_snapshot=_device("device-a"),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.EXECUTION_ERROR,
                result_level=ResultLevel.FAILED,
                issues=[
                    _issue(
                        issue_id="issue-crash-v2-a",
                        run_id=run_v2_a.run_id,
                        instance_id="instance-v2-a",
                        device_id="device-a",
                        issue_type=IssueType.CRASH,
                        detected_at=datetime(2025, 7, 20, 9, 21, 0),
                        raw_key="crash:com.example.app",
                    ),
                    _issue(
                        issue_id="issue-timeout-v2-a",
                        run_id=run_v2_a.run_id,
                        instance_id="instance-v2-a",
                        device_id="device-a",
                        issue_type=IssueType.STARTUP_TIMEOUT,
                        detected_at=datetime(2025, 7, 20, 9, 22, 0),
                        raw_key="startup_timeout:device-a",
                        severity=SeverityLevel.HIGH,
                        title="冷启动超时",
                    ),
                ],
                metadata={"report_path": "runtime/run-v2-a/report.md"},
            ),
            ExecutionInstance(
                instance_id="instance-cold-v1",
                run_id=run_cold_v1.run_id,
                task_definition_id=task_cold_v1.task_id,
                device_id="device-a",
                device_snapshot=_device("device-a"),
                template_type=TaskTemplateType.COLD_START_LOOP,
                target_app_package="com.example.app",
                status=ExecutionStatus.FAILED,
                exit_reason=ExitReason.EXECUTION_ERROR,
                result_level=ResultLevel.FAILED,
                issues=[
                    _issue(
                        issue_id="issue-crash-cold-v1",
                        run_id=run_cold_v1.run_id,
                        instance_id="instance-cold-v1",
                        device_id="device-a",
                        issue_type=IssueType.CRASH,
                        detected_at=datetime(2025, 7, 20, 9, 31, 0),
                        raw_key="crash:com.example.app",
                    ),
                    _issue(
                        issue_id="issue-reboot-cold-v1",
                        run_id=run_cold_v1.run_id,
                        instance_id="instance-cold-v1",
                        device_id="device-a",
                        issue_type=IssueType.REBOOT,
                        detected_at=datetime(2025, 7, 20, 9, 32, 0),
                        raw_key="reboot",
                        severity=SeverityLevel.CRITICAL,
                        title="设备发生重启",
                    ),
                ],
                metadata={"report_path": "runtime/run-cold-v1/report.md"},
            ),
        ]
    )

    analysis_service = AnalysisService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
    )
    return ComparisonService(analysis_service=analysis_service)


def _device(device_id: str):
    return Device(
        device_id=device_id,
        serial=device_id,
        connection_state=DeviceConnectionState.ONLINE,
        availability_state=DeviceAvailabilityState.IDLE,
    ).snapshot()


def _issue(
    *,
    issue_id: str,
    run_id: str,
    instance_id: str,
    device_id: str,
    issue_type: IssueType,
    detected_at: datetime,
    raw_key: str,
    severity: SeverityLevel = SeverityLevel.CRITICAL,
    title: str = "检测到 Crash",
) -> IssueRecord:
    package_name = "com.example.app"
    process_name = package_name if issue_type == IssueType.CRASH else ""
    summary = title
    return IssueRecord(
        issue_id=issue_id,
        instance_id=instance_id,
        task_run_id=run_id,
        device_id=device_id,
        issue_type=issue_type,
        issue_title=title,
        severity=severity,
        detected_at=detected_at,
        process_name=process_name,
        package_name=package_name,
        raw_key=raw_key,
        summary=summary,
    )


if __name__ == "__main__":
    unittest.main()
