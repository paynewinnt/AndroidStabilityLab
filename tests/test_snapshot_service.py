from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
import unittest

from stability.app import AnalysisService, ComparisonService, RegressionService, RuleGovernanceService, RuleReplayService, RuleReviewService, SnapshotRecordNotFound, SnapshotService
from stability.domain import ComparedMetricTrend, ComparisonScope, MetricTrendSummary, PerformanceTrendComparison
from stability.domain.value_objects import utcnow

from tests.test_comparison_service import build_comparison_service_fixture
from tests.test_rule_replay_service import build_rule_replay_fixture


class SnapshotServiceTest(unittest.TestCase):
    def test_create_top_issues_snapshot_persists_json_and_markdown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = build_snapshot_service_fixture(Path(temp_dir))

            record = service.create_top_issues_snapshot(
                name="Top Issues Snapshot",
                created_by="tester",
                package_name="com.example.app",
                limit=5,
            )

            self.assertEqual(record.snapshot_type, "top_issues")
            self.assertTrue(Path(record.detail_path).exists())
            self.assertTrue(Path(record.markdown_path).exists())
            loaded = service.get_snapshot(record.snapshot_id)
            self.assertEqual(loaded.name, "Top Issues Snapshot")
            self.assertEqual(loaded.summary["top_issue_count"], 5)
            self.assertGreaterEqual(loaded.source_refs["summary"]["run_count"], 1)
            integrity = service.inspect_snapshot_integrity(loaded)
            self.assertTrue(integrity["detail_path_exists"])
            self.assertTrue(integrity["markdown_path_exists"])
            self.assertGreaterEqual(integrity["tracked_path_count"], 2)

    def test_create_comparison_snapshot_and_list_snapshots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = build_snapshot_service_fixture(Path(temp_dir))

            comparison = service.create_comparison_snapshot(
                name="Scenario Compare",
                created_by="tester",
                dimension="scenario",
                left_value="monkey",
                right_value="cold_start_loop",
                version="1.0.0(100)",
                package_name="com.example.app",
            )
            regression = service.create_regression_snapshot(
                name="Regression Decide",
                created_by="tester",
                dimension="version",
                left_value="1.0.0(100)",
                right_value="2.0.0(200)",
                template_type="monkey",
                package_name="com.example.app",
            )

            self.assertEqual(comparison.snapshot_type, "comparison")
            self.assertEqual(regression.snapshot_type, "regression")
            self.assertEqual(regression.summary["metric_count"], 1)
            self.assertEqual(regression.payload["metrics"][0]["regression_result"], "worsened")
            all_items = service.list_snapshots(limit=10)
            self.assertEqual(len(all_items), 2)
            regression_only = service.list_snapshots(snapshot_type="regression", limit=10)
            self.assertEqual(len(regression_only), 1)
            self.assertEqual(regression_only[0].snapshot_id, regression.snapshot_id)

    def test_create_rule_replay_snapshot_persists_rule_versions_and_source_refs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            baseline_path = root_dir / "baseline.json"
            candidate_path = root_dir / "candidate.json"
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
            service = build_snapshot_service_fixture(root_dir)

            record = service.create_rule_replay_snapshot(
                name="Replay Snapshot",
                created_by="tester",
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name="com.example.app",
                include_unchanged=True,
            )

            self.assertEqual(record.snapshot_type, "replay")
            self.assertEqual(record.rule_versions["baseline_fingerprint_rule_version"], "v1")
            self.assertEqual(record.rule_versions["candidate_fingerprint_rule_version"], "v2")
            self.assertGreaterEqual(int(record.summary["changed_family_count"]), 1)
            loaded = service.get_snapshot(record.snapshot_id)
            self.assertGreaterEqual(int(loaded.payload["change_summary"]["regrouped"]), 1)
            self.assertGreaterEqual(loaded.source_refs["summary"]["run_count"], 1)
            self.assertGreaterEqual(loaded.source_refs["summary"]["report_count"], 1)

    def test_create_rule_review_snapshot_persists_decision_and_findings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            baseline_path = root_dir / "baseline.json"
            candidate_path = root_dir / "candidate.json"
            policy_path = root_dir / "policy.json"
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
            review_service = RuleReviewService(
                rule_replay_service=build_rule_replay_fixture(default_rule_path=str(baseline_path)),
                rule_governance_service=RuleGovernanceService(),
                policy_path=str(policy_path),
            )
            service = build_snapshot_service_fixture(root_dir, rule_review_service=review_service)

            record = service.create_rule_review_snapshot(
                name="Review Snapshot",
                created_by="tester",
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                policy_path=str(policy_path),
                package_name="com.example.app",
            )

            self.assertEqual(record.snapshot_type, "review")
            self.assertEqual(record.summary["decision"], "fail")
            loaded = service.get_snapshot(record.snapshot_id)
            self.assertEqual(loaded.payload["decision"], "fail")
            self.assertEqual(loaded.payload["findings"][0]["level"], "fail")
            self.assertGreaterEqual(loaded.source_refs["summary"]["run_count"], 1)

    def test_create_rule_review_snapshot_persists_performance_risks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            baseline_path = root_dir / "baseline.json"
            candidate_path = root_dir / "candidate.json"
            policy_path = root_dir / "policy.json"
            baseline_path.write_text("{}", encoding="utf-8")
            candidate_path.write_text("{}", encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "version": "review-v2",
                        "minimum_family_count": 1,
                        "global_change_limits": {},
                        "issue_type_limits": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review_service = RuleReviewService(
                rule_replay_service=build_rule_replay_fixture(default_rule_path=str(baseline_path)),
                rule_governance_service=RuleGovernanceService(),
                policy_path=str(policy_path),
                performance_risk_provider=lambda **kwargs: {
                    "dimension": kwargs.get("dimension", ""),
                    "metric_result_summary": {"worsened_count": 1, "improved_count": 0},
                    "items": (
                        {
                            "risk_key": "performance_memory_pss_worsened",
                            "category": "performance",
                            "severity": "medium",
                            "summary": "Memory PSS worsened.",
                            "details": {"metric_key": "memory_pss"},
                            "source": "performance_trend_service.compare_performance_trends",
                        },
                    ),
                },
            )
            service = build_snapshot_service_fixture(root_dir, rule_review_service=review_service)

            record = service.create_rule_review_snapshot(
                name="Review Snapshot With Perf",
                created_by="tester",
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                policy_path=str(policy_path),
                package_name="com.example.app",
                dimension="version",
                left_value="1.0.0(100)",
                right_value="2.0.0(200)",
            )

            self.assertEqual(record.summary["performance_risk_count"], 1)
            self.assertEqual(record.summary["metric_result_summary"]["worsened_count"], 1)
            loaded = service.get_snapshot(record.snapshot_id)
            self.assertEqual(loaded.payload["performance_summary"]["dimension"], "version")
            self.assertEqual(loaded.payload["performance_risk_items"][0]["risk_key"], "performance_memory_pss_worsened")

    def test_get_snapshot_raises_for_missing_record(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = build_snapshot_service_fixture(Path(temp_dir))

            with self.assertRaises(SnapshotRecordNotFound):
                service.get_snapshot("snapshot_missing")

    def test_delete_snapshot_removes_snapshot_bundle(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = build_snapshot_service_fixture(Path(temp_dir))
            record = service.create_top_issues_snapshot(
                name="Delete Me",
                created_by="tester",
                package_name="com.example.app",
                limit=3,
            )

            result = service.delete_snapshot(record.snapshot_id)

            self.assertTrue(result["deleted"])
            self.assertFalse(Path(record.detail_path).exists())
            with self.assertRaises(SnapshotRecordNotFound):
                service.get_snapshot(record.snapshot_id)

    def test_plan_retention_marks_old_and_over_limit_snapshots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = build_snapshot_service_fixture(Path(temp_dir))
            older = service.create_top_issues_snapshot(
                name="Older",
                created_by="tester",
                package_name="com.example.app",
                limit=1,
            )
            newer = service.create_top_issues_snapshot(
                name="Newer",
                created_by="tester",
                package_name="com.example.app",
                limit=1,
            )
            older_path = Path(older.detail_path)
            payload = json.loads(older_path.read_text(encoding="utf-8"))
            payload["created_at"] = (utcnow() - timedelta(days=10)).isoformat()
            older_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            plan = service.plan_retention(created_by="tester", max_count=1, max_age_days=7)

            self.assertEqual(plan["matched_snapshot_count"], 2)
            self.assertEqual(plan["delete_count"], 1)
            self.assertEqual(plan["candidates"][0]["snapshot_id"], older.snapshot_id)
            self.assertIn("older_than_max_age_days", plan["candidates"][0]["reasons"])
            self.assertEqual(plan["kept"][0]["snapshot_id"], newer.snapshot_id)

    def test_apply_retention_deletes_matching_snapshots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = build_snapshot_service_fixture(Path(temp_dir))
            first = service.create_top_issues_snapshot(
                name="First",
                created_by="tester",
                package_name="com.example.app",
                limit=1,
            )
            second = service.create_top_issues_snapshot(
                name="Second",
                created_by="tester",
                package_name="com.example.app",
                limit=1,
            )

            result = service.apply_retention(created_by="tester", max_count=1)

            self.assertEqual(result["delete_count"], 1)
            self.assertTrue(any(item["snapshot_id"] == first.snapshot_id for item in result["deleted"]))
            self.assertFalse(Path(first.detail_path).exists())
            self.assertTrue(Path(second.detail_path).exists())


def build_snapshot_service_fixture(
    root_dir: Path,
    *,
    rule_review_service: RuleReviewService | None = None,
) -> SnapshotService:
    comparison_service = build_comparison_service_fixture()
    analysis_service: AnalysisService = comparison_service._analysis_service  # type: ignore[attr-defined]
    regression_service = RegressionService(
        comparison_service=comparison_service,
        performance_trend_service=_FakePerformanceTrendService(
            PerformanceTrendComparison(
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
                sample_summary={"left_session_count": 1, "right_session_count": 1},
                metric_change_summary={},
                comparability_notes=(),
                metrics=(
                    ComparedMetricTrend(
                        metric_key="memory_pss",
                        label="Memory PSS",
                        unit="MB",
                        higher_is_worse=True,
                        left_summary=MetricTrendSummary(
                            metric_key="memory_pss",
                            label="Memory PSS",
                            unit="MB",
                            sample_count=10,
                            session_count=1,
                            average=100.0,
                            peak=120.0,
                            p95=118.0,
                            latest=101.0,
                        ),
                        right_summary=MetricTrendSummary(
                            metric_key="memory_pss",
                            label="Memory PSS",
                            unit="MB",
                            sample_count=10,
                            session_count=1,
                            average=125.0,
                            peak=145.0,
                            p95=143.0,
                            latest=126.0,
                        ),
                        average_delta=25.0,
                        peak_delta=25.0,
                        p95_delta=25.0,
                        latest_delta=25.0,
                        change_type="worsened",
                    ),
                ),
            )
        ),
    )
    rule_replay_service = RuleReplayService(
        task_repository=analysis_service._task_repository,  # type: ignore[attr-defined]
        run_repository=analysis_service._run_repository,  # type: ignore[attr-defined]
        instance_repository=analysis_service._instance_repository,  # type: ignore[attr-defined]
    )
    effective_rule_review_service = rule_review_service or RuleReviewService(
        rule_replay_service=rule_replay_service,
        rule_governance_service=RuleGovernanceService(),
    )
    return SnapshotService(
        root_dir=root_dir,
        analysis_service=analysis_service,
        comparison_service=comparison_service,
        regression_service=regression_service,
        rule_replay_service=rule_replay_service,
        rule_review_service=effective_rule_review_service,
    )


class _FakePerformanceTrendService:
    def __init__(self, result: PerformanceTrendComparison) -> None:
        self._result = result

    def compare_performance_trends(self, **filters):
        return self._result


if __name__ == "__main__":
    unittest.main()
