from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import RuleReplayGoldenSuiteService


def _golden_case(
    *,
    case_id: str,
    issue_type: str,
    layer: str,
    expectation: str,
    description: str = "",
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "description": description or case_id,
        "issue_type": issue_type,
        "layer": layer,
        "expectation": expectation,
        "baseline_rules": {
            "fingerprint": {
                "version": "baseline-v1",
            }
        },
        "candidate_rules": {
            "fingerprint": {
                "version": "candidate-v1",
            }
        },
        "filters": {
            "package_name": "com.example.app",
            "issue_type": issue_type,
        },
        "dataset": {
            "task": {
                "task_id": "task-1",
                "task_name": "Golden Task",
                "template_type": "monkey",
                "target_app": {"package_name": "com.example.app"},
            },
            "run": {
                "run_id": "run-1",
                "status": "failed",
                "created_at": "2025-07-22T12:00:00",
            },
            "instances": [
                {
                    "instance_id": "instance-1",
                    "device_id": "device-1",
                    "template_type": "monkey",
                    "issues": [
                        {
                            "issue_id": f"issue-{case_id}",
                            "issue_type": issue_type,
                            "package_name": "com.example.app",
                            "raw_key": f"{issue_type}:{case_id}",
                        }
                    ],
                }
            ],
        },
        "expected": {
            "family_count": 1,
            "changed_family_count": 1 if expectation != "unchanged" else 0,
            "change_summary": {expectation: 1},
        },
        "draft_metadata": {
            "source_run_id": "run-1",
        },
    }


class RuleReplayGoldenSuiteServiceTest(unittest.TestCase):
    def test_list_cases_filters_by_issue_type_and_layer(self) -> None:
        service = RuleReplayGoldenSuiteService()

        with TemporaryDirectory() as temp_dir:
            suite_path = Path(temp_dir) / "golden.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "suite_version": "v2",
                        "cases": [
                            _golden_case(
                                case_id="crash_regroup",
                                issue_type="crash",
                                layer="merge_semantics",
                                expectation="regrouped",
                            ),
                            _golden_case(
                                case_id="offline_identity",
                                issue_type="device_offline",
                                layer="identity_semantics",
                                expectation="fingerprint_changed",
                            ),
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = service.list_cases(
                suite_path=str(suite_path),
                issue_type="device_offline",
                layer="identity_semantics",
            )

        self.assertEqual(result.case_count, 1)
        self.assertEqual(result.suite_version, "v2")
        self.assertEqual(result.issue_type_counts, {"device_offline": 1})
        self.assertEqual(result.layer_counts, {"identity_semantics": 1})
        self.assertEqual(result.expectation_counts, {"fingerprint_changed": 1})
        self.assertEqual(result.cases[0].case_id, "offline_identity")
        self.assertEqual(result.cases[0].source_run_id, "run-1")

    def test_get_case_returns_full_payload(self) -> None:
        service = RuleReplayGoldenSuiteService()

        with TemporaryDirectory() as temp_dir:
            suite_path = Path(temp_dir) / "golden.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "suite_version": "v2",
                        "cases": [
                            _golden_case(
                                case_id="startup_guard",
                                issue_type="startup_timeout",
                                layer="stability_guard",
                                expectation="unchanged",
                                description="Startup guard case",
                            )
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = service.get_case(case_id="startup_guard", suite_path=str(suite_path))

        self.assertEqual(result.summary.case_id, "startup_guard")
        self.assertEqual(result.summary.layer, "stability_guard")
        self.assertTrue(result.payload["filters"]["package_name"], "com.example.app")
        self.assertEqual(result.payload["expected"]["change_summary"], {"unchanged": 1})

    def test_diff_suites_reports_added_removed_and_modified_cases(self) -> None:
        service = RuleReplayGoldenSuiteService()

        with TemporaryDirectory() as temp_dir:
            left_path = Path(temp_dir) / "left.json"
            right_path = Path(temp_dir) / "right.json"
            left_path.write_text(
                json.dumps(
                    {
                        "suite_version": "v2",
                        "cases": [
                            _golden_case(
                                case_id="case-modified",
                                issue_type="crash",
                                layer="merge_semantics",
                                expectation="regrouped",
                                description="before",
                            ),
                            _golden_case(
                                case_id="case-removed",
                                issue_type="anr",
                                layer="merge_semantics",
                                expectation="regrouped",
                            ),
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            right_path.write_text(
                json.dumps(
                    {
                        "suite_version": "v3",
                        "cases": [
                            _golden_case(
                                case_id="case-modified",
                                issue_type="crash",
                                layer="merge_semantics",
                                expectation="regrouped",
                                description="after",
                            ),
                            _golden_case(
                                case_id="case-added",
                                issue_type="device_offline",
                                layer="identity_semantics",
                                expectation="fingerprint_changed",
                            ),
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = service.diff_suites(
                left_path=str(left_path),
                right_path=str(right_path),
            )

        self.assertEqual(result.left_suite_version, "v2")
        self.assertEqual(result.right_suite_version, "v3")
        self.assertEqual(result.diff_count, 3)
        self.assertEqual(result.change_counts, {"modified": 1, "removed": 1, "added": 1})
        by_case_id = {item.case_id: item for item in result.entries}
        self.assertEqual(by_case_id["case-added"].change_type, "added")
        self.assertEqual(by_case_id["case-removed"].change_type, "removed")
        self.assertEqual(by_case_id["case-modified"].change_type, "modified")
        self.assertIn("description", by_case_id["case-modified"].changed_fields)


if __name__ == "__main__":
    unittest.main()
