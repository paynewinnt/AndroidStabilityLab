from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import unittest

from stability.domain import ExecutionInstance, TaskDefinition, TaskRun, TaskTargetApp, TaskTemplateType
from stability.infrastructure import ArtifactPathPlanner, ArtifactScope
from stability.scenario.custom_automation import (
    CommandResult,
    CustomAutomationScenarioRunner,
)


class FakeADBCollector:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.device_id = None
        self.commands: list[str] = []

    def _run_adb_command(self, command: str, log_errors: bool = False) -> str:
        self.commands.append(command)
        return str(self._responses.get(command, ""))


class FakeCommandRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, command, *, timeout_seconds: int) -> CommandResult:
        normalized = tuple(command)
        self.calls.append(normalized)
        if normalized not in self._responses:
            raise AssertionError(f"Unexpected command: {normalized!r}")
        return self._responses[normalized]


class FakeSelector:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists
        self.clicked = False

    def click(self) -> None:
        self.clicked = True


class FakeU2Client:
    def __init__(self) -> None:
        self.started: list[tuple[str, str | None]] = []
        self.stopped: list[str] = []
        self.clicked: list[tuple[float, float]] = []
        self.keys: list[str] = []
        self.texts: list[str] = []
        self.screenshots: list[str] = []
        self.selectors: list[dict[str, object]] = []

    def app_start(self, package_name: str, activity: str | None = None) -> None:
        self.started.append((package_name, activity))

    def app_stop(self, package_name: str) -> None:
        self.stopped.append(package_name)

    def click(self, x: float, y: float) -> None:
        self.clicked.append((x, y))

    def press(self, key: str) -> None:
        self.keys.append(key)

    def send_keys(self, text: str, clear: bool = False) -> None:
        self.texts.append(text)

    def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"fake-png")
        self.screenshots.append(path)

    def dump_hierarchy(self) -> str:
        return "<hierarchy />"

    def __call__(self, **selector):
        self.selectors.append(selector)
        return FakeSelector(exists=True)


