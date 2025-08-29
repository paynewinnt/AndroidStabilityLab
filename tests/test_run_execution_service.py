from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from stability.app import ExecutionService, RunExecutionService, TaskService
from stability.artifact.collector import CommandResult, IssueArtifactCollector
from stability.domain import (
    ArtifactType,
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    SamplingConfig,
    TaskDefinition,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry
from stability.infrastructure import ArtifactPathPlanner, MonitoringSessionConfig, MonitoringSessionHandle, MonitoringSnapshot
from stability.repositories import (
    DomainExecutionInstanceFactory,
    DomainTaskRunFactory,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)
from stability.scenario.base import ScenarioExecutionResult
from stability.time_utils import utcnow


class FakeCommandRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult]) -> None:
        self._responses = responses

    def run(self, command, *, timeout: int) -> CommandResult:
        normalized = tuple(command)
        if normalized not in self._responses:
            raise AssertionError(f"Unexpected command: {normalized!r}")
        return self._responses[normalized]


class FakeHostCommandRunner:
    def __init__(self, responses: dict[tuple[str, ...], object]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, ...]] = []
        self._cursor: dict[tuple[str, ...], int] = {}

    def run(self, command, *, timeout_seconds: int):
        normalized = tuple(command)
        self.calls.append(normalized)
        if normalized not in self._responses:
            raise AssertionError(f"Unexpected cleanup command: {normalized!r}")
        response = self._responses[normalized]
        if isinstance(response, list):
            index = self._cursor.get(normalized, 0)
            if index >= len(response):
                return response[-1]
            self._cursor[normalized] = index + 1
            return response[index]
        return response


class FailingScenarioRunner:
    def execute(self, task, run, instance, layout, log_path):
        return ScenarioExecutionResult(
            success=False,
            note="Detected native crash during scenario execution.",
            exit_reason="execution_error",
            result_level="failed",
            metadata={
                "stdout_tail": "signal 11 (SIGSEGV) code 1 (SEGV_MAPERR) fault addr 0x0\nProcess: com.example.app, PID: 2456",
                "stderr_tail": "",
            },
        )


class ColdStartTimeoutScenarioRunner:
    def execute(self, task, run, instance, layout, log_path):
        return ScenarioExecutionResult(
            success=False,
            note="冷启动循环第 1 轮启动超时：启动耗时 5800 ms，超过阈值 4000 ms。",
            exit_reason="timeout",
            result_level="failed",
            metadata={
                "template_type": "cold_start_loop",
                "process_name": "com.example.app",
                "package_name": "com.example.app",
                "startup_failure": True,
                "startup_failure_kind": "startup_timeout",
                "startup_failure_loop": 1,
                "stdout_tail": "Status: ok\nWaitTime: 5800",
                "stderr_tail": "",
                "startup_summary": {
                    "configured_loops": 3,
                    "completed_loops": 1,
                    "successful_loops": 0,
                    "timed_out_loop": 1,
                    "average_wait_time_ms": 5800,
                    "min_wait_time_ms": 5800,
                    "max_wait_time_ms": 5800,
                    "startup_timeout_ms": 4000,
                    "launch_target": "com.example.app/.MainActivity",
                    "iterations": [
                        {
                            "iteration": 1,
                            "status": "timeout",
                            "wait_time_ms": 5800,
                            "total_time_ms": 5600,
                            "this_time_ms": 5400,
                        }
                    ],
                },
            },
        )


class ConcurrentSuccessScenarioRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._both_started = threading.Event()
        self.max_active = 0
        self.started_devices: list[str] = []
        self._active = 0

    def execute(self, task, run, instance, layout, log_path):
        with self._lock:
            self.started_devices.append(instance.device_id)
            self._active += 1
            self.max_active = max(self.max_active, self._active)
            if len(self.started_devices) >= 2:
                self._both_started.set()

        self._both_started.wait(timeout=1.0)

        with self._lock:
            self._active -= 1

        return ScenarioExecutionResult(
            success=True,
            note=f"{instance.device_id} completed successfully.",
            exit_reason="completed",
            result_level="passed",
        )


class DeviceAwareScenarioRunner:
    def __init__(self, results_by_device: dict[str, ScenarioExecutionResult]) -> None:
        self._results_by_device = results_by_device
        self.calls: list[str] = []

    def execute(self, task, run, instance, layout, log_path):
        self.calls.append(instance.device_id)
        return self._results_by_device[instance.device_id]


