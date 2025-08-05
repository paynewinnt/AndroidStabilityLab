from __future__ import annotations

from dataclasses import dataclass
import logging
import shlex
import subprocess
from typing import Protocol, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandResult:
    """Normalized result for host-side commands, including adb."""

    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class CommandRunner(Protocol):
    """Shared command execution boundary for CLI/Web services and scenarios."""

    def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute one command and preserve stdout/stderr/timeout state."""
        ...


class SubprocessCommandRunner:
    """Default subprocess-backed command runner."""

    def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        resolved_timeout = self._resolve_timeout(timeout_seconds=timeout_seconds, timeout=timeout)
        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                timeout=resolved_timeout,
                check=False,
            )
            return CommandResult(
                returncode=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                returncode=None,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
                timed_out=True,
            )
        except FileNotFoundError as exc:
            return CommandResult(
                returncode=127,
                stdout="",
                stderr=str(exc),
                timed_out=False,
            )

    @staticmethod
    def _resolve_timeout(*, timeout_seconds: int | None, timeout: int | None) -> int:
        if timeout_seconds is not None:
            return int(timeout_seconds)
        if timeout is not None:
            return int(timeout)
        return 30


class ADBCommandRunner:
    """ADB-specific runner that applies one device id and normalizes adb output."""

    def __init__(
        self,
        *,
        device_id: str | None = None,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.device_id = device_id
        self._command_runner = command_runner or SubprocessCommandRunner()

    def run_adb(
        self,
        command: str | Sequence[str],
        *,
        timeout_seconds: int | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        return self._command_runner.run(
            self.build_adb_command(command),
            timeout_seconds=timeout_seconds,
            timeout=timeout,
        )

    def build_adb_command(self, command: str | Sequence[str]) -> list[str]:
        args = self._normalize_args(command)
        full_command = ["adb"]
        if self.device_id:
            full_command.extend(["-s", self.device_id])
        full_command.extend(args)
        return full_command

    @staticmethod
    def _normalize_args(command: str | Sequence[str]) -> list[str]:
        if isinstance(command, str):
            return shlex.split(command)
        return [str(part) for part in command]


def command_output_or_none(result: CommandResult) -> str | None:
    """Return stripped stdout only when the command succeeded."""

    if not result.ok:
        return None
    output = result.stdout.strip()
    return output or None

