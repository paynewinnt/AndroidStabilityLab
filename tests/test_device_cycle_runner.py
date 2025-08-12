from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import unittest

from stability.domain import ExecutionInstance, TaskDefinition, TaskRun, TaskTargetApp, TaskTemplateType
from stability.scenario.device_cycle import (
    CommandResult,
    ForegroundBackgroundLoopScenarioRunner,
    InstallUninstallLoopScenarioRunner,
    RebootLoopScenarioRunner,
    StandbyWakeLoopScenarioRunner,
)


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


class DeviceCycleScenarioRunnerTest(unittest.TestCase):
    def test_foreground_background_loop_runner_executes_configured_loops(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell cmd package resolve-activity --brief com.example.app": "com.example.app/.MainActivity\n",
            }
        )
        runner = ForegroundBackgroundLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "shell", "am", "start", "-W", "-n", "com.example.app/.MainActivity"): CommandResult(
                        returncode=0,
                        stdout="Status: ok\n",
                        stderr="",
                        timed_out=False,
                    ),
                    ("adb", "-s", "device-1", "shell", "input", "keyevent", "KEYCODE_HOME"): CommandResult(
                        returncode=0,
                        stdout="",
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            template_type=TaskTemplateType.FOREGROUND_BACKGROUND_LOOP,
            task_params={"loop_count": 2, "foreground_wait_ms": 0, "background_wait_ms": 0},
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["loop_summary"]["completed_loops"], 2)
        self.assertEqual(result.metadata["launch_target"], "com.example.app/.MainActivity")

    def test_install_uninstall_loop_runner_reinstalls_package_from_apk(self) -> None:
        with NamedTemporaryFile(suffix=".apk") as fake_apk:
            collector = FakeADBCollector(
                {
                    "get-state": "device\n",
                    "shell pm list packages com.example.app": [
                        "package:com.example.app\n",
                        "package:com.example.app\n",
                        "package:com.example.app\n",
                    ],
                }
            )
            runner = InstallUninstallLoopScenarioRunner(
                collector_factory=lambda timeout, retry_count: collector,
                command_runner=FakeCommandRunner(
                    {
                        ("adb", "-s", "device-1", "uninstall", "com.example.app"): CommandResult(
                            returncode=0,
                            stdout="Success\n",
                            stderr="",
                            timed_out=False,
                        ),
                        ("adb", "-s", "device-1", "install", "-r", fake_apk.name): CommandResult(
                            returncode=0,
                            stdout="Success\n",
                            stderr="",
                            timed_out=False,
                        ),
                    }
                ),
                sleep_func=lambda _: None,
            )
            task, run, instance = build_entities(
                template_type=TaskTemplateType.INSTALL_UNINSTALL_LOOP,
                task_params={"loop_count": 1, "apk_path": fake_apk.name, "settle_ms": 0},
            )

            with TemporaryDirectory() as tempdir:
                result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["loop_summary"]["apk_path"], fake_apk.name)
        self.assertEqual(result.metadata["loop_summary"]["completed_loops"], 1)

    def test_reboot_loop_runner_waits_until_device_returns(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "offline\n", "device\n"],
                "shell getprop sys.boot_completed": "1\n",
            }
        )
        runner = RebootLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "reboot"): CommandResult(
                        returncode=0,
                        stdout="",
                        stderr="",
                        timed_out=False,
                    )
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            template_type=TaskTemplateType.REBOOT_LOOP,
            task_params={"loop_count": 1, "settle_ms": 0, "poll_interval_seconds": 1, "boot_wait_timeout_seconds": 5},
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["loop_summary"]["completed_loops"], 1)

    def test_standby_wake_loop_runner_sends_sleep_and_wake_commands(self) -> None:
        collector = FakeADBCollector({"get-state": "device\n"})
        runner = StandbyWakeLoopScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "shell", "input", "keyevent", "KEYCODE_SLEEP"): CommandResult(
                        returncode=0,
                        stdout="",
                        stderr="",
                        timed_out=False,
                    ),
                    ("adb", "-s", "device-1", "shell", "input", "keyevent", "KEYCODE_WAKEUP"): CommandResult(
                        returncode=0,
                        stdout="",
                        stderr="",
                        timed_out=False,
                    ),
                    ("adb", "-s", "device-1", "shell", "input", "keyevent", "KEYCODE_MENU"): CommandResult(
                        returncode=0,
                        stdout="",
                        stderr="",
                        timed_out=False,
                    ),
                }
            ),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            template_type=TaskTemplateType.STANDBY_WAKE_LOOP,
            task_params={"loop_count": 2, "standby_wait_ms": 0, "wake_wait_ms": 0},
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["loop_summary"]["completed_loops"], 2)


def build_entities(
    *,
    template_type: TaskTemplateType,
    task_params: dict[str, object],
    device_id: str = "device-1",
) -> tuple[TaskDefinition, TaskRun, ExecutionInstance]:
    task = TaskDefinition(
        task_id="task-1",
        task_name="Loop Task",
        template_type=template_type,
        target_app=TaskTargetApp(package_name="com.example.app"),
        task_params=task_params,
    )
    run = TaskRun(run_id="run-1", task_definition_id=task.task_id, task_name=task.task_name)
    instance = ExecutionInstance(
        instance_id="instance-1",
        run_id=run.run_id,
        task_definition_id=task.task_id,
        device_id=device_id,
    )
    return task, run, instance


if __name__ == "__main__":
    unittest.main()
