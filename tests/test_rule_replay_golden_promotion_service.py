from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import RuleReplayAcceptanceService, RuleReplayGoldenPromotionService


class RuleReplayGoldenPromotionServiceTest(unittest.TestCase):
    def test_promote_merges_new_case_and_runs_acceptance(self) -> None:
        service = RuleReplayGoldenPromotionService(
            acceptance_service=RuleReplayAcceptanceService(),
        )

        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "draft.json"
            target_path = temp / "target.json"
            source_path.write_text(
                json.dumps(
                    {
                        "suite_version": "v2",
                        "cases": [
                            {
                                "case_id": "startup_timeout_guard_stays_unchanged_when_rules_match",
                                "description": "Imported draft",
                                "layer": "stability_guard",
                                "expectation": "unchanged",
                                "issue_type": "startup_timeout",
                                "baseline_rules": {
                                    "fingerprint": {
                                        "version": "golden-baseline-startup-guard-v1",
                                        "ignore_raw_key_issue_types": ["startup_timeout"],
                                    }
                                },
                                "candidate_rules": {
                                    "fingerprint": {
                                        "version": "golden-baseline-startup-guard-v1",
                                        "ignore_raw_key_issue_types": ["startup_timeout"],
                                    }
                                },
                                "filters": {
                                    "package_name": "com.example.app",
                                    "issue_type": "startup_timeout",
                                },
                                "include_unchanged": True,
                                "dataset": {
                                    "task": {
                                        "task_id": "task-startup-guard",
                                        "task_name": "Golden Startup Guard Replay",
                                        "template_type": "cold_start_loop",
                                        "target_app": {"package_name": "com.example.app"},
                                    },
                                    "run": {
                                        "run_id": "run-startup-guard",
                                        "status": "failed",
                                        "created_at": "2025-07-21T13:30:00",
                                    },
                                    "instances": [
                                        {
                                            "instance_id": "instance-startup-guard-a",
                                            "device_id": "device-startup-guard-a",
                                            "template_type": "cold_start_loop",
                                            "status": "failed",
                                            "exit_reason": "timeout",
                                            "result_level": "failed",
                                            "issues": [
                                                {
                                                    "issue_id": "issue-startup-guard-a",
                                                    "issue_type": "startup_timeout",
                                                    "issue_title": "启动超时",
                                                    "severity": "high",
                                                    "detected_at": "2025-07-21T13:31:00",
                                                    "process_name": "com.example.app",
                                                    "package_name": "com.example.app",
                                                    "raw_key": "startup:guard-a",
                                                    "summary": "Startup guard A",
                                                }
                                            ],
                                        }
                                    ],
                                },
                                "expected": {
                                    "family_count": 1,
                                    "changed_family_count": 0,
                                    "change_summary": {"unchanged": 1},
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            target_path.write_text(
                json.dumps({"suite_version": "v2", "cases": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = service.promote(
                source_path=str(source_path),
                target_path=str(target_path),
            )

            payload = json.loads(target_path.read_text(encoding="utf-8"))

        self.assertEqual(result.promoted_case_count, 1)
        self.assertEqual(result.promoted_case_ids, ("startup_timeout_guard_stays_unchanged_when_rules_match",))
        self.assertEqual(result.replaced_case_ids, ())
        self.assertIsNotNone(result.acceptance)
        self.assertEqual(result.acceptance.failed_case_count, 0)
        self.assertEqual(len(payload["cases"]), 1)
        self.assertEqual(payload["cases"][0]["case_id"], "startup_timeout_guard_stays_unchanged_when_rules_match")

    def test_promote_rejects_duplicate_target_case_without_replace(self) -> None:
        service = RuleReplayGoldenPromotionService(
            acceptance_service=RuleReplayAcceptanceService(),
        )

        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "draft.json"
            target_path = temp / "target.json"
            case = {
                "case_id": "case-1",
                "description": "case",
                "baseline_rules": {},
                "candidate_rules": {},
                "filters": {},
                "dataset": {},
                "expected": {},
            }
            source_path.write_text(json.dumps({"suite_version": "v2", "cases": [case]}, ensure_ascii=False), encoding="utf-8")
            target_path.write_text(json.dumps({"suite_version": "v2", "cases": [case]}, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                service.promote(source_path=str(source_path), target_path=str(target_path))

        self.assertIn("Target suite already contains case ids: case-1", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
