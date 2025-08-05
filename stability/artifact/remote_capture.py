from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, Iterable, Sequence

from stability.domain import ArtifactCaptureStatus, ArtifactRecord, ArtifactType


class RemoteArtifactCaptureMixin:
    """ADB-backed issue evidence capture helpers."""

    def _capture_bugreport(
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
        """Best-effort capture one text bugreport snapshot without blocking the main flow."""
        if not device_id:
            return None, "bugreport 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"bugreport 抓取跳过：设备 {device_id} 当前不可用。"

        completed = self._command_runner.run(
            ["adb", "-s", device_id, "shell", "bugreport"],
            timeout=60,
        )
        if completed.returncode != 0:
            stderr_tail = (completed.stderr or "").strip()[-200:]
            return None, f"bugreport 抓取失败：{stderr_tail or completed.returncode}"

        content_parts = []
        if (completed.stdout or "").strip():
            content_parts.append(completed.stdout.rstrip())
        if (completed.stderr or "").strip():
            content_parts.append(f"===== stderr =====\n{completed.stderr.rstrip()}")
        if not content_parts:
            return None, "bugreport 抓取失败：命令成功但没有返回任何内容。"

        target_path.write_text("\n\n".join(content_parts) + "\n", encoding="utf-8")
        artifact = ArtifactRecord(
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.BUGREPORT,
            file_path=str(target_path),
            capture_reason="issue_context",
            capture_status=ArtifactCaptureStatus.SUCCESS,
            metadata={
                "command": "adb shell bugreport",
                "format": "text",
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
        )
        artifact.mark_captured(size_bytes=target_path.stat().st_size)
        return artifact, ""

    def _capture_shell_command_artifact(
        self,
        *,
        command: Sequence[str],
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        artifact_type: ArtifactType,
        failure_prefix: str,
        metadata: dict[str, Any] | None = None,
        timeout: int,
    ) -> tuple[ArtifactRecord | None, str]:
        completed = self._command_runner.run(command, timeout=timeout)
        if completed.returncode != 0:
            stderr_tail = (completed.stderr or "").strip()[-200:]
            return None, f"{failure_prefix}：{stderr_tail or completed.returncode}"

        content_parts = []
        if (completed.stdout or "").strip():
            content_parts.append(completed.stdout.rstrip())
        if (completed.stderr or "").strip():
            content_parts.append(f"===== stderr =====\n{completed.stderr.rstrip()}")
        if not content_parts:
            return None, f"{failure_prefix}：命令成功但没有返回任何内容。"

        target_path.write_text("\n\n".join(content_parts) + "\n", encoding="utf-8")
        artifact = ArtifactRecord(
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=artifact_type,
            file_path=str(target_path),
            capture_reason="issue_context",
            capture_status=ArtifactCaptureStatus.SUCCESS,
            metadata=dict(metadata or {}),
        )
        artifact.mark_captured(size_bytes=target_path.stat().st_size)
        return artifact, ""

    def _resolve_meminfo_pid(self, device_id: str, target_name: str, issue: Any) -> int | None:
        issue_pid = getattr(issue, "pid", None)
        if isinstance(issue_pid, int) and issue_pid > 0:
            return issue_pid
        completed = self._command_runner.run(
            ["adb", "-s", device_id, "shell", "pidof", target_name],
            timeout=10,
        )
        if completed.returncode != 0:
            return None
        first_pid = (completed.stdout or "").strip().split()
        if not first_pid:
            return None
        try:
            return int(first_pid[0])
        except ValueError:
            return None

    @staticmethod
    def _looks_like_missing_meminfo_target(output: str) -> bool:
        normalized = (output or "").strip().lower()
        if not normalized:
            return False
        return "no process found" in normalized or "could not find process" in normalized

    @staticmethod
    def _copy_existing_file(
        *,
        source_path: Path,
        target_path: Path,
        artifact_type: ArtifactType,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        capture_reason: str,
    ) -> ArtifactRecord | None:
        """Copy an existing runtime file into the issue evidence directory."""
        if not source_path.exists() or not source_path.is_file():
            return None
        shutil.copy2(source_path, target_path)
        artifact = ArtifactRecord(
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=artifact_type,
            file_path=str(target_path),
            capture_reason=capture_reason,
            capture_status=ArtifactCaptureStatus.SUCCESS,
            metadata={"source_path": str(source_path)},
        )
        artifact.mark_captured(size_bytes=target_path.stat().st_size)
        return artifact

    def _capture_logcat(
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
        """Best-effort capture a small logcat snapshot for the current device."""
        if not device_id:
            return None, "logcat 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"logcat 抓取跳过：设备 {device_id} 当前不可用。"

        pid = getattr(issue, "pid", None)
        process_name = getattr(issue, "process_name", "") or ""
        plans: list[tuple[str, list[str]]] = []
        if isinstance(pid, int) and pid > 0:
            plans.append(
                (
                    "pid_tail",
                    [
                        "adb",
                        "-s",
                        device_id,
                        "logcat",
                        "--pid",
                        str(pid),
                        "-d",
                        "-v",
                        "threadtime",
                        "-t",
                        "250",
                    ],
                )
            )
        plans.extend(
            [
                (
                    "crash_buffer",
                    [
                        "adb",
                        "-s",
                        device_id,
                        "logcat",
                        "-b",
                        "crash",
                        "-d",
                        "-v",
                        "threadtime",
                        "-t",
                        "200",
                    ],
                ),
                (
                    "all_buffers",
                    [
                        "adb",
                        "-s",
                        device_id,
                        "logcat",
                        "-b",
                        "all",
                        "-d",
                        "-v",
                        "threadtime",
                        "-t",
                        "400",
                    ],
                ),
            ]
        )
        sections: list[str] = []
        captures: list[dict[str, Any]] = []
        failures: list[str] = []
        for label, command in plans:
            completed = self._command_runner.run(command, timeout=15)
            if completed.returncode != 0:
                stderr_tail = (completed.stderr or "").strip()[-200:]
                failures.append(f"{label}:{stderr_tail or completed.returncode}")
                continue
            output = completed.stdout or ""
            if not output.strip():
                failures.append(f"{label}:empty")
                continue
            sections.append(f"===== {label} =====\n{output.rstrip()}\n")
            capture_metadata: dict[str, Any] = {"mode": label}
            if label == "pid_tail":
                capture_metadata["pid"] = pid
            captures.append(capture_metadata)

        if not sections:
            failure_detail = " | ".join(failures[-3:]) if failures else "无可用输出"
            return None, f"logcat 抓取失败：{failure_detail}"

        target_path.write_text("\n".join(sections), encoding="utf-8")
        artifact = ArtifactRecord(
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.LOGCAT,
            file_path=str(target_path),
            capture_reason="issue_context",
            capture_status=ArtifactCaptureStatus.SUCCESS,
            metadata={
                "captures": captures,
                "format": "threadtime",
                "issue_process_name": process_name,
                "issue_pid": pid,
            },
        )
        artifact.mark_captured(size_bytes=target_path.stat().st_size)
        return artifact, ""

    def _capture_traces(
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
        """Best-effort capture traces.txt or the latest ANR trace file."""
        if not device_id:
            return None, "traces 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"traces 抓取跳过：设备 {device_id} 当前不可用。"

        candidates = ["/data/anr/traces.txt"]
        candidates.extend(
            self._resolve_remote_candidates(
                device_id,
                "/data/anr",
                limit=3,
                prefix="anr_",
            )
        )

        return self._capture_first_available_remote_file(
            device_id=device_id,
            remote_paths=candidates,
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.TRACES,
            failure_prefix="traces 抓取失败",
            metadata={
                "candidate_count": len(candidates),
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
        )

    def _capture_tombstone(
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
        """Best-effort capture the latest tombstone text file."""
        if not device_id:
            return None, "tombstone 抓取失败：缺少设备标识。"
        if not device_available:
            return None, f"tombstone 抓取跳过：设备 {device_id} 当前不可用。"

        candidates = self._resolve_remote_candidates(
            device_id,
            "/data/tombstones",
            limit=3,
            prefix="tombstone_",
            exclude_suffixes=(".pb",),
        )
        if not candidates:
            return None, "tombstone 抓取跳过：未发现可读取的 tombstone 文件。"

        return self._capture_first_available_remote_file(
            device_id=device_id,
            remote_paths=candidates,
            target_path=target_path,
            task_run_id=task_run_id,
            instance_id=instance_id,
            issue_id=issue_id,
            artifact_type=ArtifactType.TOMBSTONE,
            failure_prefix="tombstone 抓取失败",
            metadata={
                "candidate_count": len(candidates),
                "issue_process_name": getattr(issue, "process_name", "") or "",
                "issue_pid": getattr(issue, "pid", None),
            },
        )

    def _capture_first_available_remote_file(
        self,
        *,
        device_id: str,
        remote_paths: Iterable[str],
        target_path: Path,
        task_run_id: str,
        instance_id: str,
        issue_id: str,
        artifact_type: ArtifactType,
        failure_prefix: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[ArtifactRecord | None, str]:
        """Try remote files in order and persist the first readable one as an artifact."""
        attempted: list[str] = []
        for remote_path in remote_paths:
            normalized = str(remote_path).strip()
            if not normalized:
                continue
            attempted.append(normalized)
            completed = self._command_runner.run(
                ["adb", "-s", device_id, "shell", "cat", normalized],
                timeout=15,
            )
            if completed.returncode != 0 or not (completed.stdout or "").strip():
                continue
            target_path.write_text(completed.stdout, encoding="utf-8")
            artifact = ArtifactRecord(
                task_run_id=task_run_id,
                instance_id=instance_id,
                issue_id=issue_id,
                artifact_type=artifact_type,
                file_path=str(target_path),
                capture_reason="issue_context",
                capture_status=ArtifactCaptureStatus.SUCCESS,
                metadata={
                    **dict(metadata or {}),
                    "remote_path": normalized,
                },
            )
            artifact.mark_captured(size_bytes=target_path.stat().st_size)
            return artifact, ""

        attempted_text = ", ".join(attempted) if attempted else "无候选文件"
        return None, f"{failure_prefix}：未能读取候选文件 {attempted_text}。"

    def _resolve_remote_candidates(
        self,
        device_id: str,
        directory_path: str,
        *,
        limit: int,
        prefix: str = "",
        exclude_suffixes: tuple[str, ...] = (),
    ) -> list[str]:
        """Return newest candidate file paths from a remote directory when available."""
        completed = self._command_runner.run(
            ["adb", "-s", device_id, "shell", "ls", "-t", directory_path],
            timeout=10,
        )
        if completed.returncode != 0:
            return []
        candidates: list[str] = []
        for line in completed.stdout.splitlines():
            candidate = line.strip()
            if (
                not candidate
                or candidate.startswith("ls:")
                or candidate in {".", ".."}
                or candidate.endswith(":")
            ):
                continue
            name = candidate.split("/")[-1]
            if prefix and not name.startswith(prefix):
                continue
            if exclude_suffixes and any(name.endswith(suffix) for suffix in exclude_suffixes):
                continue
            resolved = candidate if candidate.startswith(directory_path) else f"{directory_path.rstrip('/')}/{name}"
            if resolved in candidates:
                continue
            candidates.append(resolved)
            if len(candidates) >= limit:
                break
        return candidates

    def _is_device_available(self, device_id: str) -> bool:
        """Check whether adb can talk to the target device before collecting remote evidence."""
        if not device_id:
            return False
        get_state = self._command_runner.run(
            ["adb", "-s", device_id, "get-state"],
            timeout=5,
        )
        return get_state.returncode == 0 and get_state.stdout.strip() == "device"

    @staticmethod
    def _task_package_name(task: Any) -> str:
        if task is None:
            return ""
        target_app = getattr(task, "target_app", None)
        return str(getattr(target_app, "package_name", "") or "")
