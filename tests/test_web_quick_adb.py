from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from stability.infrastructure.command_runner import CommandResult
from stability.web import WebPortalApplication
from tests.helpers import web_portal as web_portal_helpers


class WebQuickAdbTest(unittest.TestCase):
    def test_quick_adb_page_and_api_expose_catalog(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())

        status, content_type, body = app.handle_request("/quick-adb")
        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("快捷 ADB", html)
        self.assertIn("全部链路", html)
        self.assertIn("href='/quick-adb'", html)
        self.assertIn("App 层", html)
        self.assertIn("Kernel / Driver 层", html)
        self.assertIn("执行", html)
        self.assertIn("id='quick-adb-device-select'", html)
        self.assertIn("id='quick-adb-custom-device-ids'", html)
        self.assertIn("multiple", html)
        self.assertIn("/quick-adb/actions/execute?as_session=", html)
        self.assertNotIn("name='device_id'", html)

        status, content_type, body = app.handle_request("/api/quick-adb?layer=kernel")
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["filters"]["layer"], "kernel")
        self.assertIn("device_choices", payload)
        self.assertGreaterEqual(payload["summary"]["command_count"], 1)
        self.assertTrue(all(item["layer"] == "kernel" for item in payload["commands"]))

    def test_quick_adb_execute_uses_whitelisted_template(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())
        calls: list[list[str]] = []

        def fake_run(self, command, *, timeout_seconds=None, timeout=None):
            del self, timeout_seconds, timeout
            calls.append(list(command))
            return CommandResult(returncode=0, stdout="package info", stderr="")

        with patch("stability.infrastructure.command_runner.SubprocessCommandRunner.run", new=fake_run):
            status, content_type, body = app.handle_request(
                "/api/quick-adb/actions/execute",
                method="POST",
                body=urlencode(
                    {
                        "command_id": "app_package",
                        "device_ids": "serial-1 serial-2",
                        "package_name": "com.example.app",
                    }
                ).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                headers={"X-ASL-Actor": "tester"},
            )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(
            calls,
            [
                ["adb", "-s", "serial-1", "shell", "dumpsys", "package", "com.example.app"],
                ["adb", "-s", "serial-2", "shell", "dumpsys", "package", "com.example.app"],
            ],
        )
        self.assertTrue(payload["result"]["ok"])
        self.assertEqual(len(payload["executions"]), 2)
        self.assertIn("[serial-1]\npackage info", payload["result"]["stdout"])
        self.assertIn("[serial-2]\npackage info", payload["result"]["stdout"])


if __name__ == "__main__":
    unittest.main()
