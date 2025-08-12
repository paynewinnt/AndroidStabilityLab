from __future__ import annotations

import json
import unittest
from urllib.parse import urlencode

from stability.app import TaskService
from stability.repositories import InMemoryTaskRepository
from stability.web.application import WebPortalApplication
from tests.helpers.web_portal import writable_bundle


class AppErrorBoundaryTest(unittest.TestCase):
    def test_web_api_returns_stable_app_error_for_invalid_scenario_params(self) -> None:
        bundle = writable_bundle()
        bundle.task_service = TaskService(repository=InMemoryTaskRepository())
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/tasks/actions/create",
            method="POST",
            body=urlencode(
                {
                    "task_name": "Invalid Install",
                    "package_name": "com.example.app",
                    "template_type": "install_uninstall_loop",
                    "task_params": '{"loop_count":"bad"}',
                    "metadata": "{}",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Actor": "tester", "X-Request-ID": "request-web-1"},
        )

        self.assertEqual(status, 400)
        self.assertIn("application/json", content_type)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["error_code"], "invalid_task_params")
        self.assertEqual(payload["request_id"], "request-web-1")
        self.assertEqual(payload["app_error"]["details"]["template_type"], "install_uninstall_loop")


if __name__ == "__main__":
    unittest.main()
