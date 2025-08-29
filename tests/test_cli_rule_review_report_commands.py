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


class CLIRuleReviewReportCommandsTest(unittest.TestCase):
    def test_review_analysis_rules_outputs_decision(self) -> None:
        bundle = SimpleNamespace(
            rule_review_service=SimpleNamespace(
                review_rule_change=lambda **kwargs: SimpleNamespace(
                    decision="conditional_pass",
                    policy_version="review-v1",
                    policy_path="config/rule_review_policy.json",
                    baseline_path="config/stability_rules.json",
                    candidate_path=kwargs["candidate_path"],
                    baseline_rule_version="v1",
                    candidate_rule_version="v2",
                    filters={"package_name": kwargs.get("package_name", "")},
                    family_count=2,
                    changed_family_count=1,
                    change_summary={"fingerprint_changed": 1},
                    issue_type_change_summary={"device_offline": {"fingerprint_changed": 1}},
                    findings=(
                        SimpleNamespace(
                            level="warning",
                            scope="global",
                            issue_type="",
                            change_type="fingerprint_changed",
                            observed_count=1,
                            threshold=1,
                            message="warning message",
                        ),
                    ),
                    reasons=("warning message",),
                    baseline_valid=True,
                    candidate_valid=True,
                    baseline_errors=(),
                    candidate_errors=(),
                    golden_suite=SimpleNamespace(
                        suite_path="config/rule_replay_golden_samples.json",
                        suite_version="v2",
                        case_count=4,
                        passed_case_count=4,
                        failed_case_count=0,
                        layer_summaries={
                            "merge_semantics": {
                                "case_count": 4,
                                "passed_case_count": 4,
                                "failed_case_count": 0,
                            }
                        },
                        cases=(),
                    ),
                    families=(),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "review-analysis-rules",
                "--candidate-path",
                "candidate.json",
                "--package-name",
                "com.example.app",
            ],
            bundle,
        )

        self.assertEqual(payload["review"]["decision"], "conditional_pass")
        self.assertEqual(payload["review"]["policy_version"], "review-v1")
        self.assertEqual(payload["review"]["change_summary"]["fingerprint_changed"], 1)
        self.assertTrue(payload["review"]["golden_suite"]["passed"])
        self.assertEqual(
            payload["review"]["golden_suite"]["layer_summaries"]["merge_semantics"]["passed_case_count"],
            4,
        )

    def test_review_analysis_rules_forwards_optional_performance_scope(self) -> None:
        captured: dict[str, object] = {}

        def _review_rule_change(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                decision="pass",
                policy_version="review-v1",
                policy_path="config/rule_review_policy.json",
                baseline_path="config/stability_rules.json",
                candidate_path=kwargs["candidate_path"],
                baseline_rule_version="v1",
                candidate_rule_version="v2",
                filters={},
                family_count=1,
                changed_family_count=0,
                change_summary={},
                issue_type_change_summary={},
                findings=(),
                reasons=("ok",),
                baseline_valid=True,
                candidate_valid=True,
                baseline_errors=(),
                candidate_errors=(),
                golden_suite=None,
                performance_summary={"dimension": kwargs.get("dimension", "")},
                performance_risk_items=(),
                families=(),
            )

        bundle = SimpleNamespace(rule_review_service=SimpleNamespace(review_rule_change=_review_rule_change))

        payload = self._run_main_with_bundle(
            [
                "review-analysis-rules",
                "--candidate-path",
                "candidate.json",
                "--dimension",
                "version",
                "--left-value",
                "1.0.0(100)",
                "--right-value",
                "2.0.0(200)",
            ],
            bundle,
        )

        self.assertEqual(captured["dimension"], "version")
        self.assertEqual(captured["left_value"], "1.0.0(100)")
        self.assertEqual(captured["right_value"], "2.0.0(200)")
        self.assertEqual(payload["review"]["performance_summary"]["dimension"], "version")

    def test_create_rule_review_report_outputs_report_paths(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                create_report=lambda **kwargs: SimpleNamespace(
                    report_id="review_report_1",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    filters={"snapshot_created_by": kwargs.get("snapshot_created_by", "")},
                    summary={
                        "snapshot_count": 2,
                        "decision_counts": {"conditional_pass": 1, "fail": 1},
                        "golden_suite_case_count_total": 8,
                        "golden_suite_passed_case_count_total": 8,
                        "golden_suite_failed_case_count_total": 0,
                    },
                    entries=(
                        SimpleNamespace(
                            snapshot_id="snapshot_a",
                            name="Review A",
                            created_at=None,
                            created_by="tester",
                            decision="fail",
                            policy_version="review-v1",
                            baseline_path="config/stability_rules.json",
                            candidate_path="candidate_a.json",
                            changed_family_count=2,
                            finding_count=1,
                            change_summary={"regrouped": 1},
                            reasons=("failed",),
                            golden_suite_passed=True,
                            golden_suite_case_count=4,
                            golden_suite_passed_case_count=4,
                            golden_suite_failed_case_count=0,
                            golden_suite_version="golden-v1",
                            golden_suite_suite_path="config/rule_replay_golden_samples.json",
                            detail_path="runtime/analysis_snapshots/snapshot_a/snapshot.json",
                            markdown_path="runtime/analysis_snapshots/snapshot_a/summary.md",
                        ),
                    ),
                    high_risk_families=(
                        SimpleNamespace(
                            family_key="family_a",
                            issue_type="crash",
                            package_name="com.example.app",
                            scenario_name="monkey",
                            title="检测到 Crash",
                            change_type="regrouped",
                            snapshot_count=1,
                            total_occurrence_count=2,
                            highest_decision="fail",
                            sample_snapshot_ids=("snapshot_a",),
                        ),
                    ),
                    detail_path="runtime/analysis_review_reports/review_report_1/report.json",
                    markdown_path="runtime/analysis_review_reports/review_report_1/summary.md",
                    html_path="runtime/analysis_review_reports/review_report_1/report.html",
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "create-rule-review-report",
                "--name",
                "Review Report",
                "--snapshot-created-by",
                "tester",
            ],
            bundle,
        )

        self.assertEqual(payload["report"]["report_id"], "review_report_1")
        self.assertEqual(payload["report"]["summary"]["snapshot_count"], 2)
        self.assertEqual(payload["report"]["summary"]["golden_suite_case_count_total"], 8)
        self.assertEqual(payload["report"]["entries"][0]["decision"], "fail")
        self.assertTrue(payload["report"]["entries"][0]["golden_suite_passed"])
        self.assertEqual(payload["report"]["high_risk_families"][0]["change_type"], "regrouped")

    def test_compare_rule_review_reports_outputs_comparison_paths(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                compare_reports=lambda **kwargs: SimpleNamespace(
                    comparison_id="review_report_compare_1",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    left_report_id=kwargs["left_report_id"],
                    right_report_id=kwargs["right_report_id"],
                    left_report_name="Left Report",
                    right_report_name="Right Report",
                    left_detail_path="runtime/analysis_review_reports/review_report_left/report.json",
                    right_detail_path="runtime/analysis_review_reports/review_report_right/report.json",
                    summary={
                        "snapshot_count_delta": 1,
                        "decision_count_deltas": {"fail": 1},
                        "left_golden_suite": {"case_count_total": 4, "failed_case_count_total": 0},
                        "right_golden_suite": {"case_count_total": 4, "failed_case_count_total": 1},
                        "golden_suite_failed_case_count_total_delta": 1,
                        "family_delta_counts": {"added": 1, "changed": 1},
                    },
                    family_diffs=(
                        SimpleNamespace(
                            family_key="family_a",
                            issue_type="crash",
                            package_name="com.example.app",
                            scenario_name="monkey",
                            title="检测到 Crash",
                            change_type="regrouped",
                            delta_status="changed",
                            left_snapshot_count=1,
                            right_snapshot_count=2,
                            left_total_occurrence_count=1,
                            right_total_occurrence_count=3,
                            left_highest_decision="pass",
                            right_highest_decision="fail",
                        ),
                    ),
                    detail_path="runtime/analysis_review_report_comparisons/review_report_compare_1/report.json",
                    markdown_path="runtime/analysis_review_report_comparisons/review_report_compare_1/summary.md",
                    html_path="runtime/analysis_review_report_comparisons/review_report_compare_1/report.html",
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "compare-rule-review-reports",
                "--name",
                "Review Compare",
                "--left-report-id",
                "review_report_left",
                "--right-report-id",
                "review_report_right",
            ],
            bundle,
        )

        self.assertEqual(payload["comparison"]["comparison_id"], "review_report_compare_1")
        self.assertEqual(payload["comparison"]["summary"]["snapshot_count_delta"], 1)
        self.assertEqual(payload["comparison"]["summary"]["right_golden_suite"]["failed_case_count_total"], 1)
        self.assertEqual(payload["comparison"]["family_diffs"][0]["delta_status"], "changed")

    def test_set_rule_review_report_baseline_outputs_baseline_payload(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                set_baseline=lambda **kwargs: SimpleNamespace(
                    baseline_key=kwargs["baseline_key"],
                    report_id=kwargs["report_id"],
                    report_name="Review Report",
                    policy_versions=("v1",),
                    candidate_paths=("candidate.json",),
                    baseline_paths=("config/stability_rules.json",),
                    report_created_at="2025-07-20T10:00:00",
                    created_at=None,
                    updated_at=None,
                    updated_by=kwargs["updated_by"],
                    latest_audit_id="baseline_audit_latest_device_offline_default",
                    latest_audit_detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
                    latest_audit_markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
                    latest_audit_html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
                    latest_audit_index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
                    latest_audit_version_count=1,
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "set-rule-review-report-baseline",
                "--baseline-key",
                "device_offline_default",
                "--report-id",
                "review_report_1",
            ],
            bundle,
        )

        self.assertEqual(payload["baseline"]["baseline_key"], "device_offline_default")
        self.assertEqual(payload["baseline"]["report_id"], "review_report_1")
        self.assertEqual(payload["baseline"]["report_created_at"], "2025-07-20 18:00:00.000000")
        self.assertEqual(payload["baseline"]["latest_audit_id"], "baseline_audit_latest_device_offline_default")
        self.assertEqual(payload["baseline"]["latest_audit_version_count"], 1)

    def test_compare_rule_review_report_against_baseline_outputs_comparison_paths(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                compare_report_against_baseline=lambda **kwargs: SimpleNamespace(
                    comparison_id="review_report_compare_2",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    left_report_id="review_report_baseline",
                    right_report_id=kwargs["report_id"],
                    left_report_name="Baseline Report",
                    right_report_name="Current Report",
                    left_detail_path="runtime/analysis_review_reports/review_report_baseline/report.json",
                    right_detail_path="runtime/analysis_review_reports/review_report_current/report.json",
                    summary={"snapshot_count_delta": 0, "family_delta_counts": {"unchanged": 1}},
                    family_diffs=(),
                    detail_path="runtime/analysis_review_report_comparisons/review_report_compare_2/report.json",
                    markdown_path="runtime/analysis_review_report_comparisons/review_report_compare_2/summary.md",
                    html_path="runtime/analysis_review_report_comparisons/review_report_compare_2/report.html",
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "compare-rule-review-report-against-baseline",
                "--name",
                "Against Baseline",
                "--report-id",
                "review_report_current",
                "--baseline-key",
                "device_offline_default",
            ],
            bundle,
        )

        self.assertEqual(payload["comparison"]["comparison_id"], "review_report_compare_2")
        self.assertEqual(payload["comparison"]["left_report_id"], "review_report_baseline")

    def test_promote_rule_review_report_baseline_outputs_promotion_payload(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                promote_baseline=lambda **kwargs: SimpleNamespace(
                    baseline_key=kwargs["baseline_key"],
                    target_report_id=kwargs["report_id"],
                    target_report_name="Current Report",
                    baseline_report_id="review_report_baseline",
                    baseline_report_name="Baseline Report",
                    policy_version="v1",
                    approved=True,
                    promoted=True,
                    reasons=("Promotion policy checks passed.",),
                    comparison_id="review_report_compare_3",
                    comparison_detail_path="runtime/analysis_review_report_comparisons/review_report_compare_3/report.json",
                    target_golden_suite={
                        "snapshot_count": 2,
                        "passed_snapshot_count": 2,
                        "failed_snapshot_count": 0,
                        "case_count_total": 8,
                        "passed_case_count_total": 8,
                        "failed_case_count_total": 0,
                    },
                    baseline_golden_suite={
                        "snapshot_count": 2,
                        "passed_snapshot_count": 2,
                        "failed_snapshot_count": 0,
                        "case_count_total": 8,
                        "passed_case_count_total": 8,
                        "failed_case_count_total": 0,
                    },
                    updated_baseline=SimpleNamespace(
                        baseline_key=kwargs["baseline_key"],
                        report_id=kwargs["report_id"],
                        report_name="Current Report",
                        policy_versions=("v1",),
                        candidate_paths=("candidate.json",),
                        baseline_paths=("config/stability_rules.json",),
                        report_created_at="2025-07-20T10:00:00",
                        created_at=None,
                        updated_at=None,
                        updated_by=kwargs["updated_by"],
                        latest_audit_id="baseline_audit_latest_device_offline_default",
                        latest_audit_detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
                        latest_audit_markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
                        latest_audit_html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
                        latest_audit_index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
                        latest_audit_version_count=2,
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "promote-rule-review-report-baseline",
                "--baseline-key",
                "device_offline_default",
                "--report-id",
                "review_report_current",
            ],
            bundle,
        )

        self.assertTrue(payload["promotion"]["approved"])
        self.assertEqual(payload["promotion"]["target_golden_suite"]["case_count_total"], 8)
        self.assertEqual(payload["promotion"]["baseline_golden_suite"]["failed_case_count_total"], 0)
        self.assertEqual(payload["promotion"]["updated_baseline"]["report_id"], "review_report_current")
        self.assertEqual(
            payload["promotion"]["updated_baseline"]["latest_audit_detail_path"],
            "runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
        )
        self.assertEqual(payload["promotion"]["updated_baseline"]["latest_audit_version_count"], 2)

    def test_list_rule_review_report_baseline_history_outputs_history_rows(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                list_baseline_history=lambda baseline_key: (
                    SimpleNamespace(
                        revision_id="baseline_rev_1",
                        report_id="review_report_1",
                        report_name="Review Report 1",
                        policy_versions=("v1",),
                        candidate_paths=("candidate.json",),
                        baseline_paths=("config/stability_rules.json",),
                        report_created_at="2025-07-20T10:00:00",
                        changed_at=None,
                        changed_by="cli",
                        action="set",
                        reasons=("Baseline pointer was updated manually.",),
                        comparison_id="",
                        comparison_detail_path="",
                        policy_version="",
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "list-rule-review-report-baseline-history",
                "--baseline-key",
                "device_offline_default",
            ],
            bundle,
        )

        self.assertEqual(payload["history_count"], 1)
        self.assertEqual(payload["history"][0]["report_id"], "review_report_1")

    def test_rollback_rule_review_report_baseline_outputs_rollback_payload(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                rollback_baseline=lambda **kwargs: SimpleNamespace(
                    baseline_key=kwargs["baseline_key"],
                    from_report_id="review_report_current",
                    from_report_name="Current Report",
                    to_report_id="review_report_previous",
                    to_report_name="Previous Report",
                    rolled_back=True,
                    reasons=("Rolled back baseline to report review_report_previous.",),
                    updated_baseline=SimpleNamespace(
                        baseline_key=kwargs["baseline_key"],
                        report_id="review_report_previous",
                        report_name="Previous Report",
                        policy_versions=("v1",),
                        candidate_paths=("candidate.json",),
                        baseline_paths=("config/stability_rules.json",),
                        report_created_at="2025-07-20T09:00:00",
                        created_at=None,
                        updated_at=None,
                        updated_by=kwargs["updated_by"],
                        latest_audit_id="baseline_audit_latest_device_offline_default",
                        latest_audit_detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
                        latest_audit_markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
                        latest_audit_html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
                        latest_audit_index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
                        latest_audit_version_count=3,
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "rollback-rule-review-report-baseline",
                "--baseline-key",
                "device_offline_default",
            ],
            bundle,
        )

        self.assertTrue(payload["rollback"]["rolled_back"])
        self.assertEqual(payload["rollback"]["to_report_id"], "review_report_previous")
        self.assertEqual(
            payload["rollback"]["updated_baseline"]["latest_audit_html_path"],
            "runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
        )
        self.assertEqual(payload["rollback"]["updated_baseline"]["latest_audit_version_count"], 3)

    def test_create_rule_review_report_baseline_audit_outputs_paths(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                create_baseline_audit_report=lambda **kwargs: SimpleNamespace(
                    audit_id="baseline_audit_1",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    baseline_key=kwargs["baseline_key"],
                    current_report_id="review_report_previous",
                    current_report_name="Previous Report",
                    summary={
                        "history_count": 3,
                        "action_counts": {"set": 1, "promote": 1, "rollback": 1},
                        "current_report_golden_suite": {
                            "snapshot_count": 1,
                            "passed_snapshot_count": 1,
                            "failed_snapshot_count": 0,
                            "case_count_total": 4,
                            "passed_case_count_total": 4,
                            "failed_case_count_total": 0,
                        },
                    },
                    events=(
                        SimpleNamespace(
                            revision_id="baseline_rev_3",
                            action="rollback",
                            changed_at=None,
                            changed_by="cli",
                            from_report_id="review_report_current",
                            from_report_name="Current Report",
                            to_report_id="review_report_previous",
                            to_report_name="Previous Report",
                            reason_summary="Rolled back baseline to report review_report_previous.",
                            reasons=("Rolled back baseline to report review_report_previous.",),
                            comparison_id="",
                            comparison_detail_path="",
                            policy_version="",
                        ),
                    ),
                    detail_path="runtime/analysis_review_report_baseline_audits/baseline_audit_1/report.json",
                    markdown_path="runtime/analysis_review_report_baseline_audits/baseline_audit_1/summary.md",
                    html_path="runtime/analysis_review_report_baseline_audits/baseline_audit_1/report.html",
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "create-rule-review-report-baseline-audit",
                "--baseline-key",
                "device_offline_default",
                "--name",
                "Baseline Audit",
            ],
            bundle,
        )

        self.assertEqual(payload["audit"]["audit_id"], "baseline_audit_1")
        self.assertEqual(payload["audit"]["summary"]["history_count"], 3)
        self.assertEqual(payload["audit"]["summary"]["current_report_golden_suite"]["case_count_total"], 4)
        self.assertEqual(payload["audit"]["events"][0]["action"], "rollback")

    def test_show_rule_review_report_baseline_audit_outputs_latest_summary(self) -> None:
        bundle = SimpleNamespace(
            rule_review_report_service=SimpleNamespace(
                show_latest_baseline_audit=lambda **kwargs: SimpleNamespace(
                    baseline=SimpleNamespace(
                        baseline_key=kwargs["baseline_key"],
                        report_id="review_report_current",
                        report_name="Current Report",
                        policy_versions=("v1",),
                        candidate_paths=("candidate.json",),
                        baseline_paths=("config/stability_rules.json",),
                        report_created_at="2025-07-20T10:00:00",
                        created_at=None,
                        updated_at=None,
                        updated_by="cli",
                        latest_audit_id="baseline_audit_latest_device_offline_default",
                        latest_audit_detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
                        latest_audit_markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
                        latest_audit_html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
                        latest_audit_index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
                        latest_audit_version_count=3,
                    ),
                    audit_id="baseline_audit_latest_device_offline_default",
                    audit_name="Baseline Audit Latest | device_offline_default",
                    created_at=None,
                    created_by="cli",
                    summary={
                        "history_count": 3,
                        "current_report_golden_suite": {
                            "snapshot_count": 1,
                            "passed_snapshot_count": 1,
                            "failed_snapshot_count": 0,
                            "case_count_total": 4,
                            "passed_case_count_total": 4,
                            "failed_case_count_total": 0,
                        },
                    },
                    retention={"max_versions": 10, "preserve_actions": ["promote", "rollback"]},
                    version_count=3,
                    versions=(
                        SimpleNamespace(
                            revision_id="baseline_rev_3",
                            action="rollback",
                            changed_at=None,
                            changed_by="cli",
                            report_id="review_report_previous",
                            report_name="Previous Report",
                            audit_id="baseline_audit_latest_device_offline_default",
                            summary={"history_count": 3},
                            detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/versions/baseline_rev_3/report.json",
                            markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/versions/baseline_rev_3/summary.md",
                            html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/versions/baseline_rev_3/report.html",
                        ),
                    ),
                    detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
                    markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
                    html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
                    index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "show-rule-review-report-baseline-audit",
                "--baseline-key",
                "device_offline_default",
                "--limit",
                "3",
            ],
            bundle,
        )

        self.assertEqual(payload["audit"]["audit_id"], "baseline_audit_latest_device_offline_default")
        self.assertEqual(payload["audit"]["retention"]["max_versions"], 10)
        self.assertEqual(payload["audit"]["summary"]["current_report_golden_suite"]["case_count_total"], 4)
        self.assertEqual(payload["audit"]["versions"][0]["action"], "rollback")

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
