from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping


class PerformanceIssueCardsMixin:
    def _issue_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return self._notice("当前没有聚合问题。")
        cards = []
        for item in items:
            chips = "".join(
                f"<span class='pill'>{escape(str(chip))}</span>"
                for chip in (
                    item.get("issue_type", ""),
                    item.get("severity", ""),
                    f"occ:{item.get('occurrence_count', 0)}",
                    f"dev:{item.get('affected_device_count', 0)}",
                )
                if chip
            )
            cards.append(
                "<article class='card stack'>"
                + f"<h3>{escape(str(item.get('title', '')))}</h3>"
                + f"<div>{chips}</div>"
                + f"<div class='mono'>{escape(str(item.get('fingerprint', '')))}</div>"
                + f"<div>协作状态：{self._status_pill(str(item.get('workflow_state', 'new') or 'new'), tone=self._workflow_state_tone(str(item.get('workflow_state', 'new') or 'new')))}</div>"
                + f"<div>责任人：{escape(str(item.get('assignee_display_name', '') or item.get('assignee_id', '') or 'unassigned'))}</div>"
                + f"<div>评论：{escape(str(item.get('comment_count', 0) or 0))}</div>"
                + f"<div>缺陷：{escape(str(item.get('defect_link_count', 0) or 0))} / 可关闭={escape('yes' if item.get('has_acceptable_defect') else 'no')}</div>"
                + self._issue_evidence_summary(item)
                + self._issue_attribution_summary(item)
                + (
                    f"<div class='meta'>最新评论：{escape(str(item.get('latest_comment_by', '') or ''))} / {escape(str(item.get('latest_comment_body', '') or ''))}</div>"
                    if str(item.get("latest_comment_body", "") or "").strip()
                    else ""
                )
                + self._issue_defect_cards(list(item.get("defect_links", []) or []))
                + f"<div class='meta'>最近出现：{escape(str(item.get('last_seen_at', '')))}</div>"
                + f"<div>场景：{escape(', '.join(item.get('affected_scenarios', [])[:3]))}</div>"
                + f"<div>包名：{escape(', '.join(item.get('affected_packages', [])[:3]))}</div>"
                + self._issue_assign_form(item)
                + self._issue_transition_form(item)
                + self._issue_comment_form(item)
                + self._issue_create_defect_form(item)
                + self._issue_sync_defect_form(item)
                + "</article>"
            )
        return "<div class='cards'>" + "".join(cards) + "</div>"

    def _issue_evidence_summary(self, item: Mapping[str, Any]) -> str:
        evidence_signals = item.get("evidence_signals", None)
        confirmation_level = str(item.get("confirmation_level", "") or "")
        if not evidence_signals and not confirmation_level:
            return ""
        if isinstance(evidence_signals, Mapping):
            evidence_text = json.dumps(dict(evidence_signals), ensure_ascii=False, sort_keys=True)
        elif isinstance(evidence_signals, (list, tuple)):
            evidence_text = ", ".join(str(value) for value in evidence_signals)
        else:
            evidence_text = str(evidence_signals or "n/a")
        return (
            "<div class='meta'>高级异常证据："
            f"confirmation_level={escape(confirmation_level or 'n/a')} / "
            f"evidence_signals={escape(evidence_text or 'n/a')}"
            "</div>"
        )

    def _issue_attribution_summary(self, item: Mapping[str, Any]) -> str:
        attribution = dict(item.get("attribution", {}) or {})
        if not attribution:
            return ""
        direction = str(attribution.get("direction_label", "") or attribution.get("direction", "") or "")
        confidence = str(attribution.get("confidence_score", "") or attribution.get("confidence", "") or "")
        matched_rule_ids = attribution.get("matched_rule_ids", None) or attribution.get("matched_rule_id", "")
        rows = [
            f"方向={escape(direction or 'n/a')}",
            f"置信度={escape(confidence or 'n/a')}",
            f"命中规则={escape(self._compact_value_text(matched_rule_ids) or 'n/a')}",
        ]
        evidence_text = self._compact_value_text(attribution.get("evidence_summary", ""))
        if evidence_text:
            rows.append(f"证据摘要={escape(evidence_text)}")
        next_steps_text = self._compact_value_text(attribution.get("recommended_next_steps", ""))
        if next_steps_text:
            rows.append(f"建议动作={escape(next_steps_text)}")
        review_notes_text = self._compact_value_text(attribution.get("review_notes", ""))
        if review_notes_text:
            rows.append(f"Review Notes={escape(review_notes_text)}")
        return "<div class='meta'>初步归因建议：" + " / ".join(rows) + "</div>"

    def _issue_assign_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        return (
            "<details><summary>认领 / 转派</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/assign', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>责任人<input type='text' name='assignee_id' value='developer' placeholder='developer' required /></label>"
            "<div><button type='submit'>提交认领</button></div>"
            "</form></details>"
        )

    def _issue_transition_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current = str(item.get("workflow_state", "") or "new")
        current_actor = dict(item.get("current_actor", {}) or {})
        options = "".join(
            f"<option value='{escape(state, quote=True)}'{' selected' if state == current else ''}>{escape(state)}</option>"
            for state in ("new", "assigned", "processing", "confirmed", "resolved", "ignored")
        )
        return (
            "<details><summary>状态流转</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/transition', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            f"<label>目标状态<select name='workflow_state' required>{options}</select></label>"
            "<label>原因<input type='text' name='reason' value='' placeholder='例如 已确认并转研发处理' /></label>"
            "<div><button type='submit'>更新状态</button></div>"
            "</form></details>"
        )

    def _issue_comment_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        return (
            "<details><summary>评论讨论</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/comment', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>评论<textarea name='body' rows='3' placeholder='记录复现、风险说明或处理结论' required></textarea></label>"
            "<div><button type='submit'>提交评论</button></div>"
            "</form></details>"
        )

    def _issue_create_defect_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        default_title = str(item.get("title", "") or "")
        return (
            "<details><summary>创建缺陷请求</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/create-defect', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            "<label>系统标识<input type='text' name='system_key' value='defect_system' placeholder='例如 jira / zentao' required /></label>"
            f"<label>标题<input type='text' name='title' value='{escape(default_title, quote=True)}' placeholder='缺陷标题' required /></label>"
            "<label>责任团队<input type='text' name='team_key' value='' placeholder='可选，例如 client_android' /></label>"
            "<label>描述<textarea name='description' rows='3' placeholder='补充复现、影响范围、证据路径'></textarea></label>"
            "<div><button type='submit'>创建缺陷请求</button></div>"
            "</form></details>"
        )

    def _issue_sync_defect_form(self, item: Mapping[str, Any]) -> str:
        fingerprint = str(item.get("fingerprint", "") or "")
        current_actor = dict(item.get("current_actor", {}) or {})
        latest_link = dict((list(item.get("defect_links", []) or []) or [{}])[-1] or {})
        return (
            "<details><summary>同步缺陷状态</summary>"
            f"<form method='post' action='{escape(self._actor_scoped_path('/issues/actions/sync-defect', current_actor=current_actor), quote=True)}' class='stack'>"
            f"<input type='hidden' name='fingerprint' value='{escape(fingerprint, quote=True)}' />"
            f"<div class='meta'>当前操作人：{escape(str(current_actor.get('display_name', current_actor.get('actor_id', 'tester')) or 'tester'))}</div>"
            f"<label>Link ID<input type='text' name='link_id' value='{escape(str(latest_link.get('link_id', '') or ''), quote=True)}' placeholder='优先使用 link_id' /></label>"
            f"<label>系统标识<input type='text' name='system_key' value='{escape(str(latest_link.get('system_key', '') or ''), quote=True)}' placeholder='例如 jira / zentao' /></label>"
            f"<label>缺陷单号<input type='text' name='defect_id' value='{escape(str(latest_link.get('defect_id', '') or ''), quote=True)}' placeholder='例如 AND-1234' /></label>"
            f"<label>状态<input type='text' name='status' value='{escape(str(latest_link.get('status', '') or ''), quote=True)}' placeholder='例如 fixed / verified / waived' required /></label>"
            f"<label>链接<input type='text' name='url' value='{escape(str(latest_link.get('url', '') or ''), quote=True)}' placeholder='https://example.invalid/ticket/1234' /></label>"
            "<label>允许关闭<select name='acceptable_for_close'><option value='0'>否</option><option value='1'>是</option></select></label>"
            "<div><button type='submit'>同步缺陷状态</button></div>"
            "</form></details>"
        )

    def _issue_defect_cards(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "<div class='meta'>当前还没有关联缺陷。</div>"
        cards = []
        for item in items:
            cards.append(
                "<details><summary>缺陷联动</summary><article class='card stack'>"
                f"<div><span class='pill'>{escape(str(item.get('system_key', '') or 'defect_system'))}</span>"
                f" <span class='pill'>{escape(str(item.get('status', '') or 'pending'))}</span>"
                + (f" <span class='pill'>acceptable</span>" if item.get("acceptable_for_close") else "")
                + "</div>"
                f"<div>defect_id={escape(str(item.get('defect_id', '') or 'pending_create'))}</div>"
                f"<div>title={escape(str(item.get('title', '') or 'n/a'))}</div>"
                f"<div>sync_status={escape(str(item.get('sync_status', '') or 'n/a'))}</div>"
                + (
                    f"<div><a href='{escape(str(item.get('url', '') or ''), quote=True)}'>打开外部缺陷</a></div>"
                    if str(item.get("url", "") or "").strip()
                    else ""
                )
                + "</article></details>"
            )
        return "".join(cards)


__all__ = ["PerformanceIssueCardsMixin"]
