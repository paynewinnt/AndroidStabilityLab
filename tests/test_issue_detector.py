from __future__ import annotations

import unittest

from stability.domain import ExecutionInstance, TaskDefinition, TaskRun, TaskTargetApp, TaskTemplateType
from stability.issue import MonkeyIssueDetector
from stability.scenario.base import ScenarioExecutionResult


class MonkeyIssueDetectorTest(unittest.TestCase):
    def test_detect_reboot_issue_from_note_and_output(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Reboot Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            note="device reboot detected during scenario execution",
            metadata={
                "stderr_tail": "sys.boot_completed=1",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["reboot"])
        self.assertEqual(issues[0].severity.value, "critical")

    def test_detect_process_exit_issue_with_process_and_pid(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Process Exit Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            metadata={
                "stdout_tail": "I ActivityManager: Killing 2456:com.example.app/u0a123 (adj 900): empty process",
                "stderr_tail": "",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["process_exit"])
        self.assertEqual(issues[0].process_name, "com.example.app")
        self.assertEqual(issues[0].pid, 2456)

    def test_detect_does_not_emit_process_exit_when_crash_already_detected(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Crash Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            metadata={
                "stdout_tail": (
                    "FATAL EXCEPTION: main\n"
                    "Process: com.example.app, PID: 2456\n"
                    "I ActivityManager: Killing 2456:com.example.app/u0a123 (adj 900): empty process"
                ),
                "stderr_tail": "",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["crash"])

    def test_detect_freeze_issue_from_screen_and_input_keywords(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Freeze Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            metadata={
                "summary": "screen no refresh for 30s, input no response while monkey keeps sending events",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["freeze"])
        self.assertEqual(issues[0].issue_title, "检测到画面冻结或无响应")
        self.assertEqual(issues[0].severity.value, "high")
        self.assertTrue(issues[0].summary.startswith("Freeze:"))
        self.assertIn("screen no refresh", issues[0].metadata["evidence"])
        self.assertEqual(issues[0].metadata["evidence_level"], "strong")
        self.assertEqual(issues[0].metadata["confirmation_level"], "strong")
        self.assertIn("frame_refresh", issues[0].metadata["matched_sources"])
        self.assertIn("input", issues[0].metadata["matched_sources"])
        self.assertTrue(issues[0].metadata["matched_fragments"])
        self.assertTrue(issues[0].metadata["evidence_signals"])

    def test_detect_black_screen_issue_from_logcat_keywords(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Black Screen Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            metadata={
                "logcat_tail": "SurfaceMonitor: surface black on com.example.app after resume",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["black_screen"])
        self.assertEqual(issues[0].issue_title, "检测到黑屏")
        self.assertEqual(issues[0].severity.value, "high")
        self.assertTrue(issues[0].summary.startswith("Black Screen:"))
        self.assertIn("surface black", issues[0].metadata["evidence"])
        self.assertEqual(issues[0].metadata["evidence_level"], "weak")
        self.assertEqual(issues[0].metadata["confirmation_level"], "weak")
        self.assertIn("surfaceflinger", issues[0].metadata["matched_sources"])
        self.assertTrue(issues[0].metadata["matched_fragments"])

    def test_detect_system_server_crash_as_first_class_issue(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="System Server Crash Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            highlights=("framework crash observed",),
            metadata={
                "logcat_tail": (
                    "FATAL EXCEPTION: android.ui\n"
                    "Process: system_server, PID: 1234\n"
                    "java.lang.RuntimeException: boom"
                ),
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["system_server_crash", "java_exception"])
        self.assertEqual(issues[0].issue_title, "检测到 system_server Crash")
        self.assertEqual(issues[0].severity.value, "critical")
        self.assertEqual(issues[0].process_name, "system_server")
        self.assertEqual(issues[0].pid, 1234)
        self.assertIn("system_server", issues[0].metadata["evidence"])
        self.assertIn("text", issues[0].metadata["matched_sources"])
        self.assertTrue(issues[0].metadata["evidence_signals"])

    def test_detect_watchdog_as_first_class_issue_from_metadata(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Watchdog Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            note="device became unresponsive",
            metadata={
                "artifact_summary": "Watchdog: *** WATCHDOG KILLING SYSTEM PROCESS: Blocked in handler on ActivityManager",
                "process_name": "system_server",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual([issue.issue_type.value for issue in issues], ["watchdog"])
        self.assertEqual(issues[0].issue_title, "检测到 Watchdog")
        self.assertEqual(issues[0].severity.value, "critical")
        self.assertEqual(issues[0].process_name, "system_server")
        self.assertIn("WATCHDOG KILLING SYSTEM PROCESS", issues[0].metadata["evidence"])
        self.assertIn("text", issues[0].metadata["matched_sources"])
        self.assertTrue(issues[0].metadata["matched_fragments"])

    def test_detect_extracts_process_and_pid_context(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Detector Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="execution_error",
            result_level="failed",
            metadata={
                "stdout_tail": (
                    "FATAL EXCEPTION: main\n"
                    "Process: com.example.app, PID: 2456\n"
                    "java.lang.RuntimeException: boom"
                ),
                "stderr_tail": "",
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertTrue(issues)
        crash_issue = next(issue for issue in issues if issue.issue_type.value == "crash")
        self.assertEqual(crash_issue.process_name, "com.example.app")
        self.assertEqual(crash_issue.pid, 2456)

    def test_detect_maps_cold_start_timeout_to_startup_timeout_issue(self) -> None:
        detector = MonkeyIssueDetector()
        task = TaskDefinition(
            task_id="task-1",
            task_name="Cold Start Detector Task",
            template_type=TaskTemplateType.COLD_START_LOOP,
            target_app=TaskTargetApp(package_name="com.example.app"),
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
            device_id="device-1",
        )
        scenario_result = ScenarioExecutionResult(
            success=False,
            exit_reason="timeout",
            result_level="failed",
            note="冷启动循环第 1 轮启动超时。",
            metadata={
                "template_type": "cold_start_loop",
                "process_name": "com.example.app",
                "startup_failure": True,
                "startup_failure_kind": "startup_timeout",
                "startup_failure_loop": 1,
                "startup_summary": {"timed_out_loop": 1},
            },
        )

        issues = detector.detect(task, run, instance, scenario_result)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type.value, "startup_timeout")
        self.assertEqual(issues[0].issue_title, "冷启动超时")


if __name__ == "__main__":
    unittest.main()
