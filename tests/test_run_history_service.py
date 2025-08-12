from __future__ import annotations

from datetime import datetime
import json
import unittest

from stability.app import ExecutionService, RunHistoryService, TaskService
from stability.domain import (
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    IssueRecord,
    IssueType,
    SeverityLevel,
    TaskDefinition,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry
from stability.repositories import (
    DomainExecutionInstanceFactory,
    DomainTaskRunFactory,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)


class RunHistoryServiceTest(unittest.TestCase):
    def test_list_runs_orders_newest_first_and_supports_extended_filters(self) -> None:
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        instance_repository = InMemoryInstanceRepository()
        devices = {
            "device-1": Device(
                device_id="device-1",
                serial="device-1",
                model="Pixel 1",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            ),
            "device-2": Device(
                device_id="device-2",
                serial="device-2",
                model="Pixel 2",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            ),
        }
        execution_service = ExecutionService(
            planner=StaticDevicePlanner(devices=devices),
            run_factory=DomainTaskRunFactory(),
            instance_factory=DomainExecutionInstanceFactory(devices=devices),
            run_repository=run_repository,
            instance_repository=instance_repository,
            state_machine=ExecutionStateMachine(),
            hooks=LifecycleHookRegistry(),
        )
        history_service = RunHistoryService(
            task_repository=task_repository,
            run_repository=run_repository,
            instance_repository=instance_repository,
        )

        task_service = TaskService(repository=task_repository)
        task_a = task_service.create_task(
            TaskDefinition(
                task_id="task-a",
                task_name="Task A",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.a"),
                selected_device_ids=["device-1"],
            )
        ).task
        task_b = task_service.create_task(
            TaskDefinition(
                task_id="task-b",
                task_name="Task B",
                template_type=TaskTemplateType.COLD_START_LOOP,
                target_app=TaskTargetApp(package_name="com.example.b", launch_activity=".MainActivity"),
                selected_device_ids=["device-2"],
            )
        ).task

        batch_a = execution_service.create_run(task_a)
        batch_b = execution_service.create_run(task_b)
        batch_c = execution_service.create_run(task_a)

        batch_a.run.created_at = datetime(2025, 7, 17, 10, 0, 0)
        batch_b.run.created_at = datetime(2025, 7, 18, 10, 0, 0)
        batch_c.run.created_at = datetime(2025, 7, 19, 10, 0, 0)
        run_repository.save(batch_a.run)
        run_repository.save(batch_b.run)
        run_repository.save(batch_c.run)

        instance_a = batch_a.instances[0]
        execution_service.mark_instance_preparing(task_a, batch_a.run, instance_a)
        execution_service.mark_instance_running(task_a, batch_a.run, instance_a)
        execution_service.complete_instance(
            task_a,
            batch_a.run,
            instance_a,
            summary={"note": "run a ok"},
        )

        instance_b = batch_b.instances[0]
        instance_b.add_issue(
            IssueRecord(
                instance_id=instance_b.instance_id,
                task_run_id=batch_b.run.run_id,
                device_id=instance_b.device_id,
                issue_type=IssueType.DEVICE_OFFLINE,
                issue_title="offline",
                severity=SeverityLevel.HIGH,
                summary="lost adb",
            )
        )
        execution_service.mark_instance_preparing(task_b, batch_b.run, instance_b)
        execution_service.mark_instance_running(task_b, batch_b.run, instance_b)
        execution_service.fail_instance(
            task_b,
            batch_b.run,
            instance_b,
            exit_reason="device_offline",
            summary={"note": "run b failed"},
        )

        all_runs = history_service.list_runs(limit=10)
        self.assertEqual([item["run_id"] for item in all_runs], [batch_c.run.run_id, batch_b.run.run_id, batch_a.run.run_id])

        task_a_runs = history_service.list_runs(task_id=task_a.task_id, limit=10)
        self.assertEqual([item["run_id"] for item in task_a_runs], [batch_c.run.run_id, batch_a.run.run_id])

        failed_runs = history_service.list_runs(run_status="failed", limit=10)
        self.assertEqual([item["run_id"] for item in failed_runs], [batch_b.run.run_id])
        self.assertEqual(failed_runs[0]["instance_status_counts"], {"failed": 1})

        monkey_runs = history_service.list_runs(template_type=TaskTemplateType.MONKEY.value, limit=10)
        self.assertEqual([item["run_id"] for item in monkey_runs], [batch_c.run.run_id, batch_a.run.run_id])

        package_b_runs = history_service.list_runs(package_name="com.example.b", limit=10)
        self.assertEqual([item["run_id"] for item in package_b_runs], [batch_b.run.run_id])

        device_2_runs = history_service.list_runs(device_id="device-2", limit=10)
        self.assertEqual([item["run_id"] for item in device_2_runs], [batch_b.run.run_id])

        issue_runs = history_service.list_runs(has_issue=True, limit=10)
        self.assertEqual([item["run_id"] for item in issue_runs], [batch_b.run.run_id])
        json.dumps(issue_runs, ensure_ascii=False)

        clean_runs = history_service.list_runs(has_issue=False, limit=10)
        self.assertEqual([item["run_id"] for item in clean_runs], [batch_c.run.run_id, batch_a.run.run_id])

        recent_runs = history_service.list_runs(created_from="2025-07-18T00:00:00", limit=10)
        self.assertEqual([item["run_id"] for item in recent_runs], [batch_c.run.run_id, batch_b.run.run_id])

        early_runs = history_service.list_runs(created_to="2025-07-18T23:59:59", limit=10)
        self.assertEqual([item["run_id"] for item in early_runs], [batch_b.run.run_id, batch_a.run.run_id])

    def test_get_run_detail_returns_task_and_instance_history(self) -> None:
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        instance_repository = InMemoryInstanceRepository()
        devices = {
            "device-1": Device(
                device_id="device-1",
                serial="device-1",
                model="Pixel 1",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            ),
            "device-2": Device(
                device_id="device-2",
                serial="device-2",
                model="Pixel 2",
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            ),
        }
        execution_service = ExecutionService(
            planner=StaticDevicePlanner(devices=devices),
            run_factory=DomainTaskRunFactory(),
            instance_factory=DomainExecutionInstanceFactory(devices=devices),
            run_repository=run_repository,
            instance_repository=instance_repository,
            state_machine=ExecutionStateMachine(),
            hooks=LifecycleHookRegistry(),
        )
        history_service = RunHistoryService(
            task_repository=task_repository,
            run_repository=run_repository,
            instance_repository=instance_repository,
        )

        task = TaskService(repository=task_repository).create_task(
            TaskDefinition(
                task_id="task-history",
                task_name="History Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.history"),
                selected_device_ids=["device-1", "device-2"],
            )
        ).task
        batch = execution_service.create_run(task)

        success_instance = batch.instances[0]
        success_instance.metadata["report_path"] = "/tmp/report-1.md"
        success_instance.metadata["html_report_path"] = "/tmp/report-1.html"
        success_instance.metadata["execution_log_path"] = "/tmp/execution-1.log"
        success_instance.metadata["monitoring_backend"] = "solox"
        success_instance.metadata["monitoring_profile"] = "solox"
        success_instance.metadata["monitoring_snapshot_path"] = "/tmp/monitoring-1.json"
        success_instance.metadata["monitoring_trace_path"] = "/tmp/trace-1.perfetto-trace"
        success_instance.metadata["monitoring_session_id"] = "monitoring-session-1"
        execution_service.mark_instance_preparing(task, batch.run, success_instance)
        execution_service.mark_instance_running(task, batch.run, success_instance)
        execution_service.complete_instance(
            task,
            batch.run,
            success_instance,
            summary={
                "note": "instance 1 success",
                "highlights": ["events injected: 100"],
            },
        )

        failed_instance = batch.instances[1]
        failed_instance.metadata["report_path"] = "/tmp/report-2.md"
        failed_instance.metadata["html_report_path"] = "/tmp/report-2.html"
        failed_instance.metadata["execution_log_path"] = "/tmp/execution-2.log"
        execution_service.mark_instance_preparing(task, batch.run, failed_instance)
        execution_service.mark_instance_running(task, batch.run, failed_instance)
        execution_service.fail_instance(
            task,
            batch.run,
            failed_instance,
            exit_reason="device_offline",
            summary={"note": "instance 2 lost device"},
        )

        detail = history_service.get_run_detail(batch.run.run_id)
        json.dumps(detail, ensure_ascii=False)

        self.assertEqual(detail["run_id"], batch.run.run_id)
        self.assertEqual(detail["run_status"], "partial_failed")
        self.assertEqual(detail["task"]["package_name"], "com.example.history")
        self.assertEqual(detail["task"]["template_type"], TaskTemplateType.MONKEY.value)
        self.assertEqual(detail["instance_status_counts"], {"success": 1, "failed": 1})
        self.assertEqual(detail["report_paths"][success_instance.instance_id], "/tmp/report-1.md")
        self.assertEqual(detail["report_paths"][failed_instance.instance_id], "/tmp/report-2.md")
        self.assertEqual(detail["html_report_paths"][success_instance.instance_id], "/tmp/report-1.html")
        self.assertEqual(detail["html_report_paths"][failed_instance.instance_id], "/tmp/report-2.html")
        self.assertEqual(len(detail["instances"]), 2)
        self.assertEqual(detail["instances"][0]["status"], "success")
        self.assertEqual(detail["instances"][0]["report_path"], "/tmp/report-1.md")
        self.assertEqual(detail["instances"][0]["html_report_path"], "/tmp/report-1.html")
        self.assertEqual(detail["instances"][0]["monitoring_backend"], "solox")
        self.assertEqual(detail["instances"][0]["monitoring_profile"], "solox")
        self.assertEqual(detail["instances"][0]["monitoring_snapshot_path"], "/tmp/monitoring-1.json")
        self.assertEqual(detail["instances"][0]["monitoring_trace_path"], "/tmp/trace-1.perfetto-trace")
        self.assertEqual(detail["instances"][0]["monitoring_session_id"], "monitoring-session-1")
        self.assertEqual(detail["instances"][1]["status"], "failed")
        self.assertEqual(detail["instances"][1]["exit_reason"], "device_offline")
        self.assertEqual(detail["instances"][1]["execution_log_path"], "/tmp/execution-2.log")


if __name__ == "__main__":
    unittest.main()
