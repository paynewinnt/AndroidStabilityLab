from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.domain import ExecutionInstance, TaskDefinition, TaskRun, TaskTargetApp, TaskTemplateType
from stability.scenario.monkey import MonkeyScenarioRunner, _CommandResult


class FakeADBCollector:
    def __init__(self, responses: dict[str, str | list[str]]) -> None:
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
    def __init__(self, responses: dict[tuple[str, ...], _CommandResult | list[_CommandResult]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, ...]] = []
        self._cursor: dict[tuple[str, ...], int] = {}

    def run(self, command, *, timeout_seconds: int) -> _CommandResult:
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


class MonkeyScenarioRunnerTest(unittest.TestCase):
    def test_execute_reports_events_injected_for_successful_run(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
            }
        )
        command = build_monkey_command("device-1")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    command: _CommandResult(
                        returncode=0,
                        stdout="Events injected: 100\n",
                        stderr="",
                        timed_out=False,
                    )
                }
            ),
        )
        task, run, instance = build_entities()

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["events_injected"], 100)
        self.assertEqual(result.metadata["command_attempts"], 1)
        self.assertFalse(result.metadata["recovered_after_disconnect"])

    def test_execute_attempts_tcp_reconnect_when_device_unavailable_before_start(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["offline\n", "device\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
            }
        )
        command = build_monkey_command("192.168.31.99:5555")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "connect", "192.168.31.99:5555"): _CommandResult(
                        returncode=0,
                        stdout="connected to 192.168.31.99:5555\n",
                        stderr="",
                        timed_out=False,
                    ),
                    command: _CommandResult(
                        returncode=0,
                        stdout="Events injected: 100\n",
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
        )
        task, run, instance = build_entities(device_id="192.168.31.99:5555")

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertIn(("adb", "connect", "192.168.31.99:5555"), runner._command_runner.calls)

    def test_execute_retries_tcp_command_after_disconnect_and_succeeds(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "device\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
            }
        )
        command = build_monkey_command("192.168.31.99:5555")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "connect", "192.168.31.99:5555"): _CommandResult(
                        returncode=0,
                        stdout="connected to 192.168.31.99:5555\n",
                        stderr="",
                        timed_out=False,
                    ),
                    command: [
                        _CommandResult(
                            returncode=1,
                            stdout="",
                            stderr="adb: device offline\n",
                            timed_out=False,
                        ),
                        _CommandResult(
                            returncode=0,
                            stdout="Events injected: 100\n",
                            stderr="",
                            timed_out=False,
                        ),
                    ],
                }
            ),
        )
        task, run, instance = build_entities(device_id="192.168.31.99:5555")

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_attempts"], 2)
        self.assertTrue(result.metadata["recovered_after_disconnect"])
        self.assertEqual(runner._command_runner.calls.count(command), 2)

    def test_execute_returns_device_offline_when_reconnect_after_command_failure_fails(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "offline\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
            }
        )
        command = build_monkey_command("192.168.31.99:5555")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "connect", "192.168.31.99:5555"): _CommandResult(
                        returncode=1,
                        stdout="",
                        stderr="failed to connect\n",
                        timed_out=False,
                    ),
                    command: _CommandResult(
                        returncode=None,
                        stdout="",
                        stderr="adb: device offline\n",
                        timed_out=True,
                    ),
                }
            ),
        )
        task, run, instance = build_entities(device_id="192.168.31.99:5555")

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_reason, "device_offline")
        self.assertEqual(result.metadata["command_attempts"], 1)
        self.assertFalse(result.metadata["recovered_after_disconnect"])


def build_monkey_command(device_id: str) -> tuple[str, ...]:
    return (
        "adb",
        "-s",
        device_id,
        "shell",
        "monkey",
        "-p",
        "com.example.app",
        "--throttle",
        "300",
        "--ignore-crashes",
        "--ignore-timeouts",
        "--ignore-security-exceptions",
        "-v",
        "100",
    )


def build_entities(
    *,
    device_id: str = "device-1",
) -> tuple[TaskDefinition, TaskRun, ExecutionInstance]:
    task = TaskDefinition(
        task_id="task-1",
        task_name="Monkey Task",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(package_name="com.example.app"),
        task_params={},
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
