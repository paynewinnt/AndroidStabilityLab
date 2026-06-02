from __future__ import annotations

from datetime import datetime
from tempfile import TemporaryDirectory
import unittest

from stability.domain import AppError
from stability.app.analysis_service import AnalysisService
from stability.app.issue_fingerprint_governance_service import IssueFingerprintGovernanceService
from stability.domain import (
    ArtifactCaptureStatus,
    ArtifactRecord,
    ArtifactType,
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


class AnalysisServiceTest(unittest.TestCase):
    def test_list_top_issues_groups_same_crash_across_devices(self) -> None:
        service = build_service_fixture()

        items = service.list_top_issues(package_name="com.example.app")

        self.assertEqual(len(items), 2)
        top_issue = items[0]
        self.assertEqual(top_issue.issue_type.value, "crash")
        self.assertEqual(top_issue.occurrence_count, 2)
        self.assertEqual(top_issue.affected_device_count, 2)
        self.assertEqual(top_issue.affected_scenario_count, 1)
        self.assertEqual(list(top_issue.affected_packages), ["com.example.app"])

    def test_list_top_issues_groups_device_offline_without_device_specific_raw_key(self) -> None:
        service = build_service_fixture()

        items = service.list_top_issues(issue_type="device_offline")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].occurrence_count, 2)
        self.assertEqual(items[0].affected_device_count, 2)

    def test_get_issue_group_returns_sample_events_and_artifacts(self) -> None:
        service = build_service_fixture()
        top_issue = service.list_top_issues(issue_type="crash")[0]

        detail = service.get_issue_group(top_issue.fingerprint.value)

        self.assertEqual(detail.fingerprint.value, top_issue.fingerprint.value)
        self.assertEqual(detail.occurrence_count, 2)
        self.assertEqual(len(detail.sample_events), 2)
        self.assertTrue(detail.sample_events[0].artifact_paths)
        self.assertTrue(detail.sample_events[0].report_path.endswith("report.md"))

    def test_get_issue_group_raises_for_missing_fingerprint(self) -> None:
        service = build_service_fixture()

        with self.assertRaises(AppError):
            service.get_issue_group("ifp_missing")

    def test_list_top_issues_applies_fingerprint_suppression(self) -> None:
        with self.subTest("baseline has crash"):
            service = build_service_fixture()
            crash_fingerprint = service.list_top_issues(issue_type="crash")[0].fingerprint.value

        with TemporaryDirectory() as temp_dir:
            governance_service = IssueFingerprintGovernanceService(root_dir=temp_dir)
            governance_service.suppress_fingerprint(fingerprint=crash_fingerprint, reason="duplicate external defect")
            governed_service = build_service_fixture(fingerprint_governance_service=governance_service)

            items = governed_service.list_top_issues()

        self.assertNotIn(crash_fingerprint, {item.fingerprint.value for item in items})
        self.assertEqual({item.issue_type.value for item in items}, {"device_offline"})


def build_service_fixture(
    *,
    fingerprint_governance_service: IssueFingerprintGovernanceService | None = None,
) -> AnalysisService:
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()

    task = TaskDefinition(
        task_id="task-1",
        task_name="Task 1",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(
            package_name="com.example.app",
            version_name="1.0.0",
            version_code="100",
        ),
    )
    task_repository.add(task)

    run = TaskRun(
        run_id="run-1",
        task_definition_id=task.task_id,
        task_name=task.task_name,
        status=TaskRunStatus.SUCCESS,
        created_at=datetime(2025, 7, 20, 8, 0, 0),
        metadata={"build_id": "build-1"},
    )
    run_repository.add(run)

    crash_issue_a = IssueRecord(
        issue_id="issue-crash-a",
        instance_id="instance-a",
        task_run_id=run.run_id,
        device_id="device-a",
        issue_type=IssueType.CRASH,
        issue_title="检测到 Crash",
        severity=SeverityLevel.CRITICAL,
        detected_at=datetime(2025, 7, 20, 8, 1, 0),
        process_name="com.example.app",
        package_name="com.example.app",
        raw_key="crash:com.example.app",
        summary="Process crashed",
    )
    crash_issue_b = IssueRecord(
        issue_id="issue-crash-b",
        instance_id="instance-b",
        task_run_id=run.run_id,
        device_id="device-b",
        issue_type=IssueType.CRASH,
        issue_title="检测到 Crash",
        severity=SeverityLevel.CRITICAL,
        detected_at=datetime(2025, 7, 20, 8, 2, 0),
        process_name="com.example.app",
        package_name="com.example.app",
        raw_key="crash:com.example.app",
        summary="Process crashed again",
    )
    offline_issue_a = IssueRecord(
        issue_id="issue-offline-a",
        instance_id="instance-a",
        task_run_id=run.run_id,
        device_id="device-a",
        issue_type=IssueType.DEVICE_OFFLINE,
        issue_title="执行期间设备离线",
        severity=SeverityLevel.HIGH,
        detected_at=datetime(2025, 7, 20, 8, 3, 0),
        package_name="com.example.app",
        raw_key="device_offline:device-a",
        summary="Device A offline",
    )
    offline_issue_b = IssueRecord(
        issue_id="issue-offline-b",
        instance_id="instance-b",
        task_run_id=run.run_id,
        device_id="device-b",
        issue_type=IssueType.DEVICE_OFFLINE,
        issue_title="执行期间设备离线",
        severity=SeverityLevel.HIGH,
        detected_at=datetime(2025, 7, 20, 8, 4, 0),
        package_name="com.example.app",
        raw_key="device_offline:device-b",
        summary="Device B offline",
    )

    artifact_a = ArtifactRecord(
        artifact_id="artifact-a",
        task_run_id=run.run_id,
        instance_id="instance-a",
        issue_id=crash_issue_a.issue_id,
        artifact_type=ArtifactType.LOGCAT,
        file_path="runtime/run-1/instance-a/logcat.txt",
        capture_status=ArtifactCaptureStatus.SUCCESS,
    )
    artifact_b = ArtifactRecord(
        artifact_id="artifact-b",
        task_run_id=run.run_id,
        instance_id="instance-b",
        issue_id=crash_issue_b.issue_id,
        artifact_type=ArtifactType.LOGCAT,
        file_path="runtime/run-1/instance-b/logcat.txt",
        capture_status=ArtifactCaptureStatus.SUCCESS,
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
                issues=[crash_issue_a, offline_issue_a],
                artifacts=[artifact_a],
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
                issues=[crash_issue_b, offline_issue_b],
                artifacts=[artifact_b],
                metadata={
                    "report_path": "runtime/run-1/instance-b/report.md",
                    "execution_log_path": "runtime/run-1/instance-b/execution.log",
                },
            ),
        ]
    )

    return AnalysisService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        fingerprint_governance_service=fingerprint_governance_service,
    )


if __name__ == "__main__":
    unittest.main()
