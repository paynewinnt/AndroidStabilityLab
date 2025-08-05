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


class RuleReviewReportSerializerMixin:
    @staticmethod
    def _payload(item: RuleReviewReportRecord) -> dict[str, Any]:
        return {
            "report_id": item.report_id,
            "name": item.name,
            "created_at": item.created_at.isoformat(),
            "created_by": item.created_by,
            "filters": dict(item.filters),
            "summary": dict(item.summary),
            "entries": [asdict(entry) | {"created_at": entry.created_at.isoformat()} for entry in item.entries],
            "high_risk_families": [asdict(entry) for entry in item.high_risk_families],
            "detail_path": item.detail_path,
            "markdown_path": item.markdown_path,
            "html_path": item.html_path,
        }

    @staticmethod
    def _comparison_payload(item: RuleReviewReportComparisonRecord) -> dict[str, Any]:
        return {
            "comparison_id": item.comparison_id,
            "name": item.name,
            "created_at": item.created_at.isoformat(),
            "created_by": item.created_by,
            "left_report_id": item.left_report_id,
            "right_report_id": item.right_report_id,
            "left_report_name": item.left_report_name,
            "right_report_name": item.right_report_name,
            "left_detail_path": item.left_detail_path,
            "right_detail_path": item.right_detail_path,
            "summary": dict(item.summary),
            "family_diffs": [asdict(entry) for entry in item.family_diffs],
            "detail_path": item.detail_path,
            "markdown_path": item.markdown_path,
            "html_path": item.html_path,
        }

    @staticmethod
    def _baseline_audit_payload(item: RuleReviewReportBaselineAuditRecord) -> dict[str, Any]:
        return {
            "audit_id": item.audit_id,
            "name": item.name,
            "created_at": item.created_at.isoformat(),
            "created_by": item.created_by,
            "baseline_key": item.baseline_key,
            "current_report_id": item.current_report_id,
            "current_report_name": item.current_report_name,
            "summary": dict(item.summary),
            "events": [
                {
                    "revision_id": entry.revision_id,
                    "action": entry.action,
                    "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
                    "changed_by": entry.changed_by,
                    "from_report_id": entry.from_report_id,
                    "from_report_name": entry.from_report_name,
                    "to_report_id": entry.to_report_id,
                    "to_report_name": entry.to_report_name,
                    "reason_summary": entry.reason_summary,
                    "reasons": list(entry.reasons),
                    "comparison_id": entry.comparison_id,
                    "comparison_detail_path": entry.comparison_detail_path,
                    "policy_version": entry.policy_version,
                }
                for entry in item.events
            ],
            "detail_path": item.detail_path,
            "markdown_path": item.markdown_path,
            "html_path": item.html_path,
        }

    @staticmethod
    def _build_baseline_history_entry(
        *,
        report: RuleReviewReportRecord,
        changed_at: datetime,
        changed_by: str,
        action: str,
        reasons: Sequence[str] = (),
        comparison_id: str = "",
        comparison_detail_path: str = "",
        policy_version: str = "",
    ) -> RuleReviewReportBaselineHistoryEntry:
        return RuleReviewReportBaselineHistoryEntry(
            revision_id=new_id("baseline_rev"),
            report_id=report.report_id,
            report_name=report.name,
            policy_versions=tuple(report.summary.get("policy_versions", ()) or ()),
            candidate_paths=tuple(report.summary.get("candidate_paths", ()) or ()),
            baseline_paths=tuple(report.summary.get("baseline_paths", ()) or ()),
            report_created_at=report.created_at.isoformat(),
            changed_at=changed_at,
            changed_by=changed_by,
            action=action,
            reasons=tuple(reasons),
            comparison_id=comparison_id,
            comparison_detail_path=comparison_detail_path,
            policy_version=policy_version,
        )

    @classmethod
    def _baseline_history_from_payload(cls, payload: Mapping[str, Any]) -> tuple[RuleReviewReportBaselineHistoryEntry, ...]:
        history_payload = payload.get("history", ()) or ()
        items: list[RuleReviewReportBaselineHistoryEntry] = []
        for entry in history_payload:
            if not isinstance(entry, Mapping):
                continue
            items.append(cls._baseline_history_entry_from_payload(entry))
        if items:
            return tuple(items)
        report_id = str(payload.get("report_id", "") or "")
        if not report_id:
            return tuple()
        created_at_raw = str(payload.get("updated_at", "") or payload.get("created_at", "") or "")
        changed_at = datetime.fromisoformat(created_at_raw) if created_at_raw else None
        return (
            RuleReviewReportBaselineHistoryEntry(
                revision_id=str(payload.get("revision_id", "") or new_id("baseline_rev")),
                report_id=report_id,
                report_name=str(payload.get("report_name", "") or ""),
                policy_versions=tuple(payload.get("policy_versions", ()) or ()),
                candidate_paths=tuple(payload.get("candidate_paths", ()) or ()),
                baseline_paths=tuple(payload.get("baseline_paths", ()) or ()),
                report_created_at=str(payload.get("report_created_at", "") or ""),
                changed_at=changed_at,
                changed_by=str(payload.get("updated_by", "") or ""),
                action="set",
                reasons=tuple(),
                comparison_id="",
                comparison_detail_path="",
                policy_version="",
            ),
        )

    @staticmethod
    def _baseline_history_entry_payload(item: RuleReviewReportBaselineHistoryEntry) -> dict[str, Any]:
        return {
            "revision_id": item.revision_id,
            "report_id": item.report_id,
            "report_name": item.report_name,
            "policy_versions": list(item.policy_versions),
            "candidate_paths": list(item.candidate_paths),
            "baseline_paths": list(item.baseline_paths),
            "report_created_at": item.report_created_at,
            "changed_at": item.changed_at.isoformat() if item.changed_at else None,
            "changed_by": item.changed_by,
            "action": item.action,
            "reasons": list(item.reasons),
            "comparison_id": item.comparison_id,
            "comparison_detail_path": item.comparison_detail_path,
            "policy_version": item.policy_version,
        }

    @staticmethod
    def _baseline_history_entry_from_payload(payload: Mapping[str, Any]) -> RuleReviewReportBaselineHistoryEntry:
        return RuleReviewReportBaselineHistoryEntry(
            revision_id=str(payload.get("revision_id", "") or ""),
            report_id=str(payload.get("report_id", "") or ""),
            report_name=str(payload.get("report_name", "") or ""),
            policy_versions=tuple(payload.get("policy_versions", ()) or ()),
            candidate_paths=tuple(payload.get("candidate_paths", ()) or ()),
            baseline_paths=tuple(payload.get("baseline_paths", ()) or ()),
            report_created_at=str(payload.get("report_created_at", "") or ""),
            changed_at=(
                datetime.fromisoformat(str(payload.get("changed_at", "") or ""))
                if str(payload.get("changed_at", "") or "")
                else None
            ),
            changed_by=str(payload.get("changed_by", "") or ""),
            action=str(payload.get("action", "") or ""),
            reasons=tuple(payload.get("reasons", ()) or ()),
            comparison_id=str(payload.get("comparison_id", "") or ""),
            comparison_detail_path=str(payload.get("comparison_detail_path", "") or ""),
            policy_version=str(payload.get("policy_version", "") or ""),
        )

    @classmethod
    def _baseline_payload(
        cls,
        item: RuleReviewReportBaselineRecord,
        *,
        history: Sequence[RuleReviewReportBaselineHistoryEntry],
    ) -> dict[str, Any]:
        return {
            "baseline_key": item.baseline_key,
            "report_id": item.report_id,
            "report_name": item.report_name,
            "policy_versions": list(item.policy_versions),
            "candidate_paths": list(item.candidate_paths),
            "baseline_paths": list(item.baseline_paths),
            "report_created_at": item.report_created_at,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "updated_by": item.updated_by,
            "latest_audit_id": item.latest_audit_id,
            "latest_audit_detail_path": item.latest_audit_detail_path,
            "latest_audit_markdown_path": item.latest_audit_markdown_path,
            "latest_audit_html_path": item.latest_audit_html_path,
            "latest_audit_index_path": item.latest_audit_index_path,
            "latest_audit_version_count": item.latest_audit_version_count,
            "history": [cls._baseline_history_entry_payload(entry) for entry in history],
        }

    @staticmethod
    def _baseline_from_payload(payload: Mapping[str, Any]) -> RuleReviewReportBaselineRecord:
        return RuleReviewReportBaselineRecord(
            baseline_key=str(payload.get("baseline_key", "") or ""),
            report_id=str(payload.get("report_id", "") or ""),
            report_name=str(payload.get("report_name", "") or ""),
            policy_versions=tuple(payload.get("policy_versions", ()) or ()),
            candidate_paths=tuple(payload.get("candidate_paths", ()) or ()),
            baseline_paths=tuple(payload.get("baseline_paths", ()) or ()),
            report_created_at=str(payload.get("report_created_at", "") or ""),
            created_at=(
                datetime.fromisoformat(str(payload.get("created_at", "") or ""))
                if str(payload.get("created_at", "") or "")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(str(payload.get("updated_at", "") or ""))
                if str(payload.get("updated_at", "") or "")
                else None
            ),
            updated_by=str(payload.get("updated_by", "") or ""),
            latest_audit_id=str(payload.get("latest_audit_id", "") or ""),
            latest_audit_detail_path=str(payload.get("latest_audit_detail_path", "") or ""),
            latest_audit_markdown_path=str(payload.get("latest_audit_markdown_path", "") or ""),
            latest_audit_html_path=str(payload.get("latest_audit_html_path", "") or ""),
            latest_audit_index_path=str(payload.get("latest_audit_index_path", "") or ""),
            latest_audit_version_count=int(payload.get("latest_audit_version_count", 0) or 0),
        )

    @staticmethod
    def _with_latest_audit(
        baseline: RuleReviewReportBaselineRecord,
        audit: RuleReviewReportBaselineAuditRecord,
        *,
        latest_audit_index_path: str,
        latest_audit_version_count: int,
    ) -> RuleReviewReportBaselineRecord:
        return RuleReviewReportBaselineRecord(
            baseline_key=baseline.baseline_key,
            report_id=baseline.report_id,
            report_name=baseline.report_name,
            policy_versions=baseline.policy_versions,
            candidate_paths=baseline.candidate_paths,
            baseline_paths=baseline.baseline_paths,
            report_created_at=baseline.report_created_at,
            created_at=baseline.created_at,
            updated_at=baseline.updated_at,
            updated_by=baseline.updated_by,
            latest_audit_id=audit.audit_id,
            latest_audit_detail_path=audit.detail_path,
            latest_audit_markdown_path=audit.markdown_path,
            latest_audit_html_path=audit.html_path,
            latest_audit_index_path=latest_audit_index_path,
            latest_audit_version_count=latest_audit_version_count,
        )

    @staticmethod
    def _slugify_baseline_key(value: str) -> str:
        slug = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value.strip())
        return slug or "baseline"

    @classmethod
    def _record_from_payload(cls, payload: Mapping[str, Any]) -> RuleReviewReportRecord:
        try:
            entries = tuple(
                RuleReviewReportEntry(
                    snapshot_id=str(entry.get("snapshot_id", "") or ""),
                    name=str(entry.get("name", "") or ""),
                    created_at=datetime.fromisoformat(str(entry.get("created_at", "") or datetime.min.isoformat())),
                    created_by=str(entry.get("created_by", "") or ""),
                    decision=str(entry.get("decision", "") or ""),
                    policy_version=str(entry.get("policy_version", "") or ""),
                    baseline_path=str(entry.get("baseline_path", "") or ""),
                    candidate_path=str(entry.get("candidate_path", "") or ""),
                    changed_family_count=int(entry.get("changed_family_count", 0) or 0),
                    finding_count=int(entry.get("finding_count", 0) or 0),
                    change_summary=dict(entry.get("change_summary", {}) or {}),
                    reasons=tuple(entry.get("reasons", ()) or ()),
                    golden_suite_passed=entry.get("golden_suite_passed", None),
                    golden_suite_case_count=int(entry.get("golden_suite_case_count", 0) or 0),
                    golden_suite_passed_case_count=int(entry.get("golden_suite_passed_case_count", 0) or 0),
                    golden_suite_failed_case_count=int(entry.get("golden_suite_failed_case_count", 0) or 0),
                    golden_suite_version=str(entry.get("golden_suite_version", "") or ""),
                    golden_suite_suite_path=str(entry.get("golden_suite_suite_path", "") or ""),
                    golden_suite_layer_summaries={
                        str(key): dict(value)
                        for key, value in dict(entry.get("golden_suite_layer_summaries", {}) or {}).items()
                    },
                    performance_summary=dict(entry.get("performance_summary", {}) or {}),
                    performance_risk_items=tuple(
                        cls._risk_item_from_payload(item)
                        for item in (entry.get("performance_risk_items", ()) or ())
                        if isinstance(item, Mapping)
                    ),
                    detail_path=str(entry.get("detail_path", "") or ""),
                    markdown_path=str(entry.get("markdown_path", "") or ""),
                )
                for entry in (payload.get("entries", ()) or ())
                if isinstance(entry, Mapping)
            )
            families = tuple(
                RuleReviewFamilySummary(
                    family_key=str(entry.get("family_key", "") or ""),
                    issue_type=str(entry.get("issue_type", "") or ""),
                    package_name=str(entry.get("package_name", "") or ""),
                    scenario_name=str(entry.get("scenario_name", "") or ""),
                    title=str(entry.get("title", "") or ""),
                    change_type=str(entry.get("change_type", "") or ""),
                    snapshot_count=int(entry.get("snapshot_count", 0) or 0),
                    total_occurrence_count=int(entry.get("total_occurrence_count", 0) or 0),
                    highest_decision=str(entry.get("highest_decision", "") or ""),
                    sample_snapshot_ids=tuple(entry.get("sample_snapshot_ids", ()) or ()),
                )
                for entry in (payload.get("high_risk_families", ()) or ())
                if isinstance(entry, Mapping)
            )
            return RuleReviewReportRecord(
                report_id=str(payload.get("report_id", "") or ""),
                name=str(payload.get("name", "") or ""),
                created_at=datetime.fromisoformat(str(payload.get("created_at", "") or datetime.min.isoformat())),
                created_by=str(payload.get("created_by", "") or ""),
                filters=dict(payload.get("filters", {}) or {}),
                summary=dict(payload.get("summary", {}) or {}),
                entries=entries,
                high_risk_families=families,
                detail_path=str(payload.get("detail_path", "") or ""),
                markdown_path=str(payload.get("markdown_path", "") or ""),
                html_path=str(payload.get("html_path", "") or ""),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid rule review report payload.") from exc

    @staticmethod
    def _risk_item_payload(item: QualityGateRiskItem) -> dict[str, Any]:
        return {
            "risk_key": item.risk_key,
            "category": item.category,
            "severity": item.severity,
            "summary": item.summary,
            "details": dict(item.details),
            "source": item.source,
            "blocks_admission": bool(item.blocks_admission),
        }

    @staticmethod
    def _risk_item_from_payload(payload: Mapping[str, Any]) -> QualityGateRiskItem:
        return QualityGateRiskItem(
            risk_key=str(payload.get("risk_key", "") or ""),
            category=str(payload.get("category", "") or ""),
            severity=str(payload.get("severity", "") or ""),
            summary=str(payload.get("summary", "") or ""),
            details=dict(payload.get("details", {}) or {}),
            source=str(payload.get("source", "") or ""),
            blocks_admission=bool(payload.get("blocks_admission", False)),
        )
