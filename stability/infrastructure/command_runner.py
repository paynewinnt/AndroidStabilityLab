from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
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
        resolved_command = resolve_host_command(command)
        try:
            completed = subprocess.run(
                resolved_command,
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
        adb_path: str | None = None,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.device_id = device_id
        self.adb_path = adb_path or "adb"
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
        full_command = [self.adb_path]
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


def resolve_host_command(command: Sequence[str]) -> list[str]:
    """Resolve host tool shims before subprocess execution."""
    resolved = [str(part) for part in command]
    if resolved and resolved[0].lower() in {"adb", "adb.exe"}:
        resolved[0] = resolve_adb_executable()
    return resolved


def resolve_adb_executable() -> str:
    """Return the preferred adb executable for source and PyInstaller runs.

    Resolution order:
    1. `ASL_ADB_PATH` / `ADB_PATH` explicit executable override.
    2. `ASL_PLATFORM_TOOLS_DIR` and bundled PyInstaller/source platform-tools.
    3. Android SDK `platform-tools` from `ANDROID_HOME` / `ANDROID_SDK_ROOT`.
    4. `adb` from PATH, then the bare command name as a final fallback.
    """
    explicit_path = _first_configured_path("ASL_ADB_PATH", "ADB_PATH")
    if explicit_path:
        return explicit_path

    for directory in _platform_tools_candidate_dirs():
        adb_path = directory / _adb_executable_name()
        if adb_path.exists():
            return str(adb_path)

    found = shutil.which(_adb_executable_name()) or shutil.which("adb")
    return found or _adb_executable_name()


def _first_configured_path(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return str(Path(value).expanduser())
    return ""


def _platform_tools_candidate_dirs() -> list[Path]:
    candidates: list[Path] = []
    configured_dir = _first_configured_path("ASL_PLATFORM_TOOLS_DIR")
    if configured_dir:
        candidates.append(Path(configured_dir))

    candidates.extend(_bundled_platform_tools_dirs())

    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.environ.get(name, "").strip()
        if sdk_root:
            candidates.append(Path(sdk_root).expanduser() / "platform-tools")

    return [candidate for candidate in candidates if str(candidate)]


def _bundled_platform_tools_dirs() -> list[Path]:
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        roots.append(Path(str(meipass)))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parents[2])

    platform_name = _platform_tools_platform_name()
    candidates: list[Path] = []
    for root in roots:
        candidates.append(root / "platform-tools")
        candidates.append(root / "packaging" / "vendor" / "platform-tools" / platform_name)
    return candidates


def _platform_tools_platform_name() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def _adb_executable_name() -> str:
    return "adb.exe" if sys.platform.startswith("win") else "adb"
