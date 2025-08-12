from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import AnalysisService, RegressionService
from stability.domain import AnalysisRuleConfig, ComparisonScope, ComparisonResult, ComparedIssue, FingerprintRuleConfig, IssueType, RegressionRuleSet
from stability.infrastructure import FileBackedRuleConfigProvider
from stability.repositories import InMemoryInstanceRepository, InMemoryRunRepository, InMemoryTaskRepository


class RuleConfigProviderTest(unittest.TestCase):
    def test_load_reads_fingerprint_regression_and_attribution_rules(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "fingerprint": {
                            "version": "fp-v2",
                            "ignore_raw_key_issue_types": ["crash", "device_offline"],
                        },
                        "regression": {
                            "version": "reg-v2",
                            "min_side_issue_groups": 2,
                            "significant_occurrence_delta": 3,
                            "significant_affected_run_delta": 4,
                            "significant_affected_device_delta": 5,
                            "significant_affected_scenario_delta": 6,
                            "min_side_metric_sessions": 7,
                            "min_side_metric_samples": 8,
                            "significant_metric_delta_ratio": 0.25,
                        },
                        "attribution": {
                            "version": "attr-v2",
                            "fallback_direction": "unknown",
                            "medium_confidence_score": 4,
                            "high_confidence_score": 7,
                            "rules": [
                                {
                                    "rule_id": "app_rule",
                                    "name": "App rule",
                                    "direction": "app_logic",
                                    "issue_types": ["crash", "system_server_crash"],
                                    "scored_issue_types": ["system_server_crash"],
                                    "issue_type_score": 4,
                                    "summary_keywords": ["fatal exception"],
                                    "evidence_signal_keywords": ["watchdog"],
                                    "evidence_source_keywords": ["dropbox"],
                                    "matched_fragment_keywords": ["system_server"],
                                    "confirmation_level_scores": {"strong": 3},
                                    "recommended_next_steps": ["Inspect dropbox."],
                                    "review_notes": ["Needs manual review."],
                                    "package_process_match": True,
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            config = FileBackedRuleConfigProvider(path).load()

        self.assertEqual(config.fingerprint.version, "fp-v2")
        self.assertEqual(
            list(config.fingerprint.ignore_raw_key_issue_types),
            [IssueType.CRASH, IssueType.DEVICE_OFFLINE],
        )
        self.assertEqual(config.regression.version, "reg-v2")
        self.assertEqual(config.regression.min_side_metric_sessions, 7)
        self.assertEqual(config.regression.significant_metric_delta_ratio, 0.25)
        self.assertEqual(config.attribution.version, "attr-v2")
        self.assertEqual(config.attribution.high_confidence_score, 7)
        self.assertEqual(config.attribution.rules[0].direction, "app_logic")
        self.assertEqual(list(config.attribution.rules[0].issue_types), [IssueType.CRASH, IssueType.SYSTEM_SERVER_CRASH])
        self.assertEqual(list(config.attribution.rules[0].scored_issue_types), [IssueType.SYSTEM_SERVER_CRASH])
        self.assertEqual(config.attribution.rules[0].issue_type_score, 4)
        self.assertEqual(list(config.attribution.rules[0].evidence_signal_keywords), ["watchdog"])
        self.assertEqual(list(config.attribution.rules[0].evidence_source_keywords), ["dropbox"])
        self.assertEqual(list(config.attribution.rules[0].matched_fragment_keywords), ["system_server"])
        self.assertEqual(dict(config.attribution.rules[0].confirmation_level_scores), {"strong": 3})
        self.assertEqual(list(config.attribution.rules[0].recommended_next_steps), ["Inspect dropbox."])
        self.assertEqual(list(config.attribution.rules[0].review_notes), ["Needs manual review."])
        self.assertTrue(config.attribution.rules[0].package_process_match)


class RuleConfigIntegrationTest(unittest.TestCase):
    def test_analysis_service_uses_configured_fingerprint_version(self) -> None:
        service = AnalysisService(
            task_repository=InMemoryTaskRepository(),
            run_repository=InMemoryRunRepository(),
            instance_repository=InMemoryInstanceRepository(),
            rule_config=AnalysisRuleConfig(
                fingerprint=FingerprintRuleConfig(
                    version="fp-v2",
                    ignore_raw_key_issue_types=(IssueType.CRASH,),
                )
            ),
        )

        self.assertEqual(service.fingerprint_rule_version, "fp-v2")

    def test_regression_service_uses_configured_rule_set_by_default(self) -> None:
        service = RegressionService(
            comparison_service=_FakeComparisonService(),
            configured_rule_set=RegressionRuleSet(
                version="reg-v2",
                min_side_issue_groups=3,
                significant_occurrence_delta=4,
                significant_affected_run_delta=5,
                significant_affected_device_delta=6,
                significant_affected_scenario_delta=7,
                min_side_metric_sessions=8,
                min_side_metric_samples=9,
                significant_metric_delta_ratio=0.3,
            ),
        )

        result = service.evaluate_regression(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            package_name="com.example.app",
        )

        self.assertEqual(result.rule_set.version, "reg-v2")
        self.assertEqual(result.rule_set.min_side_issue_groups, 3)
        self.assertEqual(result.rule_set.min_side_metric_sessions, 8)
        self.assertEqual(result.rule_set.significant_metric_delta_ratio, 0.3)


class _FakeComparisonService:
    def compare_issues(self, **filters):
        return ComparisonResult(
            dimension="version",
            left_scope=ComparisonScope(
                dimension="version",
                value="1.0.0(100)",
                label="version:1.0.0(100)",
                filters={"version": "1.0.0(100)"},
            ),
            right_scope=ComparisonScope(
                dimension="version",
                value="2.0.0(200)",
                label="version:2.0.0(200)",
                filters={"version": "2.0.0(200)"},
            ),
            base_filters={"package_name": "com.example.app"},
            sample_summary={"left_issue_group_count": 0, "right_issue_group_count": 0},
            issue_change_summary={},
            metric_change_summary={},
            comparability_notes=(),
            issues=(
                ComparedIssue(
                    comparison_key="cmp-1",
                    title="Crash",
                    issue_type="crash",
                    severity="critical",
                    change_type="new",
                    occurrence_delta=1,
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
