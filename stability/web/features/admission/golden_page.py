from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping
from urllib.parse import quote


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
