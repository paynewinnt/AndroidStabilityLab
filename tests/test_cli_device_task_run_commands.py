from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability.app import DeviceRecordNotFound
from stability.app.task_service import TaskRecordNotFound
from stability.cli import task_create
from tests.helpers.cli import run_main_with_bundle


class CLIDeviceTaskRunCommandsTest(unittest.TestCase):
    def test_show_task_template_schema_outputs_shared_contract(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = task_create.main(["show-task-template-schema", "--template-type", "reboot_loop"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["contract"], "scenario_template_schema.v1")
        self.assertEqual(payload["template_type"], "reboot_loop")
        self.assertEqual(payload["risk"]["risk_level"], "high")
        self.assertTrue(payload["risk"]["changes_device_state"])
        self.assertIn("cpu", payload["metrics"]["default"])

    def test_list_devices_outputs_device_summaries(self) -> None:
        sync_calls: list[bool] = []
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                sync_devices=lambda include_unavailable, mark_missing_offline: sync_calls.append(True) or SimpleNamespace(
                    scanned_count=1,
                    created=[],
                    updated=[],
                    refreshed=[],
                    marked_offline=[],
                ),
                list_devices=lambda: [object()],
                list_device_summaries=lambda: [{"device_id": "device-1", "serial": "serial-1"}],
            )
        )

        payload = self._run_main_with_bundle(["list-devices", "--sync"], bundle)

        self.assertEqual(payload["device_count"], 1)
        self.assertEqual(payload["devices"][0]["device_id"], "device-1")
        self.assertEqual(len(sync_calls), 1)
        self.assertEqual(payload["device_sync"]["mode"], "full_registry")
        self.assertEqual(payload["device_sync"]["scanned_count"], 1)

    def test_list_devices_can_sync_one_target_device(self) -> None:
        sync_targets: list[str] = []
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                sync_device=lambda device_id: sync_targets.append(device_id) or SimpleNamespace(device_id=device_id),
                list_devices=lambda: [object()],
                list_device_summaries=lambda: [{"device_id": "device-1", "serial": "serial-1"}],
            )
        )

        payload = self._run_main_with_bundle(["list-devices", "--sync-device", "device-1"], bundle)

        self.assertEqual(payload["device_count"], 1)
        self.assertEqual(sync_targets, ["device-1"])
        self.assertEqual(payload["device_sync"]["mode"], "target_device")
        self.assertTrue(payload["device_sync"]["found"])
        self.assertEqual(payload["device_sync"]["updated_device_id"], "device-1")

    def test_list_device_pools_outputs_schedulable_summary(self) -> None:
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                list_device_summaries=lambda: [
                    {
                        "device_id": "device-1",
                        "group_name": "lab-a",
                        "team": "checkout",
                        "tags": ["smoke", "android14"],
                        "is_online": True,
                        "is_schedulable": True,
                        "connection_state": "connected",
                        "availability_state": "idle",
                    },
                    {
                        "device_id": "device-2",
                        "group_name": "lab-a",
                        "team": "checkout",
                        "tags": ["smoke"],
                        "is_online": False,
                        "is_schedulable": False,
                        "connection_state": "offline",
                        "availability_state": "error",
                    },
                ],
            )
        )

        payload = self._run_main_with_bundle(["list-device-pools", "--group", "lab-a", "--tag", "smoke"], bundle)

        self.assertEqual(payload["summary"]["pool_count"], 1)
        self.assertEqual(payload["summary"]["device_count"], 2)
        self.assertEqual(payload["summary"]["schedulable_device_count"], 1)
        self.assertEqual(payload["summary"]["unschedulable_reason_counts"]["offline"], 1)
        self.assertEqual(payload["pools"][0]["schedulable_devices"][0]["device_id"], "device-1")
        self.assertEqual(payload["pools"][0]["unschedulable_devices"][0]["unschedulable_reasons"][0], "availability:error")

    def test_list_device_pools_prefers_formal_device_service_methods(self) -> None:
        calls: list[object] = []
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                summarize_device_pools=lambda group_by="group": calls.append(("summarize", group_by)) or [
                    {"key": "lab-a", "dimension": group_by, "total_count": 2, "online_count": 1}
                ],
                suggest_device_candidates=lambda **kwargs: calls.append(("suggest", kwargs)) or {
                    "candidates": [
                        {
                            "device_id": "device-1",
                            "serial": "serial-1",
                            "display_name": "Pixel 8",
                            "schedulable": True,
                            "profile": {"group_name": "lab-a", "team_name": "checkout", "tags": ["smoke"]},
                        }
                    ],
                    "rejected_candidates": [
                        {
                            "device_id": "device-2",
                            "serial": "serial-2",
                            "display_name": "Pixel 7",
                            "schedulable": False,
                            "reasons": ["offline"],
                            "profile": {"group_name": "lab-a", "team_name": "checkout", "tags": ["smoke"]},
                        }
                    ],
                },
                list_device_summaries=lambda: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
            )
        )

        payload = self._run_main_with_bundle(
            ["list-device-pools", "--group", "lab-a", "--team", "checkout", "--tag", "smoke"],
            bundle,
        )

        self.assertEqual([item for item in calls if item[0] == "summarize"], [("summarize", "group"), ("summarize", "team"), ("summarize", "tag")])
        self.assertEqual(calls[-1][0], "suggest")
        self.assertEqual(calls[-1][1]["group_name"], "lab-a")
        self.assertEqual(calls[-1][1]["team_name"], "checkout")
        self.assertEqual(calls[-1][1]["tags"], ("smoke",))
        self.assertEqual(payload["summary"]["schedulable_device_count"], 1)
        self.assertEqual(payload["summary"]["unschedulable_reason_counts"]["offline"], 1)

    def test_inspect_device_pool_prefers_formal_device_service_methods(self) -> None:
        calls: list[object] = []
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                summarize_device_pools=lambda group_by="group": calls.append(("summarize", group_by)) or [
                    {"key": "lab-a", "dimension": group_by, "total_count": 1, "online_count": 1}
                ],
                suggest_device_candidates=lambda **kwargs: calls.append(("suggest", kwargs)) or {
                    "candidates": [
                        {
                            "device_id": "device-1",
                            "serial": "serial-1",
                            "display_name": "Pixel 8",
                            "schedulable": True,
                            "profile": {"group_name": "lab-a", "team_name": "checkout", "tags": ["smoke"]},
                        }
                    ],
                    "rejected_candidates": [],
                },
                describe_device_pools=lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy fallback should not be used")),
            )
        )

        payload = self._run_main_with_bundle(["inspect-device-pool", "--group", "lab-a"], bundle)

        self.assertEqual(calls[-1][0], "suggest")
        self.assertEqual(calls[-1][1]["group_name"], "lab-a")
        self.assertEqual(payload["pool"]["group_name"], "lab-a")
        self.assertEqual(payload["pool"]["schedulable_devices"][0]["device_id"], "device-1")

    def test_inspect_device_pool_requires_filter(self) -> None:
        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=SimpleNamespace(device_service=SimpleNamespace())):
            with self.assertRaises(SystemExit) as ctx:
                task_create.main(["inspect-device-pool"])

        self.assertIn("At least one of --group, --team, or --tag is required.", str(ctx.exception))

    def test_show_device_outputs_detail(self) -> None:
        device = object()
        sync_calls: list[bool] = []
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                sync_devices=lambda include_unavailable, mark_missing_offline: sync_calls.append(True) or SimpleNamespace(
                    scanned_count=1,
                    created=[],
                    updated=[],
                    refreshed=[],
                    marked_offline=[],
                ),
                require_device=lambda device_id: device if device_id == "device-1" else None,
                describe_device=lambda item, include_metadata=True: {
                    "device_id": "device-1",
                    "metadata": {"api_level": 34},
                },
            )
        )

        payload = self._run_main_with_bundle(["show-device", "--device-id", "device-1", "--sync"], bundle)

        self.assertEqual(payload["device"]["device_id"], "device-1")
        self.assertEqual(payload["device"]["metadata"]["api_level"], 34)
        self.assertEqual(len(sync_calls), 1)
        self.assertEqual(payload["device_sync"]["mode"], "full_registry")
        self.assertEqual(payload["device_sync"]["scanned_count"], 1)

    def test_show_device_can_sync_target_only(self) -> None:
        device = object()
        sync_targets: list[str] = []
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                sync_device=lambda device_id: sync_targets.append(device_id) or SimpleNamespace(device_id=device_id),
                require_device=lambda device_id: device if device_id == "device-1" else None,
                describe_device=lambda item, include_metadata=True: {
                    "device_id": "device-1",
                    "metadata": {"api_level": 34},
                },
            )
        )

        payload = self._run_main_with_bundle(
            ["show-device", "--device-id", "device-1", "--sync-target-only"],
            bundle,
        )

        self.assertEqual(payload["device"]["device_id"], "device-1")
        self.assertEqual(sync_targets, ["device-1"])
        self.assertEqual(payload["device_sync"]["mode"], "target_device")
        self.assertTrue(payload["device_sync"]["found"])
        self.assertEqual(payload["device_sync"]["updated_device_id"], "device-1")

    def test_show_device_raises_for_missing_device(self) -> None:
        bundle = SimpleNamespace(
            device_service=SimpleNamespace(
                require_device=lambda device_id: (_ for _ in ()).throw(
                    DeviceRecordNotFound(f"Device '{device_id}' was not found.")
                )
            )
        )

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            with self.assertRaises(SystemExit) as ctx:
                task_create.main(["show-device", "--device-id", "missing"])

        self.assertIn("Device 'missing' was not found.", str(ctx.exception))

    def test_list_tasks_outputs_task_summaries(self) -> None:
        bundle = SimpleNamespace(
            task_service=SimpleNamespace(
                list_tasks=lambda: [object(), object()],
                list_task_summaries=lambda: [{"task_id": "task-1"}, {"task_id": "task-2"}],
            )
        )

        payload = self._run_main_with_bundle(["list-tasks"], bundle)

        self.assertEqual(payload["task_count"], 2)
        self.assertEqual([item["task_id"] for item in payload["tasks"]], ["task-1", "task-2"])

    def test_show_task_outputs_detail(self) -> None:
        task = object()
        bundle = SimpleNamespace(
            task_service=SimpleNamespace(
                get_task=lambda task_id: task if task_id == "task-1" else None,
                describe_task=lambda item, include_metadata=True: {
                    "task_id": "task-1",
                    "task_name": "Task 1",
                    "metadata": {"owner": "cli"},
                },
            )
        )

        payload = self._run_main_with_bundle(["show-task", "--task-id", "task-1"], bundle)

        self.assertEqual(payload["task"]["task_id"], "task-1")
        self.assertEqual(payload["task"]["metadata"]["owner"], "cli")

    def test_list_runs_passes_extended_filters(self) -> None:
        history_service = SimpleNamespace(
            list_runs=lambda **kwargs: [
                {
                    "run_id": "run-1",
                    "run_status": "failed",
                    "task_id": "task-1",
                }
            ]
        )
        bundle = SimpleNamespace(run_history_service=history_service)

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = task_create.main(
                    [
                        "list-runs",
                        "--task-id",
                        "task-1",
                        "--status",
                        "failed",
                        "--template-type",
                        "monkey",
                        "--package-name",
                        "com.example.app",
                        "--device-id",
                        "device-1",
                        "--has-issue",
                        "true",
                        "--created-from",
                        "2025-07-18T00:00:00",
                        "--created-to",
                        "2025-07-19T00:00:00",
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["filters"]["template_type"], "monkey")
        self.assertEqual(payload["filters"]["has_issue"], True)
        self.assertEqual(payload["runs"][0]["run_id"], "run-1")

    def test_show_task_raises_for_missing_task(self) -> None:
        bundle = SimpleNamespace(
            task_service=SimpleNamespace(
                get_task=lambda task_id: (_ for _ in ()).throw(TaskRecordNotFound(f"Task '{task_id}' was not found."))
            )
        )

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            with self.assertRaises(SystemExit) as ctx:
                task_create.main(["show-task", "--task-id", "missing"])

        self.assertIn("Task 'missing' was not found.", str(ctx.exception))

    def test_list_long_run_templates_prefers_service_templates(self) -> None:
        calls: list[str] = []
        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                list_long_run_templates=lambda: calls.append("list") or [
                    {
                        "template_id": "service_soak",
                        "name": "Service Soak",
                        "default_template_type": "monkey",
                        "default_interval_minutes": 15,
                        "default_max_rounds": 4,
                        "recommended_device_count": 1,
                        "recommended_rotation_strategy": "round_robin",
                    }
                ]
            )
        )

        payload = self._run_main_with_bundle(["list-long-run-templates"], bundle)

        self.assertEqual(calls, ["list"])
        self.assertEqual(payload["source"], "service")
        self.assertEqual(payload["template_count"], 1)
        self.assertEqual(payload["templates"][0]["template_key"], "service_soak")
        self.assertEqual(payload["templates"][0]["template_id"], "service_soak")
        self.assertEqual(payload["templates"][0]["defaults"]["interval_minutes"], 15)
        self.assertIn("interval_minutes", payload["templates"][0]["overridable_parameters"])

    def test_plan_long_run_template_calls_service_plan_with_overrides(self) -> None:
        calls: list[object] = []

        def list_long_run_templates() -> list[dict[str, object]]:
            calls.append("list")
            return [
                {
                    "template_id": "service_soak",
                    "name": "Service Soak",
                    "default_template_type": "monkey",
                    "default_interval_minutes": 15,
                    "default_max_rounds": 4,
                    "recommended_device_count": 1,
                    "recommended_rotation_strategy": "round_robin",
                }
            ]

        def plan_long_run_template(template_key: str, *, overrides: dict[str, object]) -> dict[str, object]:
            calls.append(("plan", template_key, overrides))
            return {
                "template_key": template_key,
                "effective_defaults": {"interval_minutes": overrides["interval_minutes"]},
                "overrides": overrides,
            }

        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                list_long_run_templates=list_long_run_templates,
                plan_long_run_template=plan_long_run_template,
            )
        )

        payload = self._run_main_with_bundle(
            [
                "plan-long-run-template",
                "--template-key",
                "service_soak",
                "--override",
                "interval_minutes=45",
            ],
            bundle,
        )

        self.assertEqual(calls[0], "list")
        self.assertEqual(calls[1], ("plan", "service_soak", {"interval_minutes": 45}))
        self.assertEqual(payload["source"], "service")
        self.assertEqual(payload["plan"]["effective_defaults"]["interval_minutes"], 45)

    def test_plan_long_run_template_calls_service_build_plan_with_overrides(self) -> None:
        calls: list[object] = []

        def list_long_run_templates() -> list[dict[str, object]]:
            calls.append("list")
            return [
                {
                    "template_key": "service_soak",
                    "name": "Service Soak",
                    "defaults": {"interval_minutes": 15, "desired_device_count": 1},
                    "overridable_parameters": ["interval_minutes", "task_name"],
                }
            ]

        def build_long_run_plan(template_id: str, **kwargs: object) -> dict[str, object]:
            calls.append(("build", template_id, kwargs))
            return {
                "template_key": template_id,
                "source": "build",
                "effective_defaults": {"interval_minutes": kwargs["interval_minutes"]},
                "overrides": kwargs,
            }

        bundle = SimpleNamespace(
            unattended_service=SimpleNamespace(
                list_long_run_templates=list_long_run_templates,
                build_long_run_plan=build_long_run_plan,
            )
        )

        payload = self._run_main_with_bundle(
            [
                "plan-long-run-template",
                "--template-key",
                "service_soak",
                "--override",
                "interval_minutes=45",
                "--override",
                "task_name=Nightly Soak",
            ],
            bundle,
        )

        self.assertEqual(calls[0], "list")
        self.assertEqual(
            calls[1],
            ("build", "service_soak", {"interval_minutes": 45}),
        )
        self.assertEqual(payload["source"], "service")
        self.assertEqual(payload["plan"]["source"], "build")
        self.assertEqual(payload["plan"]["effective_defaults"]["interval_minutes"], 45)

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