class CustomAutomationScenarioRunnerTest(unittest.TestCase):
    def test_execute_uiautomator2_steps_and_collect_artifacts(self) -> None:
        client = FakeU2Client()
        runner = CustomAutomationScenarioRunner(
            collector_factory=lambda timeout, retry_count: FakeADBCollector({}),
            uiautomator2_client_factory=lambda device_id: client,
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={
                "automation_mode": "uiautomator2",
                "scenario_name": "login_journey",
                "automation_steps": [
                    {"step_id": "launch", "action": "launch_app"},
                    {"step_id": "tap_login", "action": "click", "x": 100, "y": 200},
                    {"step_id": "type_name", "action": "input_text", "text": "demo"},
                    {"step_id": "check_home", "action": "assert_exists", "text": "Home"},
                    {"step_id": "shot", "action": "screenshot", "name": "home"},
                    {"step_id": "tree", "action": "dump_hierarchy", "name": "home_tree"},
                ],
            }
        )

        with TemporaryDirectory() as tempdir:
            layout = ArtifactPathPlanner(runtime_root=Path(tempdir)).plan(
                ArtifactScope(task_id=task.task_id, run_id=run.run_id, execution_id=instance.instance_id, device_id=instance.device_id),
                ensure_exists=True,
            )
            result = runner.execute(task, run, instance, layout, layout.logs_dir / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["automation_mode"], "uiautomator2")
        self.assertEqual(result.metadata["scenario_name"], "login_journey")
        self.assertEqual(result.metadata["step_count"], 6)
        self.assertEqual(client.started[0][0], "com.example.app")
        self.assertEqual(client.clicked[0], (100.0, 200.0))
        self.assertEqual(client.texts[0], "demo")
        self.assertEqual(len(result.metadata["artifact_paths"]), 2)

    def test_execute_external_script_parses_callback_payload(self) -> None:
        with NamedTemporaryFile("w", suffix=".py", delete=False) as script:
            script.write(
                "import json, sys\n"
                "context_path = sys.argv[sys.argv.index('--asl-context') + 1]\n"
                "output_path = sys.argv[sys.argv.index('--asl-output') + 1]\n"
                "payload = json.load(open(context_path, 'r', encoding='utf-8'))\n"
                "json.dump({'success': True, 'note': 'external ok', 'highlights': ['callback ok'], 'steps': [{'step_id': 'business_path', 'status': 'passed'}]}, open(output_path, 'w', encoding='utf-8'))\n"
                "print(json.dumps({'echo_task_id': payload['task']['task_id']}))\n"
            )
            script_path = Path(script.name)
        runner = CustomAutomationScenarioRunner(
            collector_factory=lambda timeout, retry_count: FakeADBCollector({}),
            command_runner=FakeCommandRunner({}),
        )
        # Swap in the real subprocess runner for this one path.
        runner = CustomAutomationScenarioRunner(
            collector_factory=lambda timeout, retry_count: FakeADBCollector({}),
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={
                "automation_mode": "external_script",
                "script_path": str(script_path),
                "scenario_name": "checkout_flow",
            }
        )

        with TemporaryDirectory() as tempdir:
            layout = ArtifactPathPlanner(runtime_root=Path(tempdir)).plan(
                ArtifactScope(task_id=task.task_id, run_id=run.run_id, execution_id=instance.instance_id, device_id=instance.device_id),
                ensure_exists=True,
            )
            result = runner.execute(task, run, instance, layout, layout.logs_dir / "execution.log")

        script_path.unlink(missing_ok=True)
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["automation_mode"], "external_script")
        self.assertEqual(result.metadata["callback_summary"]["callback_payload"]["note"], "external ok")
        self.assertEqual(result.metadata["step_count"], 2)

    def test_execute_adb_script_records_step_timeline(self) -> None:
        collector = FakeADBCollector(
            {
                "shell input keyevent KEYCODE_HOME": "",
                "shell am start -W -n com.example.app/.MainActivity": "Status: ok\n",
            }
        )
        runner = CustomAutomationScenarioRunner(
            collector_factory=lambda timeout, retry_count: collector,
            sleep_func=lambda _: None,
        )
        task, run, instance = build_entities(
            task_params={
                "automation_mode": "adb_script",
                "scenario_name": "warm_path",
                "adb_commands": [
                    {"step_id": "home", "command": "shell input keyevent KEYCODE_HOME"},
                    {"step_id": "launch", "command": "shell am start -W -n com.example.app/.MainActivity"},
                ],
            }
        )

        with TemporaryDirectory() as tempdir:
            layout = ArtifactPathPlanner(runtime_root=Path(tempdir)).plan(
                ArtifactScope(task_id=task.task_id, run_id=run.run_id, execution_id=instance.instance_id, device_id=instance.device_id),
                ensure_exists=True,
            )
            result = runner.execute(task, run, instance, layout, layout.logs_dir / "execution.log")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["automation_mode"], "adb_script")
        self.assertEqual(result.metadata["step_count"], 2)
        self.assertEqual(collector.commands[0], "shell input keyevent KEYCODE_HOME")


def build_entities(*, task_params: dict[str, object]) -> tuple[TaskDefinition, TaskRun, ExecutionInstance]:
    task = TaskDefinition(
        task_id="task-custom-1",
        task_name="Custom Automation Task",
        template_type=TaskTemplateType.CUSTOM,
        target_app=TaskTargetApp(package_name="com.example.app"),
        task_params=task_params,
    )
    run = TaskRun(run_id="run-custom-1", task_definition_id=task.task_id, task_name=task.task_name)
    instance = ExecutionInstance(
        instance_id="instance-custom-1",
        run_id=run.run_id,
        task_definition_id=task.task_id,
        device_id="device-1",
    )
    return task, run, instance


if __name__ == "__main__":
    unittest.main()
