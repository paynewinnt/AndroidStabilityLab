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
from stability.app.analysis_service import AggregatedIssueNotFound
from stability.app.task_service import TaskRecordNotFound
from stability.cli import task_create
from tests.helpers.cli import run_main_with_bundle


class CLIExecutionCommandsTest(unittest.TestCase):
    def test_execution_commands_accept_monitoring_backend_override(self) -> None:
        parser = task_create.build_parser()

        for argv in (
            ["execute-run", "--run-id", "run-1", "--monitoring-backend", "solox"],
            ["run-unattended-round", "--task-id", "task-1", "--monitoring-backend", "auto"],
            ["patrol-unattended-tasks", "--monitoring-backend", "disabled"],
            ["run-unattended-patrol-runner", "--monitoring-backend", "adb_collector"],
        ):
            args = parser.parse_args(argv)
            self.assertEqual(args.monitoring_backend, argv[-1])

    def test_execute_run_passes_monitoring_backend_override_to_bootstrap(self) -> None:
        execute_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            monitoring_backend="solox",
            run_execution_service=SimpleNamespace(
                execute_run=lambda *args, **kwargs: execute_calls.append(dict(kwargs))
                or SimpleNamespace(
                    task=SimpleNamespace(task_id="task-1", task_name="Task 1"),
                    run=SimpleNamespace(run_id="run-1", run_status="success"),
                    instances=[],
                    executed_at=datetime(2025, 7, 23, 10, 0, 0),
                    report_paths={},
                )
            ),
        )

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle) as bootstrap_mock:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = task_create.main(
                    [
                        "execute-run",
                        "--run-id",
                        "run-1",
                        "--monitoring-backend",
                        "solox",
                    ]
                )

        self.assertEqual(exit_code, 0)
        bootstrap_mock.assert_called_once_with(monitoring_backend="solox")
        self.assertEqual(execute_calls[0]["collect_snapshot"], True)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["monitoring_backend"], "solox")
        self.assertEqual(payload["run_id"], "run-1")

    def test_execute_run_outputs_monitoring_trace_fields_for_instances(self) -> None:
        bundle = SimpleNamespace(
            monitoring_backend="perfetto",
            run_execution_service=SimpleNamespace(
                execute_run=lambda *args, **kwargs: SimpleNamespace(
                    task=SimpleNamespace(task_id="task-1", task_name="Task 1"),
                    run=SimpleNamespace(run_id="run-1", run_status="success"),
                    instances=[
                        SimpleNamespace(
                            instance_id="instance-1",
                            device_id="device-1",
                            instance_status="success",
                            queued_at=None,
                            monitoring_session_id="monitor-instance-1",
                            metadata={
                                "monitoring_backend": "perfetto",
                                "monitoring_trace_path": "runtime/monitoring/trace.perfetto-trace",
                                "monitoring_snapshot_path": "runtime/monitoring/snapshot.json",
                            },
                        )
                    ],
                    executed_at=datetime(2025, 7, 23, 10, 0, 0),
                    report_paths={"instance-1": "runtime/report.md"},
                )
            ),
        )

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = task_create.main(
                    [
                        "execute-run",
                        "--run-id",
                        "run-1",
                        "--monitoring-backend",
                        "perfetto",
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["instances"][0]["monitoring_backend"], "perfetto")
        self.assertEqual(
            payload["instances"][0]["monitoring_trace_path"],
            "runtime/monitoring/trace.perfetto-trace",
        )
        self.assertEqual(
            payload["instances"][0]["monitoring_snapshot_path"],
            "runtime/monitoring/snapshot.json",
        )

    def test_describe_rule_entrypoint_prefers_rule_governance_service_method(self) -> None:
        calls: list[object] = []
        service = SimpleNamespace(
            describe_rule_entrypoint=lambda path=None: calls.append(path) or {
                "contract_version": "asl.rule_entrypoint.v1",
                "config_path": path or "config/stability_rules.json",
                "current_version": "rules-v2",
                "validation": {"valid": True, "error_count": 0, "warning_count": 0},
                "editable_fields": ["version", "performance_thresholds"],
                "risk_prompts": ["review required"],
                "recommended_flow": ["preview-analysis-rule-update"],
                "related_policy_files": ["config/stability_rules.json"],
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            ["describe-rule-entrypoint", "--path", "config/custom_rules.json"],
            SimpleNamespace(rule_governance_service=service),
        )

        self.assertEqual(calls, ["config/custom_rules.json"])
        self.assertEqual(payload["rule_entrypoint"]["source"], "service")
        self.assertEqual(payload["rule_entrypoint"]["current_version"], "rules-v2")
        self.assertIn("performance_thresholds", payload["rule_entrypoint"]["editable_fields"])

    def test_preview_analysis_rule_update_outputs_json_without_writing_config(self) -> None:
        calls: list[object] = []
        service = SimpleNamespace(
            preview_analysis_rule_update=lambda **kwargs: calls.append(kwargs) or {
                "contract_version": "asl.rule_update_preview.v1",
                "config_path": kwargs.get("path") or "config/stability_rules.json",
                "updates": kwargs["updates"],
                "changed_field_count": len(kwargs["updates"]),
                "write_policy": "preview_only_no_config_write",
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            [
                "preview-analysis-rule-update",
                "--path",
                "config/custom_rules.json",
                "--set",
                "version=rules-v3",
                "--set",
                "performance_thresholds={\"fps_drop\":10}",
            ],
            SimpleNamespace(rule_governance_service=service),
        )

        self.assertEqual(calls[0]["path"], "config/custom_rules.json")
        self.assertEqual(calls[0]["updates"]["version"], "rules-v3")
        self.assertEqual(calls[0]["updates"]["performance_thresholds"], {"fps_drop": 10})
        self.assertEqual(payload["rule_update_preview"]["source"], "service")
        self.assertEqual(payload["rule_update_preview"]["write_policy"], "preview_only_no_config_write")

    def test_preview_analysis_rule_update_prefers_formal_preview_rule_update(self) -> None:
        calls: list[object] = []
        service = SimpleNamespace(
            preview_rule_update=lambda patch, path=None: calls.append((patch, path)) or {
                "rule_path": path or "config/stability_rules.json",
                "patch": patch,
                "valid": True,
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            [
                "preview-analysis-rule-update",
                "--path",
                "config/custom_rules.json",
                "--set",
                "version=rules-v3",
            ],
            SimpleNamespace(rule_governance_service=service),
        )

        self.assertEqual(calls, [({"fingerprint": {"version": "rules-v3"}}, "config/custom_rules.json")])
        self.assertEqual(payload["rule_update_preview"]["source"], "service")
        self.assertEqual(payload["rule_update_preview"]["config_path"], "config/custom_rules.json")
        self.assertEqual(payload["rule_update_preview"]["changed_field_count"], 1)

    def test_preview_analysis_rule_update_uses_formal_build_rule_edit_plan(self) -> None:
        calls: list[object] = []
        service = SimpleNamespace(
            build_rule_edit_plan=lambda **kwargs: calls.append(kwargs) or {
                "rule_path": kwargs.get("path") or "config/stability_rules.json",
                "patch": {kwargs["section"]: {kwargs["key"]: kwargs["value"]}},
                "valid": True,
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            [
                "preview-analysis-rule-update",
                "--path",
                "config/custom_rules.json",
                "--set",
                "regression.version=rules-v3",
            ],
            SimpleNamespace(rule_governance_service=service),
        )

        self.assertEqual(
            calls,
            [
                {
                    "section": "regression",
                    "key": "version",
                    "value": "rules-v3",
                    "path": "config/custom_rules.json",
                }
            ],
        )
        self.assertEqual(payload["rule_update_preview"]["source"], "service")
        self.assertEqual(payload["rule_update_preview"]["patch"]["regression"]["version"], "rules-v3")

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
