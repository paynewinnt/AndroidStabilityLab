from __future__ import annotations

from pathlib import Path
import sys
from threading import Thread
import time
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

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
        self.timeout_seconds: list[int] = []
        self._cursor: dict[tuple[str, ...], int] = {}

    def run(self, command, *, timeout_seconds: int) -> _CommandResult:
        normalized = tuple(command)
        self.calls.append(normalized)
        self.timeout_seconds.append(timeout_seconds)
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

    def test_builds_supported_event_percentage_options(self) -> None:
        config = MonkeyScenarioRunner._config_from_task(
            build_entities(
                task_params={
                    "block_notification_shade": False,
                    "pct_touch": 70,
                    "pct_motion": 30,
                    "pct_syskeys": 0,
                    "pct_appswitch": 0,
                    "pct_anyevent": 0,
                    "pct_trackball": 0,
                    "pct_flip": 0,
                }
            )[0]
        )

        command = MonkeyScenarioRunner._build_monkey_command("device-1", "com.example.app", config)

        self.assertIn("--pct-touch", command)
        self.assertIn("70", command)
        self.assertIn("--pct-motion", command)
        self.assertIn("30", command)
        self.assertIn("--pct-syskeys", command)
        self.assertIn("--pct-appswitch", command)
        self.assertIn("--pct-anyevent", command)

    def test_notification_shade_guard_converts_motion_to_touch_events(self) -> None:
        config = MonkeyScenarioRunner._config_from_task(
            build_entities(
                task_params={
                    "block_notification_shade": True,
                    "pct_touch": 70,
                    "pct_motion": 30,
                }
            )[0]
        )

        command = MonkeyScenarioRunner._build_monkey_command("device-1", "com.example.app", config)

        self.assertEqual(config.event_percentages["pct_touch"], 100)
        self.assertEqual(config.event_percentages["pct_motion"], 0)
        self.assertIn("--pct-touch", command)
        self.assertIn("100", command)
        self.assertIn("--pct-motion", command)
        self.assertIn("0", command)

    def test_execute_recovers_from_inject_events_by_relaunching_target(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
                "shell input keyevent HOME": "",
                "shell am start -W -n com.example.app/.MainActivity": "Status: ok\n",
            }
        )
        command = build_monkey_command("device-1")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    command: [
                        _CommandResult(
                            returncode=110,
                            stdout="Events injected: 42\n",
                            stderr="java.lang.SecurityException: Injecting to another application requires INJECT_EVENTS permission\n",
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
        task, run, instance = build_entities(
            launch_activity="com.example.app/.MainActivity",
            task_params={"relaunch_wait_seconds": 0},
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_attempts"], 2)
        self.assertTrue(result.metadata["recovered_after_inject_events"])
        self.assertEqual(result.metadata["inject_events_recovery_count"], 1)
        self.assertIn("shell input keyevent HOME", collector.commands)
        self.assertIn("shell am start -W -n com.example.app/.MainActivity", collector.commands)

    def test_execute_recovers_from_usb_transport_interruption_by_relaunching_target(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": ["device\n", "offline\n", "device\n"],
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
                "shell input keyevent HOME": "",
                "shell am start -W -n com.example.app/.MainActivity": "Status: ok\n",
            }
        )
        command = build_monkey_command("device-1")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    command: [
                        _CommandResult(
                            returncode=255,
                            stdout=":Sending Touch (ACTION_DOWN): 0:(100.0,100.0)\n",
                            stderr="",
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
        task, run, instance = build_entities(
            launch_activity="com.example.app/.MainActivity",
            task_params={"adb_transport_wait_seconds": 1, "relaunch_wait_seconds": 0},
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_attempts"], 2)
        self.assertTrue(result.metadata["recovered_after_adb_transport"])
        self.assertEqual(result.metadata["adb_transport_recovery_count"], 1)
        self.assertIn("shell input keyevent HOME", collector.commands)
        self.assertIn("shell am start -W -n com.example.app/.MainActivity", collector.commands)

    def test_execute_recovers_from_foreground_drift_by_stopping_foreign_app_and_relaunching_target(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
                "shell am force-stop com.xingin.xhs": "",
                "shell input keyevent HOME": "",
                "shell am start -W -n com.example.app/.MainActivity": "Status: ok\n",
            }
        )
        command = build_monkey_command("device-1")
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=FakeCommandRunner(
                {
                    command: [
                        _CommandResult(
                            returncode=245,
                            stdout="Events injected: 20\n",
                            stderr="[monkey] foreground_drift_detected foreground_package=com.xingin.xhs target_package=com.example.app\n",
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
        task, run, instance = build_entities(
            launch_activity="com.example.app/.MainActivity",
            task_params={"relaunch_wait_seconds": 0},
        )

        with TemporaryDirectory() as tempdir:
            result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_attempts"], 2)
        self.assertTrue(result.metadata["recovered_after_foreground_drift"])
        self.assertEqual(result.metadata["foreground_drift_recovery_count"], 1)
        self.assertIn("shell am force-stop com.xingin.xhs", collector.commands)
        self.assertIn("shell am start -W -n com.example.app/.MainActivity", collector.commands)

    def test_parse_foreground_package_prefers_current_focus(self) -> None:
        output = (
            "mCurrentFocus=Window{c2b32fc u0 com.dragon.read/com.dragon.read.component.shortvideo.impl.ShortSeriesActivity}\n"
            "mFocusedApp=ActivityRecord{278a918 u0 com.xingin.xhs/.index.v2.IndexActivityV2 t57}\n"
        )

        self.assertEqual(MonkeyScenarioRunner._parse_foreground_package(output), "com.dragon.read")

    def test_parse_foreground_package_detects_notification_shade_focus(self) -> None:
        output = "mCurrentFocus=Window{4479d2 u0 NotificationShade}\n"

        self.assertEqual(MonkeyScenarioRunner._parse_foreground_package(output), "com.android.systemui")

    def test_stop_device_monkey_processes_kills_all_residual_monkey_pids(self) -> None:
        collector = FakeADBCollector(
            {
                "shell ps -A": (
                    "USER PID PPID VSZ RSS WCHAN ADDR S NAME\n"
                    "shell 101 1 123 456 0 0 S com.android.commands.monkey\n"
                    "shell 202 1 123 456 0 0 S com.android.commands.monkey\n"
                ),
                "shell kill 101 202": "",
            }
        )

        MonkeyScenarioRunner._stop_device_monkey_processes(collector)

        self.assertIn("shell kill 101 202", collector.commands)

    def test_foreground_guard_stops_running_command_when_foreground_drifts(self) -> None:
        collector = FakeADBCollector(
            {
                "shell dumpsys window": (
                    "mCurrentFocus=Window{c2b32fc u0 com.xingin.xhs/com.xingin.xhs.index.v2.IndexActivityV2}\n"
                )
            }
        )
        runner = MonkeyScenarioRunner()

        with TemporaryDirectory() as tempdir:
            result = runner._run_command_with_foreground_guard(
                collector=collector,
                package_name="com.example.app",
                allowed_packages=("com.example.app",),
                command=[sys.executable, "-c", "import time; time.sleep(5)"],
                timeout_seconds=10,
                poll_interval_seconds=0.1,
                grace_seconds=0,
                log_path=Path(tempdir) / "execution.log",
                attempt_index=1,
            )

        self.assertEqual(result.returncode, 245)
        self.assertIn("foreground_drift_detected", result.stderr)
        self.assertIn("foreground_package=com.xingin.xhs", result.stderr)

    def test_stop_active_processes_terminates_foreground_guard_process(self) -> None:
        collector = FakeADBCollector(
            {
                "shell dumpsys window": "mCurrentFocus=Window{c2b32fc u0 com.example.app/.MainActivity}\n",
            }
        )
        collector.device_id = "device-1"
        runner = MonkeyScenarioRunner()
        result_box: dict[str, _CommandResult] = {}

        with TemporaryDirectory() as tempdir:
            thread = Thread(
                target=lambda: result_box.update(
                    result=runner._run_command_with_foreground_guard(
                        collector=collector,
                        package_name="com.example.app",
                        allowed_packages=("com.example.app",),
                        command=[sys.executable, "-c", "import time; time.sleep(5)"],
                        timeout_seconds=10,
                        poll_interval_seconds=0.1,
                        grace_seconds=0,
                        log_path=Path(tempdir) / "execution.log",
                        attempt_index=1,
                    )
                )
            )
            thread.start()
            time.sleep(0.3)

            stopped = MonkeyScenarioRunner.stop_active_processes(
                device_ids=("device-1",),
                package_name="com.example.app",
                timeout_seconds=2,
            )
            thread.join(timeout=3)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(stopped), 1)
        self.assertTrue(stopped[0]["ok"])
        self.assertIn("result", result_box)
        self.assertNotEqual(result_box["result"].returncode, 0)

    def test_execute_stops_recovery_retry_after_overall_timeout(self) -> None:
        collector = FakeADBCollector(
            {
                "get-state": "device\n",
                "shell pm list packages com.example.app": "package:com.example.app\n",
                "shell am force-stop com.example.app": "",
                "shell input keyevent HOME": "",
                "shell am start -W -n com.example.app/.MainActivity": "Status: ok\n",
            }
        )
        command = build_monkey_command("device-1")
        command_runner = FakeCommandRunner(
            {
                command: [
                    _CommandResult(
                        returncode=110,
                        stdout="Events injected: 42\n",
                        stderr="java.lang.SecurityException: Injecting to another application requires INJECT_EVENTS permission\n",
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
        )
        runner = MonkeyScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            command_runner=command_runner,
        )
        task, run, instance = build_entities(
            launch_activity="com.example.app/.MainActivity",
            task_params={"timeout_seconds": 1, "relaunch_wait_seconds": 0},
        )

        with TemporaryDirectory() as tempdir:
            with patch("stability.scenario.monkey.time.monotonic", side_effect=[0.0, 0.1, 1.1]):
                result = runner.execute(task, run, instance, None, Path(tempdir) / "execution.log")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_reason, "timeout")
        self.assertEqual(result.metadata["command_attempts"], 1)
        self.assertEqual(result.metadata["inject_events_recovery_count"], 0)
        self.assertEqual(command_runner.calls.count(command), 1)
        self.assertEqual(command_runner.timeout_seconds, [1])
        self.assertIn("overall_timeout_reached", result.metadata["stderr_tail"])


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
        "--pct-touch",
        "100",
        "--pct-motion",
        "0",
        "--ignore-crashes",
        "--ignore-timeouts",
        "--ignore-security-exceptions",
        "-v",
        "100",
    )


def build_entities(
    *,
    device_id: str = "device-1",
    launch_activity: str = "",
    task_params: dict | None = None,
) -> tuple[TaskDefinition, TaskRun, ExecutionInstance]:
    task = TaskDefinition(
        task_id="task-1",
        task_name="Monkey Task",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(package_name="com.example.app", launch_activity=launch_activity),
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
