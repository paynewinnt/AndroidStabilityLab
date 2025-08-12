from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.domain import ExecutionInstance, TaskDefinition, TaskRun, TaskTargetApp, TaskTemplateType
from stability.scenario.cold_start_loop import ColdStartLoopScenarioRunner, CommandResult


class FakeADBCollector:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.device_id = None
        self.commands: list[str] = []
        self._cursor: dict[str, int] = {}

    def _run_adb_command(self, command: str, log_errors: bool = False) -> str:
        self.commands.append(command)
        response = self._responses.get(command, "")
        if isinstance(response, list):
            index = self._cursor.get(command, 0)
            if index >= len(response):
                return response[-1] if response else ""
            self._cursor[command] = index + 1
            return response[index]
        return response


class FakeCommandRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult | list[CommandResult]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, ...]] = []
        self._cursor: dict[tuple[str, ...], int] = {}

    def run(self, command, *, timeout_seconds: int) -> CommandResult:
        normalized = tuple(command)
        self.calls.append(normalized)
        if normalized not in self._responses:
            raise AssertionError(f"Unexpected command: {normalized!r}")
        response = self._responses[normalized]
        if isinstance(response, list):
            index = self._cursor.get(normalized, 0)
            if index >= len(response):
                return response[-1]
            self._cursor[normalized] = index + 1
            return response[index]
        return response


