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


class RuleReviewReportSnapshotMixin:
    @staticmethod
    def _golden_suite_summary_from_report_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_count": int(summary.get("golden_suite_snapshot_count", 0) or 0),
            "passed_snapshot_count": int(summary.get("golden_suite_passed_snapshot_count", 0) or 0),
            "failed_snapshot_count": int(summary.get("golden_suite_failed_snapshot_count", 0) or 0),
            "case_count_total": int(summary.get("golden_suite_case_count_total", 0) or 0),
            "passed_case_count_total": int(summary.get("golden_suite_passed_case_count_total", 0) or 0),
            "failed_case_count_total": int(summary.get("golden_suite_failed_case_count_total", 0) or 0),
            "versions": list(summary.get("golden_suite_versions", ()) or ()),
            "suite_paths": list(summary.get("golden_suite_suite_paths", ()) or ()),
            "layer_summaries": {
                str(key): dict(value)
                for key, value in dict(summary.get("golden_suite_layer_summaries", {}) or {}).items()
            },
        }

    def _select_review_snapshots(
        self,
        *,
        snapshot_created_by: str,
        decision: str,
        policy_version: str,
        baseline_path: str,
        candidate_path: str,
        created_from: str,
        created_to: str,
        limit: int,
    ) -> list[AnalysisSnapshotRecord]:
        summaries = self._snapshot_service.list_snapshots(snapshot_type="review", limit=1000000)
        lower = self._parse_datetime(created_from)
        upper = self._parse_datetime(created_to)
        matched: list[AnalysisSnapshotRecord] = []
        for summary in summaries:
            if snapshot_created_by and summary.created_by != snapshot_created_by:
                continue
            if lower and summary.created_at < lower:
                continue
            if upper and summary.created_at > upper:
                continue
            record = self._snapshot_service.get_snapshot(summary.snapshot_id)
            payload = record.payload if isinstance(record.payload, Mapping) else {}
            if decision and str(payload.get("decision", "") or "") != decision:
                continue
            if policy_version and str(payload.get("policy_version", "") or "") != policy_version:
                continue
            if baseline_path and str(payload.get("baseline_path", "") or "") != baseline_path:
                continue
            if candidate_path and str(payload.get("candidate_path", "") or "") != candidate_path:
                continue
            matched.append(record)
        matched.sort(key=lambda item: item.created_at, reverse=True)
        return matched[: max(0, int(limit))]

    @staticmethod
    def _parse_datetime(raw: str) -> datetime | None:
        value = raw.strip()
        if not value:
            return None
        return datetime.fromisoformat(value)

    @classmethod
    def _entry_from_snapshot(cls, item: AnalysisSnapshotRecord) -> RuleReviewReportEntry:
        payload = item.payload if isinstance(item.payload, Mapping) else {}
        summary = item.summary if isinstance(item.summary, Mapping) else {}
        golden_suite = payload.get("golden_suite", {}) or {}
        if not isinstance(golden_suite, Mapping):
            golden_suite = {}
        return RuleReviewReportEntry(
            snapshot_id=item.snapshot_id,
            name=item.name,
            created_at=item.created_at,
            created_by=item.created_by,
            decision=str(payload.get("decision", summary.get("decision", "")) or ""),
            policy_version=str(payload.get("policy_version", item.rule_versions.get("policy_version", "")) or ""),
            baseline_path=str(payload.get("baseline_path", item.scope.get("baseline_path", "")) or ""),
            candidate_path=str(payload.get("candidate_path", item.scope.get("candidate_path", "")) or ""),
            changed_family_count=int(payload.get("changed_family_count", summary.get("changed_family_count", 0)) or 0),
            finding_count=len(payload.get("findings", ()) or ()),
            change_summary=dict(payload.get("change_summary", {}) or {}),
            reasons=tuple(payload.get("reasons", ()) or ()),
            golden_suite_passed=(
                bool(golden_suite.get("passed", False))
                if golden_suite or "golden_suite" in payload
                else None
            ),
            golden_suite_case_count=int(golden_suite.get("case_count", 0) or 0),
            golden_suite_passed_case_count=int(golden_suite.get("passed_case_count", 0) or 0),
            golden_suite_failed_case_count=int(golden_suite.get("failed_case_count", 0) or 0),
            golden_suite_version=str(golden_suite.get("suite_version", "") or ""),
            golden_suite_suite_path=str(golden_suite.get("suite_path", "") or ""),
            golden_suite_layer_summaries={
                str(key): dict(value)
                for key, value in dict(golden_suite.get("layer_summaries", {}) or {}).items()
            },
            performance_summary=dict(payload.get("performance_summary", summary.get("performance_summary", {}) or {})),
            performance_risk_items=tuple(
                cls._risk_item_from_payload(entry)
                for entry in (payload.get("performance_risk_items", ()) or ())
                if isinstance(entry, Mapping)
            ),
            detail_path=item.detail_path,
            markdown_path=item.markdown_path,
        )

    @classmethod
    def _high_risk_families(cls, records: Sequence[AnalysisSnapshotRecord]) -> list[RuleReviewFamilySummary]:
        bucket: dict[str, dict[str, Any]] = {}
        for record in records:
            payload = record.payload if isinstance(record.payload, Mapping) else {}
            decision = str(payload.get("decision", "") or "")
            for family in payload.get("families", ()) or ():
                if not isinstance(family, Mapping):
                    continue
                change_type = str(family.get("change_type", "") or "")
                if not change_type or change_type == "unchanged":
                    continue
                issue_type = str(family.get("issue_type", "") or "")
                package_name = str(family.get("package_name", "") or "")
                scenario_name = str(family.get("scenario_name", "") or "")
                title = str(family.get("title", "") or "")
                key = json.dumps(
                    {
                        "issue_type": issue_type,
                        "package_name": package_name,
                        "scenario_name": scenario_name,
                        "title": title,
                        "change_type": change_type,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                item = bucket.setdefault(
                    key,
                    {
                        "issue_type": issue_type,
                        "package_name": package_name,
                        "scenario_name": scenario_name,
                        "title": title,
                        "change_type": change_type,
                        "snapshot_ids": set(),
                        "total_occurrence_count": 0,
                        "highest_decision": decision or "pass",
                    },
                )
                item["snapshot_ids"].add(record.snapshot_id)
                item["total_occurrence_count"] += max(
                    int(family.get("left_occurrence_count", 0) or 0),
                    int(family.get("right_occurrence_count", 0) or 0),
                )
                item["highest_decision"] = cls._max_decision(item["highest_decision"], decision or "pass")

        summaries = [
            RuleReviewFamilySummary(
                family_key=key,
                issue_type=value["issue_type"],
                package_name=value["package_name"],
                scenario_name=value["scenario_name"],
                title=value["title"],
                change_type=value["change_type"],
                snapshot_count=len(value["snapshot_ids"]),
                total_occurrence_count=int(value["total_occurrence_count"]),
                highest_decision=value["highest_decision"],
                sample_snapshot_ids=tuple(sorted(value["snapshot_ids"])[:5]),
            )
            for key, value in bucket.items()
        ]
        summaries.sort(
            key=lambda item: (
                cls._decision_priority(item.highest_decision),
                cls._change_priority(item.change_type),
                item.snapshot_count,
                item.total_occurrence_count,
                item.family_key,
            ),
            reverse=True,
        )
        return summaries[:20]

    @classmethod
    def _summary(
        cls,
        entries: Sequence[RuleReviewReportEntry],
        high_risk_families: Sequence[RuleReviewFamilySummary],
    ) -> dict[str, Any]:
        decision_counts = Counter(item.decision for item in entries)
        policy_versions = sorted({item.policy_version for item in entries if item.policy_version})
        candidate_paths = sorted({item.candidate_path for item in entries if item.candidate_path})
        baseline_paths = sorted({item.baseline_path for item in entries if item.baseline_path})
        golden_entries = [item for item in entries if item.golden_suite_passed is not None]
        golden_versions = sorted({item.golden_suite_version for item in golden_entries if item.golden_suite_version})
        golden_suite_paths = sorted(
            {item.golden_suite_suite_path for item in golden_entries if item.golden_suite_suite_path}
        )
        performance_comparison_dimensions = sorted(
            {
                str(item.performance_summary.get("dimension", "") or "")
                for item in entries
                if str(item.performance_summary.get("dimension", "") or "")
            }
        )
        performance_comparability_notes = sorted(
            {
                str(note)
                for item in entries
                for note in (item.performance_summary.get("comparability_notes", ()) or ())
                if str(note).strip()
            }
        )
        performance_metric_result_summary: Counter[str] = Counter()
        performance_risk_items: list[QualityGateRiskItem] = []
        seen_performance_risk_keys: set[str] = set()
        for item in entries:
            metric_summary = dict(item.performance_summary.get("metric_result_summary", {}) or {})
            for key, value in metric_summary.items():
                try:
                    performance_metric_result_summary[str(key)] += int(value or 0)
                except (TypeError, ValueError):
                    continue
            for risk_item in item.performance_risk_items:
                risk_key = json.dumps(
                    {
                        "risk_key": risk_item.risk_key,
                        "summary": risk_item.summary,
                        "source": risk_item.source,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                if risk_key in seen_performance_risk_keys:
                    continue
                seen_performance_risk_keys.add(risk_key)
                performance_risk_items.append(risk_item)
        golden_layer_summaries: dict[str, dict[str, Any]] = {}
        for item in golden_entries:
            for layer, payload in dict(item.golden_suite_layer_summaries or {}).items():
                bucket = golden_layer_summaries.setdefault(
                    str(layer),
                    {
                        "snapshot_count": 0,
                        "case_count_total": 0,
                        "passed_case_count_total": 0,
                        "failed_case_count_total": 0,
                        "issue_types": set(),
                        "expectations": set(),
                        "case_ids": set(),
                    },
                )
                bucket["snapshot_count"] = int(bucket["snapshot_count"]) + 1
                bucket["case_count_total"] = int(bucket["case_count_total"]) + int(payload.get("case_count", 0) or 0)
                bucket["passed_case_count_total"] = int(bucket["passed_case_count_total"]) + int(
                    payload.get("passed_case_count", 0) or 0
                )
                bucket["failed_case_count_total"] = int(bucket["failed_case_count_total"]) + int(
                    payload.get("failed_case_count", 0) or 0
                )
                bucket["issue_types"].update(payload.get("issue_types", ()) or ())
                bucket["expectations"].update(payload.get("expectations", ()) or ())
                bucket["case_ids"].update(payload.get("case_ids", ()) or ())
        return {
            "snapshot_count": len(entries),
            "decision_counts": dict(decision_counts),
            "policy_versions": policy_versions,
            "candidate_paths": candidate_paths,
            "baseline_paths": baseline_paths,
            "changed_family_count_total": sum(item.changed_family_count for item in entries),
            "finding_count_total": sum(item.finding_count for item in entries),
            "high_risk_family_count": len(high_risk_families),
            "golden_suite_snapshot_count": len(golden_entries),
            "golden_suite_passed_snapshot_count": sum(
                1 for item in golden_entries if item.golden_suite_passed is True
            ),
            "golden_suite_failed_snapshot_count": sum(
                1 for item in golden_entries if item.golden_suite_passed is False
            ),
            "golden_suite_case_count_total": sum(item.golden_suite_case_count for item in golden_entries),
            "golden_suite_passed_case_count_total": sum(
                item.golden_suite_passed_case_count for item in golden_entries
            ),
            "golden_suite_failed_case_count_total": sum(
                item.golden_suite_failed_case_count for item in golden_entries
            ),
            "golden_suite_versions": golden_versions,
            "golden_suite_suite_paths": golden_suite_paths,
            "golden_suite_layer_summaries": {
                layer: {
                    "snapshot_count": int(payload["snapshot_count"]),
                    "case_count_total": int(payload["case_count_total"]),
                    "passed_case_count_total": int(payload["passed_case_count_total"]),
                    "failed_case_count_total": int(payload["failed_case_count_total"]),
                    "issue_types": sorted(payload["issue_types"]),
                    "expectations": sorted(payload["expectations"]),
                    "case_ids": sorted(payload["case_ids"]),
                }
                for layer, payload in golden_layer_summaries.items()
            },
            "performance_comparison_dimensions": performance_comparison_dimensions,
            "performance_comparability_notes": performance_comparability_notes,
            "metric_result_summary": dict(performance_metric_result_summary),
            "performance_risk_snapshot_count": sum(1 for item in entries if item.performance_risk_items),
            "performance_risk_count_total": sum(len(item.performance_risk_items) for item in entries),
            "performance_risk_items": [cls._risk_item_payload(item) for item in performance_risk_items[:20]],
        }

    @staticmethod
    def _family_delta_priority(value: str) -> int:
        order = {"added": 4, "removed": 3, "changed": 2, "unchanged": 1}
        return order.get(value, 0)

    @staticmethod
    def _decision_priority(value: str) -> int:
        order = {"fail": 3, "conditional_pass": 2, "pass": 1}
        return order.get(value, 0)

    @staticmethod
    def _change_priority(value: str) -> int:
        order = {"regrouped": 5, "added": 4, "removed": 3, "fingerprint_changed": 2, "count_changed": 1}
        return order.get(value, 0)

    @classmethod
    def _max_decision(cls, left: str, right: str) -> str:
        return left if cls._decision_priority(left) >= cls._decision_priority(right) else right
