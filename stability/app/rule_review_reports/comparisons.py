from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

from stability.domain import (
    AnalysisSnapshotRecord,
    QualityGateRiskItem,
    RuleReviewFamilySummary,
    RuleReviewReportBaselineAuditEvent,
    RuleReviewReportBaselineAuditRecord,
    RuleReviewReportBaselineAuditVersionRecord,
    RuleReviewReportBaselineAuditView,
    RuleReviewReportBaselineHistoryEntry,
    RuleReviewReportBaselineRecord,
    RuleReviewReportBaselinePromotionResult,
    RuleReviewReportBaselineRollbackResult,
    RuleReviewReportComparisonFamily,
    RuleReviewReportComparisonRecord,
    RuleReviewReportEntry,
    RuleReviewReportRecord,
)
from stability.domain.value_objects import new_id, utcnow


class RuleReviewReportComparisonMixin:
    def compare_reports(
        self,
        *,
        name: str,
        created_by: str,
        left_report_id: str,
        right_report_id: str,
        include_unchanged: bool = False,
    ) -> RuleReviewReportComparisonRecord:
        left = self.get_report(left_report_id.strip())
        right = self.get_report(right_report_id.strip())

        family_diffs = tuple(
            self._compare_family_summaries(
                left.high_risk_families,
                right.high_risk_families,
                include_unchanged=include_unchanged,
            )
        )
        summary = self._comparison_summary(left, right, family_diffs)

        comparison_id = new_id("review_report_compare")
        created_at = utcnow()
        report_dir = self._comparison_root_dir / comparison_id
        report_dir.mkdir(parents=True, exist_ok=False)
        detail_path = report_dir / "report.json"
        markdown_path = report_dir / "summary.md"
        html_path = report_dir / "report.html"

        record = RuleReviewReportComparisonRecord(
            comparison_id=comparison_id,
            name=name.strip(),
            created_at=created_at,
            created_by=created_by.strip() or "cli",
            left_report_id=left.report_id,
            right_report_id=right.report_id,
            left_report_name=left.name,
            right_report_name=right.name,
            left_detail_path=left.detail_path,
            right_detail_path=right.detail_path,
            summary=summary,
            family_diffs=family_diffs,
            detail_path=str(detail_path),
            markdown_path=str(markdown_path),
            html_path=str(html_path),
        )
        detail_path.write_text(
            json.dumps(self._comparison_payload(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_comparison_markdown(record), encoding="utf-8")
        html_path.write_text(self._render_comparison_html(record), encoding="utf-8")
        return record

    def compare_report_against_baseline(
        self,
        *,
        name: str,
        created_by: str,
        report_id: str,
        baseline_key: str = "",
        policy_version: str = "",
        candidate_path: str = "",
        include_unchanged: bool = False,
    ) -> RuleReviewReportComparisonRecord:
        target = self.get_report(report_id.strip())
        baseline_report = self._resolve_baseline_report(
            report_id=target.report_id,
            baseline_key=baseline_key,
            policy_version=policy_version,
            candidate_path=candidate_path,
        )
        return self.compare_reports(
            name=name,
            created_by=created_by,
            left_report_id=baseline_report.report_id,
            right_report_id=target.report_id,
            include_unchanged=include_unchanged,
        )

    def _resolve_baseline_report(
        self,
        *,
        report_id: str,
        baseline_key: str,
        policy_version: str,
        candidate_path: str,
    ) -> RuleReviewReportRecord:
        if baseline_key.strip():
            baseline = self.get_baseline(baseline_key.strip())
            if baseline.report_id == report_id:
                raise ValueError("Target report is already the selected baseline report.")
            return self.get_report(baseline.report_id)
        candidates = self._list_reports()
        matched: list[RuleReviewReportRecord] = []
        for item in candidates:
            if item.report_id == report_id:
                continue
            decision_counts = dict(item.summary.get("decision_counts", {}) or {})
            if int(decision_counts.get("fail", 0) or 0) > 0:
                continue
            if policy_version.strip():
                versions = set(item.summary.get("policy_versions", ()) or ())
                if policy_version.strip() not in versions:
                    continue
            if candidate_path.strip():
                paths = set(item.summary.get("candidate_paths", ()) or ())
                if candidate_path.strip() not in paths:
                    continue
            matched.append(item)
        matched.sort(key=lambda item: item.created_at, reverse=True)
        if not matched:
            raise ValueError("No accepted baseline report matched the requested criteria.")
        return matched[0]

    def _list_reports(self) -> list[RuleReviewReportRecord]:
        items: list[RuleReviewReportRecord] = []
        if not self._root_dir.exists():
            return items
        for path in sorted(self._root_dir.glob("review_report_*/report.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            try:
                items.append(self._record_from_payload(payload))
            except ValueError:
                continue
        return items

    @classmethod
    def _compare_family_summaries(
        cls,
        left_items: Sequence[RuleReviewFamilySummary],
        right_items: Sequence[RuleReviewFamilySummary],
        *,
        include_unchanged: bool,
    ) -> list[RuleReviewReportComparisonFamily]:
        left_by_key = {item.family_key: item for item in left_items}
        right_by_key = {item.family_key: item for item in right_items}
        keys = sorted(set(left_by_key) | set(right_by_key))
        rows: list[RuleReviewReportComparisonFamily] = []
        for key in keys:
            left = left_by_key.get(key)
            right = right_by_key.get(key)
            if left is None and right is not None:
                delta_status = "added"
            elif left is not None and right is None:
                delta_status = "removed"
            elif left is not None and right is not None:
                if (
                    left.snapshot_count == right.snapshot_count
                    and left.total_occurrence_count == right.total_occurrence_count
                    and left.highest_decision == right.highest_decision
                ):
                    delta_status = "unchanged"
                else:
                    delta_status = "changed"
            else:
                continue
            if delta_status == "unchanged" and not include_unchanged:
                continue
            source = right or left
            if source is None:
                continue
            rows.append(
                RuleReviewReportComparisonFamily(
                    family_key=key,
                    issue_type=source.issue_type,
                    package_name=source.package_name,
                    scenario_name=source.scenario_name,
                    title=source.title,
                    change_type=source.change_type,
                    delta_status=delta_status,
                    left_snapshot_count=left.snapshot_count if left else 0,
                    right_snapshot_count=right.snapshot_count if right else 0,
                    left_total_occurrence_count=left.total_occurrence_count if left else 0,
                    right_total_occurrence_count=right.total_occurrence_count if right else 0,
                    left_highest_decision=left.highest_decision if left else "",
                    right_highest_decision=right.highest_decision if right else "",
                )
            )
        rows.sort(
            key=lambda item: (
                cls._family_delta_priority(item.delta_status),
                cls._decision_priority(item.right_highest_decision or item.left_highest_decision),
                cls._change_priority(item.change_type),
                max(item.left_total_occurrence_count, item.right_total_occurrence_count),
                item.family_key,
            ),
            reverse=True,
        )
        return rows[:50]

    @classmethod
    def _comparison_summary(
        cls,
        left: RuleReviewReportRecord,
        right: RuleReviewReportRecord,
        family_diffs: Sequence[RuleReviewReportComparisonFamily],
    ) -> dict[str, Any]:
        left_counts = dict(left.summary.get("decision_counts", {}) or {})
        right_counts = dict(right.summary.get("decision_counts", {}) or {})
        decision_keys = sorted(set(left_counts) | set(right_counts))
        decision_deltas = {
            key: int(right_counts.get(key, 0) or 0) - int(left_counts.get(key, 0) or 0)
            for key in decision_keys
        }
        left_golden_suite = cls._golden_suite_summary_from_report_summary(left.summary)
        right_golden_suite = cls._golden_suite_summary_from_report_summary(right.summary)
        delta_counts = Counter(item.delta_status for item in family_diffs)
        return {
            "left_report_id": left.report_id,
            "right_report_id": right.report_id,
            "left_created_at": left.created_at.isoformat(),
            "right_created_at": right.created_at.isoformat(),
            "snapshot_count_delta": int(right.summary.get("snapshot_count", 0) or 0)
            - int(left.summary.get("snapshot_count", 0) or 0),
            "changed_family_count_total_delta": int(right.summary.get("changed_family_count_total", 0) or 0)
            - int(left.summary.get("changed_family_count_total", 0) or 0),
            "finding_count_total_delta": int(right.summary.get("finding_count_total", 0) or 0)
            - int(left.summary.get("finding_count_total", 0) or 0),
            "high_risk_family_count_delta": int(right.summary.get("high_risk_family_count", 0) or 0)
            - int(left.summary.get("high_risk_family_count", 0) or 0),
            "performance_risk_count_total_delta": int(right.summary.get("performance_risk_count_total", 0) or 0)
            - int(left.summary.get("performance_risk_count_total", 0) or 0),
            "metric_worsened_count_delta": int(
                dict(right.summary.get("metric_result_summary", {}) or {}).get("worsened_count", 0) or 0
            )
            - int(dict(left.summary.get("metric_result_summary", {}) or {}).get("worsened_count", 0) or 0),
            "left_golden_suite": left_golden_suite,
            "right_golden_suite": right_golden_suite,
            "golden_suite_snapshot_count_delta": int(right_golden_suite.get("snapshot_count", 0) or 0)
            - int(left_golden_suite.get("snapshot_count", 0) or 0),
            "golden_suite_passed_snapshot_count_delta": int(
                right_golden_suite.get("passed_snapshot_count", 0) or 0
            )
            - int(left_golden_suite.get("passed_snapshot_count", 0) or 0),
            "golden_suite_failed_snapshot_count_delta": int(
                right_golden_suite.get("failed_snapshot_count", 0) or 0
            )
            - int(left_golden_suite.get("failed_snapshot_count", 0) or 0),
            "golden_suite_case_count_total_delta": int(right_golden_suite.get("case_count_total", 0) or 0)
            - int(left_golden_suite.get("case_count_total", 0) or 0),
            "golden_suite_passed_case_count_total_delta": int(
                right_golden_suite.get("passed_case_count_total", 0) or 0
            )
            - int(left_golden_suite.get("passed_case_count_total", 0) or 0),
            "golden_suite_failed_case_count_total_delta": int(
                right_golden_suite.get("failed_case_count_total", 0) or 0
            )
            - int(left_golden_suite.get("failed_case_count_total", 0) or 0),
            "decision_count_deltas": decision_deltas,
            "family_delta_counts": dict(delta_counts),
        }
