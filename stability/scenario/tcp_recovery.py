from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, Sequence

from stability.infrastructure.adb import ADBCollector


class CommandResultLike(Protocol):
    """Minimal subprocess result shape needed for TCP reconnect decisions."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


class CommandRunnerLike(Protocol):
    """Execute one host-side command with timeout control."""

    def run(self, command: Sequence[str], *, timeout_seconds: int) -> CommandResultLike:
        """Execute one command and preserve stdout/stderr/timeout state."""
        ...


class TCPReconnectHelper:
    """Shared best-effort reconnect helper for TCP-connected adb devices."""

    DISCONNECT_MARKERS = (
        "device offline",
        "device not found",
        "no devices/emulators found",
        "closed",
    )

    def __init__(
        self,
        *,
        command_runner: CommandRunnerLike,
        availability_checker: Callable[[ADBCollector], bool],
        log_label: str,
    ) -> None:
        self._command_runner = command_runner
        self._availability_checker = availability_checker
        self._log_label = log_label

    def ensure_device_available(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        log_path: Path,
        loop_label: str,
        reason: str,
    ) -> bool:
        """Reconnect one dropped TCP device before the scenario command starts."""
        if self._availability_checker(collector):
            return True
        if not self.is_tcp_device(device_id):
            return False
        return self.attempt_reconnect(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label=loop_label,
            reason=reason,
        )

    def attempt_reconnect(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        log_path: Path,
        loop_label: str,
        reason: str,
    ) -> bool:
        """Run one `adb connect` and verify the target comes back online."""
        self.append_runtime_log(
            log_path,
            f"[{self._log_label}] {loop_label} {reason}, retrying adb connect for {device_id}",
        )
        reconnect_result = self._command_runner.run(
            ["adb", "connect", device_id],
            timeout_seconds=10,
        )
        self.append_runtime_log(
            log_path,
            (
                f"[{self._log_label}] {loop_label} reconnect return_code={reconnect_result.returncode} "
                f"stdout={self._tail_text(reconnect_result.stdout, limit=200)} "
                f"stderr={self._tail_text(reconnect_result.stderr, limit=200)}"
            ),
        )
        if not self._availability_checker(collector):
            return False

        self.append_runtime_log(
            log_path,
            f"[{self._log_label}] {loop_label} reconnect succeeded for {device_id}",
        )
        return True

    def should_retry_after_disconnect(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        command_result: CommandResultLike,
        had_command_error: bool = False,
        extra_output: Sequence[str] = (),
    ) -> bool:
        """Retry once only when the scenario command failed because TCP transport dropped."""
        if not self.is_tcp_device(device_id):
            return False
        if not (command_result.timed_out or command_result.returncode not in {0, None} or had_command_error):
            return False
        if self.looks_like_disconnect(command_result=command_result, extra_output=extra_output):
            return True
        return not self._availability_checker(collector)

    @classmethod
    def looks_like_disconnect(
        cls,
        *,
        command_result: CommandResultLike,
        extra_output: Sequence[str] = (),
    ) -> bool:
        """Detect common adb transport failure strings directly from command output."""
        combined_output = "\n".join(
            part.strip()
            for part in (command_result.stdout, command_result.stderr, *extra_output)
            if part and part.strip()
        ).lower()
        if not combined_output:
            return False
        return any(marker in combined_output for marker in cls.DISCONNECT_MARKERS)

    @staticmethod
    def append_runtime_log(path: Path, line: str) -> None:
        """Append one plain-text diagnostic line to the execution log."""
        if not line:
            return
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line.strip())
            handle.write("\n")

    @staticmethod
    def is_tcp_device(device_id: str) -> bool:
        """Treat host:port targets as reconnectable TCP devices."""
        return ":" in (device_id or "")

    @staticmethod
    def _tail_text(value: str, limit: int = 2000) -> str:
        text = value.strip()
        if len(text) <= limit:
            return text
        return text[-limit:]