class ColdStartLoopScenarioRunnerTest(unittest.TestCase):
    def test_execute_collects_startup_timings_for_successful_loops(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "shell",
                        "am",
                        "start",
                        "-W",
                        "-n",
                        "com.example.app/.MainActivity",
                    ): CommandResult(
                        returncode=0,
                        stdout=(
                            "Status: ok\n"
                            "Activity: com.example.app/.MainActivity\n"
                            "ThisTime: 280\n"
                            "TotalTime: 310\n"
                            "WaitTime: 330\n"
                            "Complete\n"
                        ),
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(task_params={"loop_count": 2, "interval_ms": 0, "launch_wait_ms": 0})

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        summary = result.metadata["startup_summary"]
        self.assertEqual(summary["configured_loops"], 2)
        self.assertEqual(summary["completed_loops"], 2)
        self.assertEqual(summary["successful_loops"], 2)
        self.assertEqual(summary["average_wait_time_ms"], 330.0)
        self.assertEqual(summary["launch_target"], "com.example.app/.MainActivity")
        self.assertEqual(len(summary["iterations"]), 2)

    def test_execute_returns_timeout_failure_when_wait_time_exceeds_threshold(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "shell",
                        "am",
                        "start",
                        "-W",
                        "-n",
                        "com.example.app/.MainActivity",
                    ): CommandResult(
                        returncode=0,
                        stdout=(
                            "Status: ok\n"
                            "Activity: com.example.app/.MainActivity\n"
                            "ThisTime: 5400\n"
                            "TotalTime: 5600\n"
                            "WaitTime: 5800\n"
                            "Complete\n"
                        ),
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={"loop_count": 1, "startup_timeout_ms": 4000, "interval_ms": 0, "launch_wait_ms": 0}
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_reason, "timeout")
        self.assertTrue(result.metadata["startup_failure"])
        self.assertEqual(result.metadata["startup_failure_kind"], "startup_timeout")
        self.assertEqual(result.metadata["startup_summary"]["timed_out_loop"], 1)

    def test_execute_retries_current_loop_after_launch_disconnect_and_succeeds(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "device\n", "device\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        launch_command = (
            "adb",
            "-s",
            "192.168.31.99:5555",
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            "com.example.app/.MainActivity",
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    launch_command: [
                        CommandResult(
                            returncode=1,
                            stdout="",
                            stderr="adb: device offline\n",
                            timed_out=False,
                        ),
                        CommandResult(
                            returncode=0,
                            stdout=(
                                "Status: ok\n"
                                "Activity: com.example.app/.MainActivity\n"
                                "TotalTime: 120\n"
                                "WaitTime: 140\n"
                                "Complete\n"
                            ),
                            stderr="",
                            timed_out=False,
                        ),
                    ],
                    ("adb", "connect", "192.168.31.99:5555"): CommandResult(
                        returncode=0,
                        stdout="connected to 192.168.31.99:5555\n",
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={"loop_count": 1, "interval_ms": 0, "launch_wait_ms": 0},
            device_id="192.168.31.99:5555",
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        summary = result.metadata["startup_summary"]
        self.assertEqual(summary["completed_loops"], 1)
        self.assertEqual(summary["successful_loops"], 1)
        self.assertEqual(summary["iterations"][0]["launch_attempts"], 2)
        self.assertTrue(summary["iterations"][0]["recovered_after_disconnect"])
        self.assertEqual(runner._command_runner.calls.count(launch_command), 2)
        self.assertIn(("adb", "connect", "192.168.31.99:5555"), runner._command_runner.calls)

    def test_execute_returns_device_offline_when_launch_timeout_reconnect_fails(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "device\n", "offline\n", "offline\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        launch_command = (
            "adb",
            "-s",
            "192.168.31.99:5555",
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            "com.example.app/.MainActivity",
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    launch_command: CommandResult(
                        returncode=None,
                        stdout="",
                        stderr="adb: device offline\n",
                        timed_out=True,
                    ),
                    ("adb", "connect", "192.168.31.99:5555"): CommandResult(
                        returncode=1,
                        stdout="",
                        stderr="failed to connect\n",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={"loop_count": 1, "interval_ms": 0, "launch_wait_ms": 0},
            device_id="192.168.31.99:5555",
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_reason, "device_offline")
        self.assertEqual(result.metadata["startup_summary"]["completed_loops"], 1)
        self.assertEqual(result.metadata["startup_summary"]["iterations"][0]["status"], "device_offline")
        self.assertEqual(runner._command_runner.calls.count(("adb", "connect", "192.168.31.99:5555")), 1)

    def test_execute_reconnects_tcp_device_once_and_continues_next_loop(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "device\n", "offline\n", "device\n", "device\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        launch_command = (
            "adb",
            "-s",
            "192.168.31.99:5555",
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            "com.example.app/.MainActivity",
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    launch_command: CommandResult(
                        returncode=0,
                        stdout=(
                            "Status: ok\n"
                            "Activity: com.example.app/.MainActivity\n"
                            "TotalTime: 120\n"
                            "WaitTime: 140\n"
                            "Complete\n"
                        ),
                        stderr="",
                        timed_out=False,
                    ),
                    ("adb", "connect", "192.168.31.99:5555"): CommandResult(
                        returncode=0,
                        stdout="connected to 192.168.31.99:5555\n",
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={"loop_count": 2, "interval_ms": 0, "launch_wait_ms": 0},
            device_id="192.168.31.99:5555",
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["startup_summary"]["completed_loops"], 2)
        self.assertIn(("adb", "connect", "192.168.31.99:5555"), runner._command_runner.calls)

    def test_execute_does_not_retry_launch_failure_for_non_tcp_device(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "device\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        launch_command = (
            "adb",
            "-s",
            "device-1",
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            "com.example.app/.MainActivity",
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    launch_command: CommandResult(
                        returncode=1,
                        stdout="",
                        stderr="adb: device offline\n",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(task_params={"loop_count": 1, "interval_ms": 0, "launch_wait_ms": 0})

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_reason, "execution_error")
        self.assertEqual(result.metadata["startup_failure_kind"], "startup_failure")
        self.assertEqual(result.metadata["startup_summary"]["iterations"][0]["launch_attempts"], 1)
        self.assertEqual(runner._command_runner.calls, [launch_command])

    def test_execute_returns_device_offline_when_tcp_reconnect_fails(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "offline\n", "offline\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
                "shell am force-stop com.example.app": "",
            }
        )
        runner = ColdStartLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "connect", "192.168.31.99:5555"): CommandResult(
                        returncode=1,
                        stdout="",
                        stderr="failed to connect\n",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={"loop_count": 2, "interval_ms": 0, "launch_wait_ms": 0},
            device_id="192.168.31.99:5555",
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_reason, "device_offline")
        self.assertEqual(result.metadata["startup_summary"]["completed_loops"], 0)


def build_entities(
    *,
    task_params: dict | None = None,
    device_id: str = "device-1",
) -> tuple[TaskDefinition, TaskRun, ExecutionInstance]:
    task = TaskDefinition(
        task_id="task-1",
        task_name="Cold Start Task",
        template_type=TaskTemplateType.COLD_START_LOOP,
        target_app=TaskTargetApp(package_name="com.example.app"),
        task_params=task_params or {},
    )
    run = TaskRun(
        run_id="run-1",
        task_definition_id=task.task_id,
        task_name=task.task_name,
    )
    instance = ExecutionInstance(
        instance_id="instance-1",
        run_id=run.run_id,
        task_definition_id=task.task_id,
        device_id=device_id,
    )
    return task, run, instance


if __name__ == "__main__":
    unittest.main()
