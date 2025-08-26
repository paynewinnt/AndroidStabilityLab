from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping
from urllib.parse import quote


from .detail_page import AdmissionDetailPageMixin
from .golden_page import GoldenAdmissionPageMixin
from .quality_page import QualityPageMixin

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
