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


class CLIAnalysisCommandsTest(unittest.TestCase):
    def test_list_top_issues_outputs_aggregated_results(self) -> None:
        bundle = SimpleNamespace(
            analysis_service=SimpleNamespace(
                list_top_issues=lambda **kwargs: [
                    SimpleNamespace(
                        fingerprint=SimpleNamespace(
                            value="ifp_1",
                            rule_version="v1",
                            components={"issue_type": "crash", "package_name": "com.example.app"},
                        ),
                        issue_type=SimpleNamespace(value="crash"),
                        title="检测到 Crash",
                        severity=SimpleNamespace(value="critical"),
                        first_seen_at=None,
                        last_seen_at=None,
                        occurrence_count=2,
                        affected_run_count=1,
                        affected_device_count=2,
                        affected_scenario_count=1,
                        affected_version_count=1,
                        affected_packages=("com.example.app",),
                        affected_devices=("device-1", "device-2"),
                        affected_scenarios=("monkey",),
                        affected_versions=("1.0.0(100)",),
                        sample_event_ids=("issue-1",),
                        sample_events=(),
                        score=430.0,
                        score_breakdown={"severity": 400.0, "occurrence_count": 20.0, "affected_device_count": 10.0},
                        metadata={
                            "evidence_signals": ["crash_stack", "logcat_fatal"],
                            "confirmation_level": "multi_evidence",
                        },
                    )
                ]
            )
        )

        payload = self._run_main_with_bundle(["list-top-issues", "--package-name", "com.example.app"], bundle)

        self.assertEqual(payload["top_issue_count"], 1)
        self.assertEqual(payload["issues"][0]["fingerprint"], "ifp_1")
        self.assertEqual(payload["issues"][0]["issue_type"], "crash")
        self.assertEqual(payload["issues"][0]["evidence_signals"], ["crash_stack", "logcat_fatal"])
        self.assertEqual(payload["issues"][0]["confirmation_level"], "multi_evidence")

    def test_show_issue_group_outputs_sample_events(self) -> None:
        bundle = SimpleNamespace(
            analysis_service=SimpleNamespace(
                get_issue_group=lambda fingerprint, **kwargs: SimpleNamespace(
                    fingerprint=SimpleNamespace(
                        value=fingerprint,
                        rule_version="v1",
                        components={"issue_type": "crash", "package_name": "com.example.app"},
                    ),
                    issue_type=SimpleNamespace(value="crash"),
                    title="检测到 Crash",
                    severity=SimpleNamespace(value="critical"),
                    first_seen_at=None,
                    last_seen_at=None,
                    occurrence_count=2,
                    affected_run_count=1,
                    affected_device_count=2,
                    affected_scenario_count=1,
                    affected_version_count=1,
                    affected_packages=("com.example.app",),
                    affected_devices=("device-1", "device-2"),
                    affected_scenarios=("monkey",),
                    affected_versions=("1.0.0(100)",),
                    sample_event_ids=("issue-1", "issue-2"),
                    sample_events=(
                        SimpleNamespace(
                            event_id="issue-1",
                            run_id="run-1",
                            task_id="task-1",
                            task_name="Task 1",
                            instance_id="instance-1",
                            device_id="device-1",
                            package_name="com.example.app",
                            scenario_name="monkey",
                            issue_type=SimpleNamespace(value="crash"),
                            severity=SimpleNamespace(value="critical"),
                            detected_at=None,
                            summary="summary",
                            report_path="runtime/report.md",
                            execution_log_path="runtime/execution.log",
                            artifact_paths=("runtime/logcat.txt",),
                            metadata={
                                "run_status": "failed",
                                "evidence_signals": ["stacktrace", "process_exit"],
                                "confirmation_level": "confirmed",
                            },
                        ),
                    ),
                    score=430.0,
                    score_breakdown={"severity": 400.0},
                )
            ),
            attribution_service=SimpleNamespace(
                attribute_issue_group=lambda item: SimpleNamespace(
                    fingerprint=item.fingerprint.value,
                    issue_type=item.issue_type,
                    title=item.title,
                    direction="app_logic",
                    direction_label="应用侧逻辑异常",
                    confidence="high",
                    summary="matched app rule",
                    rule_version="v1",
                    matched_rule_id="app_target_process_crash",
                    matched_rule_name="Target app process failure",
                    matched_rule_ids=("app_target_process_crash", "fatal_stacktrace"),
                    confidence_score=0.91,
                    evidence_summary="process matched target package and fatal stacktrace",
                    recommended_next_steps=("inspect logcat around crash", "assign to app owner"),
                    review_notes=("rule needs human confirmation",),
                    score=6,
                    sample_event_ids=item.sample_event_ids,
                    hits=(
                        SimpleNamespace(
                            field="process_name",
                            keyword="package_process_match",
                            evidence="com.example.app",
                            score=4,
                        ),
                    ),
                    notes=(),
                )
            ),
        )

        payload = self._run_main_with_bundle(["show-issue-group", "--fingerprint", "ifp_1"], bundle)

        self.assertEqual(payload["issue_group"]["fingerprint"], "ifp_1")
        self.assertEqual(payload["issue_group"]["sample_events"][0]["event_id"], "issue-1")
        self.assertEqual(payload["issue_group"]["sample_events"][0]["evidence_signals"], ["stacktrace", "process_exit"])
        self.assertEqual(payload["issue_group"]["sample_events"][0]["confirmation_level"], "confirmed")
        self.assertEqual(payload["attribution"]["direction"], "app_logic")
        self.assertEqual(payload["attribution"]["confidence_score"], 0.91)
        self.assertEqual(payload["attribution"]["matched_rule_ids"], ["app_target_process_crash", "fatal_stacktrace"])
        self.assertEqual(payload["attribution"]["evidence_summary"], "process matched target package and fatal stacktrace")
        self.assertEqual(payload["attribution"]["recommended_next_steps"], ["inspect logcat around crash", "assign to app owner"])
        self.assertEqual(payload["attribution"]["review_notes"], ["rule needs human confirmation"])
        self.assertEqual(payload["attribution"]["hits"][0]["field"], "process_name")

    def test_show_issue_group_raises_for_missing_fingerprint(self) -> None:
        bundle = SimpleNamespace(
            analysis_service=SimpleNamespace(
                get_issue_group=lambda fingerprint, **kwargs: (_ for _ in ()).throw(
                    AggregatedIssueNotFound(f"Aggregated issue '{fingerprint}' was not found.")
                )
            )
        )

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            with self.assertRaises(SystemExit) as ctx:
                task_create.main(["show-issue-group", "--fingerprint", "ifp_missing"])

        self.assertIn("Aggregated issue 'ifp_missing' was not found.", str(ctx.exception))

    def test_compare_issues_outputs_comparison_result(self) -> None:
        bundle = SimpleNamespace(
            comparison_service=SimpleNamespace(
                compare_issues=lambda **kwargs: SimpleNamespace(
                    dimension=kwargs["dimension"],
                    left_scope=SimpleNamespace(
                        dimension="device",
                        value="device-a",
                        label="device:device-a",
                        filters={"device_id": "device-a", "version": "1.0.0(100)"},
                    ),
                    right_scope=SimpleNamespace(
                        dimension="device",
                        value="device-b",
                        label="device:device-b",
                        filters={"device_id": "device-b", "version": "1.0.0(100)"},
                    ),
                    base_filters={"package_name": "com.example.app", "version": "1.0.0(100)"},
                    sample_summary={"left_issue_group_count": 2, "right_issue_group_count": 2},
                    issue_change_summary={"new_count": 1, "gone_count": 1, "changed_count": 1, "unchanged_count": 0},
                    metric_change_summary={"available": False, "reason": "not implemented"},
                    comparability_notes=("device-id compare",),
                    issues=(
                        SimpleNamespace(
                            comparison_key="cmp_1",
                            title="检测到 Crash",
                            issue_type="crash",
                            severity="critical",
                            change_type="changed",
                            occurrence_delta=1,
                            left_fingerprint="ifp_left",
                            right_fingerprint="ifp_right",
                            left_occurrence_count=1,
                            right_occurrence_count=2,
                            left_affected_run_count=1,
                            right_affected_run_count=1,
                            left_affected_device_count=1,
                            right_affected_device_count=1,
                            left_affected_scenario_count=1,
                            right_affected_scenario_count=1,
                            left_sample_event_ids=("issue-1",),
                            right_sample_event_ids=("issue-2",),
                            left_sample_events=(),
                            right_sample_events=(),
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "compare-issues",
                "--dimension",
                "device",
                "--left-value",
                "device-a",
                "--right-value",
                "device-b",
                "--version",
                "1.0.0(100)",
                "--package-name",
                "com.example.app",
            ],
            bundle,
        )

        self.assertEqual(payload["comparison"]["dimension"], "device")
        self.assertEqual(payload["comparison"]["issue_count"], 1)
        self.assertEqual(payload["comparison"]["issues"][0]["comparison_key"], "cmp_1")
        self.assertEqual(payload["comparison"]["issues"][0]["left_fingerprint"], "ifp_left")

    def test_judge_regression_outputs_rule_based_result(self) -> None:
        bundle = SimpleNamespace(
            regression_service=SimpleNamespace(
                evaluate_regression=lambda **kwargs: SimpleNamespace(
                    dimension=kwargs["dimension"],
                    left_scope=SimpleNamespace(
                        dimension="version",
                        value="1.0.0(100)",
                        label="version:1.0.0(100)",
                        filters={"version": "1.0.0(100)"},
                    ),
                    right_scope=SimpleNamespace(
                        dimension="version",
                        value="2.0.0(200)",
                        label="version:2.0.0(200)",
                        filters={"version": "2.0.0(200)"},
                    ),
                    base_filters={"package_name": "com.example.app", "template_type": "monkey"},
                    rule_set=SimpleNamespace(
                        as_dict=lambda: {
                            "version": "v1",
                            "min_side_issue_groups": 1,
                            "significant_occurrence_delta": 1,
                            "significant_affected_run_delta": 1,
                            "significant_affected_device_delta": 1,
                            "significant_affected_scenario_delta": 1,
                        }
                    ),
                    overall_result="obvious_regression",
                    issue_result_summary={"new_count": 1, "worsened_count": 0},
                    metric_result_summary={"available": True, "metric_count": 1, "worsened_count": 1},
                    summary={"left_issue_group_count": 1, "right_issue_group_count": 2, "issue_count": 1},
                    reasons=("Found new high-severity issues on the target side.",),
                    comparability_notes=("comparison notes",),
                    issues=(
                        SimpleNamespace(
                            comparison_key="cmp_2",
                            title="设备发生重启",
                            issue_type="reboot",
                            severity="critical",
                            regression_result="new",
                            change_type="new",
                            reason="The issue only exists on the target side.",
                            occurrence_delta=1,
                            left_fingerprint="",
                            right_fingerprint="ifp_reboot",
                            left_occurrence_count=0,
                            right_occurrence_count=1,
                            left_affected_run_count=0,
                            right_affected_run_count=1,
                            left_affected_device_count=0,
                            right_affected_device_count=1,
                            left_affected_scenario_count=0,
                            right_affected_scenario_count=1,
                        ),
                    ),
                    metrics=(
                        SimpleNamespace(
                            metric_key="memory_pss",
                            label="Memory PSS",
                            unit="MB",
                            higher_is_worse=True,
                            regression_result="worsened",
                            change_type="worsened",
                            reason="Average metric value increased by 20.0, crossing threshold 10.0.",
                            left_summary=SimpleNamespace(
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
                            right_summary=SimpleNamespace(
                                metric_key="memory_pss",
                                label="Memory PSS",
                                unit="MB",
                                sample_count=10,
                                session_count=1,
                                average=120.0,
                                peak=140.0,
                                p95=138.0,
                                latest=121.0,
                            ),
                            average_delta=20.0,
                            peak_delta=20.0,
                            p95_delta=20.0,
                            latest_delta=20.0,
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "judge-regression",
                "--dimension",
                "version",
                "--left-value",
                "1.0.0(100)",
                "--right-value",
                "2.0.0(200)",
                "--template-type",
                "monkey",
                "--package-name",
                "com.example.app",
            ],
            bundle,
        )

        self.assertEqual(payload["regression"]["overall_result"], "obvious_regression")
        self.assertEqual(payload["regression"]["issue_count"], 1)
        self.assertEqual(payload["regression"]["metric_count"], 1)
        self.assertEqual(payload["regression"]["issues"][0]["regression_result"], "new")
        self.assertEqual(payload["regression"]["metrics"][0]["regression_result"], "worsened")

    def test_compare_performance_trends_outputs_metric_rows(self) -> None:
        bundle = SimpleNamespace(
            performance_trend_service=SimpleNamespace(
                compare_performance_trends=lambda **kwargs: SimpleNamespace(
                    dimension=kwargs["dimension"],
                    left_scope=SimpleNamespace(
                        dimension="version",
                        value="1.0.0(100)",
                        label="version:1.0.0(100)",
                        filters={"version": "1.0.0(100)", "package_name": "com.example.app"},
                    ),
                    right_scope=SimpleNamespace(
                        dimension="version",
                        value="2.0.0(200)",
                        label="version:2.0.0(200)",
                        filters={"version": "2.0.0(200)", "package_name": "com.example.app"},
                    ),
                    base_filters={"package_name": "com.example.app", "template_type": "monkey"},
                    sample_summary={"left_session_count": 1, "right_session_count": 1},
                    metric_change_summary={"worsened_count": 1, "improved_count": 1, "unchanged_count": 0},
                    comparability_notes=("monitoring compare",),
                    metrics=(
                        SimpleNamespace(
                            metric_key="cpu_usage",
                            label="CPU Usage",
                            unit="%",
                            higher_is_worse=True,
                            left_summary=SimpleNamespace(
                                metric_key="cpu_usage",
                                label="CPU Usage",
                                unit="%",
                                sample_count=2,
                                session_count=1,
                                average=10.0,
                                peak=12.0,
                                p95=11.9,
                                latest=12.0,
                            ),
                            right_summary=SimpleNamespace(
                                metric_key="cpu_usage",
                                label="CPU Usage",
                                unit="%",
                                sample_count=2,
                                session_count=1,
                                average=20.0,
                                peak=25.0,
                                p95=24.8,
                                latest=18.0,
                            ),
                            average_delta=10.0,
                            peak_delta=13.0,
                            p95_delta=12.9,
                            latest_delta=6.0,
                            change_type="worsened",
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "compare-performance-trends",
                "--dimension",
                "version",
                "--left-value",
                "1.0.0(100)",
                "--right-value",
                "2.0.0(200)",
                "--template-type",
                "monkey",
                "--package-name",
                "com.example.app",
            ],
            bundle,
        )

        self.assertEqual(payload["comparison"]["dimension"], "version")
        self.assertEqual(payload["comparison"]["metric_count"], 1)
        self.assertEqual(payload["comparison"]["metrics"][0]["metric_key"], "cpu_usage")
        self.assertEqual(payload["comparison"]["metrics"][0]["change_type"], "worsened")
        self.assertEqual(payload["comparison"]["metrics"][0]["right_summary"]["latest"], 18.0)

    def test_create_analysis_snapshot_outputs_snapshot_record(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                create_top_issues_snapshot=lambda **kwargs: SimpleNamespace(
                    snapshot_id="snapshot_1",
                    snapshot_type="top_issues",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    scope={},
                    filters={"package_name": "com.example.app"},
                    data_range={"created_from": None, "created_to": None},
                    rule_versions={"fingerprint_rule_versions": ["v1"]},
                    summary={"top_issue_count": 1},
                    detail_path="runtime/analysis_snapshots/snapshot_1/snapshot.json",
                    markdown_path="runtime/analysis_snapshots/snapshot_1/summary.md",
                    payload={"top_issue_count": 1},
                    tags=("nightly",),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "create-analysis-snapshot",
                "--snapshot-type",
                "top_issues",
                "--name",
                "Nightly Top Issues",
                "--created-by",
                "cli",
                "--package-name",
                "com.example.app",
                "--tag",
                "nightly",
            ],
            bundle,
        )

        self.assertEqual(payload["snapshot"]["snapshot_id"], "snapshot_1")
        self.assertEqual(payload["snapshot"]["snapshot_type"], "top_issues")
        self.assertEqual(payload["snapshot"]["tags"], ["nightly"])

    def test_create_replay_analysis_snapshot_outputs_snapshot_record(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                create_rule_replay_snapshot=lambda **kwargs: SimpleNamespace(
                    snapshot_id="snapshot_replay_1",
                    snapshot_type="replay",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    scope={
                        "baseline_path": kwargs.get("baseline_path", "config/stability_rules.json"),
                        "candidate_path": kwargs["candidate_path"],
                    },
                    filters={"package_name": kwargs.get("package_name", "")},
                    data_range={"created_from": None, "created_to": None},
                    rule_versions={
                        "baseline_fingerprint_rule_version": "v1",
                        "candidate_fingerprint_rule_version": "v2",
                    },
                    summary={"changed_family_count": 2},
                    source_refs={"summary": {"run_count": 1, "report_count": 1}},
                    detail_path="runtime/analysis_snapshots/snapshot_replay_1/snapshot.json",
                    markdown_path="runtime/analysis_snapshots/snapshot_replay_1/summary.md",
                    payload={"change_summary": {"fingerprint_changed": 2}},
                    tags=tuple(kwargs.get("tags", ())),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "create-analysis-snapshot",
                "--snapshot-type",
                "replay",
                "--name",
                "Replay Snapshot",
                "--candidate-path",
                "candidate.json",
                "--package-name",
                "com.example.app",
                "--include-unchanged",
            ],
            bundle,
        )

        self.assertEqual(payload["snapshot"]["snapshot_type"], "replay")
        self.assertEqual(payload["snapshot"]["scope"]["candidate_path"], "candidate.json")
        self.assertEqual(payload["snapshot"]["rule_versions"]["candidate_fingerprint_rule_version"], "v2")
        self.assertEqual(payload["snapshot"]["payload"]["change_summary"]["fingerprint_changed"], 2)

    def test_create_review_analysis_snapshot_outputs_snapshot_record(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                create_rule_review_snapshot=lambda **kwargs: SimpleNamespace(
                    snapshot_id="snapshot_review_1",
                    snapshot_type="review",
                    name=kwargs["name"],
                    created_at=None,
                    created_by=kwargs["created_by"],
                    scope={
                        "baseline_path": kwargs.get("baseline_path", "config/stability_rules.json"),
                        "candidate_path": kwargs["candidate_path"],
                    },
                    filters={"package_name": kwargs.get("package_name", "")},
                    data_range={"created_from": None, "created_to": None},
                    rule_versions={
                        "policy_version": "review-v1",
                        "baseline_fingerprint_rule_version": "v1",
                        "candidate_fingerprint_rule_version": "v2",
                    },
                    summary={"decision": "conditional_pass"},
                    source_refs={"summary": {"run_count": 1, "report_count": 1}},
                    detail_path="runtime/analysis_snapshots/snapshot_review_1/snapshot.json",
                    markdown_path="runtime/analysis_snapshots/snapshot_review_1/summary.md",
                    payload={"decision": "conditional_pass", "change_summary": {"fingerprint_changed": 2}},
                    tags=tuple(kwargs.get("tags", ())),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "create-analysis-snapshot",
                "--snapshot-type",
                "review",
                "--name",
                "Review Snapshot",
                "--candidate-path",
                "candidate.json",
                "--package-name",
                "com.example.app",
            ],
            bundle,
        )

        self.assertEqual(payload["snapshot"]["snapshot_type"], "review")
        self.assertEqual(payload["snapshot"]["summary"]["decision"], "conditional_pass")
        self.assertEqual(payload["snapshot"]["rule_versions"]["policy_version"], "review-v1")

    def test_list_analysis_snapshots_outputs_summaries(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                list_snapshots=lambda **kwargs: [
                    SimpleNamespace(
                        snapshot_id="snapshot_1",
                        snapshot_type="comparison",
                        name="Compare Snapshot",
                        created_at=None,
                        created_by="cli",
                        detail_path="runtime/analysis_snapshots/snapshot_1/snapshot.json",
                        markdown_path="runtime/analysis_snapshots/snapshot_1/summary.md",
                        summary={"issue_count": 2},
                        filters={"package_name": "com.example.app"},
                        rule_versions={"fingerprint_rule_version": "v1"},
                    )
                ]
            )
        )

        payload = self._run_main_with_bundle(
            ["list-analysis-snapshots", "--snapshot-type", "comparison"],
            bundle,
        )

        self.assertEqual(payload["snapshot_count"], 1)
        self.assertEqual(payload["snapshots"][0]["snapshot_type"], "comparison")

    def test_show_analysis_snapshot_outputs_detail(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                get_snapshot=lambda snapshot_id: SimpleNamespace(
                    snapshot_id=snapshot_id,
                    snapshot_type="regression",
                    name="Regression Snapshot",
                    created_at=None,
                    created_by="cli",
                    scope={"dimension": "version"},
                    filters={"package_name": "com.example.app"},
                    data_range={"created_from": None, "created_to": None},
                    rule_versions={"regression_rule_version": "v1"},
                    summary={"overall_result": "obvious_regression"},
                    source_refs={"summary": {"run_count": 2}},
                    detail_path="runtime/analysis_snapshots/snapshot_1/snapshot.json",
                    markdown_path="runtime/analysis_snapshots/snapshot_1/summary.md",
                    payload={"overall_result": "obvious_regression"},
                    tags=("release",),
                ),
                inspect_snapshot_integrity=lambda record: {
                    "tracked_path_count": 2,
                    "existing_path_count": 2,
                    "missing_path_count": 0,
                    "detail_path_exists": True,
                    "markdown_path_exists": True,
                    "missing_paths": [],
                },
            )
        )

        payload = self._run_main_with_bundle(
            ["show-analysis-snapshot", "--snapshot-id", "snapshot_1"],
            bundle,
        )

        self.assertEqual(payload["snapshot"]["snapshot_id"], "snapshot_1")
        self.assertEqual(payload["snapshot"]["snapshot_type"], "regression")
        self.assertEqual(payload["snapshot"]["summary"]["overall_result"], "obvious_regression")
        self.assertEqual(payload["integrity"]["missing_path_count"], 0)

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
