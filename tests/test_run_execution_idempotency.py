from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import ExecutionService, RunExecutionService, TaskService
from stability.artifact.collector import IssueArtifactCollector
from stability.domain import (
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    TaskDefinition,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry
from stability.infrastructure import ArtifactPathPlanner
from stability.repositories import (
    DomainExecutionInstanceFactory,
    DomainTaskRunFactory,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)
from stability.scenario.base import ScenarioExecutionResult

from tests.test_run_execution_service import FakeCommandRunner, RetryAwareScenarioRunner


class RunExecutionIdempotencyTest(unittest.TestCase):
    def test_execute_run_is_idempotent_for_completed_run(self) -> None:
        with TemporaryDirectory() as tempdir:
            runtime_root = Path(tempdir) / "runtime"
            device = Device(
                device_id="device-1",
                serial="device-1",
                model="Pixel",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            )
            task_repository = InMemoryTaskRepository()
            run_repository = InMemoryRunRepository()
            instance_repository = InMemoryInstanceRepository()
            execution_service = ExecutionService(
                planner=StaticDevicePlanner(devices={device.device_id: device}),
                run_factory=DomainTaskRunFactory(),
                instance_factory=DomainExecutionInstanceFactory(devices={device.device_id: device}),
                run_repository=run_repository,
                instance_repository=instance_repository,
                state_machine=ExecutionStateMachine(),
                hooks=LifecycleHookRegistry(),
            )
            scenario_runner = RetryAwareScenarioRunner(
                [
                    ScenarioExecutionResult(
                        success=True,
                        note="first execution succeeded",
                        exit_reason="completed",
                        result_level="passed",
                    )
                ]
            )
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=None,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={"monkey": scenario_runner},
                artifact_collector=IssueArtifactCollector(command_runner=FakeCommandRunner({})),
            )

            task = TaskDefinition(
                task_id="task-idempotent",
                task_name="Idempotent Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            first_result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
            )
            second_result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
            )

            first_instance = first_result.instances[0]
            self.assertEqual(first_result.run.run_status, "success")
            self.assertEqual(second_result.run.run_status, "success")
            self.assertEqual(second_result.instances[0].instance_status, "success")
            self.assertEqual(scenario_runner.calls, 1)
            self.assertEqual(second_result.executed_instance_count, 0)
            self.assertEqual(second_result.skipped_instance_count, 1)
            self.assertIn("Run 已处于终态", second_result.skipped_reason)
            self.assertEqual(
                second_result.report_paths[first_instance.instance_id],
                first_instance.metadata["report_path"],
            )
            self.assertEqual(
                second_result.html_report_paths[first_instance.instance_id],
                first_instance.metadata["html_report_path"],
            )


if __name__ == "__main__":
    unittest.main()
