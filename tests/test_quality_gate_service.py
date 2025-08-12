from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from stability.app import QualityGateService


class QualityGateServiceTest(unittest.TestCase):
    def test_get_quality_gate_returns_first_class_admission_result(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = QualityGateService(
                rule_review_report_service=_FakeRuleReviewReportService(
                    report_summary={
                        "snapshot_count": 2,
                        "decision_counts": {"conditional_pass": 1},
                        "high_risk_family_count": 2,
                        "golden_suite_case_count_total": 4,
                        "golden_suite_failed_case_count_total": 0,
                    }
                ),
                root_dir=Path(temp_dir),
            )

            result = service.get_quality_gate("device_offline_default")

            self.assertEqual(result.baseline_key, "device_offline_default")
            self.assertEqual(result.automatic_decision, "conditional_pass")
            self.assertEqual(result.final_decision, "conditional_pass")
            self.assertEqual(result.current_report_golden_suite["case_count_total"], 4)
            self.assertEqual(len(result.triggered_rules), 2)
            self.assertEqual(result.triggered_rules[0].rule_key, "review_warnings")
            self.assertEqual(result.triggered_rules[1].rule_key, "high_risk_families")
            self.assertEqual(len(result.risk_items), 1)
            self.assertIsNone(result.override)

    def test_record_override_keeps_auto_decision_and_final_decision_separate(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = QualityGateService(
                rule_review_report_service=_FakeRuleReviewReportService(
                    report_summary={
                        "snapshot_count": 2,
                        "decision_counts": {"fail": 1},
                        "high_risk_family_count": 0,
                        "golden_suite_case_count_total": 4,
                        "golden_suite_failed_case_count_total": 0,
                    }
                ),
                root_dir=Path(temp_dir),
            )

            override = service.record_override(
                baseline_key="device_offline_default",
                final_decision="pass",
                reason="Allow ship with tracked exception.",
                created_by="reviewer",
                session_source="query:as_actor",
                audit_source={"request_path": "/api/admission/actions/override"},
                comment="Linked to release waiver.",
                evidence_paths=("runtime/release-waiver.md",),
            )
            result = service.get_quality_gate("device_offline_default")

            self.assertEqual(override.automatic_decision, "fail")
            self.assertEqual(override.final_decision, "pass")
            self.assertEqual(result.automatic_decision, "fail")
            self.assertEqual(result.final_decision, "pass")
            self.assertIsNotNone(result.override)
            self.assertEqual(result.override.reason, "Allow ship with tracked exception.")
            self.assertEqual(result.override.created_by, "reviewer")
            self.assertEqual(result.override.session_source, "query:as_actor")
            self.assertEqual(result.override.audit_source["request_path"], "/api/admission/actions/override")
            self.assertTrue((Path(temp_dir) / "overrides.json").exists())

    def test_performance_risks_are_layered_without_replacing_stability_decision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = QualityGateService(
                rule_review_report_service=_FakeRuleReviewReportService(
                    report_summary={
                        "snapshot_count": 2,
                        "decision_counts": {},
                        "high_risk_family_count": 0,
                        "golden_suite_case_count_total": 4,
                        "golden_suite_failed_case_count_total": 0,
                    }
                ),
                root_dir=Path(temp_dir),
                performance_risk_provider=lambda **kwargs: (
                    {
                        "risk_key": "fps_regression",
                        "category": "performance",
                        "severity": "medium",
                        "summary": "FPS P95 worsened by 12%.",
                        "details": {"metric": "fps_p95", "delta_ratio": 0.12},
                        "source": "regression_snapshot",
                    },
                ),
            )

            result = service.get_quality_gate("device_offline_default")

            self.assertEqual(result.automatic_decision, "pass")
            self.assertEqual(result.final_decision, "pass")
            self.assertEqual(len(result.performance_risk_items), 1)
            self.assertEqual(result.performance_risk_items[0].risk_key, "fps_regression")
            self.assertEqual(result.triggered_rules[-1].rule_key, "performance_risks")
            self.assertEqual(result.triggered_rules[-1].decision_on_trigger, "risk_only")

    def test_get_quality_gate_gracefully_handles_missing_latest_baseline_audit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = QualityGateService(
                rule_review_report_service=_FakeRuleReviewReportService(
                    report_summary={
                        "snapshot_count": 2,
                        "decision_counts": {"conditional_pass": 1},
                        "high_risk_family_count": 0,
                        "golden_suite_case_count_total": 0,
                        "golden_suite_failed_case_count_total": 0,
                    },
                    missing_latest_audit=True,
                ),
                root_dir=Path(temp_dir),
            )

            result = service.get_quality_gate("device_offline_default")

            self.assertEqual(result.baseline_key, "device_offline_default")
            self.assertEqual(result.automatic_decision, "conditional_pass")
            self.assertEqual(result.latest_audit_summary, {})
            self.assertEqual(result.current_report_golden_suite["case_count_total"], 0)


class _FakeRuleReviewReportService:
    def __init__(self, *, report_summary: dict[str, object], missing_latest_audit: bool = False) -> None:
        self._baseline = SimpleNamespace(
            baseline_key="device_offline_default",
            report_id="review_report_1",
            report_name="Device Offline Default",
            policy_versions=("review-policy-v1",),
            candidate_paths=("config/stability_rules.json",),
            baseline_paths=("config/stability_rules.base.json",),
            report_created_at="2025-07-20T09:00:00",
            updated_at=None,
            updated_by="cli",
        )
        self._report = SimpleNamespace(
            report_id="review_report_1",
            name="Device Offline Default",
            summary=dict(report_summary),
            detail_path="runtime/analysis_review_reports/review_report_1/report.json",
            markdown_path="runtime/analysis_review_reports/review_report_1/summary.md",
            html_path="runtime/analysis_review_reports/review_report_1/report.html",
        )
        self._missing_latest_audit = missing_latest_audit
        self._latest_audit = SimpleNamespace(
            summary={
                "action_counts": {"set": 1},
                "current_report_golden_suite": {
                    "snapshot_count": 1,
                    "passed_snapshot_count": 1,
                    "failed_snapshot_count": 0,
                    "case_count_total": 4,
                    "passed_case_count_total": 4,
                    "failed_case_count_total": 0,
                    "versions": ["v1"],
                    "suite_paths": ["config/rule_replay_golden_samples.json"],
                    "layer_summaries": {},
                },
            },
            detail_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.json",
            markdown_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/summary.md",
            html_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/report.html",
            index_path="runtime/analysis_review_report_baseline_audits/latest/device_offline_default/index.json",
        )

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
