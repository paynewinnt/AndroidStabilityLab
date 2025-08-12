from __future__ import annotations

import sys
import unittest

from stability.infrastructure.command_runner import ADBCommandRunner, CommandResult, SubprocessCommandRunner


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


if __name__ == "__main__":
    unittest.main()

