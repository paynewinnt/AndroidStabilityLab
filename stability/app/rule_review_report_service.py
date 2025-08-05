from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from stability.domain import RuleReviewReportRecord
from stability.domain.value_objects import new_id, utcnow

from .rule_review_reports.baselines import RuleReviewReportBaselineMixin
from .rule_review_reports.comparisons import RuleReviewReportComparisonMixin
from .rule_review_reports.renderers import RuleReviewReportRendererMixin
from .rule_review_reports.serializers import RuleReviewReportSerializerMixin
from .rule_review_reports.snapshots import RuleReviewReportSnapshotMixin
from .snapshot_service import SnapshotService


class RuleReviewReportService(
    RuleReviewReportBaselineMixin,
    RuleReviewReportComparisonMixin,
    RuleReviewReportRendererMixin,
    RuleReviewReportSerializerMixin,
    RuleReviewReportSnapshotMixin,
):
    """Build one readable report bundle across multiple persisted rule-review snapshots."""

    _latest_audit_max_versions = 10
    _latest_audit_preserve_actions = frozenset({"promote", "rollback"})

    def __init__(self, *, root_dir: Path, snapshot_service: SnapshotService) -> None:
        self._root_dir = Path(root_dir)
        self._comparison_root_dir = self._root_dir.parent / "analysis_review_report_comparisons"
        self._baseline_root_dir = self._root_dir.parent / "analysis_review_report_baselines"
        self._baseline_audit_root_dir = self._root_dir.parent / "analysis_review_report_baseline_audits"
        self._baseline_registry_path = self._baseline_root_dir / "baselines.json"
        self._baseline_policy_path = Path("config/rule_review_baseline_policy.json")
        self._snapshot_service = snapshot_service

    def create_report(
        self,
        *,
        name: str,
        created_by: str,
        snapshot_created_by: str = "",
        decision: str = "",
        policy_version: str = "",
        baseline_path: str = "",
        candidate_path: str = "",
        created_from: str = "",
        created_to: str = "",
        limit: int = 50,
    ) -> RuleReviewReportRecord:
        matched_records = self._select_review_snapshots(
            snapshot_created_by=snapshot_created_by,
            decision=decision,
            policy_version=policy_version,
            baseline_path=baseline_path,
            candidate_path=candidate_path,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
        if not matched_records:
            raise ValueError("No review snapshots matched the requested filters.")

        entries = tuple(self._entry_from_snapshot(item) for item in matched_records)
        high_risk_families = tuple(self._high_risk_families(matched_records))
        summary = self._summary(entries, high_risk_families)
        filters = {
            "snapshot_created_by": snapshot_created_by or None,
            "decision": decision or None,
            "policy_version": policy_version or None,
            "baseline_path": baseline_path or None,
            "candidate_path": candidate_path or None,
            "created_from": created_from or None,
            "created_to": created_to or None,
            "limit": limit,
        }

        report_id = new_id("review_report")
        created_at = utcnow()
        report_dir = self._root_dir / report_id
        report_dir.mkdir(parents=True, exist_ok=False)
        detail_path = report_dir / "report.json"
        markdown_path = report_dir / "summary.md"
        html_path = report_dir / "report.html"

        record = RuleReviewReportRecord(
            report_id=report_id,
            name=name.strip(),
            created_at=created_at,
            created_by=created_by.strip() or "cli",
            filters=filters,
            summary=summary,
            entries=entries,
            high_risk_families=high_risk_families,
            detail_path=str(detail_path),
            markdown_path=str(markdown_path),
            html_path=str(html_path),
        )
        detail_path.write_text(json.dumps(self._payload(record), ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(self._render_markdown(record), encoding="utf-8")
        html_path.write_text(self._render_html(record), encoding="utf-8")
        return record

    def get_report(self, report_id: str) -> RuleReviewReportRecord:
        detail_path = self._root_dir / report_id / "report.json"
        if not detail_path.exists():
            raise ValueError(f"Rule review report not found: {report_id}")
        try:
            payload = json.loads(detail_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid rule review report payload: {report_id}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError(f"Invalid rule review report payload: {report_id}")
        return self._record_from_payload(payload)
