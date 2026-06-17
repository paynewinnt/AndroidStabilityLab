"""Perfetto trace capture adapter."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
from typing import Any, Callable, Optional, Sequence

from stability.infrastructure.command_runner import resolve_host_command, SubprocessCommandRunner
from stability.infrastructure.monitoring_base import MonitoringAdapter
from stability.infrastructure.monitoring_config import DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE
from stability.infrastructure.monitoring_models import (
    MonitoringSessionConfig,
    MonitoringSessionHandle,
    MonitoringSnapshot,
)
from stability.infrastructure.monitoring_solox_adapter import SoloXMonitoringAdapter
from stability.infrastructure.monitoring_utils import tail_text, utcnow

logger = logging.getLogger(__name__)


class PerfettoTraceCaptureAdapter(MonitoringAdapter):
    """Capture one Perfetto trace as a monitoring sidecar and expose its artifact path."""

    def __init__(
        self,
        process_factory: Callable[[Sequence[str], str], Any] | None = None,
        command_runner: Callable[[Sequence[str]], tuple[int, str, str]] | None = None,
    ) -> None:
        self._process_factory = process_factory or self._default_process_factory
        self._command_runner = command_runner or self._default_command_runner

    def start_session(
        self,
        device_id: str,
        config: Optional[MonitoringSessionConfig] = None,
        session_name: Optional[str] = None,
    ) -> MonitoringSessionHandle:
        session_config = config or MonitoringSessionConfig()
        resolved_session_name = session_name or f"perfetto_{device_id}_{utcnow().strftime('%Y%m%d_%H%M%S')}"
        runtime_monitoring_dir = Path(
            str(session_config.extra.get("runtime_monitoring_dir", "runtime/monitoring")).strip() or "runtime/monitoring"
        )
        runtime_monitoring_dir.mkdir(parents=True, exist_ok=True)
        local_trace_path = runtime_monitoring_dir / f"{resolved_session_name}.perfetto-trace"
        remote_template = str(
            session_config.extra.get("perfetto_remote_path_template", DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE)
            or DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE
        )
        remote_trace_path = remote_template.format(session_name=resolved_session_name, device_id=device_id)
        config_text = self._resolve_config_text(
            device_id=device_id,
            session_name=resolved_session_name,
            config=session_config,
        )
        output_mode = str(session_config.extra.get("perfetto_output_mode", "file") or "file").strip().lower()
        output_target = "-" if output_mode == "stdout" else remote_trace_path
        process = self._process_factory(
            [
                "adb",
                "-s",
                device_id,
                "shell",
                "perfetto",
                "--txt",
                "-c",
                "-",
                "-o",
                output_target,
            ],
            config_text,
        )
        return MonitoringSessionHandle(
            device_id=device_id,
            session_name=resolved_session_name,
            config=session_config,
            collector=None,
            state={
                "remote_trace_path": remote_trace_path,
                "local_trace_path": str(local_trace_path),
                "config_text": config_text,
                "output_mode": output_mode,
                "process": process,
                "finalized": False,
                "finalized_metadata": {},
            },
            backend_name="perfetto",
        )

    def collect_snapshot(self, handle: MonitoringSessionHandle) -> MonitoringSnapshot:
        metadata = self._finalize_trace(handle)
        system_summary = {
            "perfetto_trace_size_bytes": metadata.get("trace_size_bytes"),
            "perfetto_duration_ms": metadata.get("duration_ms"),
        }
        system_summary = {key: value for key, value in system_summary.items() if value is not None}
        artifact_payloads = []
        local_trace_path = str(metadata.get("local_trace_path", "") or "")
        if local_trace_path:
            artifact_payloads.append(
                {
                    "artifact_type": "perfetto_trace",
                    "file_path": local_trace_path,
                    "capture_reason": "perfetto trace sidecar",
                    "capture_message": metadata.get("trace_status", ""),
                    "metadata": {
                        "backend": "perfetto",
                        "remote_trace_path": metadata.get("remote_trace_path"),
                        "trace_size_bytes": metadata.get("trace_size_bytes"),
                    },
                }
            )
        return MonitoringSnapshot(
            timestamp=utcnow(),
            system=system_summary or None,
            apps=[],
            metadata={
                "backend": "perfetto",
                "trace_artifact_path": local_trace_path,
                "normalized_stats": {
                    "trace_status": metadata.get("trace_status"),
                    "trace_size_bytes": metadata.get("trace_size_bytes"),
                    "duration_ms": metadata.get("duration_ms"),
                },
                "best_effort_degraded": metadata.get("trace_status") != "captured",
                "perfetto": metadata,
                "artifacts": artifact_payloads,
            },
        )

    def persist_snapshot(self, handle: MonitoringSessionHandle, snapshot: MonitoringSnapshot) -> bool:
        return False

    def stop_session(self, handle: MonitoringSessionHandle, status: str = "completed") -> None:
        if not bool(handle.state.get("finalized", False)):
            self._finalize_trace(handle)

    def _finalize_trace(self, handle: MonitoringSessionHandle) -> dict[str, Any]:
        if bool(handle.state.get("finalized", False)):
            return dict(handle.state.get("finalized_metadata", {}) or {})

        current_time = utcnow()
        process = handle.state.get("process")
        stdout_text: str | bytes = ""
        stderr_text: str | bytes = ""
        wait_timeout = float(handle.config.extra.get("perfetto_wait_timeout_seconds", 1.0) or 1.0)
        try:
            if process is not None:
                try:
                    process.wait(timeout=wait_timeout)
                except Exception:
                    self._signal_stop(handle.device_id)
                    try:
                        process.wait(timeout=5)
                    except Exception:
                        pass
                try:
                    stdout_text, stderr_text = process.communicate(timeout=1)
                except TypeError:
                    stdout_text, stderr_text = process.communicate()
                except Exception:
                    stdout_text = ""
                    stderr_text = ""
        except Exception as exc:  # pragma: no cover - defensive guard around external processes
            logger.warning("Perfetto finalize wait failed for %s: %s", handle.device_id, exc)

        local_trace_path = Path(str(handle.state.get("local_trace_path", "") or ""))
        remote_trace_path = str(handle.state.get("remote_trace_path", "") or "")
        stdout_for_trace = self._bytes_from_process_output(stdout_text)
        stdout_display = self._text_from_process_output(stdout_text)
        stderr_display = self._text_from_process_output(stderr_text)
        output_mode = str(handle.state.get("output_mode", "file") or "file")
        pull_status = 1
        pull_stdout = ""
        pull_stderr = ""
        trace_source = "remote_file"
        if output_mode == "stdout":
            trace_source = "stdout"
            pull_status, pull_stdout, pull_stderr = self._persist_stdout_trace(local_trace_path, stdout_for_trace)
        else:
            pull_status, pull_stdout, pull_stderr = self._command_runner(
                [
                    "adb",
                    "-s",
                    handle.device_id,
                    "pull",
                    remote_trace_path,
                    str(local_trace_path),
                ]
            )
            if pull_status == 0:
                self._command_runner(
                    [
                        "adb",
                        "-s",
                        handle.device_id,
                        "shell",
                        "rm",
                        "-f",
                        remote_trace_path,
                    ]
                )
            elif self._stdout_looks_like_trace(stdout_for_trace):
                trace_source = "stdout_fallback"
                pull_status, pull_stdout, pull_stderr = self._persist_stdout_trace(local_trace_path, stdout_for_trace)
            else:
                fallback_status, fallback_stdout, fallback_stderr = self._capture_stdout_fallback(handle, local_trace_path)
                if fallback_status == 0:
                    trace_source = "stdout_fallback"
                    pull_status, pull_stdout, pull_stderr = fallback_status, fallback_stdout, fallback_stderr
                else:
                    pull_stdout = "\n".join(part for part in (pull_stdout, fallback_stdout) if part)
                    pull_stderr = "\n".join(part for part in (pull_stderr, fallback_stderr) if part)
        combined_output = "\n".join(
            item.strip()
            for item in (
                stdout_display,
                stderr_display,
                pull_stdout,
                pull_stderr,
            )
            if str(item or "").strip()
        )
        trace_status = "captured" if pull_status == 0 and local_trace_path.exists() else "pull_failed"
        degraded_reason = ""
        normalized_output = combined_output.lower()
        if trace_status != "captured" and "perfetto" in normalized_output and (
            "not found" in normalized_output
            or "inaccessible" in normalized_output
            or "unknown command" in normalized_output
        ):
            trace_status = "binary_missing"
            degraded_reason = "perfetto binary is unavailable on the device"
        elif trace_status != "captured":
            degraded_reason = "trace pull failed after best-effort capture"
        elif trace_source == "stdout_fallback":
            degraded_reason = "remote trace pull failed; captured trace from stdout fallback"
        metadata = {
            "trace_status": trace_status,
            "captured_at": current_time.isoformat(),
            "local_trace_path": str(local_trace_path) if local_trace_path.exists() else "",
            "remote_trace_path": remote_trace_path,
            "capture_mode": trace_source,
            "trace_size_bytes": local_trace_path.stat().st_size if local_trace_path.exists() else None,
            "duration_ms": int(handle.config.extra.get("perfetto_duration_ms", 0) or 0),
            "config_path": str(handle.config.extra.get("perfetto_config_path", "") or ""),
            "stdout_tail": tail_text(stdout_display or pull_stdout),
            "stderr_tail": tail_text(stderr_display or pull_stderr),
            "best_effort_degraded": trace_status != "captured",
            "degraded_reason": degraded_reason,
        }
        handle.state["finalized"] = True
        handle.state["finalized_metadata"] = dict(metadata)
        return metadata

    @staticmethod
    def _stdout_looks_like_trace(stdout_bytes: bytes) -> bool:
        if not stdout_bytes:
            return False
        return len(stdout_bytes) > 16 and not stdout_bytes.lstrip().startswith(b"[")

    @classmethod
    def _persist_stdout_trace(cls, local_trace_path: Path, stdout_bytes: bytes) -> tuple[int, str, str]:
        if not cls._stdout_looks_like_trace(stdout_bytes):
            return 1, "", "perfetto stdout did not contain trace bytes"
        local_trace_path.parent.mkdir(parents=True, exist_ok=True)
        local_trace_path.write_bytes(stdout_bytes)
        return 0, "captured perfetto stdout", ""

    @staticmethod
    def _bytes_from_process_output(value: str | bytes) -> bytes:
        if isinstance(value, bytes):
            return value
        return str(value or "").encode("latin-1", errors="ignore")

    @staticmethod
    def _text_from_process_output(value: str | bytes) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value or "")

    def _signal_stop(self, device_id: str) -> None:
        rc, _, _ = self._command_runner(["adb", "-s", device_id, "shell", "pkill", "-INT", "perfetto"])
        if rc == 0:
            return
        self._command_runner(["adb", "-s", device_id, "shell", "killall", "perfetto"])

    def _capture_stdout_fallback(
        self,
        handle: MonitoringSessionHandle,
        local_trace_path: Path,
    ) -> tuple[int, str, str]:
        process = None
        stdout_text: str | bytes = ""
        stderr_text: str | bytes = ""
        try:
            process = self._process_factory(
                [
                    "adb",
                    "-s",
                    handle.device_id,
                    "shell",
                    "perfetto",
                    "--txt",
                    "-c",
                    "-",
                    "-o",
                    "-",
                ],
                str(handle.state.get("config_text", "") or ""),
            )
            wait_timeout = float(
                handle.config.extra.get("perfetto_stdout_fallback_wait_timeout_seconds")
                or handle.config.extra.get("perfetto_wait_timeout_seconds", 1.0)
                or 1.0
            )
            try:
                process.wait(timeout=wait_timeout)
            except Exception:
                self._signal_stop(handle.device_id)
                try:
                    process.wait(timeout=5)
                except Exception:
                    pass
            try:
                stdout_text, stderr_text = process.communicate(timeout=1)
            except TypeError:
                stdout_text, stderr_text = process.communicate()
        except Exception as exc:  # pragma: no cover - defensive guard around external process fallback
            return 1, "", f"perfetto stdout fallback failed: {exc}"
        stdout_bytes = self._bytes_from_process_output(stdout_text)
        status, stdout, stderr = self._persist_stdout_trace(local_trace_path, stdout_bytes)
        stderr_display = self._text_from_process_output(stderr_text)
        if status != 0 and stderr_display:
            stderr = "\n".join(part for part in (stderr, stderr_display) if part)
        return status, stdout, stderr

    def _resolve_config_text(
        self,
        *,
        device_id: str,
        session_name: str,
        config: MonitoringSessionConfig,
    ) -> str:
        config_text = str(config.extra.get("perfetto_config_text", "") or "").strip()
        if config_text:
            return config_text
        config_path = str(config.extra.get("perfetto_config_path", "") or "").strip()
        if config_path:
            path = Path(config_path)
            if not path.exists():
                raise RuntimeError(f"Perfetto config file not found: {config_path}")
            return path.read_text(encoding="utf-8")
        return self._default_trace_config(device_id=device_id, session_name=session_name, config=config)

    @staticmethod
    def _default_trace_config(
        *,
        device_id: str,
        session_name: str,
        config: MonitoringSessionConfig,
    ) -> str:
        poll_ms = max(int(float(config.sample_interval or 1.0) * 1000), 250)
        duration_ms = int(
            config.extra.get("perfetto_duration_ms")
            or ((int(config.extra.get("task_timeout_seconds", 0) or 0) or int(config.extra.get("task_duration_seconds", 0) or 0) or 60) * 1000)
        )
        buffer_size_kb = int(config.extra.get("perfetto_buffer_size_kb", 32768) or 32768)
        atrace_categories = list(config.extra.get("perfetto_atrace_categories", ["gfx", "view", "wm", "am"]) or [])
        enable_network_packets = bool(config.extra.get("perfetto_enable_network_packets", False))
        selected_package = SoloXMonitoringAdapter._package_name(config)
        atrace_lines = "".join(f'      atrace_categories: "{item}"\n' for item in atrace_categories if str(item).strip())
        if selected_package:
            atrace_lines += f'      atrace_apps: "{selected_package}"\n'
        network_packet_block = ""
        if enable_network_packets:
            network_packet_block = (
                "data_sources {\n"
                "  config {\n"
                '    name: "android.network_packets"\n'
                "  }\n"
                "  network_packet_trace_config {\n"
                f"    poll_ms: {poll_ms}\n"
                "  }\n"
                "}\n"
            )
        return (
            f"# session={session_name} device={device_id}\n"
            f"buffers {{ size_kb: {buffer_size_kb} fill_policy: RING_BUFFER }}\n"
            f"duration_ms: {duration_ms}\n"
            "data_sources {\n"
            "  config {\n"
            '    name: "linux.process_stats"\n'
            "    process_stats_config {\n"
            "      scan_all_processes_on_start: true\n"
            f"      proc_stats_poll_ms: {poll_ms}\n"
            "    }\n"
            "  }\n"
            "}\n"
            "data_sources {\n"
            "  config {\n"
            '    name: "linux.sys_stats"\n'
            "    sys_stats_config {\n"
            f"      meminfo_period_ms: {poll_ms}\n"
            f"      stat_period_ms: {poll_ms}\n"
            "    }\n"
            "  }\n"
            "}\n"
            "data_sources {\n"
            "  config {\n"
            '    name: "android.power"\n'
            "    android_power_config {\n"
            f"      battery_poll_ms: {poll_ms}\n"
            "      collect_power_rails: false\n"
            "    }\n"
            "  }\n"
            "}\n"
            "data_sources {\n"
            "  config {\n"
            '    name: "linux.ftrace"\n'
            "    ftrace_config {\n"
            '      ftrace_events: "sched/sched_switch"\n'
            '      ftrace_events: "sched/sched_wakeup"\n'
            f"{atrace_lines}"
            "    }\n"
            "  }\n"
            "}\n"
            f"{network_packet_block}"
        )

    @staticmethod
    def _default_process_factory(command: Sequence[str], config_text: str) -> Any:
        try:
            process = subprocess.Popen(
                resolve_host_command(command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:  # pragma: no cover - depends on local adb installation
            raise RuntimeError("adb is not available for Perfetto trace capture.") from exc
        if process.stdin is not None:
            process.stdin.write(config_text.encode("utf-8"))
            process.stdin.close()
            process.stdin = None
        return process

    @staticmethod
    def _default_command_runner(command: Sequence[str]) -> tuple[int, str, str]:
        result = SubprocessCommandRunner().run(command, timeout_seconds=20)
        if result.returncode == 127:  # pragma: no cover - depends on local adb installation
            raise RuntimeError("adb is not available for Perfetto trace capture.")
        return int(result.returncode if result.returncode is not None else -1), result.stdout, result.stderr
