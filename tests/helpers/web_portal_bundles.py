from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from .web_portal_fakes_collaboration import _FakeCollaborationService
from .web_portal_fakes_core import default_runner_status
from .web_portal_fakes_integration import (
    _FakeIntegrationOutboxService,
    _FakeReleaseSubmissionService,
)
from .web_portal_fakes_quality import _FakeQualityGateService


def bundle(runner_status_override=None) -> object:
    collaboration_service = _FakeCollaborationService()
    integration_outbox_service = _FakeIntegrationOutboxService()
    release_submission_service = _FakeReleaseSubmissionService(integration_outbox_service)
    temp_root = Path(tempfile.mkdtemp(prefix="asl_web_portal_"))
    monitoring_root = (
        temp_root
        / "runtime"
        / "tasks"
        / "task-1"
        / "runs"
        / "run-1"
        / "executions"
        / "instance-1"
        / "devices"
        / "192_168_31_99_5555"
    )
    snapshot_path = monitoring_root / "monitoring" / "snapshot.json"
    trace_path = monitoring_root / "monitoring" / "trace.perfetto-trace"
    report_path = monitoring_root / "report" / "report.md"
    html_report_path = monitoring_root / "report" / "report.html"
    execution_log_path = monitoring_root / "logs" / "execution.log"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    execution_log_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "timestamp": "2025-07-20T09:01:30",
                "metadata": {"backend": "solox"},
                "system": {
                    "cpu_usage": 12.5,
                    "battery_level": 87.0,
                    "network_rx_total": 2048,
                    "network_tx_total": 512,
                },
                "apps": [
                    {
                        "app_package": "com.hihonor.calculator",
                        "memory_pss": 256.0,
                        "fps": 58.0,
                        "gpu_usage": 17.5,
                        "power_consumption": 320.0,
                        "app_info": {
                            "package_name": "com.hihonor.calculator",
                            "app_name": "Calculator",
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    trace_path.write_bytes(b"perfetto-trace")
    report_path.write_text("# report", encoding="utf-8")
    html_report_path.write_text("<html></html>", encoding="utf-8")
    execution_log_path.write_text("log", encoding="utf-8")
    issue = SimpleNamespace(
        fingerprint=SimpleNamespace(value="ifp_1", rule_version="v1"),
        title="Cold start timeout",
        issue_type=SimpleNamespace(value="startup_timeout"),
        severity=SimpleNamespace(value="high"),
        occurrence_count=3,
        affected_run_count=2,
        affected_device_count=1,
        affected_scenario_count=1,
        affected_versions=("1.0.0",),
        affected_devices=("192.168.31.99:5555",),
        affected_scenarios=("cold_start_loop",),
        affected_packages=("com.hihonor.calculator",),
        sample_event_ids=("issue-1",),
        first_seen_at=None,
        last_seen_at=None,
        score=250.0,
        score_breakdown={"severity": 250.0},
        metadata={
            "evidence_signals": ["timeout_marker", "activity_launch_gap"],
            "confirmation_level": "multi_evidence",
        },
    )
    baseline = SimpleNamespace(
        baseline_key="device_offline_default",
        report_id="review_report_1",
        report_name="Device Offline Default",
        policy_versions=("review-policy-v1",),
        candidate_paths=("config/stability_rules.json",),
        baseline_paths=("config/stability_rules.base.json",),
        report_created_at="2025-07-20T09:00:00",
        updated_at=None,
        updated_by="cli",
        latest_audit_id="baseline_audit_latest_device_offline_default",
        latest_audit_detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
        latest_audit_markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
        latest_audit_html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
        latest_audit_index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
        latest_audit_version_count=3,
    )
    latest_view = SimpleNamespace(
        audit_id="baseline_audit_latest_device_offline_default",
        audit_name="Latest Device Offline Audit",
        created_at=None,
        created_by="cli",
        summary={
            "action_counts": {"set": 1, "promote": 1, "rollback": 1},
            "current_report_golden_suite": {
                "snapshot_count": 1,
                "passed_snapshot_count": 1,
                "failed_snapshot_count": 0,
                "case_count_total": 4,
                "passed_case_count_total": 4,
                "failed_case_count_total": 0,
                "versions": ["v1"],
                "suite_paths": ["config/rule_replay_golden_samples.json"],
                "layer_summaries": {
                    "merge_semantics": {
                        "snapshot_count": 1,
                        "case_count_total": 4,
                        "passed_case_count_total": 4,
                        "failed_case_count_total": 0,
                        "issue_types": ["crash", "anr", "startup_timeout", "process_exit"],
                        "expectations": ["regrouped"],
                        "case_ids": [
                            "crash_regroup_ignore_raw_key",
                            "anr_regroup_ignore_raw_key"
                        ]
                    }
                }
            },
        },
        retention={"max_versions": 10, "pruned_count": 0},
        version_count=1,
        detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
        markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
        html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
        index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
        versions=(
            SimpleNamespace(
                revision_id="baseline_rev_3",
                action="rollback",
                changed_at=None,
                changed_by="cli",
                report_id="review_report_0",
                report_name="Previous Report",
                audit_id="baseline_audit_previous",
                summary={"action_counts": {"rollback": 1}},
                detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/versions/baseline_rev_3/report.json",
                markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/versions/baseline_rev_3/summary.md",
                html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/versions/baseline_rev_3/report.html",
            ),
        ),
    )
    report = SimpleNamespace(
        report_id="review_report_1",
        name="Device Offline Default",
        created_at=None,
        created_by="cli",
        summary={
            "snapshot_count": 2,
            "decision_counts": {"conditional_pass": 1},
            "high_risk_family_count": 2,
            "golden_suite_snapshot_count": 1,
            "golden_suite_case_count_total": 4,
            "golden_suite_failed_case_count_total": 0,
            "golden_suite_layer_summaries": {
                "merge_semantics": {
                    "snapshot_count": 1,
                    "case_count_total": 4,
                    "passed_case_count_total": 4,
                    "failed_case_count_total": 0,
                    "issue_types": ["crash", "anr", "startup_timeout", "process_exit"],
                    "expectations": ["regrouped"],
                    "case_ids": [
                        "crash_regroup_ignore_raw_key",
                        "anr_regroup_ignore_raw_key"
                    ]
                }
            },
        },
        detail_path="runtime/analysis_review_reports/review_report_1/report.json",
        markdown_path="runtime/analysis_review_reports/review_report_1/summary.md",
        html_path="runtime/analysis_review_reports/review_report_1/report.html",
    )
    quality_gate = SimpleNamespace(
        baseline_key="device_offline_default",
        report_id="review_report_1",
        report_name="Device Offline Default",
        evaluated_at=None,
        automatic_decision="conditional_pass",
        final_decision="conditional_pass",
        final_review_opinion="自动准入为 conditional_pass，仍需人工确认高风险 family。",
        failure_reasons=(
            "当前报告包含 1 个 conditional_pass 决策快照。",
            "当前报告仍有 2 个高风险 family。",
        ),
        policy_versions=("review-policy-v1",),
        candidate_paths=("config/stability_rules.json",),
        baseline_paths=("config/stability_rules.base.json",),
        report_created_at="2025-07-20T09:00:00",
        updated_at=None,
        updated_by="cli",
        latest_audit_summary=dict(latest_view.summary),
        current_report_golden_suite=dict(latest_view.summary["current_report_golden_suite"]),
        report_summary=dict(report.summary),
        source_links={
            "report_detail_path": report.detail_path,
            "report_markdown_path": report.markdown_path,
            "report_html_path": report.html_path,
            "latest_audit_detail_path": latest_view.detail_path,
            "latest_audit_markdown_path": latest_view.markdown_path,
            "latest_audit_html_path": latest_view.html_path,
            "latest_audit_index_path": latest_view.index_path,
        },
        triggered_rules=(
            SimpleNamespace(
                rule_key="review_warnings",
                rule_name="规则评审警告门槛",
                rule_version="quality-gate-v1",
                decision_on_trigger="conditional_pass",
                observed_value=1,
                threshold=0,
                message="当前报告包含 1 个 conditional_pass 决策快照。",
                source="report.summary.decision_counts.conditional_pass",
            ),
            SimpleNamespace(
                rule_key="high_risk_families",
                rule_name="高风险 Family 门槛",
                rule_version="quality-gate-v1",
                decision_on_trigger="conditional_pass",
                observed_value=2,
                threshold=0,
                message="当前报告仍有 2 个高风险 family。",
                source="report.summary.high_risk_family_count",
            ),
        ),
        risk_items=(
            SimpleNamespace(
                risk_key="stability_high_risk_families",
                category="stability",
                severity="medium",
                summary="高风险 family 数为 2，建议继续人工评审。",
                details={"high_risk_family_count": 2},
                source="report.summary.high_risk_family_count",
                blocks_admission=False,
            ),
        ),
        performance_risk_items=(
            SimpleNamespace(
                risk_key="cpu_regression",
                category="performance",
                severity="warning",
                summary="CPU delta exceeded scoped threshold.",
                details={"delta_percent": 18.5, "threshold": 10.0},
                source="performance_trend_service",
                threshold_source="performance_thresholds.version",
                matched_scope={"package_name": "com.hihonor.calculator", "template_type": "cold_start_loop"},
                threshold_detail={"metric_key": "cpu_usage", "max_delta_percent": 10.0},
                blocks_admission=False,
            ),
        ),
        coverage_gaps=(),
        override=None,
    )
    quality_gate_service = _FakeQualityGateService(
        quality_gate,
        outbox_service=integration_outbox_service,
    )
    admission_case = SimpleNamespace(
        case_id="admission_case:device_offline_default:review_report_1",
        baseline_key="device_offline_default",
        report_id="review_report_1",
        report_name="Device Offline Default",
        contract_version="admission_case.v1",
        status="open",
        revision=1,
        assignee_id="",
        assignee_display_name="",
        final_reviewer_id="",
        final_reviewer_display_name="",
        created_at=None,
        updated_at=None,
        updated_by="cli",
        filters={
            "task_id": "task-1",
            "package_name": "com.hihonor.calculator",
            "template_type": "cold_start_loop",
            "dimension": "version",
            "left_value": "1.0.0(100)",
            "right_value": "1.0.1(101)",
        },
        execution_summary=SimpleNamespace(
            total_runs=2,
            status_counts={"failed": 1, "success": 1},
            failed_run_count=1,
            issue_run_count=1,
            task_ids=("task-1",),
            task_names=("Calculator Cold Start",),
            package_names=("com.hihonor.calculator",),
            template_types=("cold_start_loop",),
            device_ids=("192.168.31.99:5555",),
            latest_run_id="run-1",
            latest_run_status="failed",
            latest_run_created_at=None,
            recent_runs=(
                {
                    "run_id": "run-1",
                    "task_id": "task-1",
                    "task_name": "Calculator Cold Start",
                    "run_status": "failed",
                    "package_name": "com.hihonor.calculator",
                    "template_type": "cold_start_loop",
                    "target_device_ids": ["192.168.31.99:5555"],
                    "created_at": "2025-07-20T09:01:00",
                },
            ),
        ),
        top_issues=(
            SimpleNamespace(
                fingerprint=issue.fingerprint.value,
                title=issue.title,
                issue_type=issue.issue_type.value,
                severity=issue.severity.value,
                occurrence_count=issue.occurrence_count,
                affected_run_count=issue.affected_run_count,
                affected_device_count=issue.affected_device_count,
                affected_scenario_count=issue.affected_scenario_count,
                last_seen_at=issue.last_seen_at,
                affected_scenarios=issue.affected_scenarios,
                affected_versions=issue.affected_versions,
                metadata=dict(issue.metadata),
            ),
        ),
        regression_summary=SimpleNamespace(
            available=True,
            dimension="version",
            overall_result="suspected_regression",
            issue_result_summary={"suspected_regression": 1},
            metric_result_summary={"available": True, "worsened_count": 1},
            reasons=("Crash occurrence increased.",),
            comparability_notes=(),
            source_filters={
                "dimension": "version",
                "left_value": "1.0.0(100)",
                "right_value": "1.0.1(101)",
            },
        ),
        scenario_coverage=SimpleNamespace(
            scenario_count=1,
            scenarios=("cold_start_loop",),
            issue_scenario_count=1,
            issue_scenarios=("cold_start_loop",),
            coverage_state="covered",
            notes=("场景覆盖当前按过滤范围内的任务模板类型估算。",),
        ),
        performance_risk_items=quality_gate.performance_risk_items,
        quality_gate=quality_gate,
        override=None,
        final_review_opinion="自动准入为 conditional_pass，仍需人工确认高风险 family。",
        report_summary=dict(report.summary),
        latest_audit_summary=dict(latest_view.summary),
        source_links=dict(quality_gate.source_links),
        source_refs={
            "report": {
                "report_id": "review_report_1",
                "detail_path": "runtime/analysis_review_reports/review_report_1/report.json",
                "markdown_path": "runtime/analysis_review_reports/review_report_1/summary.md",
                "html_path": "runtime/analysis_review_reports/review_report_1/report.html",
            },
            "latest_audit": {
                "detail_path": "runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
                "markdown_path": "runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
                "html_path": "runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
                "index_path": "runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
                "available": True,
            },
            "quality_gate": {
                "available": True,
                "baseline_key": "device_offline_default",
                "automatic_decision": "conditional_pass",
            },
            "filters": {
                "task_id": "task-1",
                "package_name": "com.hihonor.calculator",
                "template_type": "cold_start_loop",
            },
        },
        ci_contract={
            "contract_version": "admission_case.v1",
            "baseline_key": "device_offline_default",
            "report_id": "review_report_1",
            "final_decision": "conditional_pass",
            "error_code": "CONDITIONAL_PASS",
            "final_review_opinion": "自动准入为 conditional_pass，仍需人工确认高风险 family。",
        },
    )
    admission_case_service = SimpleNamespace(
        list_cases=lambda limit=20: (admission_case,),
        get_case=lambda baseline_key: admission_case,
    )
    collaboration_service.attach_outbox(integration_outbox_service)
    history = (
        SimpleNamespace(
            revision_id="baseline_rev_2",
            report_id="review_report_1",
            report_name="Device Offline Default",
            changed_at=None,
            changed_by="cli",
            action="promote",
            reasons=("Promoted after comparison.",),
            comparison_id="review_report_compare_1",
            comparison_detail_path="runtime/analysis_review_report_comparisons/review_report_compare_1/report.json",
            policy_version="baseline-policy-v1",
        ),
        SimpleNamespace(
            revision_id="baseline_rev_1",
            report_id="review_report_0",
            report_name="Previous Report",
            changed_at=None,
            changed_by="cli",
            action="rollback",
            reasons=("Rolled back to previous accepted report.",),
            comparison_id="",
            comparison_detail_path="",
            policy_version="baseline-policy-v1",
        ),
    )
    golden_listing = SimpleNamespace(
        suite_path="config/rule_replay_golden_samples.json",
        suite_version="v2",
        case_count=2,
        filters={"case_ids": [], "issue_type": "", "layer": "", "expectation": "", "limit": 50},
        layer_counts={"merge_semantics": 1, "identity_semantics": 1},
        issue_type_counts={"crash": 1, "device_offline": 1},
        expectation_counts={"regrouped": 1, "fingerprint_changed": 1},
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
                source_run_id="run-crash",
            ),
            SimpleNamespace(
                case_id="device_offline_fingerprint_changed_without_regroup",
                description="Device offline identity case",
                issue_type="device_offline",
                layer="identity_semantics",
                expectation="fingerprint_changed",
                include_unchanged=False,
                issue_count=1,
                package_name="com.example.app",
                template_type="cold_start_loop",
                source_run_id="run-offline",
            ),
        ),
    )
    golden_case = SimpleNamespace(
        suite_path="config/rule_replay_golden_samples.json",
        suite_version="v2",
        summary=SimpleNamespace(
            case_id="crash_regroup_ignore_raw_key",
            description="Crash regroup case",
            issue_type="crash",
            layer="merge_semantics",
            expectation="regrouped",
            include_unchanged=False,
            issue_count=2,
            package_name="com.example.app",
            template_type="monkey",
            source_run_id="run-crash",
        ),
        payload={
            "case_id": "crash_regroup_ignore_raw_key",
            "baseline_rules": {"fingerprint": {"version": "baseline-v1"}},
            "candidate_rules": {"fingerprint": {"version": "candidate-v2"}},
            "filters": {"package_name": "com.example.app", "issue_type": "crash"},
            "dataset": {"run": {"run_id": "run-crash"}, "instances": [{"instance_id": "instance-crash-a"}]},
            "expected": {"change_summary": {"regrouped": 1}},
            "draft_metadata": {"source_run_id": "run-crash"},
        },
    )
    golden_diff = SimpleNamespace(
        left_path="config/rule_replay_golden_samples.json",
        right_path="/tmp/golden-right.json",
        left_suite_version="v2",
        right_suite_version="v2-diff",
        diff_count=2,
        change_counts={"modified": 1, "added": 1},
        entries=(
            SimpleNamespace(
                case_id="crash_regroup_ignore_raw_key",
                change_type="modified",
                changed_fields=("description",),
                left_case={
                    "case_id": "crash_regroup_ignore_raw_key",
                    "description": "Crash regroup case",
                    "issue_type": "crash",
                    "layer": "merge_semantics",
                    "expectation": "regrouped",
                    "baseline_rules": {"fingerprint": {"version": "baseline-v1"}},
                    "candidate_rules": {"fingerprint": {"version": "candidate-v1"}},
                    "filters": {"package_name": "com.example.app", "issue_type": "crash"},
                    "expected": {"change_summary": {"regrouped": 1}},
                },
                right_case={
                    "case_id": "crash_regroup_ignore_raw_key",
                    "description": "Crash regroup case [candidate]",
                    "issue_type": "crash",
                    "layer": "merge_semantics",
                    "expectation": "regrouped",
                    "baseline_rules": {"fingerprint": {"version": "baseline-v1"}},
                    "candidate_rules": {"fingerprint": {"version": "candidate-v1"}},
                    "filters": {"package_name": "com.example.app", "issue_type": "crash"},
                    "expected": {"change_summary": {"regrouped": 1}},
                },
            ),
            SimpleNamespace(
                case_id="diff_smoke_added_case",
                change_type="added",
                changed_fields=(),
                left_case={},
                right_case={
                    "case_id": "diff_smoke_added_case",
                    "description": "Diff smoke added case",
                    "issue_type": "device_offline",
                    "layer": "identity_semantics",
                    "expectation": "fingerprint_changed",
                    "baseline_rules": {"fingerprint": {"version": "baseline-v1"}},
                    "candidate_rules": {"fingerprint": {"version": "candidate-v2"}},
                    "filters": {"package_name": "com.example.app", "issue_type": "device_offline"},
                    "expected": {"change_summary": {"fingerprint_changed": 1}},
                },
            ),
        ),
    )
    runner_status = runner_status_override or default_runner_status()
    run_detail = {
        "run_id": "run-1",
        "task_id": "task-1",
        "task_name": "Calculator Cold Start",
        "run_status": "failed",
        "planned_device_count": 1,
        "target_device_ids": ["192.168.31.99:5555"],
        "started_by": "cli",
        "created_at": "2025-07-20T09:01:00",
        "started_at": "2025-07-20T09:01:05",
        "finished_at": "2025-07-20T09:02:00",
        "summary": {
            "total_instances": 1,
            "pending_instances": 0,
            "active_instances": 0,
            "success_instances": 0,
            "failed_instances": 1,
            "cancelled_instances": 0,
            "total_issues": 1,
            "first_issue_at": "2025-07-20T09:01:20",
            "notes": [],
        },
        "instance_count": 1,
        "instance_status_counts": {"failed": 1},
        "metadata": {},
        "task": {
            "task_id": "task-1",
            "task_name": "Calculator Cold Start",
            "template_type": "cold_start_loop",
            "package_name": "com.hihonor.calculator",
            "launch_activity": "",
        },
        "report_paths": {"instance-1": str(report_path)},
        "html_report_paths": {"instance-1": str(html_report_path)},
        "instances": [
            {
                "instance_id": "instance-1",
                "device_id": "192.168.31.99:5555",
                "status": "failed",
                "exit_reason": "startup_timeout",
                "result_level": "error",
                "queued_at": "2025-07-20T09:01:00",
                "started_at": "2025-07-20T09:01:05",
                "finished_at": "2025-07-20T09:02:00",
                "duration_seconds": 55.0,
                "issue_count": 1,
                "artifact_count": 0,
                "note": "Cold start timeout after monitoring capture.",
                "highlights": ["startup timeout", "monitoring captured"],
                "report_path": str(report_path),
                "html_report_path": str(html_report_path),
                "execution_log_path": str(execution_log_path),
                "monitoring_backend": "solox",
                "monitoring_profile": "solox",
                "monitoring_snapshot_path": str(snapshot_path),
                "monitoring_trace_path": str(trace_path),
                "monitoring_session_id": "monitoring-session-1",
            }
        ],
    }
    return SimpleNamespace(
        device_service=SimpleNamespace(
            list_device_summaries=lambda: [
                {
                    "device_id": "192.168.31.99:5555",
                    "brand": "HONOR",
                    "model": "Magic",
                    "connection_state": "connected",
                    "availability_state": "idle",
                    "is_online": True,
                    "is_schedulable": True,
                }
            ]
        ),
        task_service=SimpleNamespace(
            list_task_summaries=lambda: [
                {
                    "task_id": "task-1",
                    "task_name": "Calculator Cold Start",
                    "template_type": "cold_start_loop",
                    "package_name": "com.hihonor.calculator",
                    "planned_device_count": 1,
                    "created_at": "2025-07-20T09:00:00",
                }
            ]
        ),
        run_history_service=SimpleNamespace(
            list_runs=lambda limit=20, **kwargs: [
                {
                    "run_id": "run-1",
                    "task_id": "task-1",
                    "task_name": "Calculator Cold Start",
                    "run_status": "failed",
                    "target_device_ids": ["192.168.31.99:5555"],
                    "created_at": "2025-07-20T09:01:00",
                }
            ][:limit],
            get_run_detail=lambda run_id: run_detail if run_id == "run-1" else (_ for _ in ()).throw(ValueError(run_id)),
        ),
        analysis_service=SimpleNamespace(
            list_top_issues=lambda limit=20, **kwargs: [issue][:limit]
        ),
        attribution_service=SimpleNamespace(
            attribute_issue_group=lambda item: {
                "fingerprint": item.fingerprint.value,
                "issue_type": item.issue_type.value,
                "title": item.title,
                "direction": "environment",
                "direction_label": "环境/设备侧",
                "confidence": "medium",
                "confidence_score": 0.76,
                "summary": "startup timeout matched device pressure evidence",
                "rule_version": "v2",
                "matched_rule_id": "startup_timeout_device_pressure",
                "matched_rule_name": "Startup timeout with device pressure",
                "matched_rule_ids": ["startup_timeout_device_pressure", "activity_launch_gap"],
                "evidence_summary": "activity launch gap and timeout marker",
                "recommended_next_steps": ["check device load", "rerun cold start"],
                "review_notes": ["confirm against monitoring snapshot"],
                "score": 7,
                "sample_event_ids": list(item.sample_event_ids),
                "hits": [
                    {
                        "field": "evidence_signals",
                        "keyword": "activity_launch_gap",
                        "evidence": "activity_launch_gap",
                        "score": 4,
                    }
                ],
                "notes": [],
            }
        ),
        release_submission_service=release_submission_service,
        admission_case_service=admission_case_service,
        collaboration_service=collaboration_service,
        integration_outbox_service=integration_outbox_service,
        rule_replay_golden_suite_service=SimpleNamespace(
            list_cases=lambda **kwargs: golden_listing,
            get_case=lambda case_id, **kwargs: golden_case if case_id == "crash_regroup_ignore_raw_key" else golden_case,
            diff_suites=lambda **kwargs: golden_diff,
        ),
        rule_review_report_service=SimpleNamespace(
            list_baselines=lambda: (baseline,),
            show_latest_baseline_audit=lambda baseline_key, version_limit=3: latest_view,
            get_baseline=lambda baseline_key: baseline,
            get_report=lambda report_id: report,
            list_baseline_history=lambda baseline_key: history,
        ),
        quality_gate_service=quality_gate_service,
        unattended_runner_service=SimpleNamespace(
            show_status=lambda: runner_status,
        ),
    )
