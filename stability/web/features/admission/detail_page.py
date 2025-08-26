from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping
from urllib.parse import quote


class AdmissionDetailPageMixin:
    def _render_admission_detail(self, payload: dict[str, Any]) -> str:
        admission_case = dict(payload.get("admission_case", {}) or {})
        evidence = dict(payload.get("evidence", {}) or {})
        quality_gate = dict(evidence.get("quality_gate", {}) or payload.get("quality_gate", {}) or {})
        formal_report = dict(payload.get("formal_report", {}) or {})
        baseline = dict(payload["baseline"])
        report = dict(payload["report"])
        latest_audit = dict(payload["latest_audit"])
        latest_audit_error = str(payload.get("latest_audit_error", "") or "")
        golden_suite = dict(evidence.get("golden_suite", {}) or payload.get("golden_suite", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        status_summary = dict(payload.get("status_summary", {}) or {})
        status_actions = dict(payload.get("status_actions", {}) or {})
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        if latest_audit_error:
            body.append(self._notice(f"Latest Audit 暂不可用：{latest_audit_error}", tone="warning"))
        body.extend([
            self._metric_grid(
                [
                    ("Admission Case", admission_case.get("case_id", "n/a")),
                    ("报告结论", formal_report.get("final_decision", admission_case.get("final_decision", "n/a"))),
                    ("风险等级", formal_report.get("risk_level", "n/a")),
                    ("Case 状态", admission_case.get("status", "n/a")),
                    ("Case Revision", admission_case.get("revision", 1)),
                    ("执行 Run", dict(admission_case.get("execution_summary", {}) or {}).get("total_runs", 0)),
                    ("Top Issues", admission_case.get("top_issue_count", 0)),
                    ("回归结论", dict(admission_case.get("regression_summary", {}) or {}).get("overall_result", "n/a")),
                    ("场景覆盖", dict(admission_case.get("scenario_coverage", {}) or {}).get("coverage_state", "n/a")),
                    ("自动结论", quality_gate.get("automatic_decision", "n/a")),
                    ("最终结论", admission_case.get("final_decision", quality_gate.get("final_decision", "n/a"))),
                    ("人工覆盖", "yes" if quality_gate.get("has_override") else "no"),
                    ("责任人", admission_case.get("assignee_display_name", admission_case.get("assignee_id", "n/a")) or "n/a"),
                    ("最终评审", admission_case.get("final_reviewer_display_name", admission_case.get("final_reviewer_id", "n/a")) or "n/a"),
                    ("风险项", quality_gate.get("risk_count", 0)),
                    ("性能风险", quality_gate.get("performance_risk_count", 0)),
                    ("覆盖不足", quality_gate.get("coverage_gap_count", 0)),
                    ("Latest 版本数", baseline.get("latest_audit_version_count", 0)),
                    ("Golden Cases", golden_suite.get("case_count_total", 0)),
                    ("Golden Failed", golden_suite.get("failed_case_count_total", 0)),
                    ("Promote 记录", dict(latest_audit.get("summary", {}) or {}).get("action_counts", {}).get("promote", 0)),
                ]
            ),
            self._section(
                "正式准入报告",
                [self._admission_formal_report_card(formal_report)],
                section_id="section-formal-admission-report",
            ),
            self._section(
                "Admission Case",
                [self._admission_case_summary_card(admission_case)],
                section_id="section-admission-case",
            ),
            self._section(
                "准入协作",
                [
                    self._admission_case_assign_form(admission_case),
                    self._admission_case_transition_form(admission_case),
                    self._admission_case_comment_form(admission_case),
                    self._admission_case_collaboration_timeline(admission_case),
                ],
                section_id="section-admission-collaboration",
            ),
            self._section(
                "当前身份",
                [
                    self._current_actor_card(
                        current_actor=dict(payload.get("current_actor", {}) or {}),
                        actors=list(payload.get("actors", []) or []),
                        current_path=f"/admission/baseline/{quote(str(baseline.get('baseline_key', '') or ''), safe='')}",
                    )
                ],
                section_id="section-current-actor",
            ),
            self._section(
                "执行结果",
                [self._admission_case_execution_card(dict(admission_case.get("execution_summary", {}) or {}))],
                section_id="section-execution-summary",
            ),
            self._section(
                "Top Issues",
                [self._admission_case_top_issue_cards(list(admission_case.get("top_issues", []) or []))],
                section_id="section-top-issues",
            ),
            self._section(
                "回归摘要",
                [self._admission_case_regression_card(dict(admission_case.get("regression_summary", {}) or {}))],
                section_id="section-regression-summary",
            ),
            self._section(
                "场景覆盖",
                [self._admission_case_scenario_coverage_card(dict(admission_case.get("scenario_coverage", {}) or {}))],
                section_id="section-scenario-coverage",
            ),
            self._section(
                "质量门禁摘要",
                [self._quality_gate_summary_card(quality_gate)],
                section_id="section-quality-gate",
            ),
            self._section(
                "触发规则",
                [self._quality_gate_rule_cards(list(quality_gate.get("triggered_rules", []) or []))],
                section_id="section-triggered-rules",
            ),
            self._section(
                "风险提示",
                [
                    self._quality_gate_risk_cards(
                        list(quality_gate.get("risk_items", []) or [])
                        + list(quality_gate.get("performance_risk_items", []) or [])
                    )
                ],
                section_id="section-risk-items",
            ),
            self._section(
                "覆盖不足",
                [self._quality_gate_coverage_cards(list(quality_gate.get("coverage_gaps", []) or []))],
                section_id="section-coverage-gaps",
            ),
            self._section(
                "人工覆盖",
                [
                    self._quality_gate_override_card(dict(quality_gate.get("override", {}) or {})),
                    self._quality_gate_override_form(
                        baseline_key=str(baseline.get("baseline_key", "") or ""),
                        actors=list(payload.get("actors", []) or []),
                        current_actor=dict(payload.get("current_actor", {}) or {}),
                    ),
                ],
                section_id="section-manual-override",
            ),
            self._section(
                "状态摘要",
                [self._status_summary_bar(status_summary, status_actions)],
                section_id="section-status-summary",
            ),
            self._section(
                "当前基线",
                [
                    (
                        "<div class='cards'><article class='card stack'>"
                        f"<h3>{escape(str(baseline.get('baseline_key', '')))}</h3>"
                        f"<div class='meta'>当前报告：{escape(str(baseline.get('report_name', '')))}</div>"
                        f"<div>policy_versions：{escape(', '.join(baseline.get('policy_versions', []) or []) or 'n/a')}</div>"
                        f"<div>candidate_paths：{escape(', '.join(baseline.get('candidate_paths', []) or []) or 'n/a')}</div>"
                        f"<div>baseline_paths：{escape(', '.join(baseline.get('baseline_paths', []) or []) or 'n/a')}</div>"
                        + self._artifact_links(
                            "Latest Audit 跳转",
                            [
                                ("Latest Audit HTML", baseline.get("latest_audit_html_path", "")),
                                ("Latest Audit Markdown", baseline.get("latest_audit_markdown_path", "")),
                                ("Latest Audit JSON", baseline.get("latest_audit_detail_path", "")),
                                ("Latest Audit Index", baseline.get("latest_audit_index_path", "")),
                            ],
                        )
                        + "</article></div>"
                    )
                ],
            ),
            self._section(
                "Golden Suite",
                [
                    "<pre class='mono'>"
                    + escape(json.dumps(golden_suite, ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
                section_id="section-golden-suite",
            ),
            self._section(
                "Comparison Reports",
                [self._comparison_report_cards(list(payload.get("comparison_reports", []) or []))],
                section_id="section-comparison-reports",
            ),
            self._section(
                "Baseline History",
                [
                    self._baseline_history_filter_bar(
                        baseline_key=str(baseline.get("baseline_key", "") or ""),
                        filters=filters,
                    ),
                    self._baseline_history_timeline(list(payload.get("baseline_history", []) or [])),
                ],
                section_id="section-baseline-history",
            ),
            self._section(
                "当前报告摘要",
                [
                    self._artifact_links(
                        "当前报告跳转",
                        [
                            ("Review Report HTML", report.get("html_path", "")),
                            ("Review Report Markdown", report.get("markdown_path", "")),
                            ("Review Report JSON", report.get("detail_path", "")),
                        ],
                    ),
                    "<pre class='mono'>"
                    + escape(json.dumps(dict(report.get("summary", {}) or {}), ensure_ascii=False, indent=2))
                    + "</pre>"
                ],
                section_id="section-review-report",
            ),
            self._section(
                "Latest Audit",
                [
                    self._artifact_links(
                        "Latest Audit 跳转",
                        [
                            ("Latest Audit HTML", latest_audit.get("html_path", "")),
                            ("Latest Audit Markdown", latest_audit.get("markdown_path", "")),
                            ("Latest Audit JSON", latest_audit.get("detail_path", "")),
                            ("Latest Audit Index", latest_audit.get("index_path", "")),
                        ],
                    ),
                    "<pre class='mono'>"
                    + escape(json.dumps(dict(latest_audit.get("summary", {}) or {}), ensure_ascii=False, indent=2))
                    + "</pre>",
                ],
                section_id="section-latest-audit",
            ),
            self._section(
                "最近版本",
                [self._baseline_version_table(list(latest_audit.get("versions", []) or []))],
                section_id="section-latest-versions",
            ),
        ])
        return self._layout(
            f"准入详情 · {baseline.get('baseline_key', '')}",
            "从总览进入单条准入 case 后，先看自动/最终结论，再下钻到当前报告、golden suite、latest audit 和最近版本。",
            "".join(body),
        )
