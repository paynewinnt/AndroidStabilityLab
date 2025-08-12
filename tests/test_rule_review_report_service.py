from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import RuleGovernanceService, RuleReviewReportService, RuleReviewService

from tests.test_snapshot_service import build_snapshot_service_fixture
from tests.test_rule_replay_service import build_rule_replay_fixture


class RuleReviewReportServiceTest(unittest.TestCase):
    def test_create_report_summarizes_review_snapshots(self) -> None:
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
            snapshot_service = build_snapshot_service_fixture(root_dir, rule_review_service=review_service)
            snapshot_service.create_rule_review_snapshot(
                name="Review 1",
                created_by="tester",
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                policy_path=str(policy_path),
                package_name="com.example.app",
                dimension="version",
                left_value="1.0.0(100)",
                right_value="2.0.0(200)",
            )

            report_service = RuleReviewReportService(
                root_dir=root_dir / "reports",
                snapshot_service=snapshot_service,
            )
            report = report_service.create_report(
                name="Review Report",
                created_by="cli",
                snapshot_created_by="tester",
                limit=10,
            )

            self.assertTrue(Path(report.detail_path).exists())
            self.assertTrue(Path(report.markdown_path).exists())
            self.assertTrue(Path(report.html_path).exists())
            self.assertEqual(report.summary["snapshot_count"], 1)
            self.assertEqual(report.summary["decision_counts"]["fail"], 1)
            self.assertEqual(report.entries[0].decision, "fail")
            self.assertEqual(report.summary["golden_suite_snapshot_count"], 1)
            self.assertEqual(report.summary["golden_suite_failed_snapshot_count"], 0)
            self.assertGreater(report.summary["golden_suite_case_count_total"], 0)
            self.assertIn("merge_semantics", report.summary["golden_suite_layer_summaries"])
            self.assertEqual(report.summary["metric_result_summary"]["worsened_count"], 1)
            self.assertEqual(report.summary["performance_risk_count_total"], 1)
            self.assertEqual(report.summary["performance_risk_items"][0]["risk_key"], "performance_memory_pss_worsened")
            self.assertTrue(report.entries[0].golden_suite_passed)
            self.assertIn("merge_semantics", report.entries[0].golden_suite_layer_summaries)
            self.assertEqual(report.entries[0].performance_summary["dimension"], "version")
            self.assertEqual(report.entries[0].performance_risk_items[0].risk_key, "performance_memory_pss_worsened")
            self.assertGreaterEqual(len(report.high_risk_families), 1)

    def test_compare_reports_summarizes_family_deltas(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            left_dir = report_root / "review_report_left"
            right_dir = report_root / "review_report_right"
            left_dir.mkdir(parents=True)
            right_dir.mkdir(parents=True)
            left_payload = {
                "report_id": "review_report_left",
                "name": "Left Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"pass": 1},
                    "changed_family_count_total": 1,
                    "finding_count_total": 0,
                    "high_risk_family_count": 1,
                },
                "entries": [],
                "high_risk_families": [
                    {
                        "family_key": "family_a",
                        "issue_type": "crash",
                        "package_name": "com.example.app",
                        "scenario_name": "monkey",
                        "title": "检测到 Crash",
                        "change_type": "regrouped",
                        "snapshot_count": 1,
                        "total_occurrence_count": 1,
                        "highest_decision": "pass",
                        "sample_snapshot_ids": ["snapshot_a"],
                    }
                ],
                "detail_path": str(left_dir / "report.json"),
                "markdown_path": str(left_dir / "summary.md"),
                "html_path": str(left_dir / "report.html"),
            }
            right_payload = {
                "report_id": "review_report_right",
                "name": "Right Report",
                "created_at": "2025-07-20T10:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 2,
                    "decision_counts": {"conditional_pass": 1, "fail": 1},
                    "changed_family_count_total": 3,
                    "finding_count_total": 1,
                    "high_risk_family_count": 2,
                },
                "entries": [],
                "high_risk_families": [
                    {
                        "family_key": "family_a",
                        "issue_type": "crash",
                        "package_name": "com.example.app",
                        "scenario_name": "monkey",
                        "title": "检测到 Crash",
                        "change_type": "regrouped",
                        "snapshot_count": 2,
                        "total_occurrence_count": 3,
                        "highest_decision": "fail",
                        "sample_snapshot_ids": ["snapshot_b"],
                    },
                    {
                        "family_key": "family_b",
                        "issue_type": "device_offline",
                        "package_name": "com.example.app",
                        "scenario_name": "cold_start_loop",
                        "title": "执行期间设备离线",
                        "change_type": "added",
                        "snapshot_count": 1,
                        "total_occurrence_count": 2,
                        "highest_decision": "conditional_pass",
                        "sample_snapshot_ids": ["snapshot_b"],
                    },
                ],
                "detail_path": str(right_dir / "report.json"),
                "markdown_path": str(right_dir / "summary.md"),
                "html_path": str(right_dir / "report.html"),
            }
            (left_dir / "report.json").write_text(json.dumps(left_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (right_dir / "report.json").write_text(json.dumps(right_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            comparison = report_service.compare_reports(
                name="Review Report Compare",
                created_by="cli",
                left_report_id="review_report_left",
                right_report_id="review_report_right",
            )

            self.assertTrue(Path(comparison.detail_path).exists())
            self.assertTrue(Path(comparison.markdown_path).exists())
            self.assertTrue(Path(comparison.html_path).exists())
            self.assertEqual(comparison.summary["snapshot_count_delta"], 1)
            self.assertIn("left_golden_suite", comparison.summary)
            self.assertIn("right_golden_suite", comparison.summary)
            self.assertEqual(comparison.summary["golden_suite_case_count_total_delta"], 0)
            self.assertEqual(comparison.summary["family_delta_counts"]["changed"], 1)
            self.assertEqual(comparison.summary["family_delta_counts"]["added"], 1)
            self.assertEqual(comparison.family_diffs[0].delta_status, "added")

    def test_set_and_get_baseline_persists_named_pointer(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            report_dir = report_root / "review_report_one"
            report_dir.mkdir(parents=True)
            payload = {
                "report_id": "review_report_one",
                "name": "One Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"conditional_pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/candidate.json"],
                    "baseline_paths": ["config/stability_rules.json"],
                },
                "entries": [],
                "high_risk_families": [],
                "detail_path": str(report_dir / "report.json"),
                "markdown_path": str(report_dir / "summary.md"),
                "html_path": str(report_dir / "report.html"),
            }
            (report_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            baseline = report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_one",
                updated_by="cli",
            )
            loaded = report_service.get_baseline("device_offline_default")
            history = report_service.list_baseline_history("device_offline_default")

            self.assertEqual(baseline.report_id, "review_report_one")
            self.assertEqual(loaded.baseline_key, "device_offline_default")
            self.assertEqual(list(loaded.policy_versions), ["v1"])
            self.assertEqual(list(loaded.candidate_paths), ["/tmp/candidate.json"])
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].report_id, "review_report_one")
            self.assertTrue(Path(baseline.latest_audit_detail_path).exists())
            self.assertTrue(Path(loaded.latest_audit_markdown_path).exists())
            self.assertTrue(Path(loaded.latest_audit_index_path).exists())
            self.assertEqual(loaded.latest_audit_version_count, 1)

    def test_compare_report_against_baseline_uses_latest_accepted_report(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            old_dir = report_root / "review_report_old"
            new_dir = report_root / "review_report_new"
            old_dir.mkdir(parents=True)
            new_dir.mkdir(parents=True)
            old_payload = {
                "report_id": "review_report_old",
                "name": "Old Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"conditional_pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/candidate.json"],
                    "changed_family_count_total": 1,
                    "finding_count_total": 0,
                    "high_risk_family_count": 1,
                },
                "entries": [],
                "high_risk_families": [
                    {
                        "family_key": "family_a",
                        "issue_type": "device_offline",
                        "package_name": "com.example.app",
                        "scenario_name": "cold_start_loop",
                        "title": "执行期间设备离线",
                        "change_type": "fingerprint_changed",
                        "snapshot_count": 1,
                        "total_occurrence_count": 1,
                        "highest_decision": "conditional_pass",
                        "sample_snapshot_ids": ["snapshot_a"],
                    }
                ],
                "detail_path": str(old_dir / "report.json"),
                "markdown_path": str(old_dir / "summary.md"),
                "html_path": str(old_dir / "report.html"),
            }
            new_payload = {
                "report_id": "review_report_new",
                "name": "New Report",
                "created_at": "2025-07-20T10:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 2,
                    "decision_counts": {"conditional_pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/candidate.json"],
                    "changed_family_count_total": 2,
                    "finding_count_total": 0,
                    "high_risk_family_count": 1,
                },
                "entries": [],
                "high_risk_families": [
                    {
                        "family_key": "family_a",
                        "issue_type": "device_offline",
                        "package_name": "com.example.app",
                        "scenario_name": "cold_start_loop",
                        "title": "执行期间设备离线",
                        "change_type": "fingerprint_changed",
                        "snapshot_count": 2,
                        "total_occurrence_count": 3,
                        "highest_decision": "conditional_pass",
                        "sample_snapshot_ids": ["snapshot_b"],
                    }
                ],
                "detail_path": str(new_dir / "report.json"),
                "markdown_path": str(new_dir / "summary.md"),
                "html_path": str(new_dir / "report.html"),
            }
            (old_dir / "report.json").write_text(json.dumps(old_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (new_dir / "report.json").write_text(json.dumps(new_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            comparison = report_service.compare_report_against_baseline(
                name="Against Baseline",
                created_by="cli",
                report_id="review_report_new",
                policy_version="v1",
                candidate_path="/tmp/candidate.json",
            )

            self.assertEqual(comparison.left_report_id, "review_report_old")
            self.assertEqual(comparison.right_report_id, "review_report_new")

    def test_promote_baseline_updates_registry_when_policy_passes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            baseline_dir = report_root / "review_report_baseline"
            candidate_dir = report_root / "review_report_candidate"
            baseline_dir.mkdir(parents=True)
            candidate_dir.mkdir(parents=True)
            baseline_payload = {
                "report_id": "review_report_baseline",
                "name": "Baseline Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"conditional_pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/asl_replay_rules.json"],
                    "baseline_paths": ["config/stability_rules.json"],
                    "changed_family_count_total": 3,
                    "finding_count_total": 1,
                    "high_risk_family_count": 3,
                },
                "entries": [],
                "high_risk_families": [
                    {
                        "family_key": "family_a",
                        "issue_type": "device_offline",
                        "package_name": "com.example.app",
                        "scenario_name": "cold_start_loop",
                        "title": "执行期间设备离线",
                        "change_type": "fingerprint_changed",
                        "snapshot_count": 1,
                        "total_occurrence_count": 1,
                        "highest_decision": "conditional_pass",
                        "sample_snapshot_ids": ["snapshot_a"],
                    }
                ],
                "detail_path": str(baseline_dir / "report.json"),
                "markdown_path": str(baseline_dir / "summary.md"),
                "html_path": str(baseline_dir / "report.html"),
            }
            candidate_payload = {
                **baseline_payload,
                "report_id": "review_report_candidate",
                "name": "Candidate Report",
                "created_at": "2025-07-20T10:00:00",
                "detail_path": str(candidate_dir / "report.json"),
                "markdown_path": str(candidate_dir / "summary.md"),
                "html_path": str(candidate_dir / "report.html"),
            }
            (baseline_dir / "report.json").write_text(json.dumps(baseline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (candidate_dir / "report.json").write_text(json.dumps(candidate_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_baseline",
                updated_by="seed",
            )

            result = report_service.promote_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_candidate",
                updated_by="cli",
                include_unchanged=True,
            )

            self.assertTrue(result.approved)
            self.assertTrue(result.promoted)
            self.assertEqual(result.updated_baseline.report_id, "review_report_candidate")
            self.assertTrue(Path(result.updated_baseline.latest_audit_html_path).exists())
            self.assertEqual(result.updated_baseline.latest_audit_version_count, 2)
            history = report_service.list_baseline_history("device_offline_default")
            self.assertEqual(history[0].report_id, "review_report_candidate")
            self.assertEqual(history[1].report_id, "review_report_baseline")

    def test_promote_baseline_rejects_added_family_delta(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            baseline_dir = report_root / "review_report_baseline"
            candidate_dir = report_root / "review_report_candidate"
            baseline_dir.mkdir(parents=True)
            candidate_dir.mkdir(parents=True)
            baseline_payload = {
                "report_id": "review_report_baseline",
                "name": "Baseline Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/asl_replay_rules.json"],
                    "baseline_paths": ["config/stability_rules.json"],
                    "changed_family_count_total": 0,
                    "finding_count_total": 0,
                    "high_risk_family_count": 0,
                },
                "entries": [],
                "high_risk_families": [],
                "detail_path": str(baseline_dir / "report.json"),
                "markdown_path": str(baseline_dir / "summary.md"),
                "html_path": str(baseline_dir / "report.html"),
            }
            candidate_payload = {
                "report_id": "review_report_candidate",
                "name": "Candidate Report",
                "created_at": "2025-07-20T10:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"conditional_pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/asl_replay_rules.json"],
                    "baseline_paths": ["config/stability_rules.json"],
                    "changed_family_count_total": 1,
                    "finding_count_total": 0,
                    "high_risk_family_count": 1,
                },
                "entries": [],
                "high_risk_families": [
                    {
                        "family_key": "family_a",
                        "issue_type": "device_offline",
                        "package_name": "com.example.app",
                        "scenario_name": "cold_start_loop",
                        "title": "执行期间设备离线",
                        "change_type": "added",
                        "snapshot_count": 1,
                        "total_occurrence_count": 1,
                        "highest_decision": "conditional_pass",
                        "sample_snapshot_ids": ["snapshot_b"],
                    }
                ],
                "detail_path": str(candidate_dir / "report.json"),
                "markdown_path": str(candidate_dir / "summary.md"),
                "html_path": str(candidate_dir / "report.html"),
            }
            (baseline_dir / "report.json").write_text(json.dumps(baseline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (candidate_dir / "report.json").write_text(json.dumps(candidate_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_baseline",
                updated_by="seed",
            )

            result = report_service.promote_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_candidate",
                updated_by="cli",
            )

            self.assertFalse(result.approved)
            self.assertFalse(result.promoted)
            self.assertIn("added", " ".join(result.reasons))

    def test_rollback_baseline_reverts_to_previous_report_and_records_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            baseline_dir = report_root / "review_report_old"
            current_dir = report_root / "review_report_new"
            baseline_dir.mkdir(parents=True)
            current_dir.mkdir(parents=True)
            old_payload = {
                "report_id": "review_report_old",
                "name": "Old Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/asl_replay_rules.json"],
                    "baseline_paths": ["config/stability_rules.json"],
                    "changed_family_count_total": 0,
                    "finding_count_total": 0,
                    "high_risk_family_count": 0,
                },
                "entries": [],
                "high_risk_families": [],
                "detail_path": str(baseline_dir / "report.json"),
                "markdown_path": str(baseline_dir / "summary.md"),
                "html_path": str(baseline_dir / "report.html"),
            }
            new_payload = {
                **old_payload,
                "report_id": "review_report_new",
                "name": "New Report",
                "created_at": "2025-07-20T10:00:00",
                "detail_path": str(current_dir / "report.json"),
                "markdown_path": str(current_dir / "summary.md"),
                "html_path": str(current_dir / "report.html"),
            }
            (baseline_dir / "report.json").write_text(json.dumps(old_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (current_dir / "report.json").write_text(json.dumps(new_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_old",
                updated_by="seed",
            )
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_new",
                updated_by="seed",
            )

            result = report_service.rollback_baseline(
                baseline_key="device_offline_default",
                updated_by="cli",
            )

            self.assertTrue(result.rolled_back)
            self.assertEqual(result.to_report_id, "review_report_old")
            loaded = report_service.get_baseline("device_offline_default")
            self.assertEqual(loaded.report_id, "review_report_old")
            self.assertTrue(Path(loaded.latest_audit_detail_path).exists())
            self.assertTrue(Path(loaded.latest_audit_index_path).exists())
            self.assertEqual(loaded.latest_audit_version_count, 3)
            history = report_service.list_baseline_history("device_offline_default")
            self.assertEqual(history[0].action, "rollback")
            self.assertEqual(history[0].report_id, "review_report_old")
            self.assertEqual(history[1].action, "set")
            index_payload = json.loads(Path(loaded.latest_audit_index_path).read_text(encoding="utf-8"))
            self.assertEqual(index_payload["version_count"], 3)
            self.assertEqual(index_payload["versions"][0]["action"], "rollback")

    def test_create_baseline_audit_report_summarizes_history_transitions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            first_dir = report_root / "review_report_old"
            second_dir = report_root / "review_report_new"
            first_dir.mkdir(parents=True)
            second_dir.mkdir(parents=True)
            old_payload = {
                "report_id": "review_report_old",
                "name": "Old Report",
                "created_at": "2025-07-20T09:00:00",
                "created_by": "tester",
                "filters": {},
                "summary": {
                    "snapshot_count": 1,
                    "decision_counts": {"pass": 1},
                    "policy_versions": ["v1"],
                    "candidate_paths": ["/tmp/asl_replay_rules.json"],
                    "baseline_paths": ["config/stability_rules.json"],
                    "changed_family_count_total": 0,
                    "finding_count_total": 0,
                    "high_risk_family_count": 0,
                },
                "entries": [],
                "high_risk_families": [],
                "detail_path": str(first_dir / "report.json"),
                "markdown_path": str(first_dir / "summary.md"),
                "html_path": str(first_dir / "report.html"),
            }
            new_payload = {
                **old_payload,
                "report_id": "review_report_new",
                "name": "New Report",
                "created_at": "2025-07-20T10:00:00",
                "detail_path": str(second_dir / "report.json"),
                "markdown_path": str(second_dir / "summary.md"),
                "html_path": str(second_dir / "report.html"),
            }
            (first_dir / "report.json").write_text(json.dumps(old_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (second_dir / "report.json").write_text(json.dumps(new_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_old",
                updated_by="seed",
            )
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_new",
                updated_by="reviewer",
                action="promote",
                reasons=("Promotion policy checks passed.",),
                comparison_id="review_report_compare_1",
                comparison_detail_path="runtime/analysis_review_report_comparisons/review_report_compare_1/report.json",
                policy_version="baseline-policy-v1",
            )
            report_service.rollback_baseline(
                baseline_key="device_offline_default",
                updated_by="cli",
            )

            audit = report_service.create_baseline_audit_report(
                baseline_key="device_offline_default",
                name="Baseline Audit",
                created_by="auditor",
            )

            self.assertTrue(Path(audit.detail_path).exists())
            self.assertTrue(Path(audit.markdown_path).exists())
            self.assertTrue(Path(audit.html_path).exists())
            self.assertEqual(audit.summary["history_count"], 3)
            self.assertIn("current_report_golden_suite", audit.summary)
            self.assertEqual(audit.summary["action_counts"]["rollback"], 1)
            self.assertEqual(audit.summary["action_counts"]["promote"], 1)
            self.assertEqual(audit.events[1].from_report_id, "review_report_old")
            self.assertEqual(audit.events[1].to_report_id, "review_report_new")
            self.assertEqual(audit.events[1].comparison_id, "review_report_compare_1")
            self.assertEqual(audit.events[2].reason_summary, "Rolled back baseline to report review_report_old.")

    def test_latest_audit_retention_prunes_old_set_versions_but_keeps_promote(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )
            report_service._latest_audit_max_versions = 2

            def write_report(report_id: str, name: str, created_at: str) -> None:
                report_dir = report_root / report_id
                report_dir.mkdir(parents=True, exist_ok=True)
                payload = {
                    "report_id": report_id,
                    "name": name,
                    "created_at": created_at,
                    "created_by": "tester",
                    "filters": {},
                    "summary": {
                        "snapshot_count": 1,
                        "decision_counts": {"pass": 1},
                        "policy_versions": ["v1"],
                        "candidate_paths": ["/tmp/asl_replay_rules.json"],
                        "baseline_paths": ["config/stability_rules.json"],
                        "changed_family_count_total": 0,
                        "finding_count_total": 0,
                        "high_risk_family_count": 0,
                    },
                    "entries": [],
                    "high_risk_families": [],
                    "detail_path": str(report_dir / "report.json"),
                    "markdown_path": str(report_dir / "summary.md"),
                    "html_path": str(report_dir / "report.html"),
                }
                (report_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            write_report("review_report_one", "One", "2025-07-20T09:00:00")
            write_report("review_report_two", "Two", "2025-07-20T09:10:00")
            write_report("review_report_three", "Three", "2025-07-20T09:20:00")
            write_report("review_report_four", "Four", "2025-07-20T09:30:00")

            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_one",
                updated_by="seed",
            )
            report_service.promote_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_two",
                updated_by="seed",
            )
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_three",
                updated_by="seed",
            )
            loaded = report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_four",
                updated_by="seed",
            )

            self.assertEqual(loaded.latest_audit_version_count, 3)
            index_payload = json.loads(Path(loaded.latest_audit_index_path).read_text(encoding="utf-8"))
            self.assertEqual(index_payload["version_count"], 3)
            self.assertEqual(index_payload["retention"]["max_versions"], 2)
            self.assertEqual(index_payload["retention"]["pruned_count"], 0)
            revision_actions = {item["revision_id"]: item["action"] for item in index_payload["versions"]}
            self.assertIn("promote", revision_actions.values())
            self.assertEqual(sorted(revision_actions.values()), ["promote", "set", "set"])
            detail_paths = [Path(item["detail_path"]) for item in index_payload["versions"]]
            for path in detail_paths:
                self.assertTrue(path.exists())
            versions_dir = Path(loaded.latest_audit_index_path).parent / "versions"
            version_dirs = sorted(path.name for path in versions_dir.iterdir() if path.is_dir())
            self.assertEqual(len(version_dirs), 3)

    def test_show_latest_baseline_audit_returns_summary_and_recent_versions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            report_root = root_dir / "review_reports"
            report_service = RuleReviewReportService(
                root_dir=report_root,
                snapshot_service=build_snapshot_service_fixture(root_dir),
            )

            def write_report(report_id: str, name: str, created_at: str) -> None:
                report_dir = report_root / report_id
                report_dir.mkdir(parents=True, exist_ok=True)
                payload = {
                    "report_id": report_id,
                    "name": name,
                    "created_at": created_at,
                    "created_by": "tester",
                    "filters": {},
                    "summary": {
                        "snapshot_count": 1,
                        "decision_counts": {"pass": 1},
                        "policy_versions": ["v1"],
                        "candidate_paths": ["/tmp/asl_replay_rules.json"],
                        "baseline_paths": ["config/stability_rules.json"],
                        "changed_family_count_total": 0,
                        "finding_count_total": 0,
                        "high_risk_family_count": 0,
                    },
                    "entries": [],
                    "high_risk_families": [],
                    "detail_path": str(report_dir / "report.json"),
                    "markdown_path": str(report_dir / "summary.md"),
                    "html_path": str(report_dir / "report.html"),
                }
                (report_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            write_report("review_report_one", "One", "2025-07-20T09:00:00")
            write_report("review_report_two", "Two", "2025-07-20T09:10:00")
            write_report("review_report_three", "Three", "2025-07-20T09:20:00")

            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_one",
                updated_by="seed",
            )
            report_service.promote_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_two",
                updated_by="seed",
            )
            report_service.set_baseline(
                baseline_key="device_offline_default",
                report_id="review_report_three",
                updated_by="seed",
            )

            view = report_service.show_latest_baseline_audit(
                baseline_key="device_offline_default",
                version_limit=2,
            )

            self.assertEqual(view.baseline.baseline_key, "device_offline_default")
            self.assertEqual(view.version_count, 3)
            self.assertIn("current_report_golden_suite", view.summary)
            self.assertEqual(len(view.versions), 2)
            self.assertEqual(view.versions[0].action, "set")
            self.assertTrue(Path(view.index_path).exists())


if __name__ == "__main__":
    unittest.main()
