from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from stability.app import IntegrationOutboxService, ReleaseSubmissionService
from stability.domain import TaskRun, TaskRunStatus


class ReleaseSubmissionServiceTest(unittest.TestCase):
    def test_create_submission_creates_task_run_persists_and_publishes_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            outbox = IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox")
            task_service = _FakeTaskService()
            execution_service = _FakeExecutionService()
            run_execution_service = _FakeRunExecutionService(status="success")
            service = ReleaseSubmissionService(
                task_service=task_service,
                execution_service=execution_service,
                run_execution_service=run_execution_service,
                outbox_service=outbox,
                root_dir=Path(temp_dir) / "release_submissions",
                monitoring_backend="solox",
            )

            record = service.create_submission(
                source_platform="release-center",
                source_request_id="REL-2026-001",
                package_name="com.example.app",
                version_name="1.2.3",
                version_code="123",
                build_id="build-123",
                release_channel="gray",
                owner_team="android-client",
                selected_device_ids=("device-a",),
                enabled_metrics=("cpu", "memory"),
                execute_immediately=True,
                created_by="release-bot",
                task_params={"loop_count": 3},
                metadata={"branch": "release/1.2"},
            )
            reloaded = service.get_submission(record.submission_id)
            events = outbox.list_events(limit=10)

            self.assertEqual(record.source_platform, "release-center")
            self.assertEqual(record.source_request_id, "REL-2026-001")
            self.assertEqual(record.package_name, "com.example.app")
            self.assertEqual(record.task_id, task_service.created_task.task_id)
            self.assertEqual(record.run_id, execution_service.created_run.run_id)
            self.assertEqual(record.run_status, "success")
            self.assertEqual(record.submission_status, "executed")
            self.assertEqual(record.monitoring_backend, "solox")
            self.assertEqual(record.metadata["task_params"], {"loop_count": 3})
            self.assertEqual(reloaded.submission_id, record.submission_id)
            created_event = _event_by_type(events, "release_submission.created")
            execution_event = _event_by_type(events, "release_submission.execution_updated")
            self.assertEqual(created_event.target_type, "release_submission")
            self.assertEqual(created_event.target_id, record.submission_id)
            self.assertEqual(created_event.payload["task_id"], record.task_id)
            self.assertEqual(execution_event.payload["run_status"], "success")
            self.assertEqual(run_execution_service.executed_run_id, record.run_id)

    def test_create_submission_keeps_record_when_immediate_execution_fails(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = ReleaseSubmissionService(
                task_service=_FakeTaskService(),
                execution_service=_FakeExecutionService(),
                run_execution_service=_FakeRunExecutionService(error=RuntimeError("device offline")),
                root_dir=Path(temp_dir) / "release_submissions",
            )

            record = service.create_submission(
                source_platform="release-center",
                source_request_id="REL-2026-002",
                package_name="com.example.app",
                execute_immediately=True,
            )

            self.assertEqual(record.run_status, "failed")
            self.assertEqual(record.submission_status, "executed")
            self.assertIn("device offline", record.metadata["execution_error"])

    def test_sync_admission_result_updates_same_submission_and_publishes_event(self) -> None:
        with TemporaryDirectory() as temp_dir:
            outbox = IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox")
            admission_service = _FakeAdmissionCaseService()
            service = ReleaseSubmissionService(
                task_service=_FakeTaskService(),
                execution_service=_FakeExecutionService(),
                admission_case_service=admission_service,
                outbox_service=outbox,
                root_dir=Path(temp_dir) / "release_submissions",
            )
            record = service.create_submission(
                source_platform="release-center",
                source_request_id="REL-2026-003",
                package_name="com.example.app",
            )

            updated = service.sync_admission_result(
                submission_id=record.submission_id,
                baseline_key="baseline-release-gray",
                synced_by="qa-lead",
            )
            events = outbox.list_events(limit=10)

            self.assertEqual(updated.submission_id, record.submission_id)
            self.assertEqual(updated.baseline_key, "baseline-release-gray")
            self.assertEqual(updated.admission_case_id, "admission_case:baseline-release-gray")
            self.assertEqual(updated.admission_status, "approved_with_risk")
            self.assertEqual(updated.admission_final_decision, "conditional_pass")
            self.assertEqual(updated.admission_error_code, "CONDITIONAL_PASS")
            self.assertEqual(updated.submission_status, "admission_synced")
            admission_event = _event_by_type(events, "release_submission.admission_synced")
            self.assertEqual(admission_event.payload["admission_final_decision"], "conditional_pass")


class _FakeTaskService:
    def __init__(self) -> None:
        self.created_task = None

    def create_task(self, task):
        self.created_task = task
        return SimpleNamespace(task=task)


class _FakeExecutionService:
    def __init__(self) -> None:
        self.created_run = None

    def create_run(self, task, *, requested_devices, requested_by, metadata):
        run = TaskRun(
            task_definition_id=task.task_id,
            task_name=task.task_name,
            target_device_ids=list(requested_devices),
            started_by=requested_by,
            metadata=dict(metadata),
        )
        run.status = TaskRunStatus.QUEUED
        self.created_run = run
        return SimpleNamespace(run=run)


class _FakeRunExecutionService:
    def __init__(self, *, status: str = "success", error: Exception | None = None) -> None:
        self._status = status
        self._error = error
        self.executed_run_id = ""

    def execute_run(self, run_id: str, *, max_concurrency: int, retry_count: int):
        self.executed_run_id = run_id
        if self._error is not None:
            raise self._error
        return SimpleNamespace(
            run=SimpleNamespace(run_id=run_id, run_status=self._status),
            report_paths={"run_report": "runtime/reports/run.json"},
        )


class _FakeAdmissionCaseService:
    def get_case(self, baseline_key: str):
        return SimpleNamespace(
            baseline_key=baseline_key,
            case_id=f"admission_case:{baseline_key}",
            status="approved_with_risk",
            final_decision="conditional_pass",
            error_code="CONDITIONAL_PASS",
        )


def _event_by_type(events, event_type: str):
    for event in events:
        if event.event_type == event_type:
            return event
    raise AssertionError(f"event type not found: {event_type}")


if __name__ == "__main__":
    unittest.main()
