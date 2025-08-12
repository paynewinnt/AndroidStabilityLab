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
from stability.app.admission_case_contract_payload import (
    admission_case_contract_payload,
    admission_case_list_contract_payload,
)
from stability.domain import (
    AdmissionCase,
    AdmissionCaseExecutionSummary,
    AdmissionCaseRegressionSummary,
    AdmissionCaseScenarioCoverage,
    AdmissionCaseTopIssue,
    QualityGateRiskItem,
)
from tests.helpers.cli import run_main_with_bundle


class CLIAdmissionRuleReplayCommandsTest(unittest.TestCase):
    def test_list_admission_cases_outputs_stable_contract(self) -> None:
        case = AdmissionCase(
            contract_version="admission_case.v1",
            case_id="admission_case:baseline_1:review_1",
            baseline_key="baseline_1",
            report_id="review_1",
            report_name="Baseline 1",
            status="reviewing",
            revision=3,
            assignee_id="qa",
            assignee_display_name="QA",
            final_reviewer_id="owner",
            final_reviewer_display_name="Owner",
            created_at=None,
            updated_at=None,
            updated_by="cli",
            final_review_opinion="needs_follow_up",
            final_decision="conditional_pass",
            error_code="CONDITIONAL_PASS",
            filters={"task_id": "task-1"},
            case_trace={"decision": {"final_decision": "conditional_pass"}},
            report_summary={"snapshot_count": 2},
            latest_audit_summary={"version_count": 1},
            source_links={"report_detail_path": "runtime/report.json"},
            source_refs={"report": {"report_id": "review_1"}},
            ci_contract={"contract_version": "admission_case.v1"},
            execution_summary=AdmissionCaseExecutionSummary(
                total_runs=2,
                status_counts={"failed": 1},
                failed_run_count=1,
                issue_run_count=1,
                task_ids=("task-1",),
                task_names=("Task 1",),
                package_names=("com.example.app",),
                template_types=("cold_start_loop",),
                device_ids=("device-1",),
                latest_run_id="run-1",
                latest_run_status="failed",
                latest_run_created_at=None,
                recent_runs=({"run_id": "run-1"},),
            ),
            regression_summary=AdmissionCaseRegressionSummary(
                available=True,
                dimension="version",
                overall_result="suspected_regression",
                issue_result_summary={"startup_timeout": 1},
                metric_result_summary={"cpu": "warning"},
                reasons=("delta",),
                comparability_notes=("same device",),
                source_filters={"task_id": "task-1"},
            ),
            scenario_coverage=AdmissionCaseScenarioCoverage(
                scenario_count=1,
                scenarios=("cold_start_loop",),
                issue_scenario_count=1,
                issue_scenarios=("cold_start_loop",),
                coverage_state="covered",
                notes=("ok",),
            ),
            top_issues=(
                AdmissionCaseTopIssue(
                    fingerprint="ifp-1",
                    title="Startup timeout",
                    issue_type="startup_timeout",
                    severity="high",
                    occurrence_count=2,
                    affected_run_count=1,
                    affected_device_count=1,
                    affected_scenario_count=1,
                    last_seen_at=None,
                    affected_scenarios=("cold_start_loop",),
                    affected_versions=("1.0.0",),
                ),
            ),
            performance_risk_items=(
                QualityGateRiskItem(
                    risk_key="cpu_regression",
                    category="performance",
                    severity="warning",
                    summary="CPU delta",
                    details={
                        "delta_percent": 12.5,
                        "threshold": 10.0,
                        "threshold_source": "performance_thresholds.version",
                        "matched_scope": {"package_name": "com.example.app", "metric_key": "cpu_usage"},
                        "threshold_detail": {"metric_key": "cpu_usage", "max_delta_percent": 10.0},
                    },
                ),
            ),
        )
        bundle = SimpleNamespace(
            admission_case_service=SimpleNamespace(
                list_admission_case_payloads=lambda limit=20: admission_case_list_contract_payload([case][:limit])
            )
        )

        payload = self._run_main_with_bundle(["list-admission-cases", "--limit", "5"], bundle)

        self.assertEqual(payload["storage_mode"], "persistent")
        self.assertEqual(payload["admission_cases"]["count"], 1)
        entry = payload["admission_cases"]["entries"][0]
        self.assertEqual(entry["contract_version"], "admission_case.v1")
        self.assertEqual(entry["status"], "reviewing")
        self.assertEqual(entry["revision"], 3)
        self.assertEqual(entry["source_refs"]["report"]["report_id"], "review_1")
        self.assertEqual(entry["ci_contract"]["contract_version"], "admission_case.v1")
        evidence = entry["evidence_blocks"]
        self.assertEqual(evidence["execution_summary"]["total_runs"], 2)
        self.assertEqual(evidence["regression_summary"]["overall_result"], "suspected_regression")
        self.assertEqual(evidence["scenario_coverage"]["coverage_state"], "covered")
        self.assertEqual(len(evidence["top_issues"]), 1)
        self.assertEqual(len(evidence["performance_risk_items"]), 1)
        risk_details = evidence["performance_risk_items"][0]["details"]
        self.assertEqual(risk_details["threshold_source"], "performance_thresholds.version")
        self.assertEqual(risk_details["matched_scope"]["metric_key"], "cpu_usage")
        self.assertEqual(risk_details["threshold_detail"]["max_delta_percent"], 10.0)

    def test_show_admission_case_outputs_stable_contract(self) -> None:
        case = AdmissionCase(
            contract_version="admission_case.v1",
            case_id="admission_case:baseline_1:review_1",
            baseline_key="baseline_1",
            report_id="review_1",
            report_name="Baseline 1",
            status="open",
            revision=1,
            assignee_id="",
            assignee_display_name="",
            final_reviewer_id="reviewer",
            final_reviewer_display_name="Reviewer",
            created_at=None,
            updated_at=None,
            updated_by="cli",
            final_review_opinion="",
            final_decision="pass",
            error_code="PASS",
            filters={"task_id": "task-1"},
            case_trace={"evidence": {"top_issue_count": 1}},
            report_summary={"snapshot_count": 1},
            latest_audit_summary={"version_count": 2},
            source_links={},
            source_refs={"baseline": {"baseline_key": "baseline_1"}},
            ci_contract={"contract_version": "admission_case.v1", "case_id": "admission_case:baseline_1:review_1"},
            execution_summary=AdmissionCaseExecutionSummary(),
            regression_summary=AdmissionCaseRegressionSummary(),
            scenario_coverage=AdmissionCaseScenarioCoverage(),
            top_issues=(),
            performance_risk_items=(),
        )
        bundle = SimpleNamespace(
            admission_case_service=SimpleNamespace(
                export_admission_case_payload=lambda baseline_key: (
                    admission_case_contract_payload(case)
                    if baseline_key == "baseline_1"
                    else (_ for _ in ()).throw(ValueError(baseline_key))
                )
            )
        )

        payload = self._run_main_with_bundle(["show-admission-case", "--baseline-key", "baseline_1"], bundle)

        entry = payload["admission_case"]
        self.assertEqual(payload["storage_mode"], "persistent")
        self.assertEqual(entry["case_id"], "admission_case:baseline_1:review_1")
        self.assertEqual(entry["final_decision"], "pass")
        self.assertEqual(entry["error_code"], "PASS")
        self.assertEqual(entry["source_refs"]["baseline"]["baseline_key"], "baseline_1")
        self.assertEqual(entry["ci_contract"]["case_id"], "admission_case:baseline_1:review_1")
        self.assertEqual(entry["evidence_blocks"]["top_issues"], [])

    def test_show_admission_report_prefers_service_payload_method(self) -> None:
        calls: list[str] = []
        service = SimpleNamespace(
            build_admission_report_payload=lambda baseline_key: calls.append(baseline_key) or SimpleNamespace(
                report_contract_version="admission_report.v1",
                report_id="review_1",
                baseline_key=baseline_key,
                status="open",
                final_decision="conditional_pass",
                risk_level="high",
                quality_gate_summary={"final_decision": "conditional_pass"},
                top_issue_summary={"count": 1, "items": [{"title": "Startup timeout"}]},
                performance_risk_summary={"count": 1, "items": [{"risk_key": "cpu_regression"}]},
                manual_overrides={"has_override": False},
                collaboration_summary={"assignee_id": "qa"},
                external_sync_summary={"ci_contract": {"contract_version": "admission_case.v1"}},
                evidence_refs={"report": {"report_id": "review_1"}},
                source_refs={"latest_audit": {"available": True}},
                recommended_actions=("Review top issues.",),
                generated_at=None,
            ),
            get_case=lambda baseline_key: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            ["show-admission-report", "--baseline-key", "baseline_1"],
            SimpleNamespace(admission_case_service=service),
        )

        self.assertEqual(calls, ["baseline_1"])
        report = payload["formal_report"]
        self.assertEqual(payload["storage_mode"], "persistent")
        self.assertEqual(report["source"], "service")
        self.assertEqual(report["report_contract_version"], "admission_report.v1")
        self.assertEqual(report["baseline_key"], "baseline_1")
        self.assertEqual(report["final_decision"], "conditional_pass")
        self.assertEqual(report["risk_level"], "high")
        self.assertEqual(report["top_issue_summary"]["count"], 1)
        self.assertEqual(report["performance_risk_summary"]["count"], 1)
        self.assertEqual(report["external_sync_summary"]["ci_contract"]["contract_version"], "admission_case.v1")
        self.assertEqual(report["evidence_refs"]["report"]["report_id"], "review_1")

    def test_show_admission_report_prefers_export_payload_method(self) -> None:
        calls: list[str] = []
        service = SimpleNamespace(
            export_admission_report_payload=lambda baseline_key: calls.append(baseline_key) or {
                "report_contract_version": "admission_report.v1",
                "report_id": "export_report_1",
                "baseline_key": baseline_key,
                "final_decision": "pass",
                "risk_level": "low",
                "recommended_actions": ("Continue release.",),
            },
            get_case=lambda baseline_key: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            ["show-admission-report", "--baseline-key", "baseline_1"],
            SimpleNamespace(admission_case_service=service),
        )

        self.assertEqual(calls, ["baseline_1"])
        report = payload["formal_report"]
        self.assertEqual(report["source"], "service")
        self.assertEqual(report["report_id"], "export_report_1")
        self.assertEqual(report["baseline_key"], "baseline_1")
        self.assertEqual(report["recommended_actions"], ["Continue release."])

    def test_show_admission_report_supports_build_report_dataclass(self) -> None:
        @dataclass
        class ReportPayload:
            report_contract_version: str
            report_id: str
            baseline_key: str
            final_decision: str
            risk_level: str
            generated_at: datetime

        calls: list[str] = []
        service = SimpleNamespace(
            build_admission_report=lambda baseline_key: calls.append(baseline_key) or ReportPayload(
                report_contract_version="admission_report.v1",
                report_id="build_report_1",
                baseline_key=baseline_key,
                final_decision="conditional_pass",
                risk_level="medium",
                generated_at=datetime(2025, 7, 24, 9, 30, 0),
            ),
            get_case=lambda baseline_key: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )

        payload = self._run_main_with_bundle(
            ["show-admission-report", "--baseline-key", "baseline_1"],
            SimpleNamespace(admission_case_service=service),
        )

        self.assertEqual(calls, ["baseline_1"])
        report = payload["formal_report"]
        self.assertEqual(report["source"], "service")
        self.assertEqual(report["report_id"], "build_report_1")
        self.assertEqual(report["baseline_key"], "baseline_1")
        self.assertEqual(report["generated_at"], "2025-07-24 17:30:00.000000")

    def test_replay_analysis_rules_outputs_family_diffs(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_service=SimpleNamespace(
                replay_top_issues=lambda **kwargs: SimpleNamespace(
                    baseline=SimpleNamespace(path="baseline.json", fingerprint_rule_version="v1"),
                    candidate=SimpleNamespace(path="candidate.json", fingerprint_rule_version="v2"),
                    filters={"package_name": "com.example.app"},
                    family_count=2,
                    changed_family_count=1,
                    change_summary={"regrouped": 1},
                    families=(
                        SimpleNamespace(
                            comparison_key='{"issue_type":"crash"}',
                            issue_type="crash",
                            package_name="com.example.app",
                            process_name="com.example.app",
                            scenario_name="monkey",
                            title="检测到 Crash",
                            change_type="regrouped",
                            left_group_count=2,
                            right_group_count=1,
                            left_occurrence_count=2,
                            right_occurrence_count=2,
                            left_fingerprints=("ifp_a", "ifp_b"),
                            right_fingerprints=("ifp_merged",),
                            left_sample_event_ids=("issue-a",),
                            right_sample_event_ids=("issue-a", "issue-b"),
                            notes=("The candidate rule merged this issue family.",),
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "replay-analysis-rules",
                "--candidate-path",
                "candidate.json",
                "--package-name",
                "com.example.app",
            ],
            bundle,
        )

        self.assertEqual(payload["replay"]["baseline"]["fingerprint_rule_version"], "v1")
        self.assertEqual(payload["replay"]["candidate"]["fingerprint_rule_version"], "v2")
        self.assertEqual(payload["replay"]["changed_family_count"], 1)
        self.assertEqual(payload["replay"]["families"][0]["change_type"], "regrouped")

    def test_verify_rule_replay_golden_samples_outputs_suite_summary(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_acceptance_service=SimpleNamespace(
                verify_golden_suite=lambda **kwargs: SimpleNamespace(
                    suite_path="config/rule_replay_golden_samples.json",
                    suite_version="v2",
                    case_count=2,
                    passed_case_count=2,
                    failed_case_count=0,
                    layer_summaries={
                        "merge_semantics": {
                            "case_count": 2,
                            "passed_case_count": 2,
                            "failed_case_count": 0,
                        }
                    },
                    cases=(
                        SimpleNamespace(
                            case_id="case-1",
                            description="Golden case 1",
                            layer="merge_semantics",
                            expectation="regrouped",
                            issue_type="crash",
                            passed=True,
                            mismatches=(),
                            replay=SimpleNamespace(
                                baseline=SimpleNamespace(path="baseline.json", fingerprint_rule_version="v1"),
                                candidate=SimpleNamespace(path="candidate.json", fingerprint_rule_version="v2"),
                                filters={"issue_type": "crash"},
                                family_count=1,
                                changed_family_count=1,
                                change_summary={"regrouped": 1},
                                families=(),
                            ),
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            ["verify-rule-replay-golden-samples"],
            bundle,
        )

        self.assertTrue(payload["replay_golden_suite"]["passed"])
        self.assertEqual(payload["replay_golden_suite"]["case_count"], 2)
        self.assertEqual(payload["replay_golden_suite"]["layer_summaries"]["merge_semantics"]["case_count"], 2)
        self.assertEqual(payload["replay_golden_suite"]["cases"][0]["case_id"], "case-1")
        self.assertEqual(payload["replay_golden_suite"]["cases"][0]["layer"], "merge_semantics")
        self.assertEqual(
            payload["replay_golden_suite"]["cases"][0]["replay"]["change_summary"]["regrouped"],
            1,
        )

    def test_list_rule_replay_golden_samples_outputs_case_listing(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_golden_suite_service=SimpleNamespace(
                list_cases=lambda **kwargs: SimpleNamespace(
                    suite_path=kwargs["suite_path"] or "config/rule_replay_golden_samples.json",
                    suite_version="v2",
                    case_count=1,
                    filters={
                        "case_ids": list(kwargs["case_ids"]),
                        "issue_type": kwargs["issue_type"],
                        "layer": kwargs["layer"],
                        "expectation": kwargs["expectation"],
                        "limit": kwargs["limit"],
                    },
                    layer_counts={"merge_semantics": 1},
                    issue_type_counts={"crash": 1},
                    expectation_counts={"regrouped": 1},
                    cases=(
                        SimpleNamespace(
                            case_id="crash_regroup_ignore_raw_key",
                            description="Crash regroup case",
                            issue_type="crash",
                            layer="merge_semantics",
                            expectation="regrouped",
                            include_unchanged=False,
                            issue_count=2,
                            package_name="com.example.app",
                            template_type="monkey",
                            source_run_id="run-1",
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "list-rule-replay-golden-samples",
                "--suite-path",
                "config/rule_replay_golden_samples.json",
                "--issue-type",
                "crash",
                "--layer",
                "merge_semantics",
                "--expectation",
                "regrouped",
                "--limit",
                "5",
            ],
            bundle,
        )

        self.assertEqual(payload["golden_suite"]["suite_version"], "v2")
        self.assertEqual(payload["golden_suite"]["case_count"], 1)
        self.assertEqual(payload["golden_suite"]["issue_type_counts"]["crash"], 1)
        self.assertEqual(payload["golden_suite"]["cases"][0]["case_id"], "crash_regroup_ignore_raw_key")
        self.assertEqual(payload["golden_suite"]["cases"][0]["source_run_id"], "run-1")

    def test_show_rule_replay_golden_sample_outputs_case_detail(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_golden_suite_service=SimpleNamespace(
                get_case=lambda **kwargs: SimpleNamespace(
                    suite_path=kwargs["suite_path"] or "config/rule_replay_golden_samples.json",
                    suite_version="v2",
                    summary=SimpleNamespace(
                        case_id=kwargs["case_id"],
                        description="Crash regroup case",
                        issue_type="crash",
                        layer="merge_semantics",
                        expectation="regrouped",
                        include_unchanged=False,
                        issue_count=2,
                        package_name="com.example.app",
                        template_type="monkey",
                        source_run_id="run-1",
                    ),
                    payload={
                        "case_id": kwargs["case_id"],
                        "expected": {"change_summary": {"regrouped": 1}},
                    },
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "show-rule-replay-golden-sample",
                "--suite-path",
                "config/rule_replay_golden_samples.json",
                "--case-id",
                "crash_regroup_ignore_raw_key",
            ],
            bundle,
        )

        self.assertEqual(payload["golden_case"]["summary"]["case_id"], "crash_regroup_ignore_raw_key")
        self.assertEqual(payload["golden_case"]["summary"]["layer"], "merge_semantics")
        self.assertEqual(payload["golden_case"]["payload"]["expected"]["change_summary"]["regrouped"], 1)

    def test_diff_rule_replay_golden_samples_outputs_diff_summary(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_golden_suite_service=SimpleNamespace(
                diff_suites=lambda **kwargs: SimpleNamespace(
                    left_path=kwargs["left_path"],
                    right_path=kwargs["right_path"],
                    left_suite_version="v2",
                    right_suite_version="v3",
                    diff_count=2,
                    change_counts={"modified": 1, "added": 1},
                    entries=(
                        SimpleNamespace(
                            case_id="case-modified",
                            change_type="modified",
                            changed_fields=("description",),
                            left_case={"case_id": "case-modified", "description": "before"},
                            right_case={"case_id": "case-modified", "description": "after"},
                        ),
                        SimpleNamespace(
                            case_id="case-added",
                            change_type="added",
                            changed_fields=(),
                            left_case={},
                            right_case={"case_id": "case-added"},
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "diff-rule-replay-golden-samples",
                "--left-path",
                "/tmp/left.json",
                "--right-path",
                "/tmp/right.json",
                "--include-unchanged",
            ],
            bundle,
        )

        self.assertEqual(payload["golden_suite_diff"]["left_suite_version"], "v2")
        self.assertEqual(payload["golden_suite_diff"]["right_suite_version"], "v3")
        self.assertEqual(payload["golden_suite_diff"]["diff_count"], 2)
        self.assertEqual(payload["golden_suite_diff"]["change_counts"]["modified"], 1)
        self.assertEqual(payload["golden_suite_diff"]["entries"][0]["changed_fields"], ["description"])

    def test_draft_rule_replay_golden_sample_outputs_draft_summary(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_golden_draft_service=SimpleNamespace(
                create_draft=lambda **kwargs: SimpleNamespace(
                    output_path="runtime/drafts/crash.json",
                    suite_version="v2",
                    appended=False,
                    case_id="crash_run_real_draft",
                    issue_type="crash",
                    layer="merge_semantics",
                    expectation="unchanged",
                    issue_count=2,
                    source_run_id=kwargs["run_id"],
                    selected_issue_ids=("issue-a", "issue-b"),
                    selected_instance_ids=("instance-a", "instance-b"),
                    baseline_path="config/stability_rules.json",
                    candidate_path="config/stability_rules.json",
                    expected={"family_count": 2, "changed_family_count": 0, "change_summary": {"unchanged": 2}},
                    replay_preview=SimpleNamespace(
                        baseline=SimpleNamespace(path="baseline.json", fingerprint_rule_version="v1"),
                        candidate=SimpleNamespace(path="candidate.json", fingerprint_rule_version="v1"),
                        filters={"issue_type": "crash"},
                        family_count=2,
                        changed_family_count=0,
                        change_summary={"unchanged": 2},
                        families=(),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "draft-rule-replay-golden-sample",
                "--run-id",
                "run-real",
                "--issue-id",
                "issue-a",
                "--issue-id",
                "issue-b",
                "--output",
                "runtime/drafts/crash.json",
            ],
            bundle,
        )

        self.assertEqual(payload["golden_draft"]["case_id"], "crash_run_real_draft")
        self.assertEqual(payload["golden_draft"]["issue_type"], "crash")
        self.assertEqual(payload["golden_draft"]["issue_count"], 2)
        self.assertEqual(payload["golden_draft"]["selected_issue_ids"], ["issue-a", "issue-b"])
        self.assertEqual(payload["golden_draft"]["expected"]["family_count"], 2)
        self.assertEqual(payload["golden_draft"]["replay_preview"]["change_summary"]["unchanged"], 2)

    def test_promote_rule_replay_golden_draft_outputs_promotion_summary(self) -> None:
        bundle = SimpleNamespace(
            rule_replay_golden_promotion_service=SimpleNamespace(
                promote=lambda **kwargs: SimpleNamespace(
                    source_path=kwargs["source_path"],
                    target_path=kwargs["target_path"],
                    selected_case_ids=("case-1",),
                    promoted_case_ids=("case-1",),
                    replaced_case_ids=(),
                    skipped_case_ids=(),
                    target_suite_version="v2",
                    source_suite_version="v2",
                    promoted_case_count=1,
                    replace_existing=kwargs["replace_existing"],
                    acceptance=SimpleNamespace(
                        suite_path=kwargs["target_path"],
                        suite_version="v2",
                        case_count=1,
                        passed_case_count=1,
                        failed_case_count=0,
                        layer_summaries={"merge_semantics": {"case_count": 1}},
                        cases=(),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "promote-rule-replay-golden-draft",
                "--source-path",
                "/tmp/draft.json",
                "--target-path",
                "/tmp/target.json",
                "--case-id",
                "case-1",
            ],
            bundle,
        )

        self.assertEqual(payload["golden_promotion"]["source_path"], "/tmp/draft.json")
        self.assertEqual(payload["golden_promotion"]["target_path"], "/tmp/target.json")
        self.assertEqual(payload["golden_promotion"]["promoted_case_count"], 1)
        self.assertEqual(payload["golden_promotion"]["promoted_case_ids"], ["case-1"])
        self.assertEqual(payload["golden_promotion"]["acceptance"]["passed_case_count"], 1)

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
