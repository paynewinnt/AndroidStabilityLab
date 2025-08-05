from __future__ import annotations

from ...application_common import *


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





class GoldenAdmissionPageMixin:
    def _admission_view_cards(self, payload: Mapping[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        cards = [
            ("待我处理", int(summary.get("mine_count", 0) or 0), list(payload.get("mine", []) or [])),
            (
                "待确认准入",
                int(summary.get("pending_confirmation_count", 0) or 0),
                list(payload.get("pending_confirmation", []) or []),
            ),
            (
                "已放行但有风险",
                int(summary.get("approved_with_risk_count", 0) or 0),
                list(payload.get("approved_with_risk", []) or []),
            ),
        ]
        markup = []
        for title, count, items in cards:
            preview = (
                "、".join(str(item.get("baseline_key", "") or "") for item in items[:3])
                if items
                else "当前为空"
            )
            markup.append(
                "<article class='card stack'>"
                f"<h3>{escape(title)}</h3>"
                f"<div>{self._status_pill(str(count), tone='ok' if count == 0 else 'warning')}</div>"
                f"<div class='meta'>{escape(preview)}</div>"
                "</article>"
            )
        return "<div class='cards'>" + "".join(markup) + "</div>"

    def _golden_case_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有可展示的 golden case。")
        cards = []
        for item in items:
            case_id = str(item.get("case_id", "") or "")
            cards.append(
                "<article class='golden-case-row'>"
                "<div class='golden-case-main'>"
                f"<h3>{escape(case_id)}</h3>"
                f"<p>{escape(str(item.get('description', '') or '暂无描述'))}</p>"
                "</div>"
                "<div class='golden-case-tags'>"
                f"<span class='pill'>{escape(str(item.get('issue_type', '') or 'n/a'))}</span>"
                f"<span class='pill'>{escape(str(item.get('layer', '') or 'n/a'))}</span>"
                f"<span class='pill'>{escape(str(item.get('expectation', '') or 'n/a'))}</span>"
                "</div>"
                "<div class='golden-case-meta'>"
                f"<span><b>package</b>{escape(str(item.get('package_name', '') or 'n/a'))}</span>"
                f"<span><b>source_run</b><span class='mono'>{escape(str(item.get('source_run_id', '') or 'n/a'))}</span></span>"
                f"<span><b>issue_count</b>{escape(str(item.get('issue_count', 0)))}</span>"
                "</div>"
                f"<a class='action-link' href='/goldens/case/{quote(case_id, safe='')}'>查看详情</a>"
                "</article>"
            )
        return "<div class='golden-case-list'>" + "".join(cards) + "</div>"

    def _golden_diff_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有 diff 结果。")
        cards = []
        for item in items:
            changed_fields = list(item.get("changed_fields", []) or [])
            field_diff_summary = list(item.get("field_diff_summary", []) or [])
            block_diff_summary = list(item.get("block_diff_summary", []) or [])
            left_link = str(item.get("left_case_link", "") or "")
            right_link = str(item.get("right_case_link", "") or "")
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('case_id', '')))}</h3>"
                f"<div><span class='pill'>{escape(str(item.get('change_type', '')))}</span></div>"
                + (
                    "<div>changed_fields："
                    + ", ".join(f"<span class='mono'>{escape(field)}</span>" for field in changed_fields)
                    + "</div>"
                    if changed_fields
                    else "<div class='meta'>没有字段级变化明细</div>"
                )
                + (
                    "<div class='meta'>字段差异摘要</div><ul class='link-list'>"
                    + "".join(
                        "<li>"
                        f"<span class='mono'>{escape(str(diff.get('field', '')))}</span>"
                        f"：Left={escape(str(diff.get('left', '')))} / Right={escape(str(diff.get('right', '')))}"
                        "</li>"
                        for diff in field_diff_summary
                    )
                    + "</ul>"
                    if field_diff_summary
                    else ""
                )
                + (
                    "<details><summary>展开关键块摘要</summary><div class='stack'>"
                    + "".join(
                        "<article class='card stack'>"
                        f"<div class='meta'>{escape(str(block.get('label', '')))}</div>"
                        f"<div>状态：Left={escape(str(block.get('left_status', '')))} / Right={escape(str(block.get('right_status', '')))} / {'changed' if bool(block.get('changed')) else 'same'}</div>"
                        f"<div>Left：<span class='mono'>{escape(str(block.get('left_preview', '')))}</span></div>"
                        f"<div>Right：<span class='mono'>{escape(str(block.get('right_preview', '')))}</span></div>"
                        "</article>"
                        for block in block_diff_summary
                    )
                    + "</div></details>"
                    if block_diff_summary
                    else ""
                )
                + "<div>"
                + (f"<a href='{escape(left_link, quote=True)}'>查看 Left Case</a>" if left_link else "Left Case n/a")
                + " / "
                + (f"<a href='{escape(right_link, quote=True)}'>查看 Right Case</a>" if right_link else "Right Case n/a")
                + "</div>"
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _golden_diff_filter_bar(self, *, payload: Mapping[str, Any]) -> str:
        filters = dict(payload.get("filters", {}) or {})
        summary = dict(payload.get("summary", {}) or {})
        active_change_type = str(filters.get("change_type", "") or "")
        active_changed_field = str(filters.get("changed_field", "") or "")
        case_query = str(filters.get("case_query", "") or "")
        available_change_types = list(filters.get("available_change_types", []) or [])
        available_changed_fields = list(filters.get("available_changed_fields", []) or [])
        links = [
            self._golden_diff_filter_link(payload=payload, label="全部", change_type="", active=(not active_change_type))
        ]
        for item in available_change_types:
            links.append(
                self._golden_diff_filter_link(
                    payload=payload,
                    label=item,
                    change_type=item,
                    active=(active_change_type == item),
                )
            )
        field_links = [
            self._golden_diff_filter_link(
                payload=payload,
                label="全部字段",
                changed_field="",
                active=(not active_changed_field),
            )
        ]
        for item in available_changed_fields:
            field_links.append(
                self._golden_diff_filter_link(
                    payload=payload,
                    label=item,
                    changed_field=item,
                    active=(active_changed_field == item),
                )
            )
        return (
            "<div class='cards'><article class='card stack'>"
            f"<div class='meta'>diff 过滤：{escape(str(summary.get('diff_count', 0)))} / {escape(str(summary.get('total_diff_count', 0)))}，按变化类型、字段和 case_id 搜索</div>"
            f"<div>{' '.join(links)}</div>"
            f"<div>{' '.join(field_links)}</div>"
            + self._golden_diff_search_form(payload=payload, case_query=case_query)
            + "</article></div>"
        )

    def _golden_diff_search_form(self, *, payload: Mapping[str, Any], case_query: str) -> str:
        filters = dict(payload.get("filters", {}) or {})
        hidden_fields = [
            ("left_path", str(payload.get("left_path", "") or "")),
            ("right_path", str(payload.get("right_path", "") or "")),
            ("change_type", str(filters.get("change_type", "") or "")),
            ("changed_field", str(filters.get("changed_field", "") or "")),
        ]
        if bool(filters.get("include_unchanged", False)):
            hidden_fields.append(("include_unchanged", "1"))
        hidden_fields.extend(
            ("case_id", str(item))
            for item in list(filters.get("case_ids", []) or [])
            if str(item).strip()
        )
        markup = "".join(
            f"<input type='hidden' name='{escape(name, quote=True)}' value='{escape(value, quote=True)}' />"
            for name, value in hidden_fields
            if value
        )
        return (
            "<form method='get' action='/goldens/diff' class='stack'>"
            + markup
            + "<label>搜索 case_id"
            f"<input type='text' name='case_query' value='{escape(case_query, quote=True)}' placeholder='例如 crash_regroup' />"
            "</label>"
            "<div><button type='submit'>应用搜索</button> "
            + self._golden_diff_reset_link(payload=payload)
            + "</div></form>"
        )

    def _golden_diff_reset_link(self, *, payload: Mapping[str, Any]) -> str:
        left_path = str(payload.get("left_path", "") or "")
        right_path = str(payload.get("right_path", "") or "")
        include_unchanged = bool(dict(payload.get("filters", {}) or {}).get("include_unchanged", False))
        query_parts = [
            f"left_path={quote(left_path, safe='')}",
            f"right_path={quote(right_path, safe='')}",
        ]
        if include_unchanged:
            query_parts.append("include_unchanged=1")
        return f"<a href='/goldens/diff?{'&'.join(query_parts)}'>清空过滤</a>"

    def _baseline_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前还没有规则评审基线。")
        cards = []
        for item in items:
            summary = dict(item.get("latest_audit_summary", {}) or {})
            golden_suite = dict(item.get("current_report_golden_suite", {}) or {})
            recent_versions = list(item.get("recent_versions", []) or [])
            version_markup = "".join(
                "<li>"
                f"{escape(str(version.get('action', '')))} / "
                f"{escape(str(version.get('changed_at', '')))} / "
                f"<span class='mono'>{escape(str(version.get('report_id', '')))}</span>"
                "</li>"
                for version in recent_versions
            )
            golden_failed_cases = int(golden_suite.get("failed_case_count_total", 0) or 0)
            golden_case_count = int(golden_suite.get("case_count_total", 0) or 0)
            auto_decision = str(item.get("automatic_decision", "") or "n/a")
            final_decision = str(item.get("final_decision", "") or auto_decision)
            golden_status = (
                "pass"
                if golden_suite and golden_failed_cases == 0
                else "fail"
                if golden_suite and golden_failed_cases > 0
                else "n/a"
            )
            baseline_key = str(item.get("baseline_key", "") or "")
            owner = str(item.get("assignee_display_name", "") or item.get("assignee_id", "") or "unassigned")
            reviewer = str(item.get("final_reviewer_display_name", "") or item.get("final_reviewer_id", "") or "n/a")
            regression = str(dict(item.get("regression_summary", {}) or {}).get("overall_result", "n/a"))
            total_runs = int(dict(item.get("execution_summary", {}) or {}).get("total_runs", 0) or 0)
            artifact_links = self._artifact_links(
                "快速跳转",
                [
                    ("Latest Audit HTML", item.get("latest_audit_html_path", "")),
                    ("Latest Audit Markdown", item.get("latest_audit_markdown_path", "")),
                ],
            )
            cards.append(
                (
                    "<article class='admission-case-row'>"
                    + "<div class='admission-case-main'>"
                    + f"<h3>{escape(baseline_key)}</h3>"
                    + f"<p>当前报告：{escape(str(item.get('report_name', '') or 'n/a'))}</p>"
                    + "</div>"
                    + "<div class='admission-case-pills'>"
                    + f"<span class='pill'>auto: {escape(auto_decision)}</span>"
                    + f"<span class='pill'>final: {escape(final_decision)}</span>"
                    + f"<span class='pill'>status: {escape(str(item.get('status', 'new') or 'new'))}</span>"
                    + f"<span class='pill'>golden: {escape(golden_status)}</span>"
                    + (f" <span class='pill'>override</span>" if item.get("has_override") else "")
                    + "</div>"
                    + "<div class='admission-case-meta'>"
                    + f"<span><b>case</b>runs={total_runs} / top={int(item.get('top_issue_count', 0) or 0)} / regression={escape(regression)}</span>"
                    + f"<span><b>协作</b>owner={escape(owner)} / reviewer={escape(reviewer)} / comments={escape(str(item.get('comment_count', 0) or 0))}</span>"
                    + f"<span><b>质量门禁</b>triggered={int(item.get('triggered_rule_count', 0) or 0)} / risk={int(item.get('risk_count', 0) or 0)} / perf={int(item.get('performance_risk_count', 0) or 0)} / coverage={int(item.get('coverage_gap_count', 0) or 0)}</span>"
                    + f"<span><b>Golden</b>cases={golden_case_count} / failed={golden_failed_cases} / versions={escape(', '.join(golden_suite.get('versions', []) or []) or 'n/a')}</span>"
                    + f"<span><b>latest</b>versions={escape(str(item.get('latest_audit_version_count', 0)))} / actions={escape(json.dumps(summary.get('action_counts', {}), ensure_ascii=False))}</span>"
                    + "</div>"
                    + (
                        f"<div class='admission-case-opinion'>最终意见：{escape(str(item.get('final_review_opinion', '') or 'n/a'))}</div>"
                        if str(item.get("final_review_opinion", "") or "").strip()
                        else ""
                    )
                    + (f"<div class='admission-case-links'>{artifact_links}</div>" if artifact_links else "")
                    + f"<div class='admission-case-actions'><a class='action-link' href='/admission/baseline/{quote(baseline_key, safe='')}'>查看详情</a></div>"
                    + (
                        f"<details class='compact-details admission-case-versions'><summary>最近版本</summary><ul class='link-list'>{version_markup}</ul></details>"
                        if version_markup
                        else ""
                    )
                    + "</article>"
                )
            )
        return "<div class='admission-case-list'>" + "".join(cards) + "</div>"

    def _admission_case_summary_card(self, item: Mapping[str, Any]) -> str:
        if not item:
            return self._notice("当前还没有独立 Admission Case。")
        filters = dict(item.get("filters", {}) or {})
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(item.get('case_id', '') or 'n/a'))}</h3>"
            f"<div class='meta'>baseline={escape(str(item.get('baseline_key', '') or 'n/a'))} / report={escape(str(item.get('report_name', '') or 'n/a'))}</div>"
            f"<div>协作状态：{self._status_pill(str(item.get('status', 'new') or 'new'), tone=self._workflow_state_tone(str(item.get('status', 'new') or 'new')))}</div>"
            f"<div>责任人：{escape(str(item.get('assignee_display_name', '') or item.get('assignee_id', '') or 'unassigned'))}</div>"
            f"<div>最终评审：{escape(str(item.get('final_reviewer_display_name', '') or item.get('final_reviewer_id', '') or 'n/a'))}</div>"
            f"<div>评论：{escape(str(item.get('comment_count', 0) or 0))}</div>"
            f"<div>最终意见：{escape(str(item.get('final_review_opinion', '') or 'n/a'))}</div>"
            "<details><summary>Case Filters</summary><pre class='mono'>"
            + escape(json.dumps(filters, ensure_ascii=False, indent=2))
            + "</pre></details>"
            + "</article></div>"
        )

    def _admission_formal_report_card(self, item: Mapping[str, Any]) -> str:
        if not item:
            return self._notice("当前还没有正式准入报告。", tone="warning")
        top_issue_summary = dict(item.get("top_issue_summary", {}) or {})
        performance_risk_summary = dict(item.get("performance_risk_summary", {}) or {})
        manual_overrides = dict(item.get("manual_overrides", {}) or {})
        external_sync = dict(item.get("external_sync_summary", {}) or {})
        evidence_refs = dict(item.get("evidence_refs", {}) or {})
        recommended_actions = list(item.get("recommended_actions", []) or [])
        action_markup = "".join(f"<li>{escape(str(action))}</li>" for action in recommended_actions)
        top_issue_items = list(top_issue_summary.get("items", []) or [])
        perf_items = list(performance_risk_summary.get("items", []) or [])
        top_issue_label = (
            str(dict(top_issue_items[0]).get("title", "") or dict(top_issue_items[0]).get("fingerprint", "") or "n/a")
            if top_issue_items and isinstance(top_issue_items[0], Mapping)
            else "n/a"
        )
        performance_label = (
            str(dict(perf_items[0]).get("summary", "") or dict(perf_items[0]).get("risk_key", "") or "n/a")
            if perf_items and isinstance(perf_items[0], Mapping)
            else "n/a"
        )
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(item.get('final_decision', '') or 'unknown'))}</h3>"
            f"<div class='meta'>contract={escape(str(item.get('report_contract_version', '') or 'admission_report.v1'))} / source={escape(str(item.get('source', '') or 'unknown'))}</div>"
            f"<div>风险等级：{self._status_pill(str(item.get('risk_level', 'unknown') or 'unknown'), tone='danger' if str(item.get('risk_level', '')).lower() in {'critical', 'high'} else 'warning')}</div>"
            f"<div>Top Issue：{escape(top_issue_label)}（count={escape(str(top_issue_summary.get('count', 0))) }）</div>"
            f"<div>性能风险：{escape(performance_label)}（count={escape(str(performance_risk_summary.get('count', 0))) }）</div>"
            f"<div>人工覆盖：{'yes' if manual_overrides.get('has_override') else 'no'} / {escape(str(manual_overrides.get('final_review_opinion', '') or 'n/a'))}</div>"
            "<details><summary>外部回写</summary><pre class='mono'>"
            + escape(json.dumps(external_sync, ensure_ascii=False, indent=2))
            + "</pre></details>"
            "<details><summary>证据引用</summary><pre class='mono'>"
            + escape(json.dumps(evidence_refs, ensure_ascii=False, indent=2))
            + "</pre></details>"
            + "<div class='meta'>建议动作</div>"
            + (f"<ul class='link-list'>{action_markup}</ul>" if action_markup else self._notice("当前没有建议动作。"))
            + f"<div><a href='/api/admission/reports/{quote(str(item.get('baseline_key', '') or ''), safe='')}'>查看报告 JSON</a></div>"
            + "</article></div>"
        )

    def _admission_case_assign_form(self, item: Mapping[str, Any]) -> str:
        baseline_key = str(item.get("baseline_key", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        return (
            "<details><summary>认领 / 转派</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/admission/actions/assign', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='baseline_key' value='{escape(baseline_key, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>责任人<input type='text' name='assignee_id' value='developer' placeholder='developer' /></label>"
            "<div><button type='submit'>提交认领</button></div>"
            "</form></details>"
        )

    def _admission_case_transition_form(self, item: Mapping[str, Any]) -> str:
        baseline_key = str(item.get("baseline_key", "") or "")
        current = str(item.get("status", "") or "new")
        current_actor = dict(item.get("current_actor", {}) or {})
        options = "".join(
            f"<option value='{escape(state, quote=True)}'{' selected' if state == current else ''}>{escape(state)}</option>"
            for state in (
                "new",
                "assigned",
                "reviewing",
                "pending_confirmation",
                "approved_with_risk",
                "approved",
                "rejected",
            )
        )
        return (
            "<details><summary>状态流转</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/admission/actions/transition', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='baseline_key' value='{escape(baseline_key, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            f"<label>目标状态<select name='workflow_state'>{options}</select></label>"
            "<label>原因<input type='text' name='reason' value='' placeholder='例如 进入待确认准入或已签字放行' /></label>"
            "<div><button type='submit'>更新状态</button></div>"
            "</form></details>"
        )

    def _admission_case_comment_form(self, item: Mapping[str, Any]) -> str:
        baseline_key = str(item.get("baseline_key", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        return (
            "<details><summary>评论讨论</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/admission/actions/comment', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='baseline_key' value='{escape(baseline_key, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>评论<textarea name='body' rows='3' placeholder='记录放行依据、风险备注或补充证据'></textarea></label>"
            "<div><button type='submit'>提交评论</button></div>"
            "</form></details>"
        )





class QualityPageMixin:
    def _admission_case_collaboration_timeline(self, item: Mapping[str, Any]) -> str:
        events = list(item.get("events", []) or [])
        if not events:
            return self._notice("当前准入单还没有协作动作。")
        cards = []
        for event in events:
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(event.get('action', '') or 'event'))}</h3>"
                f"<div class='meta'>{escape(str(event.get('created_by', '') or ''))} / {escape(str(event.get('created_at', '') or ''))}</div>"
                f"<div>session_source={escape(str(event.get('session_source', '') or 'n/a'))}</div>"
                "<details><summary>审计字段</summary><pre class='mono'>"
                + escape(json.dumps(dict(event.get('audit_source', {}) or {}), ensure_ascii=False, indent=2))
                + "</pre></details>"
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _admission_case_execution_card(self, item: Mapping[str, Any]) -> str:
        recent_runs = list(item.get("recent_runs", []) or [])
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>runs={escape(str(item.get('total_runs', 0)))}</h3>"
            f"<div class='meta'>latest={escape(str(item.get('latest_run_id', '') or 'n/a'))} / {escape(str(item.get('latest_run_status', '') or 'n/a'))}</div>"
            f"<div>failed_runs：{escape(str(item.get('failed_run_count', 0)))}</div>"
            f"<div>issue_runs：{escape(str(item.get('issue_run_count', 0)))}</div>"
            "<details><summary>Status Counts</summary><pre class='mono'>"
            + escape(json.dumps(dict(item.get("status_counts", {}) or {}), ensure_ascii=False, indent=2))
            + "</pre></details>"
            "<details><summary>Recent Runs</summary><pre class='mono'>"
            + escape(json.dumps(recent_runs, ensure_ascii=False, indent=2))
            + "</pre></details>"
            + "</article></div>"
        )

    def _admission_case_top_issue_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前 admission case 还没有匹配到 Top Issue。", tone="warning")
        cards = []
        for item in items:
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('title', '') or 'n/a'))}</h3>"
                f"<div class='meta'>{escape(str(item.get('fingerprint', '') or ''))}</div>"
                f"<div><span class='pill'>{escape(str(item.get('issue_type', '') or ''))}</span>"
                f" <span class='pill'>{escape(str(item.get('severity', '') or ''))}</span></div>"
                f"<div>occurrence={escape(str(item.get('occurrence_count', 0)))} / affected_runs={escape(str(item.get('affected_run_count', 0)))}</div>"
                f"<div>affected_scenarios={escape(', '.join(item.get('affected_scenarios', []) or []) or 'n/a')}</div>"
                + self._issue_evidence_summary(item)
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _admission_case_regression_card(self, item: Mapping[str, Any]) -> str:
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(item.get('overall_result', 'insufficient_data')))}</h3>"
            f"<div class='meta'>available={'yes' if item.get('available') else 'no'} / dimension={escape(str(item.get('dimension', '') or 'n/a'))}</div>"
            "<details><summary>Regression Summary</summary><pre class='mono'>"
            + escape(json.dumps(dict(item), ensure_ascii=False, indent=2))
            + "</pre></details>"
            + "</article></div>"
        )

    def _admission_case_scenario_coverage_card(self, item: Mapping[str, Any]) -> str:
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(item.get('coverage_state', 'missing') or 'missing'))}</h3>"
            f"<div class='meta'>scenario_count={escape(str(item.get('scenario_count', 0)))} / issue_scenario_count={escape(str(item.get('issue_scenario_count', 0)))}</div>"
            f"<div>scenarios：{escape(', '.join(item.get('scenarios', []) or []) or 'n/a')}</div>"
            f"<div>issue_scenarios：{escape(', '.join(item.get('issue_scenarios', []) or []) or 'n/a')}</div>"
            "<details><summary>Coverage Notes</summary><pre class='mono'>"
            + escape(json.dumps(list(item.get("notes", []) or []), ensure_ascii=False, indent=2))
            + "</pre></details>"
            + "</article></div>"
        )

    def _quality_gate_summary_card(self, item: Mapping[str, Any]) -> str:
        if not item:
            return self._notice("当前还没有独立质量门禁结果。")
        failure_reasons = list(item.get("failure_reasons", []) or [])
        reason_markup = "".join(f"<li>{escape(str(reason))}</li>" for reason in failure_reasons)
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(item.get('baseline_key', '')))}</h3>"
            f"<div><span class='pill'>automatic: {escape(str(item.get('automatic_decision', 'n/a')))}</span>"
            f" <span class='pill'>final: {escape(str(item.get('final_decision', 'n/a')))}</span>"
            + (f" <span class='pill'>manual override</span>" if item.get("has_override") else "")
            + "</div>"
            f"<div>最终评审意见：{escape(str(item.get('final_review_opinion', '') or 'n/a'))}</div>"
            f"<div>风险项：{int(item.get('risk_count', 0) or 0)} / 性能风险：{int(item.get('performance_risk_count', 0) or 0)} / 覆盖不足：{int(item.get('coverage_gap_count', 0) or 0)}</div>"
            + ("<ul class='link-list'>" + reason_markup + "</ul>" if reason_markup else "")
            + "</article></div>"
        )

    def _quality_gate_rule_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有触发任何质量门禁规则。")
        return "<div class='cards'>" + "".join(
            (
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('rule_name', '')))}</h3>"
                f"<div><span class='pill'>{escape(str(item.get('decision_on_trigger', '')))}</span>"
                f" <span class='pill'>{escape(str(item.get('rule_version', '')))}</span></div>"
                f"<div>observed={escape(str(item.get('observed_value', '')))} / threshold={escape(str(item.get('threshold', '')))}</div>"
                f"<div>{escape(str(item.get('message', '')))}</div>"
                f"<div class='meta'>{escape(str(item.get('source', '')))}</div>"
                "</article>"
            )
            for item in items
        ) + "</div>"

    def _quality_gate_risk_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有需要额外提示的风险项。")
        return "<div class='cards'>" + "".join(
            (
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('summary', '')))}</h3>"
                f"<div><span class='pill'>{escape(str(item.get('category', '')))}</span>"
                f" <span class='pill'>{escape(str(item.get('severity', '')))}</span>"
                + (f" <span class='pill'>blocks</span>" if item.get("blocks_admission") else "")
                + "</div>"
                + (
                    "<pre class='mono'>"
                    + escape(json.dumps(dict(item.get("details", {}) or {}), ensure_ascii=False, indent=2))
                    + "</pre>"
                )
                + self._performance_risk_detail_summary(item)
                + f"<div class='meta'>{escape(str(item.get('source', '')))}</div>"
                + "</article>"
            )
            for item in items
        ) + "</div>"

    def _performance_risk_detail_summary(self, item: Mapping[str, Any]) -> str:
        bits = []
        for key in self._performance_risk_detail_fields():
            value = item.get(key, None)
            if value in (None, "", (), []):
                continue
            if isinstance(value, Mapping):
                value_text = json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
            elif isinstance(value, (list, tuple)):
                value_text = ", ".join(str(part) for part in value)
            else:
                value_text = str(value)
            bits.append(f"{key}={value_text}")
        if not bits:
            return ""
        return "<div class='meta'>风险解释：" + escape(" / ".join(bits)) + "</div>"

    def _quality_gate_coverage_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有覆盖不足项。")
        return "<div class='cards'>" + "".join(
            (
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('summary', '')))}</h3>"
                f"<div><span class='pill'>{escape(str(item.get('category', '')))}</span>"
                f" <span class='pill'>{escape(str(item.get('severity', '')))}</span></div>"
                f"<div>observed={escape(str(item.get('observed_value', '')))} / required={escape(str(item.get('required_value', '')))}</div>"
                f"<div class='meta'>{escape(str(item.get('source', '')))}</div>"
                "</article>"
            )
            for item in items
        ) + "</div>"

    def _quality_gate_override_card(self, item: Mapping[str, Any]) -> str:
        if not item:
            return self._notice("当前没有人工覆盖记录。")
        evidence = list(item.get("evidence_paths", []) or [])
        evidence_markup = "".join(f"<li><span class='mono'>{escape(str(path))}</span></li>" for path in evidence)
        return (
            "<div class='cards'><article class='card stack'>"
            f"<h3>{escape(str(item.get('created_by', '')))}</h3>"
            f"<div><span class='pill'>auto: {escape(str(item.get('automatic_decision', '')))}</span>"
            f" <span class='pill'>final: {escape(str(item.get('final_decision', '')))}</span></div>"
            f"<div>原因：{escape(str(item.get('reason', '')))}</div>"
            + (
                f"<div>备注：{escape(str(item.get('comment', '')))}</div>"
                if str(item.get("comment", "") or "").strip()
                else ""
            )
            + (
                "<ul class='link-list'>"
                + evidence_markup
                + "</ul>"
                if evidence_markup
                else ""
            )
            + f"<div class='meta'>{escape(str(item.get('created_at', '')))}</div>"
            + "</article></div>"
        )

    def _quality_gate_override_form(
        self,
        *,
        baseline_key: str,
        actors: list[dict[str, Any]],
        current_actor: Mapping[str, Any],
    ) -> str:
        actor_options = ", ".join(
            f"{item.get('actor_id', '')}({item.get('role_key', '')})"
            for item in actors[:6]
            if str(item.get("actor_id", "")).strip()
        )
        hint = actor_options or "tester, admin"
        return (
            "<div class='cards'><article class='card stack'>"
            "<h3>提交人工覆盖</h3>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/admission/actions/override', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='baseline_key' value='{escape(baseline_key, quote=True)}' />"
            f"<div class='meta'>可用本地 actor：{escape(hint)}</div>"
            f"<div class='meta'>当前覆盖人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>最终结论<select name='final_decision'>"
            "<option value='pass'>pass</option>"
            "<option value='conditional_pass'>conditional_pass</option>"
            "<option value='fail'>fail</option>"
            "</select></label>"
            "<label>覆盖原因<input type='text' name='reason' value='' placeholder='必填，例如 已知风险已签字放行' /></label>"
            "<label>备注<textarea name='comment' rows='3' placeholder='补充说明、关联单号或风险备注'></textarea></label>"
            "<label>证据路径<input type='text' name='evidence_paths' value='' placeholder='逗号分隔，例如 runtime/release-waiver.md' /></label>"
            "<div><button type='submit'>提交覆盖</button></div>"
            "</form></article></div>"
        )

    @staticmethod
    def _actor_scoped_path(path: str, *, current_actor: Mapping[str, Any]) -> str:
        session_token = str(current_actor.get("session_token", "") or "").strip()
        actor_id = str(current_actor.get("actor_id", "") or "").strip()
        if session_token:
            separator = "&" if "?" in path else "?"
            return f"{path}{separator}as_session={quote(session_token, safe='')}"
        if not actor_id:
            return path
        separator = "&" if "?" in path else "?"
        return f"{path}{separator}as_actor={quote(actor_id, safe='')}"

    def _current_actor_card(
        self,
        *,
        current_actor: Mapping[str, Any],
        actors: list[dict[str, Any]],
        current_path: str,
    ) -> str:
        actor_id = str(current_actor.get("actor_id", "") or "tester")
        display_name = str(current_actor.get("display_name", "") or actor_id)
        role_key = str(current_actor.get("role_key", "") or "n/a")
        session_source = str(current_actor.get("session_source", "") or "default")
        options = "".join(
            f"<option value='{escape(str(item.get('actor_id', '') or ''), quote=True)}'{' selected' if str(item.get('actor_id', '') or '') == actor_id else ''}>{escape(str(item.get('display_name', item.get('actor_id', '')) or ''))}</option>"
            for item in actors
            if str(item.get("actor_id", "") or "").strip()
        )
        if not options:
            options = f"<option value='{escape(actor_id, quote=True)}' selected>{escape(display_name)}</option>"
        identity_id = str(current_actor.get("identity_id", "") or "")
        session_id = str(current_actor.get("session_id", "") or "")
        auth_mechanism = str(current_actor.get("auth_mechanism", "") or "n/a")
        return (
            "<article class='card current-actor-compact'>"
            "<div class='current-actor-main'>"
            "<div>"
            "<div class='meta'>当前身份</div>"
            f"<strong>{escape(display_name)}</strong>"
            f"<span class='meta'> actor_id={escape(actor_id)} / role={escape(role_key)} / auth={escape(auth_mechanism)}</span>"
            "</div>"
            "<details class='compact-details current-actor-details'>"
            "<summary>身份细节</summary>"
            f"<div class='meta'>source={escape(session_source)}</div>"
            f"<div class='meta'>identity_id={escape(identity_id or 'n/a')}</div>"
            f"<div class='meta'>session_id={escape(session_id or 'n/a')}</div>"
            "<div class='meta'>GET 支持 X-ASL-Actor / as_actor 切换只读视角；POST 仅绑定 X-ASL-Actor 或稳定 session token。</div>"
            "</details>"
            "</div>"
            "<form method='get' action='{path}' class='current-actor-switch'>"
            .format(path=escape(current_path, quote=True))
            + "<label><span class='meta'>切换本地 actor</span><select name='as_actor'>"
            + options
            + "</select></label>"
            + "<button type='submit'>切换身份</button>"
            + "</form>"
            + "</article>"
        )

    def _baseline_version_table(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有 latest audit 版本索引。")
        rows = []
        for item in items:
            rows.append(
                "<tr>"
                f"<td data-label='Action'>{escape(str(item.get('action', '')))}</td>"
                f"<td data-label='Changed At'>{escape(str(item.get('changed_at', '')))}</td>"
                f"<td data-label='Changed By'>{escape(str(item.get('changed_by', '')))}</td>"
                f"<td data-label='Report'><span class='mono'>{escape(str(item.get('report_id', '')))}</span></td>"
                "<td data-label='Audit HTML'>"
                + self._inline_link("Audit HTML", item.get("html_path", ""))
                + (" / " + self._inline_link("Audit JSON", item.get("detail_path", "")) if item.get("detail_path", "") else "")
                + (" / " + self._inline_link("Audit Markdown", item.get("markdown_path", "")) if item.get("markdown_path", "") else "")
                + "</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Action</th><th>Changed At</th><th>Changed By</th><th>Report</th><th>Audit HTML</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    def _comparison_report_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前这条基线还没有可跳转的 comparison report。")
        cards = []
        for item in items:
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('comparison_id', '')))}</h3>"
                f"<div class='meta'>{escape(str(item.get('action', '')))} / {escape(str(item.get('changed_at', '')))}</div>"
                f"<div>report: <span class='mono'>{escape(str(item.get('report_id', '')))}</span></div>"
                + self._artifact_links(
                    "Comparison 跳转",
                    [
                        ("Comparison HTML", item.get("html_path", "")),
                        ("Comparison Markdown", item.get("markdown_path", "")),
                        ("Comparison JSON", item.get("detail_path", "")),
                    ],
                )
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _baseline_history_timeline(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前这条基线还没有可展示的 history。")
        cards = []
        for item in items:
            reasons = list(item.get("reasons", []) or [])
            detail_links = (
                self._artifact_links(
                    "History 跳转",
                    [("Comparison JSON", item.get("comparison_detail_path", ""))],
                )
                if item.get("comparison_detail_path", "")
                else ""
            )
            detail_block = (
                "<details>"
                "<summary>展开详情</summary>"
                "<div class='stack'>"
                f"<div>policy_version: {escape(str(item.get('policy_version', '') or 'n/a'))}</div>"
                f"<div>comparison_id: <span class='mono'>{escape(str(item.get('comparison_id', '') or 'n/a'))}</span></div>"
                + detail_links
                + (
                    "<ul class='link-list'>"
                    + "".join(f"<li>{escape(str(reason))}</li>" for reason in reasons)
                    + "</ul>"
                    if reasons
                    else "<div class='meta'>没有附加原因</div>"
                )
                + "</div>"
                "</details>"
            )
            cards.append(
                "<article class='card stack'>"
                f"<h3>{escape(str(item.get('action', '')))}</h3>"
                f"<div class='meta'>{escape(str(item.get('changed_at', '')))} / {escape(str(item.get('changed_by', '')))}</div>"
                f"<div>report: <span class='mono'>{escape(str(item.get('report_id', '')))}</span></div>"
                + detail_block
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _baseline_history_filter_bar(self, *, baseline_key: str, filters: Mapping[str, Any]) -> str:
        action = str(filters.get("action", "") or "")
        comparison_only = bool(filters.get("comparison_only", False))
        available_actions = list(filters.get("available_actions", []) or [])
        total = int(filters.get("history_count_total", 0) or 0)
        filtered = int(filters.get("history_count_filtered", 0) or 0)
        links = [
            self._history_filter_link(
                baseline_key=baseline_key,
                label="全部",
                action="",
                comparison_only=False,
                active=(not action and not comparison_only),
            )
        ]
        for item in available_actions:
            links.append(
                self._history_filter_link(
                    baseline_key=baseline_key,
                    label=item,
                    action=item,
                    comparison_only=False,
                    active=(action == item and not comparison_only),
                )
            )
        links.append(
            self._history_filter_link(
                baseline_key=baseline_key,
                label="仅 Comparison",
                action=action,
                comparison_only=True,
                active=comparison_only,
            )
        )
        return (
            "<div class='cards'><article class='card stack'>"
            f"<div class='meta'>history 过滤：{filtered} / {total}</div>"
            f"<div>{' '.join(links)}</div>"
            "</article></div>"
        )

    def _status_summary_bar(
        self,
        summary: Mapping[str, Any],
        actions: Mapping[str, Any] | None = None,
    ) -> str:
        action_map = dict(actions or {})
        items = [
            ("Review", "review", summary.get("review", "missing"), "#section-review-report"),
            ("Comparison", "comparison", summary.get("comparison", "missing"), "#section-comparison-reports"),
            ("Latest Audit", "audit", summary.get("audit", "missing"), "#section-latest-audit"),
            ("Golden Suite", "golden", summary.get("golden", "missing"), "#section-golden-suite"),
        ]
        return "<div class='cards'>" + "".join(
            "<article class='card stack'>"
            f"<a href='{escape(anchor, quote=True)}'>"
            f"<div class='meta'>{escape(label)}</div>"
            f"<div><span class='pill'>{escape(str(value))}</span></div>"
            f"<div class='meta'>{escape(str(action_map.get(key, '')))}</div>"
            "</a>"
            "</article>"
            for label, key, value, anchor in items
        ) + "</div>"





class AdmissionRecordPageMixin(AdmissionDetailPageMixin, GoldenAdmissionPageMixin, QualityPageMixin):
    def _render_issues(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        body: list[str] = []
        flash = dict(payload.get("flash", {}) or {})
        if flash:
            body.append(self._notice(str(flash.get("message", "") or ""), tone=str(flash.get("tone", "ok") or "ok")))
        body.extend([
            self._metric_grid(
                [
                    ("聚合问题数", summary["issue_count"]),
                    ("Critical", summary["severity_counts"].get("critical", 0)),
                    ("High", summary["severity_counts"].get("high", 0)),
                    ("Crash 类", summary["issue_type_counts"].get("crash", 0)),
                    ("处理中", summary["state_counts"].get("processing", 0)),
                    ("已解决", summary["state_counts"].get("resolved", 0)),
                    ("协作参与者", summary["actor_count"]),
                ]
            ),
            self._section(
                "当前身份",
                [
                    self._current_actor_card(
                        current_actor=dict(payload.get("current_actor", {}) or {}),
                        actors=list(payload.get("actors", []) or []),
                        current_path="/issues",
                    )
                ],
            ),
            self._section("Top Issue", [self._issue_cards(payload["issues"])]),
        ])
        return self._layout(
            "问题中心",
            "先看影响面最大的聚合问题，也可以直接完成认领、评论和状态流转。",
            "".join(body),
        )

    def _render_goldens(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        filters = payload.get("filters", {})
        filter_bits = [
            f"suite={payload.get('suite_version', '') or 'n/a'}",
            f"issue_type={filters.get('issue_type', '') or 'all'}",
            f"layer={filters.get('layer', '') or 'all'}",
            f"expectation={filters.get('expectation', '') or 'all'}",
            f"limit={filters.get('limit', 0)}",
        ]
        body = [
            self._metric_grid(
                [
                    ("Case 总数", summary["case_count"]),
                    ("Layer 数", summary["layer_count"]),
                    ("Issue Type 数", summary["issue_type_count"]),
                    ("Expectation 数", summary["expectation_count"]),
                ]
            ),
            self._section(
                "Suite 概览",
                [
                    f"<p>suite_path：<span class='mono'>{escape(str(payload.get('suite_path', '')))}</span></p>",
                    f"<p>{escape(' / '.join(filter_bits))}</p>",
                    "<p><a href='/goldens/diff'>打开 Golden Suite Diff 只读页</a></p>",
                    "<details class='compact-details'><summary>查看统计 JSON</summary><pre class='mono compact-pre'>"
                    + escape(
                        json.dumps(
                            {
                                "layer_counts": summary.get("layer_counts", {}),
                                "issue_type_counts": summary.get("issue_type_counts", {}),
                                "expectation_counts": summary.get("expectation_counts", {}),
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    + "</pre></details>",
                ],
            ),
            self._section("Golden Cases", [self._golden_case_cards(list(payload.get("cases", []) or []))]),
        ]
        return self._layout(
            "Golden Suite",
            "这里用只读方式查看正式样本库，先看有哪些 case，再按单条样本下钻到完整 payload。",
            "".join(body),
        )

    def _render_golden_diff(self, payload: dict[str, Any]) -> str:
        summary = dict(payload.get("summary", {}) or {})
        change_counts = dict(summary.get("change_counts", {}) or {})
        filters = dict(payload.get("filters", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("Diff 数", summary.get("diff_count", 0)),
                    ("Modified", change_counts.get("modified", 0)),
                    ("Added", change_counts.get("added", 0)),
                    ("Removed", change_counts.get("removed", 0)),
                    ("Unchanged", change_counts.get("unchanged", 0)),
                ]
            ),
            self._section(
                "Diff 过滤",
                [self._golden_diff_filter_bar(payload=payload)],
            ),
            self._section(
                "Diff Scope",
                [
                    f"<p>left_path：<span class='mono'>{escape(str(payload.get('left_path', '')))}</span></p>",
                    f"<p>right_path：<span class='mono'>{escape(str(payload.get('right_path', '')) or 'n/a')}</span></p>",
                    f"<p>left_version：{escape(str(payload.get('left_suite_version', '') or 'n/a'))} / right_version：{escape(str(payload.get('right_suite_version', '') or 'n/a'))}</p>",
                    f"<p>当前筛选：{escape(str(summary.get('diff_count', 0)))} / {escape(str(summary.get('total_diff_count', 0)))} 条；change_type={escape(str(filters.get('change_type', '') or 'all'))}；changed_field={escape(str(filters.get('changed_field', '') or 'all'))}；case_query={escape(str(filters.get('case_query', '') or 'n/a'))}</p>",
                    "<pre class='mono'>"
                    + escape(json.dumps(filters, ensure_ascii=False, indent=2))
                    + "</pre>",
                ],
            ),
        ]
        if not bool(payload.get("comparison_ready", False)):
            body.append(
                self._section(
                    "如何使用",
                    [
                        self._notice(str(dict(payload.get("help", {}) or {}).get("message", ""))),
                        "<pre class='mono'>"
                        + escape(str(dict(payload.get("help", {}) or {}).get("example", "")))
                        + "</pre>",
                    ],
                )
            )
        else:
            body.append(
                self._section(
                    "Changed Cases",
                    [self._golden_diff_cards(list(payload.get("entries", []) or []))],
                )
            )
        return self._layout(
            "Golden Suite Diff",
            "这里用只读方式对比两份 golden suite，直接看新增、删除、修改和字段级变化。",
            "".join(body),
        )

    def _render_admission(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        views = dict(payload.get("views", {}) or {})
        body = [
            self._metric_grid(
                [
                    ("基线数", summary["baseline_count"]),
                    ("自动 Fail", summary["auto_decision_counts"].get("fail", 0)),
                    ("最终 Fail", summary["final_decision_counts"].get("fail", 0)),
                    ("人工覆盖", summary["override_count"]),
                    ("风险基线", summary["risk_baseline_count"]),
                    ("性能风险基线", summary["performance_risk_baseline_count"]),
                    ("覆盖不足基线", summary["coverage_gap_baseline_count"]),
                    ("Golden 基线", summary["golden_suite_baseline_count"]),
                    ("Golden 失败基线", summary["golden_suite_failed_baseline_count"]),
                    ("Golden 失败 Case", summary["golden_suite_failed_case_count_total"]),
                    ("Promote 记录", summary["action_counts"].get("promote", 0)),
                    ("Rollback 记录", summary["action_counts"].get("rollback", 0)),
                    ("Set 记录", summary["action_counts"].get("set", 0)),
                ]
            ),
            self._section(
                "当前身份",
                [
                    self._current_actor_card(
                        current_actor=dict(payload.get("current_actor", {}) or {}),
                        actors=list(payload.get("actors", []) or []),
                        current_path="/admission",
                    )
                ],
            ),
            self._section(
                "协作视图",
                [self._admission_view_cards(views)],
            ),
            self._section("质量门禁与准入 Case", [self._baseline_cards(payload["baselines"])]),
        ]
        return self._layout(
            "准入中心",
            "这里先看准入单协作视图和质量门禁结果，再继续下钻到当前报告、latest audit 和基线历史。",
            "".join(body),
        )

    def _render_golden_case_detail(self, payload: dict[str, Any]) -> str:
        summary = dict(payload["summary"])
        body = [
            self._metric_grid(
                [
                    ("Issue 数", summary.get("issue_count", 0)),
                    ("Layer", summary.get("layer", "")),
                    ("Expectation", summary.get("expectation", "")),
                    ("Include Unchanged", "yes" if summary.get("include_unchanged") else "no"),
                ]
            ),
            self._section(
                "Case Summary",
                [
                    (
                        "<div class='cards'><article class='card stack'>"
                        f"<h3>{escape(str(summary.get('case_id', '')))}</h3>"
                        f"<div class='meta'>{escape(str(summary.get('description', '')))}</div>"
                        f"<div><span class='pill'>{escape(str(summary.get('issue_type', '')))}</span>"
                        f"<span class='pill'>{escape(str(summary.get('layer', '')))}</span>"
                        f"<span class='pill'>{escape(str(summary.get('expectation', '')))}</span></div>"
                        f"<div>package：{escape(str(summary.get('package_name', '') or 'n/a'))}</div>"
                        f"<div>template：{escape(str(summary.get('template_type', '') or 'n/a'))}</div>"
                        f"<div>source_run：<span class='mono'>{escape(str(summary.get('source_run_id', '') or 'n/a'))}</span></div>"
                        f"<div><a href='/goldens'>返回 Golden Suite</a></div>"
                        "</article></div>"
                    )
                ],
            ),
            self._section(
                "Expected",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("expected", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-expected",
            ),
            self._section(
                "Baseline Rules",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("baseline_rules", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-baseline-rules",
            ),
            self._section(
                "Candidate Rules",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("candidate_rules", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-candidate-rules",
            ),
            self._section(
                "Filters",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("filters", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-filters",
            ),
            self._section(
                "Dataset",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("dataset", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-dataset",
            ),
            self._section(
                "Draft Metadata",
                ["<pre class='mono'>" + escape(json.dumps(payload.get("draft_metadata", {}), ensure_ascii=False, indent=2)) + "</pre>"],
                section_id="section-golden-draft-metadata",
            ),
        ]
        return self._layout(
            f"Golden Case · {summary.get('case_id', '')}",
            "单条黄金样本会把 summary、expected、rules、filters 和 dataset 一次性展开，方便直接检查样本定义。",
            "".join(body),
        )

__all__ = [
    "AdmissionDetailPageMixin",
    "GoldenAdmissionPageMixin",
    "QualityPageMixin",
    "AdmissionRecordPageMixin",
]
