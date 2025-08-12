from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import RuleReplayAcceptanceService


class RuleReplayAcceptanceServiceTest(unittest.TestCase):
    def test_verify_golden_suite_passes_repository_suite(self) -> None:
        service = RuleReplayAcceptanceService()

        result = service.verify_golden_suite()

        self.assertEqual(result.suite_version, "v2")
        self.assertEqual(result.case_count, 8)
        self.assertEqual(result.failed_case_count, 0)
        self.assertEqual(result.passed_case_count, 8)
        self.assertEqual(result.layer_summaries["merge_semantics"]["case_count"], 4)
        self.assertEqual(result.layer_summaries["identity_semantics"]["case_count"], 2)
        self.assertEqual(result.layer_summaries["stability_guard"]["case_count"], 2)
        self.assertTrue(all(item.passed for item in result.cases))

    def test_verify_golden_suite_reports_mismatch_details(self) -> None:
        with TemporaryDirectory() as temp_dir:
            suite_path = Path(temp_dir) / "goldens.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "suite_version": "v1",
                        "cases": [
                            {
                                "case_id": "broken-case",
                                "description": "Intentionally wrong expectation.",
                                "baseline_rules": {
                                    "fingerprint": {
                                        "version": "baseline-v1",
                                        "ignore_raw_key_issue_types": [],
                                    }
                                },
                                "candidate_rules": {
                                    "fingerprint": {
                                        "version": "candidate-v2",
                                        "ignore_raw_key_issue_types": ["crash"],
                                    }
                                },
                                "filters": {
                                    "package_name": "com.example.app",
                                    "issue_type": "crash",
                                },
                                "dataset": {
                                    "task": {
                                        "task_id": "task-broken",
                                        "task_name": "Broken Golden",
                                        "template_type": "monkey",
                                        "target_app": {"package_name": "com.example.app"},
                                    },
                                    "run": {
                                        "run_id": "run-broken",
                                        "status": "failed",
                                        "created_at": "2025-07-21T09:00:00",
                                    },
                                    "instances": [
                                        {
                                            "instance_id": "instance-broken-a",
                                            "device_id": "device-broken-a",
                                            "template_type": "monkey",
                                            "status": "failed",
                                            "exit_reason": "execution_error",
                                            "result_level": "failed",
                                            "issues": [
                                                {
                                                    "issue_id": "issue-broken-a",
                                                    "issue_type": "crash",
                                                    "issue_title": "检测到 Crash",
                                                    "severity": "critical",
                                                    "detected_at": "2025-07-21T09:01:00",
                                                    "process_name": "com.example.app",
                                                    "package_name": "com.example.app",
                                                    "raw_key": "crash:a",
                                                    "summary": "Crash A",
                                                }
                                            ],
                                        },
                                        {
                                            "instance_id": "instance-broken-b",
                                            "device_id": "device-broken-b",
                                            "template_type": "monkey",
                                            "status": "failed",
                                            "exit_reason": "execution_error",
                                            "result_level": "failed",
                                            "issues": [
                                                {
                                                    "issue_id": "issue-broken-b",
                                                    "issue_type": "crash",
                                                    "issue_title": "检测到 Crash",
                                                    "severity": "critical",
                                                    "detected_at": "2025-07-21T09:02:00",
                                                    "process_name": "com.example.app",
                                                    "package_name": "com.example.app",
                                                    "raw_key": "crash:b",
                                                    "summary": "Crash B",
                                                }
                                            ],
                                        },
                                    ],
                                },
                                "expected": {
                                    "family_count": 99
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            service = RuleReplayAcceptanceService(default_suite_path=str(suite_path))

            result = service.verify_golden_suite()

            self.assertEqual(result.case_count, 1)
            self.assertEqual(result.failed_case_count, 1)
            self.assertFalse(result.cases[0].passed)
            self.assertEqual(result.cases[0].layer, "default")
            self.assertIn("family_count expected 99 but got 1.", result.cases[0].mismatches)
