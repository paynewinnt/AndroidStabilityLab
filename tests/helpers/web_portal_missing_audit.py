from __future__ import annotations

from types import SimpleNamespace

from stability.app import AdmissionCaseService, QualityGateService

from .web_portal_fakes_collaboration import _FakeCollaborationService
from .web_portal_fakes_integration import _FakeIntegrationOutboxService


def bundle_with_missing_latest_audit() -> object:
    baseline = SimpleNamespace(
        baseline_key="device_offline_audit_auto_smoke",
        report_id="review_report_missing_audit",
        report_name="Missing Audit Baseline",
        policy_versions=("review-policy-v1",),
        candidate_paths=("config/stability_rules.json",),
        baseline_paths=("config/stability_rules.base.json",),
        report_created_at="2025-07-23T09:00:00",
        updated_at=None,
        updated_by="cli",
        latest_audit_id="",
        latest_audit_detail_path="",
        latest_audit_markdown_path="",
        latest_audit_html_path="",
        latest_audit_index_path="",
        latest_audit_version_count=0,
    )
    report = SimpleNamespace(
        report_id="review_report_missing_audit",
        name="Missing Audit Baseline",
        created_at=None,
        created_by="cli",
        filters={"task_id": "task-1", "template_type": "cold_start_loop"},
        summary={
            "snapshot_count": 1,
            "decision_counts": {"conditional_pass": 1},
            "high_risk_family_count": 0,
            "golden_suite_case_count_total": 0,
            "golden_suite_failed_case_count_total": 0,
        },
        detail_path="runtime/analysis_review_reports/review_report_missing_audit/report.json",
        markdown_path="runtime/analysis_review_reports/review_report_missing_audit/summary.md",
        html_path="runtime/analysis_review_reports/review_report_missing_audit/report.html",
    )

    class _MissingAuditRuleReviewReportService:
        def list_baselines(self):
            return (baseline,)

        def get_baseline(self, baseline_key: str):
            if baseline_key != baseline.baseline_key:
                raise ValueError(baseline_key)
            return baseline

        def get_report(self, report_id: str):
            if report_id != report.report_id:
                raise ValueError(report_id)
            return report

        def show_latest_baseline_audit(self, *, baseline_key: str, version_limit: int = 10):
            raise ValueError(f"No latest baseline audit available: {baseline_key}")

        def list_baseline_history(self, baseline_key: str):
            return ()

    report_service = _MissingAuditRuleReviewReportService()
    quality_gate_service = QualityGateService(rule_review_report_service=report_service)
    admission_case_service = AdmissionCaseService(
        rule_review_report_service=report_service,
        quality_gate_service=quality_gate_service,
    )
    return SimpleNamespace(
        web_portal_config={"bound_host": "127.0.0.1", "allow_remote_access": False},
        device_service=SimpleNamespace(list_device_summaries=lambda: []),
        task_service=SimpleNamespace(list_task_summaries=lambda: []),
        run_history_service=SimpleNamespace(list_runs=lambda limit=8, **kwargs: []),
        analysis_service=SimpleNamespace(list_top_issues=lambda limit=8, **kwargs: []),
        rule_review_report_service=report_service,
        quality_gate_service=quality_gate_service,
        admission_case_service=admission_case_service,
        collaboration_service=_FakeCollaborationService(),
        integration_outbox_service=_FakeIntegrationOutboxService(),
        rule_replay_golden_suite_service=SimpleNamespace(
            list_cases=lambda **kwargs: SimpleNamespace(
                suite_path="config/rule_replay_golden_samples.json",
                suite_version="v1",
                case_count=0,
                layer_counts={},
                issue_type_counts={},
                expectation_counts={},
                filters={},
                cases=(),
            ),
            get_case=lambda case_id, **kwargs: SimpleNamespace(
                summary=SimpleNamespace(case_id=case_id),
                payload={},
                suite_path="",
                suite_version="",
            ),
            diff_suites=lambda **kwargs: SimpleNamespace(
                left_path="",
                right_path="",
                left_suite_version="",
                right_suite_version="",
                diff_count=0,
                change_counts={},
                entries=(),
            ),
        ),
        unattended_runner_service=SimpleNamespace(
            show_status=lambda: SimpleNamespace(
                observed_at=None,
                root_dir="runtime/unattended_runner",
                lock_path="runtime/unattended_runner/runner.lock",
                heartbeat_path="runtime/unattended_runner/runner_status.json",
                daily_report_paths={},
                latest_daily_report={},
                weekly_report_paths={},
                latest_weekly_report={},
                lock_present=False,
                heartbeat_present=False,
                lock_state="released",
                status="idle",
                pid=None,
                started_at=None,
                finished_at=None,
                last_heartbeat_at=None,
                heartbeat_age_seconds=None,
                stale_after_seconds=300,
                is_stale=False,
                interval_seconds=60,
                max_iterations=0,
                task_id="",
                force=False,
                cycle_count=0,
                active_cycle_index=0,
                stopped_reason="",
                last_patrol={},
                recent_patrols=(),
            )
        ),
    )
