from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from stability.infrastructure.command_runner import CommandResult
from stability.web import WebPortalApplication
from stability.web.features.quick_adb.catalog import quick_adb_command_by_id
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
        self.assertIn("Android 调用链路", html)
        self.assertIn("执行目标", html)
        self.assertNotIn("三步上手", html)
        self.assertIn("<details class='panel quick-adb-target-panel' open>", html)
        self.assertIn("<summary><strong>执行目标</strong>", html)
        self.assertIn("quick-adb-target-body", html)
        self.assertIn("id='quick-adb-device-select'", html)
        self.assertIn("id='quick-adb-custom-device-ids'", html)
        self.assertIn("id='quick-adb-selected-devices'", html)
        self.assertIn("id='quick-adb-package-select'", html)
        self.assertIn("id='quick-adb-selected-packages'", html)
        self.assertIn("id='quick-adb-package-scope'", html)
        self.assertIn("id='quick-adb-manual-packages'", html)
        self.assertIn("当前已选设备", html)
        self.assertIn("当前已选包名", html)
        self.assertIn("尚未选择设备", html)
        self.assertIn("尚未选择包名", html)
        self.assertIn("renderQuickAdbSelectedDevices", html)
        self.assertIn("renderQuickAdbSelectedPackages", html)
        self.assertIn("quickAdbPackageStorageKey", html)
        self.assertIn("asl.quickAdb.selectedPackages.v1", html)
        self.assertIn("restoreQuickAdbPackages", html)
        self.assertIn("persistQuickAdbPackages", html)
        self.assertIn("scheduleAdminFilterSubmit", html)
        self.assertIn("target.closest('.admin-filter-bar')", html)
        self.assertIn("const actionPreviewLinkSelector='[data-action-preview-link][href]'", html)
        self.assertNotIn(".admin-table-actions a[href],.task-row-actions a[href]", html)
        self.assertIn("/api/quick-adb/packages", html)
        self.assertIn("data-quick-adb-package-target", html)
        self.assertIn("class='quick-adb-package-help'", html)
        self.assertIn("Package 参数说明", html)
        self.assertIn("使用上方“包名选择”。可从设备包名下拉多选，也可以手动输入包名。", html)
        self.assertIn("multiple", html)
        self.assertIn("/quick-adb/actions/execute?as_session=", html)
        self.assertNotIn("name='device_id'", html)
        self.assertNotIn("name='package_name' placeholder='com.example.app'", html)
        self.assertNotIn("<div class='notice'>使用上方“包名选择”。可从设备包名下拉多选，也可以手动输入包名。</div>", html)
        self.assertNotIn("quick-adb-result-modal is-open", html)

        status, content_type, body = app.handle_request("/api/quick-adb?layer=kernel")
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["filters"]["layer"], "kernel")
        self.assertIn("device_choices", payload)
        self.assertGreaterEqual(payload["summary"]["command_count"], 1)
        self.assertTrue(all(item["layer"] == "kernel" for item in payload["commands"]))

    def test_quick_adb_binder_state_reports_unavailable_reason(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())

        status, content_type, body = app.handle_request("/api/quick-adb?layer=hal")
        payload = json.loads(body.decode("utf-8"))
        binder_command = next(item for item in payload["commands"] if item["command_id"] == "hal_binder_state")
        command_text = " ".join(binder_command["args"])

        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertIn("/sys/kernel/debug/binder/state", command_text)
        self.assertIn("/dev/binderfs/binder_logs/state", command_text)
        self.assertIn("binder state 不可读", command_text)
        self.assertIn("exit 0", command_text)
        self.assertNotIn("2>/dev/null", command_text)
        self.assertEqual(binder_command["args"][0], "shell")
        self.assertNotIn("sh", binder_command["args"][1:])
        self.assertNotIn("-c", binder_command["args"][1:])

    def test_quick_adb_exposes_non_root_binder_fallback_commands(self) -> None:
        expected = {
            "system_binder_calls_stats_enable": ("shell", "dumpsys", "binder_calls_stats", "--enable"),
            "system_binder_calls_stats_reset": ("shell", "dumpsys", "binder_calls_stats", "--reset"),
            "system_binder_calls_stats": ("shell", "dumpsys", "binder_calls_stats"),
            "system_looper_stats": ("shell", "dumpsys", "looper_stats"),
            "system_procstats_1h": ("shell", "dumpsys", "procstats", "--hours", "1"),
        }

        for command_id, args in expected.items():
            with self.subTest(command_id=command_id):
                command = quick_adb_command_by_id(command_id)
                self.assertIsNotNone(command)
                self.assertEqual(command.args, args)
                self.assertEqual(command.layer, "system_server")
                self.assertEqual(command.group, "非 root Binder 替代诊断")

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
        self.assertIn("[serial-1 / com.example.app]\npackage info", payload["result"]["stdout"])
        self.assertIn("[serial-2 / com.example.app]\npackage info", payload["result"]["stdout"])

    def test_quick_adb_execute_supports_multiple_packages(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())
        calls: list[list[str]] = []

        def fake_run(self, command, *, timeout_seconds=None, timeout=None):
            del self, timeout_seconds, timeout
            calls.append(list(command))
            return CommandResult(returncode=0, stdout="ok", stderr="")

        with patch("stability.infrastructure.command_runner.SubprocessCommandRunner.run", new=fake_run):
            status, _content_type, body = app.handle_request(
                "/api/quick-adb/actions/execute",
                method="POST",
                body=urlencode(
                    {
                        "command_id": "app_package",
                        "device_ids": "serial-1",
                        "package_names": "com.example.one,com.example.two",
                    }
                ).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                headers={"X-ASL-Actor": "tester"},
            )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(
            calls,
            [
                ["adb", "-s", "serial-1", "shell", "dumpsys", "package", "com.example.one"],
                ["adb", "-s", "serial-1", "shell", "dumpsys", "package", "com.example.two"],
            ],
        )
        self.assertEqual(len(payload["executions"]), 2)
        self.assertIn("[serial-1 / com.example.one]\nok", payload["result"]["stdout"])
        self.assertIn("[serial-1 / com.example.two]\nok", payload["result"]["stdout"])

    def test_quick_adb_packages_api_lists_device_packages(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())
        calls: list[list[str]] = []

        def fake_run(self, command, *, timeout_seconds=None, timeout=None):
            del self, timeout_seconds, timeout
            calls.append(list(command))
            return CommandResult(
                returncode=0,
                stdout="package:com.example.app\npackage:/system/app/Settings.apk=com.android.settings\n",
                stderr="",
            )

        with patch("stability.infrastructure.command_runner.SubprocessCommandRunner.run", new=fake_run):
            status, content_type, body = app.handle_request(
                "/api/quick-adb/packages?device_id=serial-1&scope=third_party&q=example",
                headers={"X-ASL-Actor": "tester"},
            )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls, [["adb", "-s", "serial-1", "shell", "pm", "list", "packages", "-3"]])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["packages"][0]["package_name"], "com.example.app")
        self.assertEqual(payload["packages"][0]["scope"], "third_party")

    def test_quick_adb_html_execute_opens_result_modal(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())

        def fake_run(self, command, *, timeout_seconds=None, timeout=None):
            del self, command, timeout_seconds, timeout
            return CommandResult(returncode=0, stdout="uptime output", stderr="")

        with patch("stability.infrastructure.command_runner.SubprocessCommandRunner.run", new=fake_run):
            status, content_type, body = app.handle_request(
                "/quick-adb/actions/execute",
                method="POST",
                body=urlencode({"command_id": "kernel_uptime"}).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                headers={"X-ASL-Actor": "tester"},
            )

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("quick-adb-result-modal is-open", html)
        self.assertIn("ADB 执行结果 - Kernel Uptime", html)
        self.assertIn("uptime output", html)
        self.assertIn("data-task-modal-close='1'", html)
        self.assertNotIn("<h2>执行结果</h2>", html)

    def test_quick_adb_html_execute_preserves_selected_devices(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())

        def fake_run(self, command, *, timeout_seconds=None, timeout=None):
            del self, command, timeout_seconds, timeout
            return CommandResult(returncode=0, stdout="uptime output", stderr="")

        with patch("stability.infrastructure.command_runner.SubprocessCommandRunner.run", new=fake_run):
            status, content_type, body = app.handle_request(
                "/quick-adb/actions/execute",
                method="POST",
                body=urlencode(
                    {
                        "command_id": "kernel_uptime",
                        "device_ids": "192.168.31.99:5555 custom-device-1",
                    }
                ).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                headers={"X-ASL-Actor": "tester"},
            )

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("<option value='192.168.31.99:5555' selected>", html)
        self.assertIn("custom-device-1</textarea>", html)
        self.assertIn("<span class='quick-adb-device-chip'>192.168.31.99:5555</span>", html)
        self.assertIn("<span class='quick-adb-device-chip'>custom-device-1</span>", html)
        self.assertIn("当前已选设备", html)

    def test_quick_adb_html_execute_preserves_selected_packages(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())

        def fake_run(self, command, *, timeout_seconds=None, timeout=None):
            del self, command, timeout_seconds, timeout
            return CommandResult(returncode=0, stdout="package output", stderr="")

        with patch("stability.infrastructure.command_runner.SubprocessCommandRunner.run", new=fake_run):
            status, content_type, body = app.handle_request(
                "/quick-adb/actions/execute",
                method="POST",
                body=urlencode(
                    {
                        "command_id": "app_package",
                        "package_names": "com.example.one,com.example.two",
                    }
                ).encode("utf-8"),
                content_type="application/x-www-form-urlencoded",
                headers={"X-ASL-Actor": "tester"},
            )

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("quick-adb-result-modal is-open", html)
        self.assertIn("<option value='com.example.one' selected>com.example.one [已选择]</option>", html)
        self.assertIn("<option value='com.example.two' selected>com.example.two [已选择]</option>", html)
        self.assertIn("<span class='quick-adb-package-chip'>com.example.one</span>", html)
        self.assertIn("<span class='quick-adb-package-chip'>com.example.two</span>", html)
        self.assertIn("<span>2 个</span>", html)
        self.assertIn("quickAdbSelectedPackages", html)
        self.assertIn("quick-adb-selected-packages", html)
        self.assertIn("已选包名会在刷新后保留", html)

    def test_quick_adb_html_execute_missing_package_stays_on_page(self) -> None:
        app = WebPortalApplication(web_portal_helpers.bundle())

        status, content_type, body = app.handle_request(
            "/quick-adb/actions/execute",
            method="POST",
            body=urlencode({"command_id": "app_package"}).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Actor": "tester"},
        )

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Package 类命令需要先在上方选择设备包名", html)
        self.assertIn("Android 调用链路", html)
        self.assertIn("执行目标", html)
        self.assertNotIn("当前页面在读取服务层数据时发生错误", html)
        self.assertNotIn("三步上手", html)


if __name__ == "__main__":
    unittest.main()
