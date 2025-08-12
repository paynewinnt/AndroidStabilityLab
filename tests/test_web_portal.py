from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import quote, urlencode

from stability.app import TaskService
from stability.domain import TaskDefinition, TaskTargetApp, TaskTemplateType
from stability.repositories import InMemoryTaskRepository
from stability.web import WebPortalApplication
from tests.helpers import web_portal as web_portal_helpers
from tests.helpers.web_portal import _FakeIntegrationOutboxService


class WebPortalApplicationTest(unittest.TestCase):
    def test_admission_detail_shows_warning_when_latest_audit_is_missing(self) -> None:
        bundle = self._bundle_with_missing_latest_audit()
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/admission/baseline/device_offline_audit_auto_smoke")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Latest Audit 暂不可用", html)
        self.assertIn("device_offline_audit_auto_smoke", html)

    def test_admission_api_returns_golden_suite_summary(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/admission")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["auto_decision_counts"]["conditional_pass"], 1)
        self.assertEqual(payload["summary"]["final_decision_counts"]["conditional_pass"], 1)
        self.assertEqual(payload["summary"]["risk_baseline_count"], 1)
        self.assertEqual(payload["summary"]["coverage_gap_baseline_count"], 0)
        self.assertEqual(payload["summary"]["golden_suite_baseline_count"], 1)
        self.assertEqual(payload["summary"]["golden_suite_failed_case_count_total"], 0)
        baseline = payload["baselines"][0]
        admission_case = baseline["admission_case"]
        quality_gate = baseline["evidence"]["quality_gate"]
        self.assertNotIn("final_decision", baseline)
        self.assertEqual(quality_gate["automatic_decision"], "conditional_pass")
        self.assertEqual(admission_case["final_decision"], "conditional_pass")
        self.assertEqual(admission_case["error_code"], "CONDITIONAL_PASS")
        self.assertEqual(admission_case["case_id"], "admission_case:device_offline_default:review_report_1")
        self.assertEqual(admission_case["contract_version"], "admission_case.v1")
        self.assertEqual(admission_case["status"], "open")
        self.assertEqual(admission_case["revision"], 1)
        self.assertIn("case_trace", admission_case)
        self.assertIn("source_refs", admission_case)
        self.assertIn("ci_contract", admission_case)
        self.assertEqual(admission_case["execution_summary"]["total_runs"], 2)
        self.assertEqual(admission_case["top_issue_count"], 1)
        self.assertEqual(quality_gate["triggered_rule_count"], 2)
        self.assertEqual(quality_gate["risk_count"], 1)
        self.assertEqual(quality_gate["performance_risk_count"], 1)
        self.assertEqual(admission_case["top_issues"][0]["confirmation_level"], "multi_evidence")
        self.assertEqual(admission_case["performance_risk_items"][0]["threshold_source"], "performance_thresholds.version")
        self.assertEqual(admission_case["performance_risk_items"][0]["matched_scope"]["template_type"], "cold_start_loop")
        self.assertEqual(baseline["evidence"]["golden_suite"]["case_count_total"], 4)

    def test_admission_case_alias_api_returns_stable_contract(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/admission/cases")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        admission_case = payload["baselines"][0]["admission_case"]
        self.assertEqual(admission_case["contract_version"], "admission_case.v1")
        self.assertEqual(admission_case["status"], "open")
        self.assertEqual(admission_case["revision"], 1)
        self.assertEqual(admission_case["source_refs"]["report"]["report_id"], "review_report_1")
        self.assertEqual(admission_case["ci_contract"]["contract_version"], "admission_case.v1")

    def test_admission_detail_api_returns_current_report_and_latest_audit(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/admission/baseline/device_offline_default")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["baseline"]["baseline_key"], "device_offline_default")
        self.assertEqual(payload["admission_case"]["case_id"], "admission_case:device_offline_default:review_report_1")
        self.assertEqual(payload["admission_case"]["contract_version"], "admission_case.v1")
        self.assertEqual(payload["admission_case"]["status"], "open")
        self.assertEqual(payload["admission_case"]["revision"], 1)
        self.assertEqual(payload["admission_case"]["final_decision"], "conditional_pass")
        self.assertEqual(payload["admission_case"]["error_code"], "CONDITIONAL_PASS")
        self.assertIn("case_trace", payload["admission_case"])
        self.assertEqual(payload["admission_case"]["source_refs"]["report"]["report_id"], "review_report_1")
        self.assertEqual(payload["admission_case"]["ci_contract"]["contract_version"], "admission_case.v1")
        self.assertEqual(payload["admission_case"]["execution_summary"]["total_runs"], 2)
        self.assertEqual(payload["admission_case"]["regression_summary"]["overall_result"], "suspected_regression")
        self.assertEqual(payload["admission_case"]["scenario_coverage"]["coverage_state"], "covered")
        self.assertEqual(payload["report"]["report_id"], "review_report_1")
        self.assertNotIn("quality_gate", payload)
        self.assertEqual(payload["evidence"]["quality_gate"]["automatic_decision"], "conditional_pass")
        self.assertEqual(payload["evidence"]["quality_gate"]["final_decision"], "conditional_pass")
        self.assertEqual(payload["evidence"]["quality_gate"]["triggered_rule_count"], 2)
        self.assertEqual(payload["evidence"]["quality_gate"]["risk_count"], 1)
        self.assertEqual(payload["evidence"]["quality_gate"]["performance_risk_items"][0]["threshold_detail"]["max_delta_percent"], 10.0)
        self.assertEqual(payload["evidence"]["quality_gate"]["coverage_gap_count"], 0)
        self.assertEqual(payload["evidence"]["quality_gate"]["triggered_rules"][0]["rule_key"], "review_warnings")
        self.assertEqual(payload["evidence"]["golden_suite"]["case_count_total"], 4)
        self.assertEqual(payload["latest_audit"]["version_count"], 1)
        self.assertEqual(payload["latest_audit"]["versions"][0]["action"], "rollback")
        self.assertEqual(payload["filters"]["history_count_total"], 2)
        self.assertEqual(payload["filters"]["history_count_filtered"], 2)
        self.assertEqual(payload["status_summary"]["review"], "ready")
        self.assertEqual(payload["status_summary"]["comparison"], "ready")
        self.assertEqual(payload["status_summary"]["audit"], "ready")
        self.assertEqual(payload["status_summary"]["golden"], "pass")
        self.assertEqual(payload["status_actions"]["review"], "查看当前报告摘要")
        self.assertEqual(payload["status_actions"]["comparison"], "查看 comparison reports")
        self.assertEqual(payload["status_actions"]["audit"], "查看 latest audit 摘要")
        self.assertEqual(payload["status_actions"]["golden"], "黄金样本通过，可继续看当前报告")
        self.assertIn("merge_semantics", payload["evidence"]["golden_suite"]["layer_summaries"])
        self.assertEqual(payload["formal_report"]["report_contract_version"], "admission_report.v1")
        self.assertEqual(payload["formal_report"]["final_decision"], "conditional_pass")
        self.assertEqual(payload["formal_report"]["risk_level"], "high")
        self.assertEqual(payload["formal_report"]["top_issue_summary"]["count"], 1)
        self.assertEqual(payload["formal_report"]["performance_risk_summary"]["count"], 1)
        self.assertIn("ci_contract", payload["formal_report"]["external_sync_summary"])
        self.assertIn("report", payload["formal_report"]["evidence_refs"])

    def test_admission_report_api_prefers_service_payload_method(self) -> None:
        bundle = self._bundle()
        original_service = bundle.admission_case_service
        calls: list[str] = []
        bundle.admission_case_service = SimpleNamespace(
            list_cases=original_service.list_cases,
            get_case=lambda baseline_key: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
            build_admission_report_payload=lambda baseline_key: calls.append(baseline_key) or {
                "report_contract_version": "admission_report.v1",
                "report_id": "review_report_1",
                "baseline_key": baseline_key,
                "status": "open",
                "final_decision": "conditional_pass",
                "risk_level": "high",
                "quality_gate_summary": {"final_decision": "conditional_pass"},
                "top_issue_summary": {"count": 1, "items": [{"title": "Startup timeout"}]},
                "performance_risk_summary": {"count": 1, "items": [{"risk_key": "cpu_regression"}]},
                "manual_overrides": {"has_override": False},
                "collaboration_summary": {"assignee_id": "qa"},
                "external_sync_summary": {"ci_contract": {"contract_version": "admission_case.v1"}},
                "evidence_refs": {"report": {"report_id": "review_report_1"}},
                "source_refs": {"latest_audit": {"available": True}},
                "recommended_actions": ["Review top issues."],
            },
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/admission/reports/device_offline_default")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls, ["device_offline_default"])
        self.assertEqual(payload["page"], "admission_report")
        self.assertEqual(payload["formal_report"]["source"], "service")
        self.assertEqual(payload["formal_report"]["baseline_key"], "device_offline_default")
        self.assertEqual(payload["formal_report"]["risk_level"], "high")
        self.assertEqual(payload["formal_report"]["external_sync_summary"]["ci_contract"]["contract_version"], "admission_case.v1")

    def test_admission_report_api_prefers_export_payload_method(self) -> None:
        bundle = self._bundle()
        original_service = bundle.admission_case_service
        calls: list[str] = []
        bundle.admission_case_service = SimpleNamespace(
            list_cases=original_service.list_cases,
            get_case=lambda baseline_key: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
            export_admission_report_payload=lambda baseline_key: calls.append(baseline_key) or {
                "report_contract_version": "admission_report.v1",
                "report_id": "export_report_1",
                "baseline_key": baseline_key,
                "final_decision": "pass",
                "risk_level": "low",
                "recommended_actions": ("Continue release.",),
            },
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/admission/reports/device_offline_default")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls, ["device_offline_default"])
        self.assertEqual(payload["formal_report"]["source"], "service")
        self.assertEqual(payload["formal_report"]["report_id"], "export_report_1")
        self.assertEqual(payload["formal_report"]["baseline_key"], "device_offline_default")
        self.assertEqual(payload["formal_report"]["recommended_actions"], ["Continue release."])

    def test_admission_report_api_supports_build_report_dataclass(self) -> None:
        @dataclass
        class ReportPayload:
            report_contract_version: str
            report_id: str
            baseline_key: str
            final_decision: str
            risk_level: str
            generated_at: datetime

        bundle = self._bundle()
        original_service = bundle.admission_case_service
        calls: list[str] = []
        bundle.admission_case_service = SimpleNamespace(
            list_cases=original_service.list_cases,
            get_case=lambda baseline_key: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
            build_admission_report=lambda baseline_key: calls.append(baseline_key) or ReportPayload(
                report_contract_version="admission_report.v1",
                report_id="build_report_1",
                baseline_key=baseline_key,
                final_decision="conditional_pass",
                risk_level="medium",
                generated_at=datetime(2025, 7, 24, 9, 30, 0),
            ),
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/admission/reports/device_offline_default")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls, ["device_offline_default"])
        self.assertEqual(payload["formal_report"]["source"], "service")
        self.assertEqual(payload["formal_report"]["report_id"], "build_report_1")
        self.assertEqual(payload["formal_report"]["baseline_key"], "device_offline_default")
        self.assertEqual(payload["formal_report"]["generated_at"], "2025-07-24 17:30:00.000000")

    def test_admission_case_detail_alias_api_returns_same_case_contract(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/admission/cases/device_offline_default")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["admission_case"]["case_id"], "admission_case:device_offline_default:review_report_1")
        self.assertEqual(payload["admission_case"]["contract_version"], "admission_case.v1")
        self.assertEqual(payload["admission_case"]["status"], "open")
        self.assertEqual(payload["admission_case"]["revision"], 1)

    def test_admission_detail_api_filters_history_by_action(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, _, body = app.handle_request("/api/admission/baseline/device_offline_default?action=promote")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["filters"]["action"], "promote")
        self.assertEqual(payload["filters"]["history_count_filtered"], 1)
        self.assertEqual(len(payload["baseline_history"]), 1)
        self.assertEqual(payload["baseline_history"][0]["action"], "promote")

    def test_admission_detail_api_filters_history_by_comparison_only(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, _, body = app.handle_request("/api/admission/baseline/device_offline_default?comparison_only=1")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertTrue(payload["filters"]["comparison_only"])
        self.assertEqual(payload["filters"]["history_count_filtered"], 1)
        self.assertEqual(len(payload["baseline_history"]), 1)
        self.assertEqual(payload["baseline_history"][0]["comparison_id"], "review_report_compare_1")

    def test_admission_detail_page_renders_drill_down_sections(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/admission/baseline/device_offline_default")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("准入详情", html)
        self.assertIn("device_offline_default", html)
        self.assertIn("正式准入报告", html)
        self.assertIn("风险等级", html)
        self.assertIn("外部回写", html)
        self.assertIn("证据引用", html)
        self.assertIn("建议", html)
        self.assertIn("/api/admission/reports/device_offline_default", html)
        self.assertIn("Admission Case", html)
        self.assertIn("执行结果", html)
        self.assertIn("Top Issues", html)
        self.assertIn("回归摘要", html)
        self.assertIn("场景覆盖", html)
        self.assertIn("admission_case:device_offline_default:review_report_1", html)
        self.assertIn("suspected_regression", html)
        self.assertIn("质量门禁摘要", html)
        self.assertIn("触发规则", html)
        self.assertIn("风险提示", html)
        self.assertIn("覆盖不足", html)
        self.assertIn("人工覆盖", html)
        self.assertIn("automatic: conditional_pass", html)
        self.assertIn("final: conditional_pass", html)
        self.assertIn("规则评审警告门槛", html)
        self.assertIn("高风险 Family 门槛", html)
        self.assertIn("高风险 family 数为 2", html)
        self.assertIn("高级异常证据", html)
        self.assertIn("confirmation_level=multi_evidence", html)
        self.assertIn("threshold_source=performance_thresholds.version", html)
        self.assertIn("matched_scope", html)
        self.assertIn("状态摘要", html)
        self.assertIn("Review", html)
        self.assertIn("Comparison", html)
        self.assertIn("Latest Audit", html)
        self.assertIn("Golden Suite", html)
        self.assertIn("href='#section-review-report'", html)
        self.assertIn("href='#section-comparison-reports'", html)
        self.assertIn("href='#section-latest-audit'", html)
        self.assertIn("href='#section-golden-suite'", html)
        self.assertIn("查看当前报告摘要", html)
        self.assertIn("查看 comparison reports", html)
        self.assertIn("查看 latest audit 摘要", html)
        self.assertIn("黄金样本通过，可继续看当前报告", html)
        self.assertIn("merge_semantics", html)
        self.assertIn("Comparison Reports", html)
        self.assertIn("Comparison HTML", html)
        self.assertIn("Baseline History", html)
        self.assertIn("history 过滤", html)
        self.assertIn("仅 Comparison", html)
        self.assertIn("展开详情", html)
        self.assertIn("<details>", html)
        self.assertIn("promote", html)
        self.assertIn("rollback", html)
        self.assertIn("Latest Audit", html)
        self.assertIn("最近版本", html)
        self.assertIn("Review Report HTML", html)
        self.assertIn("Latest Audit HTML", html)

    def test_admission_view_serves_workspace_file(self) -> None:
        app = WebPortalApplication(self._bundle())
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=Path.cwd(),
            delete=False,
        )
        try:
            handle.write('{"ok": true}')
            handle.close()

            status, content_type, body = app.handle_request(
                f"/admission/view?path={quote(handle.name, safe='')}"
            )

            self.assertEqual(status, 200)
            self.assertIn("application/json", content_type)
            self.assertEqual(json.loads(body.decode("utf-8")), {"ok": True})
        finally:
            Path(handle.name).unlink(missing_ok=True)

    def test_users_api_prefers_profiles_and_falls_back_to_actors(self) -> None:
        bundle = self._bundle()
        bundle.collaboration_service.list_user_profiles = lambda: (
            SimpleNamespace(
                profile_id="profile-developer",
                actor_id="developer",
                display_name="Developer",
                email="dev@example.invalid",
                role_key="developer",
                team_ids=("android-client",),
                external_identities=(
                    SimpleNamespace(
                        identity_id="asl.external_identity.v1:github:dev",
                        provider="github",
                        external_subject_id="dev",
                        external_email="dev@example.invalid",
                        organization_id="mobile",
                        team_ids=("android-client",),
                        role_claims=("developer",),
                    ),
                ),
                permissions=("comment_issue",),
            ),
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/users")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["source"], "user_profiles")
        self.assertEqual(payload["profiles"][0]["profile_id"], "profile-developer")
        self.assertEqual(payload["profiles"][0]["external_identities"][0]["provider"], "github")
        self.assertEqual(payload["summary"]["team_counts"]["android-client"], 1)

        fallback_app = WebPortalApplication(self._bundle())
        status, _, body = fallback_app.handle_request("/api/users")
        fallback_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(fallback_payload["summary"]["source"], "actors_fallback")
        self.assertIn("developer", [item["actor_id"] for item in fallback_payload["profiles"]])

    def test_responsibility_api_returns_cross_system_summary(self) -> None:
        app = WebPortalApplication(self._bundle())
        self._post_json_or_skip(
            app,
            "/api/issues/actions/assign",
            {"fingerprint": "ifp_1", "assignee_id": "developer"},
        )
        self._post_json_or_skip(
            app,
            "/api/issues/actions/create-defect",
            {
                "fingerprint": "ifp_1",
                "system_key": "jira",
                "title": "Cold start timeout",
                "team_key": "android-client",
            },
        )
        self._post_json_or_skip(
            app,
            "/api/admission/actions/assign",
            {"baseline_key": "device_offline_default", "assignee_id": "developer"},
        )
        self._post_json_or_skip(
            app,
            "/api/admission/actions/transition",
            {"baseline_key": "device_offline_default", "workflow_state": "pending_confirmation"},
        )

        status, content_type, body = app.handle_request("/api/responsibility")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["contract_version"], "asl.responsibility_view.v1")
        self.assertEqual(payload["summary"]["profile_source"], "actors_fallback")
        self.assertGreaterEqual(payload["summary"]["issue_assignment_count"], 1)
        self.assertGreaterEqual(payload["summary"]["admission_assignment_count"], 1)
        self.assertGreaterEqual(payload["summary"]["defect_team_count"], 1)
        self.assertGreaterEqual(payload["summary"]["release_owner_team_count"], 1)
        self.assertEqual(payload["issues"][0]["assignee"]["actor_id"], "developer")
        self.assertEqual(payload["admissions"][0]["assignee"]["actor_id"], "developer")
        self.assertEqual(payload["admissions"][0]["final_reviewer"]["actor_id"], "tester")
        self.assertEqual(payload["defects"][0]["team_key"], "android-client")
        self.assertEqual(payload["releases"][0]["owner_team"], "android-client")

    def test_rules_api_prefers_rule_governance_service_entrypoint_methods(self) -> None:
        calls: list[object] = []
        bundle = self._bundle()
        bundle.rule_governance_service = SimpleNamespace(
            describe_rule_entrypoint=lambda path=None: calls.append(("describe", path)) or {
                "contract_version": "asl.rule_entrypoint.v1",
                "config_path": path or "config/stability_rules.json",
                "current_version": "rules-v2",
                "validation": {"valid": True, "error_count": 0, "warning_count": 0},
                "editable_fields": ["version", "performance_thresholds"],
                "risk_prompts": ["规则变更需要 golden replay"],
                "recommended_flow": ["preview-analysis-rule-update", "review-analysis-rules"],
                "related_policy_files": ["config/stability_rules.json", "config/rule_replay_golden_samples.json"],
            },
            preview_analysis_rule_update=lambda **kwargs: calls.append(("preview", kwargs)) or {
                "contract_version": "asl.rule_update_preview.v1",
                "config_path": kwargs.get("path") or "config/stability_rules.json",
                "updates": kwargs["updates"],
                "changed_field_count": len(kwargs["updates"]),
                "write_policy": "preview_only_no_config_write",
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/api/rules?path=config/custom_rules.json&set.version=rules-v3")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(calls[0], ("describe", "config/custom_rules.json"))
        self.assertEqual(calls[1][0], "preview")
        self.assertEqual(calls[1][1]["updates"]["version"], "rules-v3")
        self.assertEqual(payload["summary"]["source"], "service")
        self.assertEqual(payload["entrypoint"]["current_version"], "rules-v2")
        self.assertEqual(payload["preview"]["write_policy"], "preview_only_no_config_write")

    def test_rules_api_prefers_formal_preview_rule_update_method(self) -> None:
        calls: list[object] = []
        bundle = self._bundle()
        bundle.rule_governance_service = SimpleNamespace(
            describe_rule_entrypoint=lambda path=None: {
                "contract_version": "asl.rule_entrypoint.v1",
                "config_path": path or "config/stability_rules.json",
                "current_version": "rules-v2",
                "validation": {"valid": True, "error_count": 0, "warning_count": 0},
                "editable_fields": ["fingerprint.version"],
            },
            preview_rule_update=lambda patch, path=None: calls.append((patch, path)) or {
                "rule_path": path or "config/stability_rules.json",
                "patch": patch,
                "valid": True,
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request("/api/rules?path=config/custom_rules.json&set.version=rules-v3")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(calls, [({"fingerprint": {"version": "rules-v3"}}, "config/custom_rules.json")])
        self.assertEqual(payload["preview"]["source"], "service")
        self.assertEqual(payload["preview"]["config_path"], "config/custom_rules.json")
        self.assertEqual(payload["preview"]["changed_field_count"], 1)

    def test_rules_api_uses_formal_build_rule_edit_plan_method(self) -> None:
        calls: list[object] = []
        bundle = self._bundle()
        bundle.rule_governance_service = SimpleNamespace(
            describe_rule_entrypoint=lambda path=None: {
                "contract_version": "asl.rule_entrypoint.v1",
                "config_path": path or "config/stability_rules.json",
                "current_version": "rules-v2",
                "validation": {"valid": True, "error_count": 0, "warning_count": 0},
                "editable_fields": ["regression.version"],
            },
            build_rule_edit_plan=lambda **kwargs: calls.append(kwargs) or {
                "rule_path": kwargs.get("path") or "config/stability_rules.json",
                "patch": {kwargs["section"]: {kwargs["key"]: kwargs["value"]}},
                "valid": True,
            },
            inspect_rules=lambda path=None: (_ for _ in ()).throw(AssertionError("fallback should not be used")),
        )
        app = WebPortalApplication(bundle)

        status, _, body = app.handle_request("/api/rules?path=config/custom_rules.json&set.regression.version=rules-v3")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(
            calls,
            [
                {
                    "section": "regression",
                    "key": "version",
                    "value": "rules-v3",
                    "path": "config/custom_rules.json",
                }
            ],
        )
        self.assertEqual(payload["preview"]["source"], "service")
        self.assertEqual(payload["preview"]["patch"]["regression"]["version"], "rules-v3")

    def test_rules_page_renders_read_only_rule_center(self) -> None:
        bundle = self._bundle()
        bundle.rule_governance_service = SimpleNamespace(
            inspect_rules=lambda path=None: SimpleNamespace(
                path="config/stability_rules.json",
                source_exists=True,
                validation=SimpleNamespace(
                    path="config/stability_rules.json",
                    source_exists=True,
                    valid=True,
                    errors=(),
                    warnings=("review warnings",),
                ),
                source_rules={"version": "rules-v1"},
                default_rules={},
                effective_rules={"version": "rules-v1"},
            )
        )
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request("/rules")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("规则中心", html)
        self.assertIn("config/stability_rules.json", html)
        self.assertIn("preview_only_no_config_write", html)
        self.assertIn("可编辑字段", html)
        self.assertIn("风险提示与建议流程", html)
        self.assertIn("/api/rules", html)

    def test_release_submissions_api_returns_listing_and_detail(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/release-submissions")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["summary"]["submission_count"], 1)
        self.assertEqual(payload["summary"]["submission_status_counts"]["admission_synced"], 1)
        self.assertEqual(payload["summary"]["run_status_counts"]["failed"], 1)
        self.assertEqual(payload["summary"]["admission_decision_counts"]["conditional_pass"], 1)
        self.assertEqual(payload["release_submissions"][0]["submission_id"], "release_submission_1")
        self.assertEqual(payload["release_submissions"][0]["detail_path"], "/api/release-submissions/release_submission_1")

        status, content_type, body = app.handle_request("/api/release-submissions/release_submission_1")

        detail_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(detail_payload["release_submission"]["submission_id"], "release_submission_1")
        self.assertEqual(detail_payload["release_submission"]["baseline_key"], "device_offline_default")
        self.assertEqual(detail_payload["release_submission"]["admission_final_decision"], "conditional_pass")

    def test_integration_page_renders_release_submission_controls(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/integration")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("集成 Outbox", html)
        self.assertIn("IM 通知", html)
        self.assertIn("注册 IM 通知 Webhook", html)
        self.assertIn("Feishu/IM 验收摘要", html)
        self.assertIn("2h/24h 联调 Checklist", html)
        self.assertIn("Feishu 通知 Worker", html)
        self.assertIn("name='channel' value='feishu_bot'", html)
        self.assertIn("show-im-acceptance-summary --channel feishu_bot", html)
        self.assertIn("噪声检查占位", html)
        self.assertIn("缺陷系统", html)
        self.assertIn("注册缺陷同步 Webhook", html)
        self.assertIn("integration-two-column-form", html)
        self.assertIn("integration-form-grid", html)
        self.assertIn("integration-form-footer", html)
        self.assertIn("提测平台", html)
        self.assertIn("Webhook 注册", html)
        self.assertIn("注册 Webhook", html)
        self.assertIn("name='delivery_channel' value='generic'", html)
        self.assertIn("创建提测请求", html)
        self.assertIn("cards integration-release-stack", html)
        self.assertIn("同步提测准入", html)
        self.assertIn("注册提测 Webhook", html)
        self.assertIn("提测同步 Worker", html)
        self.assertIn("metric-choice-grid", html)
        self.assertIn("name='metrics' value='cpu' checked", html)
        self.assertIn("name='metrics' value='memory' checked", html)
        self.assertIn("name='metrics' value='power'", html)
        self.assertNotIn("<label>指标<input", html)
        self.assertIn("json-param-help", html)
        self.assertIn("查看参数", html)
        self.assertIn("data-task-param-builder", html)
        self.assertIn("data-task-param-key='loop_count'", html)

    def test_response_boundary_headers_include_request_id_and_security_headers(self) -> None:
        app = WebPortalApplication(self._bundle())

        headers = app._response_boundary_headers("portal_req_test")

        self.assertEqual(headers["X-Request-ID"], "portal_req_test")
        self.assertEqual(headers["X-ASL-Request-ID"], "portal_req_test")
        self.assertEqual(headers["X-ASL-Portal-Mode"], "local_ops_console")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_unknown_page_returns_404_html(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/missing")

        html = body.decode("utf-8")
        self.assertEqual(status, 404)
        self.assertIn("text/html", content_type)
        self.assertIn("页面不存在", html)

    def test_issues_page_renders_attribution_explanation_fields(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/issues")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("初步归因建议", html)
        self.assertIn("环境/设备侧", html)
        self.assertIn("置信度=0.76", html)
        self.assertIn("startup_timeout_device_pressure", html)
        self.assertIn("activity_launch_gap", html)
        self.assertIn("activity launch gap and timeout marker", html)
        self.assertIn("check device load", html)
        self.assertIn("confirm against monitoring snapshot", html)

    def test_issue_actions_update_collaboration_state_and_emit_outbox_event(self) -> None:
        bundle = self._bundle()
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/issues/actions/assign",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "assignee_id": "developer",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Actor": "tester"},
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["fingerprint"], "ifp_1")
        self.assertEqual(payload["identity_id"], "asl.identity.v1:tester:tester")
        self.assertTrue(payload["events"][-1]["audit_source"]["resolved_session_id"].startswith("asl.session_id.v1:"))
        self.assertEqual(payload["assignee_id"], "developer")
        self.assertEqual(payload["workflow_state"], "assigned")

        status, _, body = app.handle_request(
            "/api/issues/actions/comment",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "body": "可以稳定复现，先继续排查。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Session-Token": "asl.session.v1:developer:developer"},
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["comment_count"], 1)
        self.assertEqual(payload["identity_id"], "asl.identity.v1:developer:developer")
        self.assertEqual(payload["latest_comment_by"], "developer")

        status, _, body = app.handle_request(
            "/api/issues/actions/transition",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "workflow_state": "processing",
                    "reason": "已开始处理。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Session-Token": "asl.session.v1:developer:developer"},
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["workflow_state"], "processing")

        status, _, body = app.handle_request("/api/issues")
        issues_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(issues_payload["issues"][0]["assignee_id"], "developer")
        self.assertEqual(issues_payload["issues"][0]["workflow_state"], "processing")
        self.assertEqual(issues_payload["issues"][0]["comment_count"], 1)
        self.assertEqual(issues_payload["issues"][0]["evidence_signals"], ["timeout_marker", "activity_launch_gap"])
        self.assertEqual(issues_payload["issues"][0]["confirmation_level"], "multi_evidence")
        self.assertEqual(issues_payload["issues"][0]["attribution"]["direction"], "environment")
        self.assertEqual(issues_payload["issues"][0]["attribution"]["confidence_score"], 0.76)
        self.assertEqual(
            issues_payload["issues"][0]["attribution"]["matched_rule_ids"],
            ["startup_timeout_device_pressure", "activity_launch_gap"],
        )
        self.assertEqual(
            issues_payload["issues"][0]["attribution"]["recommended_next_steps"],
            ["check device load", "rerun cold start"],
        )

        status, _, body = app.handle_request("/api/integration/outbox")
        outbox_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(outbox_payload["summary"]["event_count"], 3)
        self.assertEqual(outbox_payload["summary"]["consumer_receipt_count"], 0)
        self.assertEqual(outbox_payload["worker"]["mode"], "local_ops_worker_surface")
        self.assertTrue(outbox_payload["worker"]["supports_run_delivery_worker"])
        self.assertIn("supports_run_delivery_daemon", outbox_payload["worker"])
        self.assertTrue(outbox_payload["worker"]["supports_replay_dead_letter_api"])
        self.assertIn("worker_status", outbox_payload["worker"])
        self.assertEqual(outbox_payload["idempotency_contract"]["strategy"], "event_id_per_delivery_target")
        self.assertEqual(outbox_payload["events"][0]["event_type"], "issue.transitioned")
        self.assertEqual(outbox_payload["events"][0]["session_source"], "header:x-asl-session-token")
        self.assertEqual(
            outbox_payload["events"][0]["idempotency_key"],
            f"asl.outbox.idempotency.v1:{outbox_payload['events'][0]['event_id']}",
        )
        self.assertEqual(
            outbox_payload["events"][0]["delivery_receipt"]["receipt_status"],
            "not_acknowledged",
        )
        self.assertEqual(outbox_payload["events"][0]["audit_source"]["resolved_actor_id"], "developer")
        self.assertEqual(outbox_payload["events"][0]["audit_source"]["resolved_identity_id"], "asl.identity.v1:developer:developer")
        self.assertTrue(outbox_payload["events"][0]["audit_source"]["resolved_session_id"].startswith("asl.session_id.v1:"))
        self.assertEqual(outbox_payload["events"][0]["audit_source"]["identity_source_type"], "session_token")
        self.assertEqual(outbox_payload["events"][0]["audit_source"]["auth_mechanism"], "session_token")
        self.assertEqual(outbox_payload["events"][0]["audit_source"]["identity_binding_status"], "verified")
        self.assertEqual(outbox_payload["events"][0]["audit_source"]["request_path"], "/api/issues/actions/transition")

    def test_sso_header_write_action_uses_external_identity_audit_boundary(self) -> None:
        bundle = self._bundle()
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/issues/actions/comment",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "body": "SSO 身份写入审计。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={
                "X-ASL-Request-ID": "req-sso-1",
                "X-ASL-SSO-Provider": "corp-idp",
                "X-ASL-External-Subject": "developer",
                "X-ASL-External-Email": "developer@example.internal",
                "X-ASL-Org": "android-platform",
                "X-ASL-Team": "stability,client",
                "X-ASL-Role": "developer",
                "X-ASL-Actor": "tester",
            },
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["latest_comment_by"], "developer")
        self.assertEqual(payload["identity_id"], "asl.identity.v1:developer:developer")

        status, _, body = app.handle_request("/api/integration/outbox")
        outbox_payload = json.loads(body.decode("utf-8"))
        event = outbox_payload["events"][0]
        audit_source = event["audit_source"]
        self.assertEqual(event["created_by"], "developer")
        self.assertEqual(event["session_source"], "header:trusted_sso")
        self.assertEqual(audit_source["request_id"], "req-sso-1")
        self.assertEqual(audit_source["auth_mechanism"], "sso_header")
        self.assertEqual(audit_source["identity_source_type"], "trusted_sso_header")
        self.assertEqual(audit_source["identity_provider"], "corp-idp")
        self.assertEqual(audit_source["external_subject_id"], "developer")
        self.assertEqual(audit_source["external_email"], "developer@example.internal")
        self.assertEqual(audit_source["organization_id"], "android-platform")
        self.assertEqual(audit_source["team_ids"], ["stability", "client"])
        self.assertTrue(str(audit_source["external_identity_id"]).startswith("asl.external_identity.v1:corp-idp:developer"))
        self.assertEqual(audit_source["resolved_actor_id"], "developer")

    def test_incomplete_sso_header_write_action_is_rejected_without_local_fallback(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request(
            "/api/issues/actions/comment",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "body": "不应该回退成本地 actor。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={
                "X-ASL-SSO-Provider": "corp-idp",
                "X-ASL-Actor": "tester",
            },
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertIn("application/json", content_type)
        self.assertIn("Writable requests with trusted SSO headers require", payload["error"])
        self.assertIn("X-ASL-External-Subject", payload["error"])
        self.assertIn("Omit all SSO headers to use local session identity", payload["error"])

    def test_integration_outbox_api_exposes_consumer_receipts(self) -> None:
        bundle = self._bundle()
        integration_service = bundle.integration_outbox_service
        integration_service._events.append(
            SimpleNamespace(
                event_id="evt_with_consumer_receipt",
                event_type="manual.outbox.check",
                target_type="admission",
                target_id="baseline_1",
                created_at=None,
                created_by="tester",
                session_source="header:x-asl-session-token",
                audit_source={"request_path": "/test/consumer/receipt"},
                payload={},
                delivery_status="delivered",
                attempt_count=1,
                last_attempt_at=None,
                delivered_at=None,
                last_error="",
                next_retry_at=None,
                signature="sha256=with_receipt",
                retry_backoff_seconds=0,
                last_response_code=200,
                dead_lettered_at=None,
                alert_status="none",
                alert_count=0,
                last_alert_at=None,
                idempotency_key="manual.receipt.idemp",
                consumer_receipts=[
                    SimpleNamespace(
                        receipt_id="consumer_receipt_1",
                        event_id="evt_with_consumer_receipt",
                        webhook_name="CI Callback",
                        idempotency_key="manual.receipt.idemp",
                        received_at=datetime(2025, 7, 23, 12, 0, 0),
                        status="delivered",
                        response_code=200,
                        consumer_id="ci-system",
                        consumer_receipt_id="cr-1",
                        response_excerpt="ok",
                    ),
                ],
            )
        )

        app = WebPortalApplication(bundle)
        status, _, body = app.handle_request("/api/integration/outbox")
        outbox_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(outbox_payload["summary"]["consumer_receipt_count"], 1)
        self.assertEqual(len(outbox_payload["consumer_receipts"]), 1)
        self.assertEqual(outbox_payload["consumer_receipts"][0]["receipt_id"], "consumer_receipt_1")
        self.assertEqual(outbox_payload["consumer_receipts"][0]["status"], "delivered")
        event = next(item for item in outbox_payload["events"] if item["event_id"] == "evt_with_consumer_receipt")
        self.assertEqual(event["consumer_receipt_count"], 1)
        self.assertEqual(event["idempotency_key"], "manual.receipt.idemp")

    def test_admission_override_action_updates_quality_gate_and_emits_outbox_event(self) -> None:
        bundle = self._bundle()
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/admission/actions/override",
            method="POST",
            body=urlencode(
                {
                    "baseline_key": "device_offline_default",
                    "final_decision": "pass",
                    "reason": "已知风险已签字放行",
                    "comment": "附 release waiver",
                    "evidence_paths": "runtime/release-waiver.md",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Session-Token": "asl.session.v1:tester:tester"},
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["automatic_decision"], "conditional_pass")
        self.assertEqual(payload["final_decision"], "pass")

        status, _, body = app.handle_request("/api/admission/baseline/device_offline_default")
        detail_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(detail_payload["evidence"]["quality_gate"]["final_decision"], "pass")
        self.assertTrue(detail_payload["evidence"]["quality_gate"]["has_override"])
        self.assertEqual(detail_payload["evidence"]["quality_gate"]["override"]["created_by"], "tester")

        status, _, body = app.handle_request("/api/integration/outbox")
        outbox_payload = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(outbox_payload["summary"]["event_count"], 1)
        event_types = [item["event_type"] for item in outbox_payload["events"]]
        self.assertIn("admission.override_recorded", event_types)
        override_event = next(item for item in outbox_payload["events"] if item["event_type"] == "admission.override_recorded")
        self.assertEqual(override_event["session_source"], "header:x-asl-session-token")
        self.assertEqual(override_event["audit_source"]["resolved_actor_id"], "tester")
        self.assertEqual(override_event["audit_source"]["resolved_identity_id"], "asl.identity.v1:tester:tester")
        self.assertEqual(override_event["audit_source"]["auth_mechanism"], "session_token")
        if "admission_case.updated" in event_types:
            case_event = next(item for item in outbox_payload["events"] if item["event_type"] == "admission_case.updated")
            self.assertEqual(case_event["payload"]["decision_source"], "admission_case")
            self.assertEqual(case_event["payload"]["case_id"], detail_payload["case"]["case_id"])

    def test_admission_case_actions_update_collaboration_state_and_views(self) -> None:
        bundle = self._bundle()
        app = WebPortalApplication(bundle)

        status, content_type, body = app.handle_request(
            "/api/admission/actions/assign",
            method="POST",
            body=urlencode(
                {
                    "baseline_key": "device_offline_default",
                    "assignee_id": "developer",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Actor": "tester"},
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["baseline_key"], "device_offline_default")
        self.assertEqual(payload["assignee_id"], "developer")
        self.assertEqual(payload["workflow_state"], "assigned")

        status, _, body = app.handle_request(
            "/api/admission/actions/comment",
            method="POST",
            body=urlencode(
                {
                    "baseline_key": "device_offline_default",
                    "body": "先补 release waiver，再确认放行。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Session-Token": "asl.session.v1:developer:developer"},
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["comment_count"], 1)
        self.assertEqual(payload["latest_comment_by"], "developer")

        status, _, body = app.handle_request(
            "/api/admission/actions/transition",
            method="POST",
            body=urlencode(
                {
                    "baseline_key": "device_offline_default",
                    "workflow_state": "pending_confirmation",
                    "reason": "等待最终确认。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Session-Token": "asl.session.v1:tester:tester"},
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["workflow_state"], "pending_confirmation")
        self.assertEqual(payload["final_reviewer_id"], "tester")

        status, _, body = app.handle_request("/api/admission")
        admission_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(admission_payload["baselines"][0]["status"], "pending_confirmation")
        self.assertEqual(admission_payload["baselines"][0]["assignee_id"], "developer")
        self.assertEqual(admission_payload["views"]["summary"]["pending_confirmation_count"], 1)
        self.assertEqual(admission_payload["views"]["summary"]["approved_with_risk_count"], 1)

        status, _, body = app.handle_request("/api/integration/outbox")
        outbox_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(outbox_payload["summary"]["event_count"], 3)
        self.assertEqual(outbox_payload["events"][0]["event_type"], "admission_case.transitioned")
        self.assertEqual(outbox_payload["summary"]["retry_pending_count"], 0)
        self.assertEqual(
            outbox_payload["delivery_receipts"][0]["contract"],
            "webhook_transport_ack_only_plus_operator_receipts",
        )

    def test_get_request_with_unknown_actor_falls_back_to_default_actor(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request("/api/issues?as_actor=ghost")

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["current_actor"]["actor_id"], "tester")
        self.assertEqual(payload["current_actor"]["session_source"], "default:collaboration_actor_registry")
        self.assertEqual(payload["current_actor"]["auth_mechanism"], "default_actor")
        self.assertEqual(payload["current_actor"]["requested_actor_id"], "ghost")

    def test_post_request_with_unknown_actor_is_rejected(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request(
            "/api/issues/actions/comment?as_actor=ghost",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "body": "不应该通过。",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertIn("application/json", content_type)
        self.assertIn("Writable requests do not accept cookie/query actor overrides", payload["error"])

    def test_post_request_rejects_identity_fields_in_form_body(self) -> None:
        app = WebPortalApplication(self._bundle())

        status, content_type, body = app.handle_request(
            "/api/issues/actions/comment",
            method="POST",
            body=urlencode(
                {
                    "fingerprint": "ifp_1",
                    "body": "不应该通过。",
                    "actor_id": "developer",
                }
            ).encode("utf-8"),
            content_type="application/x-www-form-urlencoded",
            headers={"X-ASL-Actor": "tester"},
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertIn("application/json", content_type)
        self.assertIn("Writable requests do not accept identity fields in form body", payload["error"])

    def test_web_write_entry_creates_task_run_and_execute_run(self) -> None:
        app = WebPortalApplication(self._writable_bundle())

        create_task_payload = self._post_json_or_skip(
            app,
            "/api/tasks/actions/create",
            {
                "task_name": "Calculator Cold Start",
                "package_name": "com.hihonor.calculator",
                "template_type": "cold_start_loop",
                "device": "device-1",
                "sampling_interval": "5",
            },
        )
        self.assertEqual(create_task_payload["task_id"], "task-write-1")
        self.assertEqual(create_task_payload["task_name"], "Calculator Cold Start")
        self.assertEqual(create_task_payload["package_name"], "com.hihonor.calculator")

        create_run_payload = self._post_json_or_skip(
            app,
            "/api/runs/actions/create",
            {
                "task_id": "task-1",
                "requested_by": "tester",
                "device": "device-1",
                "metadata": "{\"source\":\"web\"}",
            },
        )
        self.assertEqual(create_run_payload["run_id"], "run-write-1")
        self.assertEqual(create_run_payload["task_id"], "task-1")
        self.assertEqual(create_run_payload["target_device_ids"], ["device-1"])

        execute_run_payload = self._post_json_or_skip(
            app,
            "/api/runs/actions/execute",
            {
                "run_id": "run-1",
                "monitoring_backend": "solox",
                "retry_count": "1",
            },
            headers={"X-ASL-Session-Token": "asl.session.v1:tester:tester"},
        )
        self.assertEqual(execute_run_payload["run_id"], "run-1")
        self.assertEqual(execute_run_payload["run_status"], "success")
        self.assertEqual(execute_run_payload["monitoring_backend"], "solox")
        self.assertEqual(execute_run_payload["instance_count"], 1)

    def test_web_archive_task_hides_task_and_emits_audited_outbox_event(self) -> None:
        bundle = self._bundle()
        outbox = _FakeIntegrationOutboxService()
        task_service = TaskService(repository=InMemoryTaskRepository(), audit_event_sink=outbox)
        task_service.create_task(
            TaskDefinition(
                task_id="task-archive-web",
                task_name="Archive From Web",
                template_type=TaskTemplateType.COLD_START_LOOP,
                target_app=TaskTargetApp(package_name="com.example.app"),
            )
        )
        bundle.task_service = task_service
        bundle.integration_outbox_service = outbox
        app = WebPortalApplication(bundle)

        before_status, _, before_body = app.handle_request("/api/tasks")
        before_payload = json.loads(before_body.decode("utf-8"))
        self.assertEqual(before_status, 200)
        self.assertEqual(before_payload["summary"]["active_task_count"], 1)

        archive_payload = self._post_json_or_skip(
            app,
            "/api/tasks/actions/archive-task",
            {
                "task_id": "task-archive-web",
                "reason": "页面调试任务已完成。",
            },
            headers={"X-ASL-Session-Token": "asl.session.v1:tester:tester"},
        )

        self.assertTrue(archive_payload["archived"])
        self.assertEqual(archive_payload["audit_event"]["reason"], "页面调试任务已完成。")
        after_status, _, after_body = app.handle_request("/api/tasks")
        after_payload = json.loads(after_body.decode("utf-8"))
        self.assertEqual(after_status, 200)
        self.assertEqual(after_payload["summary"]["active_task_count"], 0)
        self.assertEqual(after_payload["summary"]["archived_task_count"], 1)
        self.assertEqual(after_payload["tasks"], [])
        archived_status, _, archived_body = app.handle_request("/api/tasks?show_archived=1")
        archived_payload = json.loads(archived_body.decode("utf-8"))
        self.assertEqual(archived_status, 200)
        self.assertEqual(archived_payload["tasks"][0]["task_id"], "task-archive-web")
        self.assertTrue(archived_payload["tasks"][0]["archived"])
        events = outbox.list_events(limit=5)
        self.assertEqual(events[0].event_type, "task.archived")
        self.assertEqual(events[0].audit_source["auth_mechanism"], "session_token")
        self.assertEqual(events[0].payload["reason"], "页面调试任务已完成。")

    def test_web_create_long_run_task_also_configures_unattended_record(self) -> None:
        bundle = self._writable_bundle()
        captured: dict[str, object] = {}

        def create_task(task: object):
            captured["task"] = task
            return SimpleNamespace(task=task, created_at=datetime(2025, 7, 23, 10, 0, 0))

        def configure_task(**kwargs: object):
            captured["unattended_kwargs"] = kwargs
            return SimpleNamespace(
                task_id=kwargs["task_id"],
                task_name="前后台长稳",
                configured=True,
                enabled=True,
                interval_minutes=kwargs["interval_minutes"],
                desired_device_count=kwargs["desired_device_count"],
                failure_threshold=kwargs["failure_threshold"],
                rotation_strategy=kwargs["rotation_strategy"],
                rotation_advance_policy=kwargs["rotation_advance_policy"],
                rotation_cursor=0,
                rotation_advance_count=0,
                primary_device_ids=tuple(kwargs["primary_device_ids"]),
                backup_device_ids=tuple(kwargs["backup_device_ids"]),
                next_run_at=None,
                last_run_at=None,
                last_run_id="",
                due=False,
                latest_summary={},
                long_run_summary={"round_count": 0},
                recent_device_windows=(),
                recent_rounds=(),
            )

        bundle.task_service.create_task = create_task
        bundle.unattended_service.configure_task = configure_task
        app = WebPortalApplication(bundle)

        payload = self._post_json_or_skip(
            app,
            "/api/tasks/actions/create",
            {
                "configure_unattended": "1",
                "task_name": "前后台长稳",
                "package_name": "com.example.app",
                "template_type": "foreground_background_loop",
                "devices": "device-1",
                "backup_devices": "device-2",
                "runtime_hours": "2",
                "interval_minutes": "30",
                "retry_count": "1",
                "desired_device_count": "1",
                "failure_threshold": "2",
                "rotation_strategy": "round_robin",
                "rotation_advance_policy": "every_round",
                "monitoring_backend": "solox",
                "metrics": "cpu",
                "sampling_interval": "5",
                "outputs": "daily_report",
                "task_params": "{\"loop_count\": 2}",
                "metadata": "{\"owner_team\":\"android-client\"}",
            },
        )

        task = captured["task"]
        unattended_kwargs = dict(captured["unattended_kwargs"])
        self.assertTrue(payload["unattended_configured"])
        self.assertEqual(payload["runner_path"], "/runner")
        self.assertEqual(payload["template_type"], "foreground_background_loop")
        self.assertEqual(task.metadata["monitoring_backend"], "solox")
        self.assertEqual(task.metadata["long_run"]["estimated_max_rounds"], 4)
        self.assertEqual(task.metadata["long_run"]["outputs"], ["daily_report"])
        self.assertEqual(task.task_params["retry_count"], 1)
        self.assertEqual(unattended_kwargs["task_id"], payload["task_id"])
        self.assertEqual(unattended_kwargs["interval_minutes"], 30)
        self.assertEqual(unattended_kwargs["primary_device_ids"], ["device-1"])
        self.assertEqual(unattended_kwargs["backup_device_ids"], ["device-2"])

    def test_web_execute_backend_override_builds_request_scoped_adapter(self) -> None:
        app = WebPortalApplication(self._bundle())
        original_adapter = object()
        original_service = SimpleNamespace(
            _task_repository=object(),
            _run_repository=object(),
            _instance_repository=object(),
            _execution_service=object(),
            _monitoring_adapter=original_adapter,
            _artifact_planner=object(),
            _scenario_runners={},
            _artifact_collector=object(),
            _host_command_runner=object(),
            _report_service=object(),
        )

        resolved_service, resolved_backend = app._run_execution_service_for_backend(original_service, "solox")

        self.assertEqual(resolved_backend, "solox")
        self.assertIsNot(resolved_service, original_service)
        self.assertIs(getattr(resolved_service, "_task_repository"), original_service._task_repository)
        self.assertIsNot(getattr(resolved_service, "_monitoring_adapter"), original_adapter)

    def test_web_write_entry_configures_unattended_rounds(self) -> None:
        app = WebPortalApplication(self._writable_bundle())

        configure_payload = self._post_json_or_skip(
            app,
            "/api/unattended/actions/configure",
            {
                "task_id": "task-1",
                "interval_minutes": "30",
                "device": "device-1",
                "backup_device": "device-2",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(configure_payload["unattended_task"]["task_id"], "task-1")
        self.assertEqual(configure_payload["unattended_task"]["primary_device_ids"], ["device-1"])
        self.assertEqual(configure_payload["unattended_task"]["backup_device_ids"], ["device-2"])
        self.assertEqual(configure_payload["unattended_task"]["rotation_strategy"], "round_robin")

        run_round_payload = self._post_json_or_skip(
            app,
            "/api/unattended/actions/run-round",
            {
                "task_id": "task-1",
                "monitoring_backend": "solox",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertTrue(run_round_payload["execution"]["executed"])
        self.assertEqual(run_round_payload["execution"]["round"]["run_id"], "run-1")

        patrol_payload = self._post_json_or_skip(
            app,
            "/api/unattended/actions/patrol",
            {
                "task_id": "task-1",
                "monitoring_backend": "solox",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(patrol_payload["patrol"]["executed_task_count"], 1)
        self.assertEqual(patrol_payload["patrol"]["quarantined_device_count"], 0)
        self.assertEqual(patrol_payload["patrol"]["metrics"]["instance_count"], 1)

    def test_web_write_entry_integrates_outbox_worker_replay_and_ci_sync(self) -> None:
        bundle = self._writable_bundle()
        bundle.integration_outbox_service.publish_event(
            event_type="admission_case.updated",
            target_type="admission_case",
            target_id="device_offline_default",
            created_by="tester",
            session_source="header:x-asl-session-token",
            payload={"final_decision": "conditional_pass"},
        )
        app = WebPortalApplication(bundle)

        register_im_payload = self._post_json_or_skip(
            app,
            "/api/integration/actions/register-im-webhook",
            {
                "name": "team-im",
                "url": "https://im.example.invalid/webhook",
                "signing_secret": "secret",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(register_im_payload["webhook"]["delivery_channel"], "im_notify")
        self.assertEqual(register_im_payload["webhook"]["delivery_contract_version"], "asl.im_notify.v1")

        worker_payload = self._post_json_or_skip(
            app,
            "/api/integration/outbox/actions/run-worker",
            {
                "webhook_name": "team-im",
                "event_types": "admission_case.updated",
                "limit_per_webhook": "10",
                "rounds": "1",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(worker_payload["worker"]["mode"], "delivery_worker_loop")
        self.assertEqual(worker_payload["delivery"]["rounds_executed"], 1)
        self.assertTrue(worker_payload["worker"]["supports_run_delivery_worker"])

        im_worker_payload = self._post_json_or_skip(
            app,
            "/api/integration/actions/run-im-worker",
            {
                "webhook_name": "team-im",
                "max_rounds": "1",
                "daemon": "1",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(im_worker_payload["mode"], "im_notify_worker")
        self.assertEqual(im_worker_payload["worker"]["mode"], "im_notification_daemon")

        replay_payload = self._post_json_or_skip(
            app,
            "/api/integration/outbox/actions/replay-dead-letters",
            {
                "event_id": "evt_dead_1",
                "limit": "10",
                "execute": "1",
                "replayed_by": "tester",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(replay_payload["worker"]["mode"], "dead_letter_replay")
        self.assertEqual(replay_payload["dead_letter_replay"]["replayed_count"], 0)

        ci_sync_payload = self._post_json_or_skip(
            app,
            "/api/integration/outbox/actions/sync-ci-admission-decisions",
            {
                "webhook_name": "ci-sync",
                "ci_endpoint": "https://ci.example.invalid/webhook",
                "event_types": "admission_case.updated",
                "limit": "10",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(ci_sync_payload["mode"], "ci_admission_decisions_sync")
        self.assertEqual(ci_sync_payload["query"]["pending_count"], 1)
        self.assertEqual(ci_sync_payload["delivery"]["delivered_count"], 1)

        register_defect_payload = self._post_json_or_skip(
            app,
            "/api/integration/actions/register-defect-webhook",
            {
                "name": "defect-sync",
                "url": "https://defect.example.invalid/webhook",
                "signing_secret": "secret",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(register_defect_payload["webhook"]["delivery_channel"], "defect_sync")
        self.assertEqual(register_defect_payload["webhook"]["delivery_contract_version"], "asl.defect_sync.v1")

        defect_worker_payload = self._post_json_or_skip(
            app,
            "/api/integration/actions/run-defect-worker",
            {
                "webhook_name": "defect-sync",
                "max_rounds": "1",
                "daemon": "1",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(defect_worker_payload["mode"], "defect_sync_worker")
        self.assertEqual(defect_worker_payload["worker"]["mode"], "defect_sync_daemon")

    def test_web_write_entry_handles_release_submission_flow(self) -> None:
        app = WebPortalApplication(self._writable_bundle())

        create_payload = self._post_json_or_skip(
            app,
            "/api/release-submissions/actions/create",
            {
                "source_platform": "release-center",
                "source_request_id": "REL-2026-002",
                "package_name": "com.hihonor.calculator",
                "version_name": "1.0.2",
                "version_code": "102",
                "build_id": "build-102",
                "release_channel": "gray",
                "owner_team": "android-client",
                "metrics": "cpu,memory",
                "sampling_interval": "5",
                "monitoring_backend": "solox",
                "execute_immediately": "1",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(create_payload["release_submission"]["source_request_id"], "REL-2026-002")
        self.assertEqual(create_payload["release_submission"]["submission_status"], "executed")
        submission_id = str(create_payload["release_submission"]["submission_id"])

        sync_payload = self._post_json_or_skip(
            app,
            "/api/release-submissions/actions/sync-admission",
            {
                "submission_id": submission_id,
                "baseline_key": "device_offline_default",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(sync_payload["release_submission"]["submission_status"], "admission_synced")
        self.assertEqual(sync_payload["release_submission"]["admission_final_decision"], "conditional_pass")

        register_payload = self._post_json_or_skip(
            app,
            "/api/integration/actions/register-release-webhook",
            {
                "name": "release-sync",
                "url": "https://release.example.invalid/webhook",
                "signing_secret": "secret",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(register_payload["webhook"]["delivery_channel"], "release_submission")
        self.assertEqual(register_payload["webhook"]["delivery_contract_version"], "asl.release_submission.v1")

        worker_payload = self._post_json_or_skip(
            app,
            "/api/integration/actions/run-release-worker",
            {
                "webhook_name": "release-sync",
                "max_rounds": "1",
                "daemon": "1",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(worker_payload["mode"], "release_submission_worker")
        self.assertEqual(worker_payload["worker"]["mode"], "release_submission_daemon")

        status, _, body = app.handle_request("/api/release-submissions")
        listing_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(listing_payload["summary"]["submission_count"], 2)
        self.assertEqual(listing_payload["summary"]["admission_synced_count"], 2)
        self.assertEqual(listing_payload["release_submissions"][0]["submission_id"], submission_id)

        status, _, body = app.handle_request("/api/integration/outbox")
        outbox_payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(outbox_payload["summary"]["release_webhook_count"], 1)
        event_types = [item["event_type"] for item in outbox_payload["events"]]
        self.assertIn("release_submission.created", event_types)
        self.assertIn("release_submission.execution_updated", event_types)
        self.assertIn("release_submission.admission_synced", event_types)

    def test_issue_defect_actions_are_available_in_web_api(self) -> None:
        app = WebPortalApplication(self._bundle())

        create_payload = self._post_json_or_skip(
            app,
            "/api/issues/actions/create-defect",
            {
                "fingerprint": "ifp_1",
                "system_key": "jira",
                "title": "首页冷启动偶发崩溃",
                "description": "需要同步到缺陷系统。",
                "team_key": "android-client",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(create_payload["action"], "create_issue_defect")
        self.assertEqual(create_payload["defect_link_count"], 1)
        self.assertEqual(create_payload["latest_defect_system_key"], "jira")

        sync_payload = self._post_json_or_skip(
            app,
            "/api/issues/actions/sync-defect",
            {
                "fingerprint": "ifp_1",
                "system_key": "jira",
                "defect_id": "ASL-1",
                "status": "accepted",
                "acceptable_for_close": "1",
                "url": "https://bugs.example.invalid/browse/ASL-1",
            },
            headers={"X-ASL-Actor": "tester"},
        )
        self.assertEqual(sync_payload["action"], "sync_issue_defect")
        self.assertTrue(sync_payload["has_acceptable_defect"])
        self.assertEqual(sync_payload["latest_defect_status"], "accepted")

    def _post_json_or_skip(
        self,
        app: WebPortalApplication,
        route: str,
        fields: dict[str, str],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        return web_portal_helpers.post_json_or_skip(self, app, route, fields, headers=headers)

    @staticmethod
    def _bundle(runner_status_override=None) -> object:
        return web_portal_helpers.bundle(runner_status_override=runner_status_override)

    @staticmethod
    def _writable_bundle() -> object:
        return web_portal_helpers.writable_bundle()

    @staticmethod
    def _bundle_with_missing_latest_audit() -> object:
        return web_portal_helpers.bundle_with_missing_latest_audit()


if __name__ == "__main__":
    unittest.main()
