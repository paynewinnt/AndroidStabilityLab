from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from stability.domain import ArtifactCaptureStatus, ArtifactRecord, ArtifactType, IssueType
from .command_runner import CommandResult, CommandRunner, SubprocessCommandRunner
from .evidence_parsers import parse_artifact_evidence
from .remote_capture import RemoteArtifactCaptureMixin


class IssueArtifactCollector(RemoteArtifactCaptureMixin):
    """Capture a minimal set of evidence artifacts when an issue is detected."""

    _DROPBOX_ISSUE_TYPES = {
        IssueType.CRASH,
        IssueType.ANR,
        IssueType.JAVA_EXCEPTION,
        IssueType.JAVA_CRASH,
        IssueType.NATIVE_CRASH,
        IssueType.SYSTEM_SERVER_CRASH,
        IssueType.WATCHDOG,
        IssueType.REBOOT,
        IssueType.PROCESS_EXIT,
        IssueType.STARTUP_TIMEOUT,
    }
    _MEMINFO_ISSUE_TYPES = {
        IssueType.CRASH,
        IssueType.ANR,
        IssueType.STARTUP_TIMEOUT,
        IssueType.EXECUTION_TIMEOUT,
        IssueType.PROCESS_EXIT,
    }
    _SURFACEFLINGER_ISSUE_TYPES = {
        IssueType.ANR,
        IssueType.NATIVE_CRASH,
        IssueType.EXECUTION_TIMEOUT,
        IssueType.FREEZE,
        IssueType.BLACK_SCREEN,
    }
    _SCREENSHOT_ISSUE_TYPES = {
        IssueType.FREEZE,
        IssueType.BLACK_SCREEN,
    }
    _INPUT_EVENTS_ISSUE_TYPES = {
        IssueType.FREEZE,
        IssueType.BLACK_SCREEN,
    }
    _PERFETTO_TRACE_ISSUE_TYPES = {
        IssueType.FREEZE,
        IssueType.BLACK_SCREEN,
        IssueType.WATCHDOG,
        IssueType.SYSTEM_SERVER_CRASH,
    }

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or SubprocessCommandRunner()

    def capture(
        self,
        *,
        task,
        run,
        instance,
        scope,
        artifact_path_planner,
        log_path: Path,
        monitoring_snapshot_path: str | None = None,
    ) -> tuple[list[ArtifactRecord], list[str]]:
        """Capture issue-scoped artifacts and return both records and capture errors."""
        if not getattr(instance, "issues", None):
            return [], []

        artifacts: list[ArtifactRecord] = []
        errors: list[str] = []
        device_id = getattr(instance, "device_id", "") or ""
        device_available = self._is_device_available(device_id)
        bugreport_captured = False
        for issue in instance.issues:
            execution_log_artifact = self._copy_existing_file(
                source_path=log_path,
                target_path=artifact_path_planner.plan_issue_artifact_path(
                    scope,
                    issue.issue_id,
                    "execution.log",
                    ensure_parent=True,
                ),
                artifact_type=ArtifactType.EXECUTION_LOG,
                task_run_id=getattr(run, "run_id", "") or "",
                instance_id=getattr(instance, "instance_id", "") or "",
                issue_id=issue.issue_id,
                capture_reason="issue_context",
            )
            if execution_log_artifact is not None:
                artifacts.append(execution_log_artifact)

            if monitoring_snapshot_path:
                monitoring_artifact = self._copy_existing_file(
                    source_path=Path(monitoring_snapshot_path),
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "monitoring_snapshot.json",
                        ensure_parent=True,
                    ),
                    artifact_type=ArtifactType.PERFORMANCE_SNAPSHOT,
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    capture_reason="issue_context",
                )
                if monitoring_artifact is not None:
                    artifacts.append(monitoring_artifact)

            issue_artifacts: list[ArtifactRecord] = []
            if not bugreport_captured:
                bugreport_artifact, bugreport_error = self._capture_bugreport(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "bugreport.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                )
                if bugreport_artifact is not None:
                    bugreport_captured = True
                    artifacts.append(bugreport_artifact)
                    issue_artifacts.append(bugreport_artifact)
                if bugreport_error:
                    errors.append(bugreport_error)

            artifact_results = [
                self._capture_dropbox(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "dropbox.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._capture_meminfo(
                    issue=issue,
                    task=task,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "meminfo.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._capture_surfaceflinger(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "surfaceflinger.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._capture_screenshot(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "screenshot.png",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._capture_input_events(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "input_events.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._copy_perfetto_trace(
                    issue=issue,
                    monitoring_snapshot_path=monitoring_snapshot_path,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "trace.perfetto-trace",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                ),
                self._capture_logcat(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "logcat.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._capture_traces(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "traces.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
                self._capture_tombstone(
                    issue=issue,
                    device_id=device_id,
                    target_path=artifact_path_planner.plan_issue_artifact_path(
                        scope,
                        issue.issue_id,
                        "tombstone.txt",
                        ensure_parent=True,
                    ),
                    task_run_id=getattr(run, "run_id", "") or "",
                    instance_id=getattr(instance, "instance_id", "") or "",
                    issue_id=issue.issue_id,
                    device_available=device_available,
                ),
            ]
            for captured_artifact, capture_error in artifact_results:
                if captured_artifact is not None:
                    self._enrich_artifact_with_structured_evidence(captured_artifact)
                    artifacts.append(captured_artifact)
                    issue_artifacts.append(captured_artifact)
                if capture_error:
                    errors.append(capture_error)
            self._enrich_issue_metadata_with_artifacts(issue, issue_artifacts)

        return artifacts, errors

    def _capture_dropbox(
        self,
        *,
        issue,
        device_id: str,
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        device_available: bool,
    ) -> tuple[ArtifactRecord | None, str]:
        """Best-effort capture one dropbox snapshot for crash-like issues."""
        if getattr(issue, "issue_type", None) not in self._DROPBOX_ISSUE_TYPES:
            return None, ""
        if not device_id:
            return None, "dropbox 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"dropbox 抓取跳过：设备 {device_id} 当前不可用。"
        return self._capture_shell_command_artifact(
            command=["adb", "-s", device_id, "shell", "dumpsys", "dropbox", "--print"],
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.DROPBOX,
            failure_prefix="dropbox 抓取失败",
            metadata={
                "command": "adb shell dumpsys dropbox --print",
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
            timeout=20,
        )

    def _capture_meminfo(
        self,
        *,
        issue,
        task,
        device_id: str,
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        device_available: bool,
    ) -> tuple[ArtifactRecord | None, str]:
        """Best-effort capture dumpsys meminfo for resource-related issues."""
        if getattr(issue, "issue_type", None) not in self._MEMINFO_ISSUE_TYPES:
            return None, ""
        if not device_id:
            return None, "meminfo 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"meminfo 抓取跳过：设备 {device_id} 当前不可用。"
        target_name = (
            getattr(issue, "package_name", "") or getattr(issue, "process_name", "") or self._task_package_name(task)
        )
        if not target_name:
            return None, "meminfo 抓取跳过：缺少包名或进程名。"
        artifact, error = self._capture_shell_command_artifact(
            command=["adb", "-s", device_id, "shell", "dumpsys", "meminfo", target_name],
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.DUMPSYS_MEMINFO,
            failure_prefix="meminfo 抓取失败",
            metadata={
                "command": f"adb shell dumpsys meminfo {target_name}",
                "target_name": target_name,
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
            timeout=20,
        )
        if artifact is not None:
            captured_text = ""
            try:
                captured_text = target_path.read_text(encoding="utf-8")
            except OSError:
                captured_text = ""
            if not self._looks_like_missing_meminfo_target(captured_text):
                return artifact, error
            try:
                target_path.unlink(missing_ok=True)
            except OSError:
                pass
            artifact = None
            error = f"meminfo 抓取失败：目标 {target_name} 当前没有存活进程。"

        resolved_pid = self._resolve_meminfo_pid(device_id, target_name, issue)
        if resolved_pid is None:
            return artifact, error
        return self._capture_shell_command_artifact(
            command=["adb", "-s", device_id, "shell", "dumpsys", "meminfo", str(resolved_pid)],
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.DUMPSYS_MEMINFO,
            failure_prefix="meminfo 抓取失败",
            metadata={
                "command": f"adb shell dumpsys meminfo {resolved_pid}",
                "target_name": target_name,
                "resolved_pid": resolved_pid,
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
            timeout=20,
        )

    def _capture_surfaceflinger(
        self,
        *,
        issue,
        device_id: str,
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        device_available: bool,
    ) -> tuple[ArtifactRecord | None, str]:
        """Best-effort capture dumpsys SurfaceFlinger for graphics-like issues."""
        if getattr(issue, "issue_type", None) not in self._SURFACEFLINGER_ISSUE_TYPES:
            return None, ""
        if not device_id:
            return None, "SurfaceFlinger 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"SurfaceFlinger 抓取跳过：设备 {device_id} 当前不可用。"
        return self._capture_shell_command_artifact(
            command=["adb", "-s", device_id, "shell", "dumpsys", "SurfaceFlinger"],
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.DUMPSYS_SURFACEFLINGER,
            failure_prefix="SurfaceFlinger 抓取失败",
            metadata={
                "command": "adb shell dumpsys SurfaceFlinger",
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
            timeout=20,
        )

    def _capture_screenshot(
        self,
        *,
        issue,
        device_id: str,
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        device_available: bool,
    ) -> tuple[ArtifactRecord | None, str]:
        """Best-effort capture one PNG screenshot for display-pipeline issues."""
        if getattr(issue, "issue_type", None) not in self._SCREENSHOT_ISSUE_TYPES:
            return None, ""
        if not device_id:
            return None, "screenshot 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"screenshot 抓取跳过：设备 {device_id} 当前不可用。"
        remote_path = f"/data/local/tmp/asl_issue_{issue_id}.png"
        capture = self._command_runner.run(
            ["adb", "-s", device_id, "shell", "screencap", "-p", remote_path],
            timeout=15,
        )
        if capture.returncode != 0:
            stderr_tail = (capture.stderr or "").strip()[-200:]
            return None, f"screenshot 抓取失败：{stderr_tail or capture.returncode}"
        pull = self._command_runner.run(
            ["adb", "-s", device_id, "pull", remote_path, str(target_path)],
            timeout=20,
        )
        self._command_runner.run(["adb", "-s", device_id, "shell", "rm", "-f", remote_path], timeout=10)
        if pull.returncode != 0:
            stderr_tail = (pull.stderr or "").strip()[-200:]
            return None, f"screenshot 拉取失败：{stderr_tail or pull.returncode}"
        if not target_path.exists():
            placeholder = "\n".join(
                [
                    "screenshot capture command succeeded, but the command runner did not materialize a local file.",
                    f"remote_path={remote_path}",
                ]
            )
            target_path.write_text(placeholder + "\n", encoding="utf-8")
        artifact = ArtifactRecord(
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.SCREENSHOT,
            file_path=str(target_path),
            capture_reason="issue_context",
            capture_status=ArtifactCaptureStatus.SUCCESS,
            metadata={
                "command": f"adb shell screencap -p {remote_path}; adb pull {remote_path}",
                "remote_path": remote_path,
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
        )
        artifact.mark_captured(size_bytes=target_path.stat().st_size)
        return artifact, ""

    def _capture_input_events(
        self,
        *,
        issue,
        device_id: str,
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        device_available: bool,
    ) -> tuple[ArtifactRecord | None, str]:
        """Best-effort capture a small input event tail for freeze/black-screen diagnosis."""
        if getattr(issue, "issue_type", None) not in self._INPUT_EVENTS_ISSUE_TYPES:
            return None, ""
        if not device_id:
            return None, "input events 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"input events 抓取跳过：设备 {device_id} 当前不可用。"
        return self._capture_shell_command_artifact(
            command=["adb", "-s", device_id, "shell", "getevent", "-lt", "-c", "80"],
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.INPUT_EVENTS,
            failure_prefix="input events 抓取失败",
            metadata={
                "command": "adb shell getevent -lt -c 80",
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
            timeout=10,
        )

    def _copy_perfetto_trace(
        self,
        *,
        issue,
        monitoring_snapshot_path: str | None,
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
    ) -> tuple[ArtifactRecord | None, str]:
        """Attach an existing Perfetto trace to high-value issue evidence when available."""
        if getattr(issue, "issue_type", None) not in self._PERFETTO_TRACE_ISSUE_TYPES:
            return None, ""
        trace_path = self._trace_path_from_monitoring_snapshot(monitoring_snapshot_path)
        if not trace_path:
            return None, ""
        artifact = self._copy_existing_file(
            source_path=Path(trace_path),
            target_path=target_path,
            artifact_type=ArtifactType.PERFETTO_TRACE,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            capture_reason="issue_context",
        )
        if artifact is None:
            return None, f"perfetto trace 附加跳过：未找到 trace 文件 {trace_path}。"
        artifact.metadata.update({"source_path": trace_path, "trace_backend": "perfetto"})
        return artifact, ""

    @staticmethod
    def _trace_path_from_monitoring_snapshot(monitoring_snapshot_path: str | None) -> str:
        if not monitoring_snapshot_path:
            return ""
        path = Path(monitoring_snapshot_path)
        if not path.exists():
            return ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        metadata = dict(payload.get("metadata", {}) or {})
        trace_path = str(metadata.get("trace_artifact_path") or metadata.get("monitoring_trace_path") or "")
        if trace_path:
            return trace_path
        perfetto = dict(metadata.get("perfetto", {}) or {})
        return str(perfetto.get("trace_artifact_path") or perfetto.get("trace_path") or "")

    @classmethod
    def _enrich_issue_metadata_with_artifacts(
        cls,
        issue,
        artifacts: Sequence[ArtifactRecord],
    ) -> None:
        """Fold captured artifact sources back into issue evidence metadata."""
        if not artifacts:
            return
        metadata = dict(getattr(issue, "metadata", {}) or {})
        existing_signals = list(metadata.get("evidence_signals", []) or [])
        matched_sources = list(metadata.get("matched_sources", []) or [])
        artifact_signals: list[dict[str, Any]] = []
        structured_signals: list[dict[str, Any]] = []
        structured_fragments: list[str] = list(metadata.get("matched_fragments", []) or [])
        structured_summaries: list[dict[str, Any]] = []
        for artifact in artifacts:
            source = cls._artifact_evidence_source(artifact.artifact_type)
            if not source:
                continue
            if source not in matched_sources:
                matched_sources.append(source)
            artifact_signals.append(
                {
                    "source": source,
                    "raw_source": "artifact",
                    "artifact_type": str(artifact.artifact_type.value),
                    "artifact_id": artifact.artifact_id,
                    "path": artifact.file_path,
                }
            )
            structured = dict((artifact.metadata or {}).get("structured_evidence", {}) or {})
            if structured:
                structured_summaries.append(
                    {
                        "artifact_type": str(artifact.artifact_type.value),
                        "artifact_id": artifact.artifact_id,
                        "path": artifact.file_path,
                        "parser": structured.get("parser", ""),
                        "summary": structured.get("summary", ""),
                        "issue_hints": list(structured.get("issue_hints", []) or []),
                        "confidence": structured.get("confidence", ""),
                        "metrics": dict(structured.get("metrics", {}) or {}),
                    }
                )
            for signal in structured.get("signals", []) or []:
                if not isinstance(signal, dict):
                    continue
                normalized_signal = {
                    "source": str(signal.get("source") or source),
                    "raw_source": str(signal.get("raw_source") or "artifact_parser"),
                    "artifact_type": str(artifact.artifact_type.value),
                    "artifact_id": artifact.artifact_id,
                    "path": artifact.file_path,
                    "pattern": str(signal.get("pattern") or ""),
                    "hint": str(signal.get("hint") or ""),
                    "fragment": str(signal.get("fragment") or ""),
                }
                structured_signals.append(normalized_signal)
                signal_source = normalized_signal["source"]
                if signal_source and signal_source not in matched_sources:
                    matched_sources.append(signal_source)
                fragment = normalized_signal["fragment"]
                if fragment and fragment not in structured_fragments:
                    structured_fragments.append(fragment)
        if not artifact_signals:
            return
        metadata["artifact_evidence_signals"] = artifact_signals
        if structured_summaries:
            metadata["structured_artifact_evidence"] = structured_summaries
        if structured_fragments:
            metadata["matched_fragments"] = structured_fragments[:20]
            metadata.setdefault("evidence", structured_fragments[0])
        metadata["evidence_signals"] = existing_signals + artifact_signals + structured_signals
        metadata["matched_sources"] = matched_sources
        metadata["evidence_level"] = cls._merged_confirmation_level(
            previous=str(metadata.get("evidence_level") or metadata.get("confirmation_level") or ""),
            matched_sources=matched_sources,
        )
        metadata["confirmation_level"] = metadata["evidence_level"]
        issue.metadata = metadata

    @staticmethod
    def _enrich_artifact_with_structured_evidence(artifact: ArtifactRecord) -> None:
        structured = parse_artifact_evidence(artifact.artifact_type, artifact.file_path)
        if not structured:
            return
        metadata = dict(artifact.metadata or {})
        metadata["structured_evidence"] = structured
        artifact.metadata = metadata

    @staticmethod
    def _artifact_evidence_source(artifact_type: ArtifactType) -> str:
        mapping = {
            ArtifactType.DROPBOX: "dropbox",
            ArtifactType.DUMPSYS_SURFACEFLINGER: "surfaceflinger",
            ArtifactType.SCREENSHOT: "screenshot",
            ArtifactType.INPUT_EVENTS: "input",
            ArtifactType.PERFETTO_TRACE: "perfetto",
            ArtifactType.LOGCAT: "logcat",
            ArtifactType.TRACES: "traces",
            ArtifactType.TOMBSTONE: "tombstone",
            ArtifactType.PERFORMANCE_SNAPSHOT: "performance_snapshot",
        }
        return mapping.get(artifact_type, "")

    @staticmethod
    def _merged_confirmation_level(*, previous: str, matched_sources: Sequence[str]) -> str:
        distinct_sources = {str(source) for source in matched_sources if source}
        if len(distinct_sources) >= 3:
            return "multi_evidence"
        if len(distinct_sources) >= 2:
            return "strong"
        if previous:
            return previous
        return "weak" if distinct_sources else "none"
