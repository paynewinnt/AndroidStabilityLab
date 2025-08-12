from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.artifact.collector import CommandResult, IssueArtifactCollector
from stability.domain import (
    ArtifactType,
    ExecutionInstance,
    IssueRecord,
    IssueType,
    SeverityLevel,
    TaskDefinition,
    TaskRun,
    TaskTargetApp,
)
from stability.infrastructure import ArtifactPathPlanner, ArtifactScope


class FakeCommandRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, command, *, timeout: int) -> CommandResult:
        normalized = tuple(command)
        self.calls.append(normalized)
        if normalized not in self._responses:
            raise AssertionError(f"Unexpected command: {normalized!r}")
        return self._responses[normalized]


class IssueArtifactCollectorTest(unittest.TestCase):
    def test_capture_collects_local_and_remote_artifacts(self) -> None:
        with TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            log_path = temp_root / "execution.log"
            log_path.write_text("execution log\n", encoding="utf-8")
            snapshot_path = temp_root / "snapshot.json"
            snapshot_path.write_text('{"fps": 60}\n', encoding="utf-8")

            task, run, instance, scope = build_runtime_entities()
            command_runner = FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "get-state"): CommandResult(0, "device\n", ""),
                    ("adb", "-s", "device-1", "shell", "bugreport"): CommandResult(
                        0,
                        "bugreport header\nsection\n",
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
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "logcat",
                        "--pid",
                        "2456",
                        "-d",
                        "-v",
                        "threadtime",
                        "-t",
                        "250",
                    ): CommandResult(0, "07-19 12:00:00.000 E AndroidRuntime: pid scoped\n", ""),
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
                    ): CommandResult(0, "07-19 12:00:00.000 I Test: crash\n", ""),
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
                        "----- pid 100 -----\nmain blocked\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "ls", "-t", "/data/tombstones"): CommandResult(
                        0,
                        "tombstone_09.pb\ntombstone_09\n",
                        "",
                    ),
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "shell",
                        "cat",
                        "/data/tombstones/tombstone_09",
                    ): CommandResult(0, "signal 11\nbacktrace:\n", ""),
                }
            )
            collector = IssueArtifactCollector(command_runner=command_runner)
            planner = ArtifactPathPlanner(runtime_root=temp_root / "runtime")

            artifacts, errors = collector.capture(
                task=task,
                run=run,
                instance=instance,
                scope=scope,
                artifact_path_planner=planner,
                log_path=log_path,
                monitoring_snapshot_path=str(snapshot_path),
            )

            self.assertEqual(errors, [])
            self.assertEqual(
                {artifact.artifact_type for artifact in artifacts},
                {
                    ArtifactType.EXECUTION_LOG,
                    ArtifactType.PERFORMANCE_SNAPSHOT,
                    ArtifactType.BUGREPORT,
                    ArtifactType.DROPBOX,
                    ArtifactType.DUMPSYS_MEMINFO,
                    ArtifactType.LOGCAT,
                    ArtifactType.TRACES,
                    ArtifactType.TOMBSTONE,
                },
            )
            self.assertTrue(all(Path(artifact.file_path).exists() for artifact in artifacts))
            logcat_artifact = next(artifact for artifact in artifacts if artifact.artifact_type == ArtifactType.LOGCAT)
            logcat_text = Path(logcat_artifact.file_path).read_text(encoding="utf-8")
            self.assertIn("===== pid_tail =====", logcat_text)
            self.assertIn("===== crash_buffer =====", logcat_text)
            self.assertEqual(logcat_artifact.metadata["issue_pid"], 2456)
            tombstone_artifact = next(
                artifact for artifact in artifacts if artifact.artifact_type == ArtifactType.TOMBSTONE
            )
            self.assertEqual(tombstone_artifact.metadata["remote_path"], "/data/tombstones/tombstone_09")

    def test_capture_keeps_local_artifacts_and_reports_skipped_remote_evidence_when_device_offline(self) -> None:
        with TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            log_path = temp_root / "execution.log"
            log_path.write_text("execution log\n", encoding="utf-8")

            task, run, instance, scope = build_runtime_entities()
            command_runner = FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "get-state"): CommandResult(1, "offline\n", "offline"),
                }
            )
            collector = IssueArtifactCollector(command_runner=command_runner)
            planner = ArtifactPathPlanner(runtime_root=temp_root / "runtime")

            artifacts, errors = collector.capture(
                task=task,
                run=run,
                instance=instance,
                scope=scope,
                artifact_path_planner=planner,
                log_path=log_path,
            )

            self.assertEqual([artifact.artifact_type for artifact in artifacts], [ArtifactType.EXECUTION_LOG])
            self.assertEqual(len(errors), 6)
            self.assertTrue(any("bugreport 抓取跳过" in error for error in errors))
            self.assertTrue(any("dropbox 抓取跳过" in error for error in errors))
            self.assertTrue(any("meminfo 抓取跳过" in error for error in errors))
            self.assertTrue(any("logcat 抓取跳过" in error for error in errors))
            self.assertTrue(any("traces 抓取跳过" in error for error in errors))
            self.assertTrue(any("tombstone 抓取跳过" in error for error in errors))

    def test_capture_keeps_other_artifacts_when_bugreport_fails(self) -> None:
        with TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            log_path = temp_root / "execution.log"
            log_path.write_text("execution log\n", encoding="utf-8")

            task, run, instance, scope = build_runtime_entities()
            command_runner = FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "get-state"): CommandResult(0, "device\n", ""),
                    ("adb", "-s", "device-1", "shell", "bugreport"): CommandResult(1, "", "permission denied"),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "dropbox", "--print"): CommandResult(
                        0,
                        "dropbox entries\nsystem_app_crash\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "meminfo", "com.example.app"): CommandResult(
                        1,
                        "",
                        "meminfo permission denied",
                    ),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "meminfo", "2456"): CommandResult(
                        1,
                        "",
                        "meminfo permission denied",
                    ),
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "logcat",
                        "--pid",
                        "2456",
                        "-d",
                        "-v",
                        "threadtime",
                        "-t",
                        "250",
                    ): CommandResult(0, "07-19 12:00:00.000 E AndroidRuntime: pid scoped\n", ""),
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
                    ): CommandResult(1, "", "no crash buffer"),
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
                    ): CommandResult(0, "07-19 12:00:00.000 I Test: fallback logcat\n", ""),
                    ("adb", "-s", "device-1", "shell", "ls", "-t", "/data/anr"): CommandResult(1, "", "no anr"),
                    ("adb", "-s", "device-1", "shell", "cat", "/data/anr/traces.txt"): CommandResult(
                        1,
                        "",
                        "No such file",
                    ),
                    ("adb", "-s", "device-1", "shell", "ls", "-t", "/data/tombstones"): CommandResult(
                        1,
                        "",
                        "no tombstone",
                    ),
                }
            )
            collector = IssueArtifactCollector(command_runner=command_runner)
            planner = ArtifactPathPlanner(runtime_root=temp_root / "runtime")

            artifacts, errors = collector.capture(
                task=task,
                run=run,
                instance=instance,
                scope=scope,
                artifact_path_planner=planner,
                log_path=log_path,
            )

            self.assertEqual(
                {artifact.artifact_type for artifact in artifacts},
                {
                    ArtifactType.EXECUTION_LOG,
                    ArtifactType.DROPBOX,
                    ArtifactType.LOGCAT,
                },
            )
            self.assertTrue(any("bugreport 抓取失败" in error for error in errors))

    def test_capture_meminfo_falls_back_to_pid_when_package_lookup_fails(self) -> None:
        with TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            log_path = temp_root / "execution.log"
            log_path.write_text("execution log\n", encoding="utf-8")

            task, run, instance, scope = build_runtime_entities()
            issue = instance.issues[0]
            issue.issue_type = IssueType.STARTUP_TIMEOUT
            issue.pid = None
            issue.process_name = "com.example.app"
            command_runner = FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "get-state"): CommandResult(0, "device\n", ""),
                    ("adb", "-s", "device-1", "shell", "bugreport"): CommandResult(1, "", "permission denied"),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "dropbox", "--print"): CommandResult(
                        0,
                        "dropbox entries\nsystem_server_wtf\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "meminfo", "com.example.app"): CommandResult(
                        0,
                        "No process found for: com.example.app\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "pidof", "com.example.app"): CommandResult(
                        0,
                        "2456\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "meminfo", "2456"): CommandResult(
                        0,
                        "Applications Memory Usage (in Kilobytes):\n** MEMINFO in pid 2456 [com.example.app] **\n",
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
            collector = IssueArtifactCollector(command_runner=command_runner)
            planner = ArtifactPathPlanner(runtime_root=temp_root / "runtime")

            artifacts, errors = collector.capture(
                task=task,
                run=run,
                instance=instance,
                scope=scope,
                artifact_path_planner=planner,
                log_path=log_path,
            )

            meminfo_artifact = next(
                artifact for artifact in artifacts if artifact.artifact_type == ArtifactType.DUMPSYS_MEMINFO
            )
            dropbox_artifact = next(
                artifact for artifact in artifacts if artifact.artifact_type == ArtifactType.DROPBOX
            )
            self.assertEqual(meminfo_artifact.metadata["target_name"], "com.example.app")
            self.assertEqual(meminfo_artifact.metadata["resolved_pid"], 2456)
            self.assertTrue(Path(dropbox_artifact.file_path).exists())
            self.assertFalse(any("meminfo 抓取失败" in error for error in errors))

    def test_capture_display_issue_collects_multi_source_evidence(self) -> None:
        with TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            log_path = temp_root / "execution.log"
            log_path.write_text("execution log\n", encoding="utf-8")
            snapshot_path = temp_root / "snapshot.json"
            trace_path = temp_root / "trace.perfetto-trace"
            trace_path.write_bytes(b"perfetto system_server SurfaceFlinger frame_timeline")
            snapshot_path.write_text(
                '{"metadata": {"backend": "perfetto", "trace_artifact_path": "' + str(trace_path) + '"}}\n',
                encoding="utf-8",
            )

            task, run, instance, scope = build_runtime_entities()
            issue = instance.issues[0]
            issue.issue_type = IssueType.BLACK_SCREEN
            issue.metadata = {
                "confirmation_level": "weak",
                "evidence_signals": [{"source": "text", "fragment": "surface black"}],
                "matched_sources": ["text"],
            }
            command_runner = FakeCommandRunner(
                {
                    ("adb", "-s", "device-1", "get-state"): CommandResult(0, "device\n", ""),
                    ("adb", "-s", "device-1", "shell", "bugreport"): CommandResult(1, "", "permission denied"),
                    ("adb", "-s", "device-1", "shell", "dumpsys", "SurfaceFlinger"): CommandResult(
                        0,
                        "SurfaceFlinger visible layers: 0\nSurfaceView com.example.app black screen no refresh\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "screencap", "-p", "/data/local/tmp/asl_issue_issue-1.png"): CommandResult(
                        0,
                        "",
                        "",
                    ),
                    ("adb", "-s", "device-1", "pull", "/data/local/tmp/asl_issue_issue-1.png", str(temp_root / "runtime" / "tasks" / "task-1" / "runs" / "run-1" / "executions" / "instance-1" / "devices" / "device-1" / "artifacts" / "issue-1" / "screenshot.png")): CommandResult(
                        0,
                        "pulled\n",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "rm", "-f", "/data/local/tmp/asl_issue_issue-1.png"): CommandResult(
                        0,
                        "",
                        "",
                    ),
                    ("adb", "-s", "device-1", "shell", "getevent", "-lt", "-c", "80"): CommandResult(
                        0,
                        "[ 1.0] /dev/input/event2: EV_ABS\n",
                        "",
                    ),
                    (
                        "adb",
                        "-s",
                        "device-1",
                        "logcat",
                        "--pid",
                        "2456",
                        "-d",
                        "-v",
                        "threadtime",
                        "-t",
                        "250",
                    ): CommandResult(0, "07-19 12:00:00.050 E SurfaceMonitor: pid scoped surface black\n", ""),
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
                    ): CommandResult(0, "07-19 12:00:00.100 E SurfaceMonitor: surface black\n", ""),
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
                    ): CommandResult(0, "07-19 12:00:00.200 I InputReader: event delivered\n", ""),
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
            collector = IssueArtifactCollector(command_runner=command_runner)
            planner = ArtifactPathPlanner(runtime_root=temp_root / "runtime")

            artifacts, errors = collector.capture(
                task=task,
                run=run,
                instance=instance,
                scope=scope,
                artifact_path_planner=planner,
                log_path=log_path,
                monitoring_snapshot_path=str(snapshot_path),
            )

            artifact_types = {artifact.artifact_type for artifact in artifacts}
            self.assertIn(ArtifactType.DUMPSYS_SURFACEFLINGER, artifact_types)
            self.assertIn(ArtifactType.SCREENSHOT, artifact_types)
            self.assertIn(ArtifactType.INPUT_EVENTS, artifact_types)
            self.assertIn(ArtifactType.PERFETTO_TRACE, artifact_types)
            surfaceflinger_artifact = next(
                artifact for artifact in artifacts if artifact.artifact_type == ArtifactType.DUMPSYS_SURFACEFLINGER
            )
            perfetto_artifact = next(artifact for artifact in artifacts if artifact.artifact_type == ArtifactType.PERFETTO_TRACE)
            self.assertEqual(surfaceflinger_artifact.metadata["structured_evidence"]["parser"], "surfaceflinger")
            self.assertIn("black_screen", surfaceflinger_artifact.metadata["structured_evidence"]["issue_hints"])
            self.assertEqual(perfetto_artifact.metadata["structured_evidence"]["parser"], "perfetto")
            self.assertEqual(issue.metadata["confirmation_level"], "multi_evidence")
            self.assertIn("surfaceflinger", issue.metadata["matched_sources"])
            self.assertIn("screenshot", issue.metadata["matched_sources"])
            self.assertIn("input", issue.metadata["matched_sources"])
            self.assertIn("structured_artifact_evidence", issue.metadata)
            self.assertTrue(any(signal.get("hint") == "black_screen" for signal in issue.metadata["evidence_signals"]))
            self.assertFalse(any("SurfaceFlinger 抓取失败" in error for error in errors))


def build_runtime_entities() -> tuple[TaskDefinition, TaskRun, ExecutionInstance, ArtifactScope]:
    task = TaskDefinition(
        task_id="task-1",
        task_name="Artifact Capture Task",
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
    instance.add_issue(
        IssueRecord(
            issue_id="issue-1",
            instance_id=instance.instance_id,
            task_run_id=run.run_id,
            device_id=instance.device_id,
            issue_type=IssueType.CRASH,
            issue_title="Crash detected",
            severity=SeverityLevel.CRITICAL,
            summary="Process crashed",
            process_name="com.example.app",
            pid=2456,
        )
    )
    return (
        task,
        run,
        instance,
        ArtifactScope(
            task_id=task.task_id,
            run_id=run.run_id,
            execution_id=instance.instance_id,
            device_id=instance.device_id,
        ),
    )


if __name__ == "__main__":
    unittest.main()
