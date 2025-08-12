from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest

from stability.app import AdmissionCaseService, IntegrationOutboxService
from stability.domain import (
    AggregatedIssue,
    ComparisonScope,
    IssueFingerprint,
    IssueType,
    RegressionResult,
    SeverityLevel,
)


class AdmissionCaseServiceTest(unittest.TestCase):
    def test_get_case_aggregates_execution_top_issues_regression_and_quality_gate(self) -> None:
        quality_gate = SimpleNamespace(
            baseline_key="device_offline_default",
            report_id="review_report_1",
            report_name="Device Offline Default",
            evaluated_at=datetime.fromisoformat("2025-07-23T09:30:00"),
            automatic_decision="conditional_pass",
            final_decision="conditional_pass",
            final_review_opinion="Need manual review because one metric worsened.",
            performance_risk_items=(
                SimpleNamespace(
                    risk_key="fps_regression",
                    category="performance",
                    severity="medium",
                    summary="FPS P95 worsened by 10%.",
                    details={"metric_key": "fps_p95"},
                    source="performance_trend_service",
                    blocks_admission=False,
                ),
            ),
            override=None,
            source_links={"report_detail_path": "runtime/reports/review_report_1/report.json"},
        )
        service = AdmissionCaseService(
            rule_review_report_service=_FakeRuleReviewReportService(),
            quality_gate_service=SimpleNamespace(get_quality_gate=lambda baseline_key: quality_gate),
            run_history_service=SimpleNamespace(
                list_runs=lambda limit=20, **kwargs: [
                    {
                        "run_id": "run-2",
                        "task_id": "task-1",
                        "task_name": "Calculator Cold Start",
                        "run_status": "failed",
                        "package_name": "com.hihonor.calculator",
                        "template_type": "cold_start_loop",
                        "target_device_ids": ["device-a"],
                        "created_at": "2025-07-23T09:00:00",
                        "has_issue": True,
                    },
                    {
                        "run_id": "run-1",
                        "task_id": "task-1",
                        "task_name": "Calculator Cold Start",
                        "run_status": "success",
                        "package_name": "com.hihonor.calculator",
                        "template_type": "cold_start_loop",
                        "target_device_ids": ["device-a"],
                        "created_at": "2025-07-22T09:00:00",
                        "has_issue": False,
                    },
                ][:limit]
            ),
            analysis_service=SimpleNamespace(
                list_top_issues=lambda limit=5, **kwargs: [
                    AggregatedIssue(
                        fingerprint=IssueFingerprint("ifp_crash", rule_version="v1"),
                        issue_type=IssueType.CRASH,
                        title="Calculator crashed on launch",
                        severity=SeverityLevel.HIGH,
                        first_seen_at=datetime.fromisoformat("2025-07-22T09:00:00"),
                        last_seen_at=datetime.fromisoformat("2025-07-23T09:05:00"),
                        occurrence_count=3,
                        affected_run_count=2,
                        affected_device_count=1,
                        affected_scenario_count=1,
                        affected_version_count=1,
                        affected_packages=("com.hihonor.calculator",),
                        affected_devices=("device-a",),
                        affected_scenarios=("cold_start_loop",),
                        affected_versions=("1.0.0(100)",),
                    )
                ][:limit]
            ),
            regression_service=SimpleNamespace(
                evaluate_regression=lambda **kwargs: RegressionResult(
                    dimension="version",
                    left_scope=ComparisonScope(dimension="version", value="1.0.0(100)", label="1.0.0(100)"),
                    right_scope=ComparisonScope(dimension="version", value="1.0.1(101)", label="1.0.1(101)"),
                    overall_result="suspected_regression",
                    issue_result_summary={"suspected_regression": 1},
                    metric_result_summary={"worsened_count": 1, "available": True},
                    reasons=("Crash occurrence increased.",),
                    comparability_notes=(),
                    metrics=(),
                )
            ),
        )

        result = service.get_case("device_offline_default")

        self.assertEqual(result.case_id, "admission_case:device_offline_default:review_report_1")
        self.assertEqual(result.execution_summary.total_runs, 2)
        self.assertEqual(result.execution_summary.failed_run_count, 1)
        self.assertEqual(result.top_issues[0].fingerprint, "ifp_crash")
        self.assertEqual(result.regression_summary.overall_result, "suspected_regression")
        self.assertEqual(result.scenario_coverage.coverage_state, "covered")
        self.assertEqual(result.performance_risk_items[0].risk_key, "fps_regression")
        self.assertEqual(result.quality_gate.final_decision, "conditional_pass")
        self.assertEqual(result.final_review_opinion, "Need manual review because one metric worsened.")
        self.assertEqual(result.final_decision, "conditional_pass")
        self.assertEqual(result.error_code, "CONDITIONAL_PASS")
        self.assertEqual(result.case_id, "admission_case:device_offline_default:review_report_1")
        self.assertEqual(result.case_trace["case_id"], "admission_case:device_offline_default:review_report_1")
        self.assertEqual(result.case_trace["decision"]["final_decision"], "conditional_pass")
        self.assertEqual(result.case_trace["decision"]["error_code"], "CONDITIONAL_PASS")
        self.assertEqual(result.case_trace["evidence"]["top_issue_count"], 1)
        self.assertEqual(result.contract_version, "admission_case.v1")
        self.assertEqual(result.status, "open")
        self.assertGreaterEqual(result.revision, 1)
        self.assertEqual(result.ci_contract["contract_version"], "admission_case.v1")
        self.assertEqual(result.source_refs["report"]["report_id"], "review_report_1")

    def test_get_case_gracefully_handles_missing_latest_baseline_audit(self) -> None:
        service = AdmissionCaseService(
            rule_review_report_service=_FakeRuleReviewReportService(missing_latest_audit=True),
            quality_gate_service=SimpleNamespace(
                get_quality_gate=lambda baseline_key: SimpleNamespace(
                    baseline_key=baseline_key,
                    final_decision="pass",
                    final_review_opinion="Auto pass without latest audit.",
                    performance_risk_items=(),
                    override=None,
                    source_links={},
                )
            ),
        )

        result = service.get_case("device_offline_default")

        self.assertEqual(result.baseline_key, "device_offline_default")
        self.assertEqual(result.latest_audit_summary, {})
        self.assertEqual(result.final_review_opinion, "Auto pass without latest audit.")

    def test_get_case_without_quality_gate_records_unknown_decision_contract(self) -> None:
        service = AdmissionCaseService(
            rule_review_report_service=_FakeRuleReviewReportService(),
            quality_gate_service=None,
        )

        result = service.get_case("device_offline_default")

        self.assertEqual(result.final_decision, "unknown")
        self.assertEqual(result.error_code, "NO_QUALITY_GATE")
        self.assertEqual(result.case_trace["decision"]["final_decision"], "unknown")

    def test_get_case_persists_process_fields_and_keeps_revision_stable_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AdmissionCaseService(
                root_dir=Path(temp_dir) / "admission_cases",
                rule_review_report_service=_FakeRuleReviewReportService(),
                quality_gate_service=SimpleNamespace(
                    get_quality_gate=lambda baseline_key: SimpleNamespace(
                        baseline_key=baseline_key,
                        report_id="review_report_1",
                        report_name="Device Offline Default",
                        final_decision="pass",
                        final_review_opinion="Approved.",
                        performance_risk_items=(),
                        override=None,
                        source_links={},
                    )
                ),
            )

            first = service.get_case("device_offline_default")
            first_path = Path(temp_dir) / "admission_cases" / first.case_id / "case.json"
            stored_payload = json.loads(first_path.read_text(encoding="utf-8"))
            stored_payload["status"] = "reviewing"
            stored_payload["assignee_id"] = "tester"
            stored_payload["assignee_display_name"] = "Tester"
            stored_payload["final_reviewer_id"] = "admin"
            stored_payload["final_reviewer_display_name"] = "Admin"
            first_path.write_text(json.dumps(stored_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            second = service.get_case("device_offline_default")
            third = service.get_case("device_offline_default")

        self.assertEqual(second.status, "reviewing")
        self.assertEqual(second.assignee_id, "tester")
        self.assertEqual(second.final_reviewer_id, "admin")
        self.assertEqual(second.revision, first.revision)
        self.assertEqual(third.revision, second.revision)

    def test_update_case_collaboration_enforces_state_machine_and_records_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AdmissionCaseService(
                root_dir=Path(temp_dir) / "admission_cases",
                rule_review_report_service=_FakeRuleReviewReportService(),
                quality_gate_service=SimpleNamespace(
                    get_quality_gate=lambda baseline_key: SimpleNamespace(
                        baseline_key=baseline_key,
                        report_id="review_report_1",
                        report_name="Device Offline Default",
                        automatic_decision="conditional_pass",
                        final_decision="conditional_pass",
                        final_review_opinion="Need review.",
                        performance_risk_items=(),
                        override=None,
                        source_links={},
                    )
                ),
            )

            case = service.get_case("device_offline_default")
            with self.assertRaises(ValueError):
                service.update_case_collaboration(
                    "device_offline_default",
                    status="approved",
                    action="transition",
                    changed_by="tester",
                )

            updated = service.update_case_collaboration(
                "device_offline_default",
                status="assigned",
                assignee_id="developer",
                assignee_display_name="Developer",
                action="assign",
                changed_by="tester",
                changed_by_display_name="Tester",
                reason="owner assigned",
                audit_source={
                    "audit_event_id": "asl.audit_event.v1:abc",
                    "permission_check_id": "asl.permission_check.v1:def",
                    "resolved_session_id": "asl.session_id.v1:123",
                },
            )

        self.assertEqual(case.status, "open")
        self.assertEqual(updated.status, "assigned")
        self.assertEqual(len(updated.lifecycle_events), 2)
        self.assertEqual(updated.lifecycle_events[-1].from_status, "open")
        self.assertEqual(updated.lifecycle_events[-1].to_status, "assigned")
        self.assertEqual(updated.role_audit_entries[-1].role_name, "assignee")
        self.assertEqual(updated.role_audit_entries[-1].to_actor_id, "developer")
        self.assertEqual(updated.role_audit_entries[-1].audit_event_id, "asl.audit_event.v1:abc")

    def test_case_contract_event_is_published_from_case_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox")
            service = AdmissionCaseService(
                root_dir=Path(temp_dir) / "admission_cases",
                rule_review_report_service=_FakeRuleReviewReportService(),
                quality_gate_service=SimpleNamespace(
                    get_quality_gate=lambda baseline_key: SimpleNamespace(
                        baseline_key=baseline_key,
                        report_id="review_report_1",
                        report_name="Device Offline Default",
                        automatic_decision="conditional_pass",
                        final_decision="conditional_pass",
                        final_review_opinion="Need review.",
                        performance_risk_items=(),
                        override=None,
                        source_links={},
                    )
                ),
                outbox_service=outbox,
            )

            result = service.get_case("device_offline_default")
            events = outbox.list_events(limit=10)

        self.assertEqual(result.ci_contract["decision_source"], "admission_case")
        self.assertEqual(events[0].event_type, "admission_case.updated")
        self.assertEqual(events[0].payload["case_id"], result.case_id)
        self.assertEqual(events[0].payload["status"], "open")
        self.assertEqual(events[0].payload["case_revision"], result.revision)

    def test_export_admission_case_payload_returns_stable_json_ready_contract(self) -> None:
        quality_gate = SimpleNamespace(
            baseline_key="device_offline_default",
            report_id="review_report_1",
            report_name="Device Offline Default",
            evaluated_at=datetime.fromisoformat("2025-07-23T09:30:00"),
            automatic_decision="conditional_pass",
            final_decision="conditional_pass",
            final_review_opinion="Need review.",
            performance_risk_items=(
                SimpleNamespace(
                    risk_key="fps_regression",
                    category="performance",
                    severity="medium",
                    summary="FPS P95 worsened by 10%.",
                    details={"metric_key": "fps_p95"},
                    source="performance_trend_service",
                    blocks_admission=False,
                ),
            ),
            override=None,
            source_links={"report_detail_path": "runtime/reports/review_report_1/report.json"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AdmissionCaseService(
                root_dir=Path(temp_dir) / "admission_cases",
                rule_review_report_service=_FakeRuleReviewReportService(),
                quality_gate_service=SimpleNamespace(get_quality_gate=lambda baseline_key: quality_gate),
                run_history_service=SimpleNamespace(
                    list_runs=lambda limit=20, **kwargs: [
                        {
                            "run_id": "run-2",
                            "task_id": "task-1",
                            "task_name": "Calculator Cold Start",
                            "run_status": "failed",
                            "package_name": "com.hihonor.calculator",
                            "template_type": "cold_start_loop",
                            "target_device_ids": ["device-a"],
                            "created_at": "2025-07-23T09:00:00",
                            "has_issue": True,
                        }
                    ][:limit]
                ),
            )

            service.get_case("device_offline_default")
            case = service.update_case_collaboration(
                "device_offline_default",
                status="assigned",
                assignee_id="developer",
                assignee_display_name="Developer",
                final_reviewer_id="reviewer",
                final_reviewer_display_name="Reviewer",
                action="assign",
                changed_by="tester",
                reason="contract owner assigned",
                audit_source={
                    "audit_event_id": "audit-1",
                    "permission_check_id": "permission-1",
                    "resolved_session_id": "session-1",
                    "changed_at": datetime.fromisoformat("2025-07-24T10:00:00"),
                },
            )
            payload = service.export_admission_case_payload(case=case)
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        self.assertIn('"case_id": "admission_case:device_offline_default:review_report_1"', encoded)
        self.assertEqual(payload["contract_version"], "admission_case.v1")
        self.assertEqual(payload["case_id"], "admission_case:device_offline_default:review_report_1")
        self.assertEqual(payload["baseline_key"], "device_offline_default")
        self.assertEqual(payload["report_id"], "review_report_1")
        self.assertEqual(payload["status"], "assigned")
        self.assertGreaterEqual(payload["revision"], 2)
        self.assertEqual(payload["decision"]["final_decision"], "conditional_pass")
        self.assertEqual(payload["decision"]["error_code"], "CONDITIONAL_PASS")
        self.assertEqual(payload["error_code"], "CONDITIONAL_PASS")
        self.assertEqual(payload["assignee"]["actor_id"], "developer")
        self.assertEqual(payload["final_reviewer"]["actor_id"], "reviewer")
        self.assertEqual(payload["evidence_blocks"]["execution_summary"]["latest_run_created_at"], "2025-07-23T09:00:00")
        self.assertEqual(payload["evidence_blocks"]["performance_risk_items"][0]["risk_key"], "fps_regression")
        self.assertEqual(payload["case_trace"]["decision"]["final_decision"], "conditional_pass")
        self.assertEqual(payload["source_refs"]["report"]["report_id"], "review_report_1")
        self.assertEqual(payload["ci_contract"]["decision_source"], "admission_case")
        self.assertEqual(payload["lifecycle"]["events"][-1]["changed_at"], "2025-07-24T10:00:00")
        self.assertEqual(payload["role_audit"]["entries"][-1]["audit_event_id"], "audit-1")

    def test_list_admission_case_payloads_returns_list_contract(self) -> None:
        service = AdmissionCaseService(
            rule_review_report_service=_FakeRuleReviewReportService(),
            quality_gate_service=None,
        )

        payload = service.list_admission_case_payloads(limit=10)

        self.assertEqual(payload["contract_version"], "admission_case_list.v1")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["entries"][0]["contract_version"], "admission_case.v1")
        self.assertEqual(payload["entries"][0]["baseline_key"], "device_offline_default")

    def test_export_admission_report_payload_collects_auditable_contract_sections(self) -> None:
        quality_gate = SimpleNamespace(
            baseline_key="device_offline_default",
            report_id="review_report_1",
            report_name="Device Offline Default",
            automatic_decision="conditional_pass",
            final_decision="conditional_pass",
            final_review_opinion="Need manual review.",
            triggered_rules=(
                SimpleNamespace(
                    rule_key="review_warnings",
                    decision_on_trigger="conditional_pass",
                    message="1 conditional snapshot.",
                    source="report.summary.decision_counts.conditional_pass",
                    observed_value=1,
                    threshold=0,
                ),
            ),
            failure_reasons=("1 conditional snapshot.",),
            risk_items=(),
            performance_risk_items=(
                SimpleNamespace(
                    risk_key="fps_regression",
                    category="performance",
                    severity="medium",
                    summary="FPS P95 worsened by 10%.",
                    details={"metric_key": "fps_p95"},
                    source="performance_trend_service",
                    blocks_admission=False,
                ),
            ),
            coverage_gaps=(),
            override=None,
            source_links={"report_markdown_path": "runtime/reports/review_report_1/summary.md"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AdmissionCaseService(
                root_dir=Path(temp_dir) / "admission_cases",
                rule_review_report_service=_FakeRuleReviewReportService(),
                quality_gate_service=SimpleNamespace(get_quality_gate=lambda baseline_key: quality_gate),
                analysis_service=SimpleNamespace(
                    list_top_issues=lambda limit=5, **kwargs: [
                        AggregatedIssue(
                            fingerprint=IssueFingerprint("ifp_crash", rule_version="v1"),
                            issue_type=IssueType.CRASH,
                            title="Calculator crashed on launch",
                            severity=SeverityLevel.HIGH,
                            first_seen_at=datetime.fromisoformat("2025-07-22T09:00:00"),
                            last_seen_at=datetime.fromisoformat("2025-07-23T09:05:00"),
                            occurrence_count=3,
                            affected_run_count=2,
                            affected_device_count=1,
                            affected_scenario_count=1,
                            affected_version_count=1,
                            affected_packages=("com.hihonor.calculator",),
                            affected_devices=("device-a",),
                            affected_scenarios=("cold_start_loop",),
                            affected_versions=("1.0.0(100)",),
                        )
                    ][:limit]
                ),
            )

            payload = service.export_admission_report_payload(
                "device_offline_default",
                generated_at=datetime.fromisoformat("2025-07-24T10:00:00"),
            )

        self.assertEqual(payload["report_contract_version"], "admission_report.v1")
        self.assertEqual(payload["report_id"], "admission_report:device_offline_default:review_report_1:r1")
        self.assertEqual(payload["baseline_key"], "device_offline_default")
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["final_decision"], "conditional_pass")
        self.assertEqual(payload["risk_level"], "high")
        self.assertEqual(payload["quality_gate_summary"]["triggered_rule_count"], 1)
        self.assertEqual(payload["top_issue_summary"]["issue_count"], 1)
        self.assertEqual(payload["top_issue_summary"]["highest_severity"], "high")
        self.assertEqual(payload["performance_risk_summary"]["risk_count"], 1)
        self.assertFalse(payload["manual_overrides"]["has_override"])
        self.assertTrue(payload["external_sync_summary"]["ci_contract_available"])
        self.assertEqual(payload["evidence_refs"]["top_issue_fingerprints"], ["ifp_crash"])
        self.assertEqual(payload["generated_at"], "2025-07-24T10:00:00")
        self.assertIn("Collect final reviewer confirmation", payload["recommended_actions"][0])

    def test_export_admission_report_payload_includes_manual_override_collaboration_and_ci_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            override = SimpleNamespace(
                override_id="override-1",
                baseline_key="device_offline_default",
                automatic_decision="fail",
                final_decision="pass",
                reason="Release waiver approved.",
                created_at=datetime.fromisoformat("2025-07-24T09:00:00"),
                created_by="reviewer",
                session_source="query:as_actor",
                audit_source={"request_path": "/api/admission/actions/override"},
                comment="Linked waiver.",
                evidence_paths=("runtime/release-waiver.md",),
            )
            outbox = IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox")
            service = AdmissionCaseService(
                root_dir=Path(temp_dir) / "admission_cases",
                rule_review_report_service=_FakeRuleReviewReportService(),
                quality_gate_service=SimpleNamespace(
                    get_quality_gate=lambda baseline_key: SimpleNamespace(
                        baseline_key=baseline_key,
                        report_id="review_report_1",
                        report_name="Device Offline Default",
                        automatic_decision="fail",
                        final_decision="pass",
                        final_review_opinion="Manual pass with waiver.",
                        triggered_rules=(),
                        failure_reasons=("Failure overridden.",),
                        risk_items=(),
                        performance_risk_items=(),
                        coverage_gaps=(),
                        override=override,
                        source_links={},
                    )
                ),
                outbox_service=outbox,
            )

            service.get_case("device_offline_default")
            service.update_case_collaboration(
                "device_offline_default",
                status="assigned",
                assignee_id="developer",
                assignee_display_name="Developer",
                final_reviewer_id="reviewer",
                final_reviewer_display_name="Reviewer",
                action="assign",
                changed_by="coordinator",
                reason="handoff",
                audit_source={
                    "audit_event_id": "audit-1",
                    "permission_check_id": "permission-1",
                    "resolved_session_id": "session-1",
                },
            )
            case = service.get_case("device_offline_default")
            payload = service.export_admission_report_payload(case=case)

        self.assertTrue(payload["manual_overrides"]["has_override"])
        self.assertEqual(payload["manual_overrides"]["override_id"], "override-1")
        self.assertEqual(payload["manual_overrides"]["evidence_paths"], ["runtime/release-waiver.md"])
        self.assertEqual(payload["collaboration_summary"]["status"], "assigned")
        self.assertEqual(payload["collaboration_summary"]["assignee"]["actor_id"], "developer")
        self.assertEqual(payload["collaboration_summary"]["latest_lifecycle_event"]["audit_event_id"], "audit-1")
        self.assertEqual(payload["external_sync_summary"]["ci_contract"]["decision_source"], "admission_case")
        self.assertEqual(payload["external_sync_summary"]["ci_contract"]["final_decision"], "pass")
        self.assertIn("Keep manual override evidence", " ".join(payload["recommended_actions"]))

    def test_export_admission_report_payload_is_stable_when_optional_sources_are_missing(self) -> None:
        service = AdmissionCaseService(
            rule_review_report_service=_FakeRuleReviewReportService(missing_latest_audit=True),
            quality_gate_service=None,
        )

        payload = service.export_admission_report_payload(
            "device_offline_default",
            generated_at=datetime.fromisoformat("2025-07-24T11:00:00"),
        )

        self.assertEqual(payload["report_contract_version"], "admission_report.v1")
        self.assertEqual(payload["final_decision"], "unknown")
        self.assertEqual(payload["risk_level"], "unknown")
        self.assertFalse(payload["quality_gate_summary"]["available"])
        self.assertEqual(payload["top_issue_summary"]["issue_count"], 0)
        self.assertEqual(payload["performance_risk_summary"]["risk_count"], 0)
        self.assertFalse(payload["manual_overrides"]["has_override"])
        self.assertFalse(payload["source_refs"]["latest_audit"]["available"])
        self.assertEqual(payload["evidence_refs"]["latest_audit_detail_path"], "")
        self.assertIn("Run quality gate evaluation", payload["recommended_actions"][0])


class _FakeRuleReviewReportService:
    def __init__(self, *, missing_latest_audit: bool = False) -> None:
        self._baseline = SimpleNamespace(
            baseline_key="device_offline_default",
            report_id="review_report_1",
            updated_at=datetime.fromisoformat("2025-07-23T10:00:00"),
            updated_by="tester",
        )
        self._missing_latest_audit = missing_latest_audit
        self._report = SimpleNamespace(
            report_id="review_report_1",
            name="Device Offline Default",
            created_at=datetime.fromisoformat("2025-07-23T09:10:00"),
            filters={
                "task_id": "task-1",
                "package_name": "com.hihonor.calculator",
                "template_type": "cold_start_loop",
                "dimension": "version",
                "left_value": "1.0.0(100)",
                "right_value": "1.0.1(101)",
            },
            summary={"decision_counts": {"conditional_pass": 1}},
        )
        self._latest_audit = SimpleNamespace(summary={"action_counts": {"set": 1}})

    def list_baselines(self):
        return (self._baseline,)

    def get_baseline(self, baseline_key: str):
        if baseline_key != self._baseline.baseline_key:
            raise ValueError(baseline_key)
        return self._baseline

    def get_report(self, report_id: str):
        if report_id != self._report.report_id:
            raise ValueError(report_id)
        return self._report

    def show_latest_baseline_audit(self, *, baseline_key: str, version_limit: int = 10):
        if baseline_key != self._baseline.baseline_key:
            raise ValueError(baseline_key)
        if self._missing_latest_audit:
            raise ValueError(f"No latest baseline audit available: {baseline_key}")
        return self._latest_audit


if __name__ == "__main__":
    unittest.main()
