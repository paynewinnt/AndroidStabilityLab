from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping
from urllib.parse import quote


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
