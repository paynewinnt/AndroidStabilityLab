from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from stability.app import RuleGovernanceService, RuleReviewService

from tests.test_rule_replay_service import (
    build_rule_replay_fingerprint_fixture,
    build_rule_replay_fixture,
)


class RuleReviewServiceTest(unittest.TestCase):
    def test_review_rule_change_fails_when_crash_family_regroups(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            policy_path = Path(temp_dir) / "policy.json"
            baseline_path.write_text("{}", encoding="utf-8")
            candidate_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "v2",
                            "ignore_raw_key_issue_types": ["crash"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            policy_path.write_text(
                json.dumps(
                    {
                        "version": "review-v1",
                        "minimum_family_count": 1,
                        "global_change_limits": {},
                        "issue_type_limits": {
                            "crash": {
                                "regrouped": {
                                    "warning": 0,
                                    "fail": 1,
                                }
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            replay_service = build_rule_replay_fixture(default_rule_path=str(baseline_path))
            service = RuleReviewService(
                rule_replay_service=replay_service,
                rule_governance_service=RuleGovernanceService(),
                policy_path=str(policy_path),
            )

            result = service.review_rule_change(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
            )

            self.assertEqual(result.decision, "fail")
            self.assertEqual(result.policy_version, "review-v1")
            self.assertEqual(result.findings[0].level, "fail")
            self.assertEqual(result.findings[0].issue_type, "crash")
            self.assertIsNotNone(result.golden_suite)
            self.assertEqual(result.golden_suite.failed_case_count, 0)
            self.assertIn("merge_semantics", result.golden_suite.layer_summaries)

    def test_review_rule_change_can_return_conditional_pass_for_warning_threshold(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            policy_path = Path(temp_dir) / "policy.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "v1",
                            "ignore_raw_key_issue_types": [],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            candidate_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "v2",
                            "ignore_raw_key_issue_types": ["device_offline"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            policy_path.write_text(
                json.dumps(
                    {
                        "version": "review-v2",
                        "minimum_family_count": 1,
                        "global_change_limits": {
                            "fingerprint_changed": {
                                "warning": 1,
                                "fail": 2,
                            }
                        },
                        "issue_type_limits": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            replay_service = build_rule_replay_fingerprint_fixture(default_rule_path=str(baseline_path))
            service = RuleReviewService(
                rule_replay_service=replay_service,
                rule_governance_service=RuleGovernanceService(),
                policy_path=str(policy_path),
            )

            result = service.review_rule_change(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
            )

            self.assertEqual(result.decision, "conditional_pass")
            self.assertEqual(result.change_summary["fingerprint_changed"], 1)
            self.assertEqual(result.findings[0].level, "warning")
            self.assertIsNotNone(result.golden_suite)
            self.assertTrue(result.golden_suite.failed_case_count == 0)
            self.assertIn("identity_semantics", result.golden_suite.layer_summaries)

    def test_review_rule_change_passes_when_no_family_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            policy_path = Path(temp_dir) / "policy.json"
            baseline_path.write_text("{}", encoding="utf-8")
            candidate_path.write_text("{}", encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "version": "review-v3",
                        "minimum_family_count": 1,
                        "global_change_limits": {
                            "regrouped": {
                                "warning": 1,
                                "fail": 2,
                            }
                        },
                        "issue_type_limits": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            replay_service = build_rule_replay_fixture(default_rule_path=str(baseline_path))
            service = RuleReviewService(
                rule_replay_service=replay_service,
                rule_governance_service=RuleGovernanceService(),
                policy_path=str(policy_path),
            )

            result = service.review_rule_change(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
                include_unchanged=True,
            )

            self.assertEqual(result.decision, "pass")
            self.assertEqual(result.changed_family_count, 0)
            self.assertEqual(tuple(result.findings), ())
            self.assertIsNotNone(result.golden_suite)
            self.assertEqual(result.golden_suite.passed_case_count, result.golden_suite.case_count)
            self.assertIn("stability_guard", result.golden_suite.layer_summaries)

    def test_review_rule_change_layers_performance_risks_without_replacing_decision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            policy_path = Path(temp_dir) / "policy.json"
            baseline_path.write_text("{}", encoding="utf-8")
            candidate_path.write_text("{}", encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "version": "review-v5",
                        "minimum_family_count": 1,
                        "global_change_limits": {
                            "regrouped": {
                                "warning": 1,
                                "fail": 2,
                            }
                        },
                        "issue_type_limits": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            replay_service = build_rule_replay_fixture(default_rule_path=str(baseline_path))
            service = RuleReviewService(
                rule_replay_service=replay_service,
                rule_governance_service=RuleGovernanceService(),
                policy_path=str(policy_path),
                performance_risk_provider=lambda **kwargs: {
                    "dimension": kwargs.get("dimension", ""),
                    "left_scope": {"label": "version:1.0.0(100)"},
                    "right_scope": {"label": "version:2.0.0(200)"},
                    "metric_result_summary": {"worsened_count": 1, "improved_count": 0},
                    "comparability_notes": ("Performance comparison is based on persisted sessions.",),
                    "items": (
                        {
                            "risk_key": "performance_memory_pss_worsened",
                            "category": "performance",
                            "severity": "medium",
                            "summary": "Memory PSS worsened.",
                            "details": {"metric_key": "memory_pss", "average_delta": 25.0},
                            "source": "performance_trend_service.compare_performance_trends",
                        },
                    ),
                },
            )

            result = service.review_rule_change(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
                dimension="version",
                left_value="1.0.0(100)",
                right_value="2.0.0(200)",
                include_unchanged=True,
            )

            self.assertEqual(result.decision, "pass")
            self.assertEqual(result.filters["dimension"], "version")
            self.assertEqual(result.filters["left_value"], "1.0.0(100)")
            self.assertEqual(result.filters["right_value"], "2.0.0(200)")
            self.assertEqual(result.performance_summary["metric_result_summary"]["worsened_count"], 1)
            self.assertEqual(result.performance_risk_items[0].risk_key, "performance_memory_pss_worsened")
            self.assertEqual(result.performance_risk_items[0].category, "performance")

    def test_review_rule_change_fails_when_golden_suite_fails(self) -> None:
        with TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            policy_path = Path(temp_dir) / "policy.json"
            baseline_path.write_text("{}", encoding="utf-8")
            candidate_path.write_text("{}", encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "version": "review-v4",
                        "minimum_family_count": 1,
                        "global_change_limits": {},
                        "issue_type_limits": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            replay_service = build_rule_replay_fixture(default_rule_path=str(baseline_path))
            acceptance_service = SimpleNamespace(
                verify_golden_suite=lambda **kwargs: SimpleNamespace(
                    suite_path="config/rule_replay_golden_samples.json",
                    suite_version="v1",
                    case_count=4,
                    passed_case_count=3,
                    failed_case_count=1,
                    cases=(
                        SimpleNamespace(
                            case_id="broken",
                            description="broken golden",
                            passed=False,
                            mismatches=("family_count expected 1 but got 2.",),
                        ),
                    ),
                )
            )
            service = RuleReviewService(
                rule_replay_service=replay_service,
                rule_governance_service=RuleGovernanceService(),
                rule_replay_acceptance_service=acceptance_service,
                policy_path=str(policy_path),
            )

            result = service.review_rule_change(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
                include_unchanged=True,
            )

            self.assertEqual(result.decision, "fail")
            self.assertIsNotNone(result.golden_suite)
            self.assertEqual(result.golden_suite.failed_case_count, 1)
            self.assertTrue(any(item.scope == "golden_suite" for item in result.findings))


if __name__ == "__main__":
    unittest.main()
