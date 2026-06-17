from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from stability.infrastructure.command_runner import (
    ADBCommandRunner,
    CommandResult,
    resolve_adb_executable,
    resolve_host_command,
    SubprocessCommandRunner,
)


class CommandRunnerTest(unittest.TestCase):
    def test_subprocess_runner_returns_success_result(self) -> None:
        result = SubprocessCommandRunner().run(
            [sys.executable, "-c", "print('ok')"],
            timeout_seconds=5,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertFalse(result.timed_out)
        self.assertTrue(result.ok)

    def test_subprocess_runner_preserves_non_zero_exit(self) -> None:
        result = SubprocessCommandRunner().run(
            [sys.executable, "-c", "import sys; sys.stderr.write('bad'); sys.exit(7)"],
            timeout_seconds=5,
        )

        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stderr, "bad")
        self.assertFalse(result.timed_out)
        self.assertFalse(result.ok)

    def test_subprocess_runner_marks_timeout(self) -> None:
        result = SubprocessCommandRunner().run(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            timeout_seconds=0,
        )

        self.assertIsNone(result.returncode)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.ok)

    def test_adb_runner_applies_device_id(self) -> None:
        command = ADBCommandRunner(device_id="device-1").build_adb_command(["shell", "getprop", "ro.product.model"])

        self.assertEqual(command, ["adb", "-s", "device-1", "shell", "getprop", "ro.product.model"])

    def test_adb_runner_splits_string_commands(self) -> None:
        command = ADBCommandRunner().build_adb_command("shell input text 'hello world'")

        self.assertEqual(command, ["adb", "shell", "input", "text", "hello world"])

    def test_adb_runner_accepts_explicit_adb_path(self) -> None:
        command = ADBCommandRunner(adb_path="/opt/android/platform-tools/adb").build_adb_command(["devices"])

        self.assertEqual(command, ["/opt/android/platform-tools/adb", "devices"])

    def test_resolve_adb_executable_uses_explicit_env_path(self) -> None:
        with patch.dict(os.environ, {"ASL_ADB_PATH": "/tmp/asl-platform-tools/adb"}, clear=True):
            self.assertEqual(resolve_adb_executable(), "/tmp/asl-platform-tools/adb")

    def test_resolve_adb_executable_uses_platform_tools_env_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            adb_path = Path(tmp_dir) / ("adb.exe" if sys.platform.startswith("win") else "adb")
            adb_path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"ASL_PLATFORM_TOOLS_DIR": tmp_dir}, clear=True):
                with patch("stability.infrastructure.command_runner.shutil.which", return_value=None):
                    self.assertEqual(resolve_adb_executable(), str(adb_path))

    def test_resolve_host_command_rewrites_bare_adb(self) -> None:
        with patch("stability.infrastructure.command_runner.resolve_adb_executable", return_value="/tmp/adb"):
            self.assertEqual(resolve_host_command(["adb", "devices"]), ["/tmp/adb", "devices"])


if __name__ == "__main__":
    unittest.main()