class RetryAwareScenarioRunner:
    def __init__(self, outcomes: list[ScenarioExecutionResult | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def execute(self, task, run, instance, layout, log_path):
        self.calls += 1
        if not self._outcomes:
            raise AssertionError("No more configured outcomes.")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SlowSuccessScenarioRunner:
    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    def execute(self, task, run, instance, layout, log_path):
        time.sleep(self._delay_seconds)
        return ScenarioExecutionResult(
            success=True,
            note="slow scenario completed successfully.",
            exit_reason="completed",
            result_level="passed",
        )


class RecordingMonitoringAdapter:
    def __init__(self) -> None:
        self.started_configs: list[MonitoringSessionConfig] = []
        self.snapshot_count = 0

    def start_session(self, device_id: str, config: MonitoringSessionConfig | None = None, session_name: str | None = None):
        resolved_config = config or MonitoringSessionConfig()
        self.started_configs.append(resolved_config)
        return MonitoringSessionHandle(
            device_id=device_id,
            session_name=session_name or "monitor-session",
            config=resolved_config,
            collector=None,
            state={"device_id": device_id},
        )

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        self.snapshot_count += 1
        monitoring_dir = Path(str(handle.config.extra.get("runtime_monitoring_dir", "") or "."))
        trace_path = monitoring_dir / "trace.perfetto-trace"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_bytes(b"perfetto-trace")
        return MonitoringSnapshot(
            timestamp=utcnow(),
            system={"perfetto_trace_size_bytes": trace_path.stat().st_size},
            apps=[],
            metadata={
                "backend": "perfetto",
                "trace_artifact_path": str(trace_path),
                "normalized_stats": {
                    "trace_status": "captured",
                    "trace_size_bytes": trace_path.stat().st_size,
                    "duration_ms": 4000,
                },
                "artifacts": [
                    {
                        "artifact_type": "perfetto_trace",
                        "file_path": str(trace_path),
                    }
                ],
            },
        )

    def persist_snapshot(self, handle: MonitoringSessionHandle, snapshot: MonitoringSnapshot) -> bool:
        return False

    def stop_session(self, handle: MonitoringSessionHandle, status: str = "completed") -> None:
        return None


class RunExecutionServiceArtifactIntegrationTest(unittest.TestCase):
    def test_stop_run_kills_device_monkey_without_remote_shell_c_wrapper(self) -> None:
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
            pidof_command = ("adb", "-s", "device-1", "shell", "pidof", "com.android.commands.monkey")
            cleanup_runner = FakeHostCommandRunner(
                {
                    pidof_command: [
                        CommandResult(0, "31882\n", ""),
                        CommandResult(1, "", ""),
                    ],
                    ("adb", "-s", "device-1", "shell", "kill", "31882"): CommandResult(0, "", ""),
                    ("adb", "-s", "device-1", "shell", "cmd", "statusbar", "collapse"): CommandResult(0, "", ""),
                    ("adb", "-s", "device-1", "shell", "input", "keyevent", "BACK"): CommandResult(0, "", ""),
                    ("adb", "-s", "device-1", "shell", "am", "force-stop", "com.example.app"): CommandResult(0, "", ""),
                }
            )
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=None,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={},
                artifact_collector=IssueArtifactCollector(command_runner=FakeCommandRunner({})),
                host_command_runner=cleanup_runner,
            )

            task = TaskDefinition(
                task_id="task-stop",
                task_name="Stop Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.stop_run(created_batch.run.run_id, requested_by="tester")

            self.assertEqual(result.run.run_status, "cancelled")
            self.assertIn(pidof_command, cleanup_runner.calls)
            self.assertIn(("adb", "-s", "device-1", "shell", "kill", "31882"), cleanup_runner.calls)
            self.assertNotIn("sh", [part for call in cleanup_runner.calls for part in call])
            self.assertEqual(result.stopped_instance_count, 1)

    def test_execute_run_retries_retryable_transport_exception_and_cleans_up_before_success(self) -> None:
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
                    RuntimeError("adb transport error: device offline"),
                    ScenarioExecutionResult(
                        success=True,
                        note="second attempt succeeded",
                        exit_reason="completed",
                        result_level="passed",
                    ),
                ]
            )
            cleanup_runner = FakeHostCommandRunner(
                {
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "shell",
                        "am",
                        "force-stop",
                        "com.example.app",
                    ): type(
                        "CleanupResult",
                        (),
                        {"returncode": 0, "stdout": "", "stderr": "", "timed_out": False},
                    )()
                }
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
                host_command_runner=cleanup_runner,
            )

            task = TaskDefinition(
                task_id="task-retry",
                task_name="Retry Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
                retry_count=1,
            )

            instance = result.instances[0]
            self.assertEqual(result.run.run_status, "success")
            self.assertEqual(instance.instance_status, "success")
            self.assertEqual(scenario_runner.calls, 2)
            self.assertEqual(len(cleanup_runner.calls), 1)
            self.assertEqual(instance.summary.metadata["retry_policy"]["retry_count"], 1)
            self.assertEqual(instance.summary.metadata["retry_policy"]["strategy"], "classified")
            self.assertEqual(len(instance.summary.metadata["execution_attempts"]), 2)
            self.assertEqual(instance.summary.metadata["execution_attempts"][0]["status"], "exception")
            self.assertTrue(instance.summary.metadata["execution_attempts"][0]["retryable"])
            self.assertEqual(
                instance.summary.metadata["execution_attempts"][0]["retry_category"],
                "adb_transport_exception",
            )
            self.assertEqual(instance.summary.metadata["execution_attempts"][1]["status"], "success")
            self.assertEqual(len(instance.summary.metadata["cleanup_events"]), 1)
            analysis_ready = instance.summary.metadata["analysis_ready"]
            self.assertEqual(analysis_ready["schema_version"], "v1")
            self.assertEqual(analysis_ready["instance"]["template_type"], "monkey")
            self.assertEqual(analysis_ready["instance"]["package_name"], "com.example.app")
            self.assertEqual(analysis_ready["scenario"]["success"], True)
            self.assertEqual(analysis_ready["issues"]["count"], 0)
            self.assertEqual(analysis_ready["artifacts"]["count"], 0)
            self.assertEqual(analysis_ready["report"]["markdown_path"], instance.metadata["report_path"])
            self.assertEqual(analysis_ready["report"]["html_path"], instance.metadata["html_report_path"])
            self.assertEqual(analysis_ready["exception"], {})

            report_text = Path(instance.metadata["report_path"]).read_text(encoding="utf-8")
            html_report_text = Path(instance.metadata["html_report_path"]).read_text(encoding="utf-8")
            self.assertIn("## Execution Attempts", report_text)
            self.assertIn("attempt 1: status=exception", report_text)
            self.assertIn("retry_category=adb_transport_exception", report_text)
            self.assertIn("attempt 2: status=success", report_text)
            self.assertIn("## Cleanup", report_text)
            self.assertIn("<h2>Execution Attempts</h2>", html_report_text)
            self.assertIn("attempt 1: status=exception", html_report_text)
            self.assertEqual(result.report_paths[instance.instance_id], instance.metadata["report_path"])
            self.assertEqual(result.html_report_paths[instance.instance_id], instance.metadata["html_report_path"])

    def test_execute_run_cleans_up_after_final_failure_when_retries_exhausted(self) -> None:
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
                        success=False,
                        note="attempt 1 device dropped",
                        exit_reason="device_offline",
                        result_level="failed",
                    ),
                    ScenarioExecutionResult(
                        success=False,
                        note="attempt 2 device still offline",
                        exit_reason="device_offline",
                        result_level="failed",
                    ),
                ]
            )
            cleanup_command = (
                "adb",
                "-s",
                "device-1",
                "shell",
                "am",
                "force-stop",
                "com.example.app",
            )
            cleanup_runner = FakeHostCommandRunner(
                {
                    cleanup_command: type(
                        "CleanupResult",
                        (),
                        {"returncode": 0, "stdout": "ok\n", "stderr": "", "timed_out": False},
                    )()
                }
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
                host_command_runner=cleanup_runner,
            )

            task = TaskDefinition(
                task_id="task-cleanup",
                task_name="Cleanup Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
                retry_count=1,
            )

            instance = result.instances[0]
            self.assertEqual(result.run.run_status, "failed")
            self.assertEqual(instance.instance_status, "failed")
            self.assertEqual(scenario_runner.calls, 2)
            self.assertEqual(cleanup_runner.calls, [cleanup_command, cleanup_command])
            self.assertEqual(len(instance.summary.metadata["execution_attempts"]), 2)
            self.assertEqual(instance.summary.metadata["execution_attempts"][0]["status"], "failed")
            self.assertTrue(instance.summary.metadata["execution_attempts"][0]["retryable"])
            self.assertEqual(instance.summary.metadata["execution_attempts"][0]["retry_category"], "device_offline")
            self.assertEqual(instance.summary.metadata["execution_attempts"][1]["status"], "failed")
            self.assertTrue(instance.summary.metadata["execution_attempts"][1]["retryable"])
            self.assertEqual(len(instance.summary.metadata["cleanup_events"]), 2)

            report_text = Path(instance.metadata["report_path"]).read_text(encoding="utf-8")
            html_report_text = Path(instance.metadata["html_report_path"]).read_text(encoding="utf-8")
            self.assertIn("attempt 1: status=failed", report_text)
            self.assertIn("retry_category=device_offline", report_text)
            self.assertIn("attempt 2: status=failed", report_text)
            self.assertIn("<h2>Cleanup</h2>", html_report_text)
            self.assertIn("retry_category=device_offline", html_report_text)

    def test_execute_run_does_not_retry_non_retryable_execution_error(self) -> None:
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
                        success=False,
                        note="target package com.example.app is not installed",
                        exit_reason="execution_error",
                        result_level="failed",
                    ),
                ]
            )
            cleanup_command = (
                "adb",
                "-s",
                "device-1",
                "shell",
                "am",
                "force-stop",
                "com.example.app",
            )
            cleanup_runner = FakeHostCommandRunner(
                {
                    cleanup_command: type(
                        "CleanupResult",
                        (),
                        {"returncode": 0, "stdout": "", "stderr": "", "timed_out": False},
                    )()
                }
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
                host_command_runner=cleanup_runner,
            )

            task = TaskDefinition(
                task_id="task-non-retryable",
                task_name="Non Retryable Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
                retry_count=2,
            )

            instance = result.instances[0]
            self.assertEqual(result.run.run_status, "failed")
            self.assertEqual(instance.instance_status, "failed")
            self.assertEqual(scenario_runner.calls, 1)
            self.assertEqual(cleanup_runner.calls, [cleanup_command])
            self.assertEqual(len(instance.summary.metadata["execution_attempts"]), 1)
            self.assertFalse(instance.summary.metadata["execution_attempts"][0]["retryable"])
            self.assertEqual(instance.summary.metadata["execution_attempts"][0]["retry_category"], "execution_error")
            analysis_ready = instance.summary.metadata["analysis_ready"]
            self.assertEqual(analysis_ready["scenario"]["exit_reason"], "execution_error")
            self.assertEqual(analysis_ready["issues"]["count"], 0)
            self.assertEqual(analysis_ready["artifacts"]["count"], 0)
            self.assertEqual(analysis_ready["report"]["execution_log_path"], instance.metadata["execution_log_path"])

    def test_execute_run_persists_analysis_ready_summary_for_exception_path(self) -> None:
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
            scenario_runner = RetryAwareScenarioRunner([RuntimeError("unexpected harness failure")])
            cleanup_command = (
                "adb",
                "-s",
                "device-1",
                "shell",
                "am",
                "force-stop",
                "com.example.app",
            )
            cleanup_runner = FakeHostCommandRunner(
                {
                    cleanup_command: type(
                        "CleanupResult",
                        (),
                        {"returncode": 0, "stdout": "", "stderr": "", "timed_out": False},
                    )()
                }
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
                host_command_runner=cleanup_runner,
            )

            task = TaskDefinition(
                task_id="task-exception-summary",
                task_name="Exception Summary Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
                retry_count=0,
            )

            instance = result.instances[0]
            self.assertEqual(instance.instance_status, "failed")
            analysis_ready = instance.summary.metadata["analysis_ready"]
            self.assertEqual(analysis_ready["scenario"]["success"], False)
            self.assertEqual(analysis_ready["issues"]["count"], 0)
            self.assertEqual(analysis_ready["artifacts"]["count"], 0)
            self.assertEqual(analysis_ready["exception"]["type"], "RuntimeError")
            self.assertIn("unexpected harness failure", analysis_ready["exception"]["message"])

    def test_execute_run_with_max_concurrency_runs_instances_in_parallel(self) -> None:
        with TemporaryDirectory() as tempdir:
            runtime_root = Path(tempdir) / "runtime"
            devices = {
                "device-1": Device(
                    device_id="device-1",
                    serial="device-1",
                    model="Pixel A",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ),
                "device-2": Device(
                    device_id="device-2",
                    serial="device-2",
                    model="Pixel B",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ),
            }
            task_repository = InMemoryTaskRepository()
            run_repository = InMemoryRunRepository()
            instance_repository = InMemoryInstanceRepository()
            execution_service = ExecutionService(
                planner=StaticDevicePlanner(devices=devices),
                run_factory=DomainTaskRunFactory(),
                instance_factory=DomainExecutionInstanceFactory(devices=devices),
                run_repository=run_repository,
                instance_repository=instance_repository,
                state_machine=ExecutionStateMachine(),
                hooks=LifecycleHookRegistry(),
            )
            scenario_runner = ConcurrentSuccessScenarioRunner()
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
                task_id="task-parallel",
                task_name="Parallel Monkey Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=["device-1", "device-2"],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
                max_concurrency=2,
            )

            self.assertEqual(result.run.run_status, "success")
            self.assertEqual(scenario_runner.max_active, 2)
            self.assertEqual(
                {instance.instance_status for instance in result.instances},
                {"success"},
            )
            self.assertEqual(len(result.report_paths), 2)
            self.assertEqual(len(result.html_report_paths), 2)

    def test_execute_run_stop_on_failure_cancels_not_started_instances(self) -> None:
        with TemporaryDirectory() as tempdir:
            runtime_root = Path(tempdir) / "runtime"
            devices = {
                "device-1": Device(
                    device_id="device-1",
                    serial="device-1",
                    model="Pixel A",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ),
                "device-2": Device(
                    device_id="device-2",
                    serial="device-2",
                    model="Pixel B",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ),
                "device-3": Device(
                    device_id="device-3",
                    serial="device-3",
                    model="Pixel C",
                    connection_state=DeviceConnectionState.ONLINE,
                    availability_state=DeviceAvailabilityState.IDLE,
                ),
            }
            task_repository = InMemoryTaskRepository()
            run_repository = InMemoryRunRepository()
            instance_repository = InMemoryInstanceRepository()
            execution_service = ExecutionService(
                planner=StaticDevicePlanner(devices=devices),
                run_factory=DomainTaskRunFactory(),
                instance_factory=DomainExecutionInstanceFactory(devices=devices),
                run_repository=run_repository,
                instance_repository=instance_repository,
                state_machine=ExecutionStateMachine(),
                hooks=LifecycleHookRegistry(),
            )
            scenario_runner = DeviceAwareScenarioRunner(
                {
                    "device-1": ScenarioExecutionResult(
                        success=False,
                        note="device-1 failed",
                        exit_reason="execution_error",
                        result_level="failed",
                    ),
                    "device-2": ScenarioExecutionResult(
                        success=True,
                        note="device-2 success",
                        exit_reason="completed",
                        result_level="passed",
                    ),
                    "device-3": ScenarioExecutionResult(
                        success=True,
                        note="device-3 success",
                        exit_reason="completed",
                        result_level="passed",
                    ),
                }
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
                task_id="task-stop-on-failure",
                task_name="Stop On Failure Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=["device-1", "device-2", "device-3"],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
                stop_on_failure=True,
                max_concurrency=1,
            )

            statuses = {instance.device_id: instance.instance_status for instance in result.instances}
            notes = {instance.device_id: instance.summary.note for instance in result.instances}

            self.assertEqual(result.run.run_status, "partial_failed")
            self.assertEqual(scenario_runner.calls, ["device-1"])
            self.assertEqual(statuses["device-1"], "failed")
            self.assertEqual(statuses["device-2"], "cancelled")
            self.assertEqual(statuses["device-3"], "cancelled")
            self.assertIn("未开始的实例已取消", notes["device-2"])
            self.assertIn("未开始的实例已取消", notes["device-3"])

    def test_execute_run_persists_artifacts_and_report_entries(self) -> None:
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
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=None,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={"monkey": FailingScenarioRunner()},
                artifact_collector=IssueArtifactCollector(
                    command_runner=FakeCommandRunner(
                        {
                            ("adb", "-s", "device-1", "get-state"): CommandResult(0, "device\n", ""),
                            ("adb", "-s", "device-1", "shell", "bugreport"): CommandResult(
                                0,
                                "bugreport snapshot\n",
                                "",
                            ),
                            ("adb", "-s", "device-1", "shell", "dumpsys", "dropbox", "--print"): CommandResult(
                                0,
                                "dropbox entries\nsystem_app_crash\n",
                                "",
                            ),
                            ("adb", "-s", "device-1", "shell", "dumpsys", "meminfo", "com.example.app"): CommandResult(
                                0,
                                "Applications Memory Usage (in Kilobytes):\ncom.example.app\n",
                                "",
                            ),
                            ("adb", "-s", "device-1", "shell", "dumpsys", "SurfaceFlinger"): CommandResult(
                                0,
                                "SurfaceFlinger dump\n",
                                "",
                            ),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "logcat",
                                "-b",
                                "crash",
                                "-d",
                                "-v",
                                "threadtime",
                                "-t",
                                "200",
                            ): CommandResult(0, "07-19 12:00:00.100 E AndroidRuntime: crash buffer\n", ""),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "logcat",
                                "-b",
                                "all",
                                "-d",
                                "-v",
                                "threadtime",
                                "-t",
                                "400",
                            ): CommandResult(0, "07-19 12:00:00.000 E AndroidRuntime: FATAL EXCEPTION\n", ""),
                            ("adb", "-s", "device-1", "shell", "ls", "-t", "/data/anr"): CommandResult(
                                0,
                                "anr_20250719\n",
                                "",
                            ),
                            ("adb", "-s", "device-1", "shell", "cat", "/data/anr/traces.txt"): CommandResult(
                                1,
                                "",
                                "No such file",
                            ),
                            ("adb", "-s", "device-1", "shell", "cat", "/data/anr/anr_20250719"): CommandResult(
                                0,
                                "main blocked\n",
                                "",
                            ),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "shell",
                                "ls",
                                "-t",
                                "/data/tombstones",
                            ): CommandResult(0, "tombstone_01.pb\ntombstone_01\n", ""),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "shell",
                                "cat",
                                "/data/tombstones/tombstone_01",
                            ): CommandResult(0, "signal 11\n", ""),
                        }
                    )
                ),
                host_command_runner=FakeHostCommandRunner(
                    {
                        ("adb", "-s", "device-1", "shell", "am", "force-stop", "com.example.app"): CommandResult(0, "", ""),
                    }
                ),
            )

            task = TaskDefinition(
                task_id="task-1",
                task_name="Monkey Artifact Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
            )

            instance = result.instances[0]
            self.assertEqual(instance.instance_status, "failed")
            self.assertEqual(len(instance.issues), 1)
            self.assertEqual(
                {artifact.artifact_type for artifact in instance.artifacts},
                {
                    ArtifactType.BUGREPORT,
                    ArtifactType.DROPBOX,
                    ArtifactType.DUMPSYS_SURFACEFLINGER,
                    ArtifactType.EXECUTION_LOG,
                    ArtifactType.LOGCAT,
                    ArtifactType.TRACES,
                    ArtifactType.TOMBSTONE,
                },
            )

            report_path = Path(instance.metadata["report_path"])
            html_report_path = Path(instance.metadata["html_report_path"])
            self.assertTrue(report_path.exists())
            self.assertTrue(html_report_path.exists())
            report_text = report_path.read_text(encoding="utf-8")
            html_report_text = html_report_path.read_text(encoding="utf-8")
            self.assertIn("## Artifacts", report_text)
            self.assertIn("logcat.txt", report_text)
            self.assertIn("bugreport.txt", report_text)
            self.assertIn("dropbox.txt", report_text)
            self.assertIn("surfaceflinger.txt", report_text)
            self.assertIn("tombstone.txt", report_text)
            self.assertIn("capture_status: success", report_text)
            self.assertIn("<h2>Artifacts</h2>", html_report_text)
            self.assertIn("logcat.txt", html_report_text)
            self.assertIn("bugreport.txt", html_report_text)
            self.assertIn("dropbox.txt", html_report_text)
            self.assertIn("surfaceflinger.txt", html_report_text)
            self.assertIn("tombstone.txt", html_report_text)
            analysis_ready = instance.summary.metadata["analysis_ready"]
            self.assertEqual(analysis_ready["issues"]["count"], 1)
            self.assertEqual(analysis_ready["issues"]["types"], ["native_crash"])
            self.assertEqual(
                analysis_ready["artifacts"]["types"],
                ["bugreport", "dropbox", "dumpsys_surfaceflinger", "execution_log", "logcat", "tombstone", "traces"],
            )
            self.assertEqual(analysis_ready["report"]["markdown_path"], instance.metadata["report_path"])
            self.assertEqual(analysis_ready["report"]["html_path"], instance.metadata["html_report_path"])

    def test_execute_cold_start_timeout_persists_issue_artifacts_and_startup_report(self) -> None:
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
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=None,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={"cold_start_loop": ColdStartTimeoutScenarioRunner()},
                artifact_collector=IssueArtifactCollector(
                    command_runner=FakeCommandRunner(
                        {
                            ("adb", "-s", "device-1", "get-state"): CommandResult(0, "device\n", ""),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "shell",
                                "bugreport",
                            ): CommandResult(0, "bugreport snapshot\n", ""),
                            ("adb", "-s", "device-1", "shell", "dumpsys", "dropbox", "--print"): CommandResult(
                                0,
                                "dropbox entries\nActivityTaskManager startup timeout\n",
                                "",
                            ),
                            ("adb", "-s", "device-1", "shell", "dumpsys", "meminfo", "com.example.app"): CommandResult(
                                0,
                                "Applications Memory Usage (in Kilobytes):\ncom.example.app\n",
                                "",
                            ),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "logcat",
                                "-b",
                                "crash",
                                "-d",
                                "-v",
                                "threadtime",
                                "-t",
                                "200",
                            ): CommandResult(0, "07-19 12:00:00.100 E ActivityTaskManager: WaitTime 5800\n", ""),
                            (
                                "adb",
                                "-s",
                                "device-1",
                                "logcat",
                                "-b",
                                "all",
                                "-d",
                                "-v",
                                "threadtime",
                                "-t",
                                "400",
                            ): CommandResult(0, "07-19 12:00:00.200 I ActivityManager: cold start timeout\n", ""),
                            ("adb", "-s", "device-1", "shell", "cat", "/data/anr/traces.txt"): CommandResult(
                                1,
                                "",
                                "no traces",
                            ),
                            ("adb", "-s", "device-1", "shell", "ls", "-t", "/data/anr"): CommandResult(1, "", "no anr"),
                            ("adb", "-s", "device-1", "shell", "ls", "-t", "/data/tombstones"): CommandResult(
                                1,
                                "",
                                "no tombstone",
                            ),
                        }
                    )
                ),
            )

            task = TaskDefinition(
                task_id="task-cold-start",
                task_name="Cold Start Loop Task",
                template_type=TaskTemplateType.COLD_START_LOOP,
                target_app=TaskTargetApp(package_name="com.example.app", launch_activity=".MainActivity"),
                task_params={"loop_count": 3, "startup_timeout_ms": 4000},
                selected_device_ids=[device.device_id],
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=False,
                persist_monitoring=False,
            )

            instance = result.instances[0]
            self.assertEqual(instance.instance_status, "failed")
            self.assertEqual(len(instance.issues), 1)
            self.assertEqual(instance.issues[0].issue_type.value, "startup_timeout")
            self.assertEqual(
                {artifact.artifact_type for artifact in instance.artifacts},
                {
                    ArtifactType.BUGREPORT,
                    ArtifactType.DROPBOX,
                    ArtifactType.DUMPSYS_MEMINFO,
                    ArtifactType.EXECUTION_LOG,
                    ArtifactType.LOGCAT,
                },
            )

            report_path = Path(instance.metadata["report_path"])
            html_report_path = Path(instance.metadata["html_report_path"])
            report_text = report_path.read_text(encoding="utf-8")
            html_report_text = html_report_path.read_text(encoding="utf-8")
            self.assertIn("## Startup Summary", report_text)
            self.assertIn("average_wait_time_ms: 5800", report_text)
            self.assertIn("[startup_timeout] 冷启动超时", report_text)
            self.assertIn("## Artifacts", report_text)
            self.assertIn("bugreport.txt", report_text)
            self.assertIn("dropbox.txt", report_text)
            self.assertIn("meminfo.txt", report_text)
            self.assertIn("<h2>Startup Summary</h2>", html_report_text)
            self.assertIn("average_wait_time_ms", html_report_text)
            self.assertIn("<h2>Artifacts</h2>", html_report_text)
            self.assertIn("bugreport.txt", html_report_text)
            self.assertIn("dropbox.txt", html_report_text)
            self.assertIn("meminfo.txt", html_report_text)

    def test_execute_run_records_perfetto_trace_path_from_monitoring_metadata(self) -> None:
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
            monitoring_adapter = RecordingMonitoringAdapter()
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=monitoring_adapter,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={
                    "monkey": RetryAwareScenarioRunner(
                        [
                            ScenarioExecutionResult(
                                success=True,
                                note="perfetto trace collected",
                                exit_reason="completed",
                                result_level="passed",
                            )
                        ]
                    )
                },
                artifact_collector=IssueArtifactCollector(command_runner=FakeCommandRunner({})),
            )

            task = TaskDefinition(
                task_id="task-perfetto",
                task_name="Perfetto Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
                sampling_config=SamplingConfig(
                    interval_seconds=2,
                    monitoring_profile="perfetto",
                    metadata={"perfetto_duration_ms": 4000},
                ),
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=True,
                persist_monitoring=False,
            )

            instance = result.instances[0]
            self.assertEqual(instance.instance_status, "success")
            self.assertEqual(monitoring_adapter.started_configs[0].profile_name, "perfetto")
            self.assertEqual(
                monitoring_adapter.started_configs[0].extra["runtime_monitoring_dir"],
                str(runtime_root / "tasks" / "task-perfetto" / "runs" / created_batch.run.run_id / "executions" / instance.instance_id / "devices" / "device-1" / "monitoring"),
            )
            self.assertTrue(instance.metadata["monitoring_trace_path"].endswith("trace.perfetto-trace"))
            snapshot_path = Path(instance.metadata["monitoring_snapshot_path"])
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot_payload["metadata"]["backend"], "perfetto")
            self.assertEqual(
                snapshot_payload["metadata"]["trace_artifact_path"],
                instance.metadata["monitoring_trace_path"],
            )
            analysis_ready = instance.summary.metadata["analysis_ready"]
            self.assertEqual(analysis_ready["report"]["monitoring_backend"], "perfetto")
            self.assertEqual(
                analysis_ready["report"]["monitoring_trace_path"],
                instance.metadata["monitoring_trace_path"],
            )

    def test_execute_run_passes_enabled_metrics_into_monitoring_config(self) -> None:
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
            monitoring_adapter = RecordingMonitoringAdapter()
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=monitoring_adapter,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={
                    "monkey": RetryAwareScenarioRunner(
                        [
                            ScenarioExecutionResult(
                                success=True,
                                note="metric selection propagated",
                                exit_reason="completed",
                                result_level="passed",
                            )
                        ]
                    )
                },
                artifact_collector=IssueArtifactCollector(command_runner=FakeCommandRunner({})),
            )

            task = TaskDefinition(
                task_id="task-metrics",
                task_name="Metric Scoped Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
                sampling_config=SamplingConfig(
                    interval_seconds=2,
                    enabled_metrics=["fps", "gpu"],
                    monitoring_profile="solox",
                ),
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=True,
                persist_monitoring=False,
            )

            started_config = monitoring_adapter.started_configs[0]
            self.assertEqual(started_config.metrics, {"system": False, "apps": True})
            self.assertEqual(started_config.extra["solox_enabled_metrics"], ("fps", "gpu"))

    def test_execute_run_collects_periodic_monitoring_samples_during_scenario(self) -> None:
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
            monitoring_adapter = RecordingMonitoringAdapter()
            run_execution_service = RunExecutionService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                execution_service=execution_service,
                monitoring_adapter=monitoring_adapter,
                artifact_path_planner=ArtifactPathPlanner(runtime_root=runtime_root),
                scenario_runners={"monkey": SlowSuccessScenarioRunner(1.2)},
                artifact_collector=IssueArtifactCollector(command_runner=FakeCommandRunner({})),
            )

            task = TaskDefinition(
                task_id="task-periodic-monitoring",
                task_name="Periodic Monitoring Task",
                template_type=TaskTemplateType.MONKEY,
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=[device.device_id],
                sampling_config=SamplingConfig(
                    interval_seconds=1,
                    enabled_metrics=["cpu", "memory"],
                ),
            )
            TaskService(repository=task_repository).create_task(task)
            created_batch = execution_service.create_run(task)

            result = run_execution_service.execute_run(
                created_batch.run.run_id,
                collect_snapshot=True,
                persist_monitoring=False,
            )

            instance = result.instances[0]
            self.assertGreaterEqual(monitoring_adapter.snapshot_count, 2)
            self.assertGreaterEqual(instance.summary.metadata["monitoring_sample_count"], 2)
            samples_path = Path(instance.summary.metadata["monitoring_samples_path"])
            samples = json.loads(samples_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(samples), 2)


if __name__ == "__main__":
    unittest.main()
