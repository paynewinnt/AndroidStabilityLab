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


class RuleReviewReportBaselineMixin:
    def set_baseline(
        self,
        *,
        baseline_key: str,
        report_id: str,
        updated_by: str,
        action: str = "set",
        reasons: Sequence[str] = (),
        comparison_id: str = "",
        comparison_detail_path: str = "",
        policy_version: str = "",
    ) -> RuleReviewReportBaselineRecord:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")
        report = self.get_report(report_id.strip())
        now = utcnow()
        registry = self._load_baseline_registry()
        existing = registry.get(key, {})
        history = list(self._baseline_history_from_payload(existing))
        created_at_raw = str(existing.get("created_at", "") or "")
        created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else now
        current = self._baseline_from_payload(existing) if isinstance(existing, Mapping) and existing else None
        if current is None or current.report_id != report.report_id:
            history.append(
                self._build_baseline_history_entry(
                    report=report,
                    changed_at=now,
                    changed_by=updated_by.strip() or "cli",
                    action=action.strip() or "set",
                    reasons=tuple(reasons),
                    comparison_id=comparison_id.strip(),
                    comparison_detail_path=comparison_detail_path.strip(),
                    policy_version=policy_version.strip(),
                )
            )
        record = RuleReviewReportBaselineRecord(
            baseline_key=key,
            report_id=report.report_id,
            report_name=report.name,
            policy_versions=tuple(report.summary.get("policy_versions", ()) or ()),
            candidate_paths=tuple(report.summary.get("candidate_paths", ()) or ()),
            baseline_paths=tuple(report.summary.get("baseline_paths", ()) or ()),
            report_created_at=report.created_at.isoformat(),
            created_at=created_at,
            updated_at=now,
            updated_by=updated_by.strip() or "cli",
        )
        latest_audit, latest_audit_index_path, latest_audit_version_count = self._write_latest_baseline_audit(
            baseline=record,
            history=history,
            created_by=updated_by.strip() or "cli",
        )
        record = self._with_latest_audit(
            record,
            latest_audit,
            latest_audit_index_path=latest_audit_index_path,
            latest_audit_version_count=latest_audit_version_count,
        )
        registry[key] = self._baseline_payload(record, history=history)
        self._save_baseline_registry(registry)
        return record

    def get_baseline(self, baseline_key: str) -> RuleReviewReportBaselineRecord:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")
        registry = self._load_baseline_registry()
        payload = registry.get(key)
        if not isinstance(payload, Mapping):
            raise ValueError(f"Rule review report baseline not found: {key}")
        return self._baseline_from_payload(payload)

    def list_baselines(self) -> tuple[RuleReviewReportBaselineRecord, ...]:
        """Return all named baselines ordered by most recently updated first."""
        registry = self._load_baseline_registry()
        items: list[RuleReviewReportBaselineRecord] = []
        for payload in registry.values():
            if isinstance(payload, Mapping):
                items.append(self._baseline_from_payload(payload))
        items.sort(key=lambda item: item.updated_at or datetime.min, reverse=True)
        return tuple(items)

    def list_baseline_history(self, baseline_key: str) -> tuple[RuleReviewReportBaselineHistoryEntry, ...]:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")
        registry = self._load_baseline_registry()
        payload = registry.get(key)
        if not isinstance(payload, Mapping):
            raise ValueError(f"Rule review report baseline not found: {key}")
        history = list(self._baseline_history_from_payload(payload))
        history.sort(key=lambda item: item.changed_at or datetime.min, reverse=True)
        return tuple(history)

    def promote_baseline(
        self,
        *,
        baseline_key: str,
        report_id: str,
        updated_by: str,
        policy_path: str = "",
        include_unchanged: bool = False,
    ) -> RuleReviewReportBaselinePromotionResult:
        target = self.get_report(report_id.strip())
        baseline = self.get_baseline(baseline_key.strip())
        baseline_report = self.get_report(baseline.report_id)
        if baseline.report_id == target.report_id:
            raise ValueError("Target report is already the current baseline.")
        comparison = self.compare_reports(
            name=f"Promote Baseline {baseline_key.strip()}",
            created_by=updated_by.strip() or "cli",
            left_report_id=baseline_report.report_id,
            right_report_id=target.report_id,
            include_unchanged=include_unchanged,
        )
        policy = self._load_baseline_policy(policy_path.strip())
        approved, reasons = self._evaluate_baseline_promotion(
            comparison=comparison,
            target=target,
            policy=policy,
        )
        updated_baseline = None
        if approved:
            updated_baseline = self.set_baseline(
                baseline_key=baseline_key.strip(),
                report_id=target.report_id,
                updated_by=updated_by.strip(),
                action="promote",
                reasons=tuple(reasons),
                comparison_id=comparison.comparison_id,
                comparison_detail_path=comparison.detail_path,
                policy_version=str(policy.get("version", "") or ""),
            )
        return RuleReviewReportBaselinePromotionResult(
            baseline_key=baseline_key.strip(),
            target_report_id=target.report_id,
            target_report_name=target.name,
            baseline_report_id=baseline.report_id,
            baseline_report_name=baseline.report_name,
            policy_version=str(policy.get("version", "") or ""),
            approved=approved,
            promoted=approved,
            reasons=tuple(reasons),
            comparison_id=comparison.comparison_id,
            comparison_detail_path=comparison.detail_path,
            target_golden_suite=self._golden_suite_summary_from_report_summary(target.summary),
            baseline_golden_suite=self._golden_suite_summary_from_report_summary(baseline_report.summary),
            updated_baseline=updated_baseline,
        )

    def rollback_baseline(
        self,
        *,
        baseline_key: str,
        updated_by: str,
        target_report_id: str = "",
    ) -> RuleReviewReportBaselineRollbackResult:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")
        registry = self._load_baseline_registry()
        payload = registry.get(key)
        if not isinstance(payload, Mapping):
            raise ValueError(f"Rule review report baseline not found: {key}")
        current = self._baseline_from_payload(payload)
        history = list(self._baseline_history_from_payload(payload))
        target = self._select_rollback_target(
            current=current,
            history=history,
            target_report_id=target_report_id.strip(),
        )
        if target is None:
            raise ValueError("No rollback target available for the selected baseline.")
        report = self.get_report(target.report_id)
        now = utcnow()
        history.append(
            self._build_baseline_history_entry(
                report=report,
                changed_at=now,
                changed_by=updated_by.strip() or "cli",
                action="rollback",
                reasons=(f"Rolled back baseline to report {report.report_id}.",),
            )
        )
        updated_baseline = RuleReviewReportBaselineRecord(
            baseline_key=key,
            report_id=report.report_id,
            report_name=report.name,
            policy_versions=tuple(report.summary.get("policy_versions", ()) or ()),
            candidate_paths=tuple(report.summary.get("candidate_paths", ()) or ()),
            baseline_paths=tuple(report.summary.get("baseline_paths", ()) or ()),
            report_created_at=report.created_at.isoformat(),
            created_at=current.created_at,
            updated_at=now,
            updated_by=updated_by.strip() or "cli",
        )
        latest_audit, latest_audit_index_path, latest_audit_version_count = self._write_latest_baseline_audit(
            baseline=updated_baseline,
            history=history,
            created_by=updated_by.strip() or "cli",
        )
        updated_baseline = self._with_latest_audit(
            updated_baseline,
            latest_audit,
            latest_audit_index_path=latest_audit_index_path,
            latest_audit_version_count=latest_audit_version_count,
        )
        registry[key] = self._baseline_payload(updated_baseline, history=history)
        self._save_baseline_registry(registry)
        return RuleReviewReportBaselineRollbackResult(
            baseline_key=key,
            from_report_id=current.report_id,
            from_report_name=current.report_name,
            to_report_id=updated_baseline.report_id,
            to_report_name=updated_baseline.report_name,
            rolled_back=True,
            reasons=(f"Rolled back baseline to report {updated_baseline.report_id}.",),
            updated_baseline=updated_baseline,
        )

    def create_baseline_audit_report(
        self,
        *,
        baseline_key: str,
        name: str,
        created_by: str,
    ) -> RuleReviewReportBaselineAuditRecord:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")
        baseline = self.get_baseline(key)
        current_report = self.get_report(baseline.report_id)
        history = list(self.list_baseline_history(key))
        if not history:
            raise ValueError(f"No baseline history available: {key}")
        ordered = sorted(history, key=lambda item: item.changed_at or datetime.min)
        events = tuple(self._build_baseline_audit_events(ordered))
        summary = self._baseline_audit_summary(
            baseline_key=key,
            current=baseline,
            current_report=current_report,
            events=events,
        )

        audit_id = new_id("baseline_audit")
        created_at = utcnow()
        report_dir = self._baseline_audit_root_dir / audit_id
        report_dir.mkdir(parents=True, exist_ok=False)
        detail_path = report_dir / "report.json"
        markdown_path = report_dir / "summary.md"
        html_path = report_dir / "report.html"

        record = RuleReviewReportBaselineAuditRecord(
            audit_id=audit_id,
            name=name.strip(),
            created_at=created_at,
            created_by=created_by.strip() or "cli",
            baseline_key=key,
            current_report_id=baseline.report_id,
            current_report_name=baseline.report_name,
            summary=summary,
            events=events,
            detail_path=str(detail_path),
            markdown_path=str(markdown_path),
            html_path=str(html_path),
        )
        detail_path.write_text(
            json.dumps(self._baseline_audit_payload(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_baseline_audit_markdown(record), encoding="utf-8")
        html_path.write_text(self._render_baseline_audit_html(record), encoding="utf-8")
        return record

    def show_latest_baseline_audit(
        self,
        *,
        baseline_key: str,
        version_limit: int = 5,
    ) -> RuleReviewReportBaselineAuditView:
        baseline = self.get_baseline(baseline_key.strip())
        if not baseline.latest_audit_index_path:
            raise ValueError(f"No latest baseline audit available: {baseline.baseline_key}")
        index_path = Path(baseline.latest_audit_index_path)
        if not index_path.exists():
            raise ValueError(f"Latest baseline audit index not found: {baseline.baseline_key}")
        try:
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid latest baseline audit index: {baseline.baseline_key}") from exc
        if not isinstance(index_payload, Mapping):
            raise ValueError(f"Invalid latest baseline audit index: {baseline.baseline_key}")

        detail_path = Path(baseline.latest_audit_detail_path)
        if not detail_path.exists():
            raise ValueError(f"Latest baseline audit payload not found: {baseline.baseline_key}")
        try:
            payload = json.loads(detail_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid latest baseline audit payload: {baseline.baseline_key}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError(f"Invalid latest baseline audit payload: {baseline.baseline_key}")

        raw_versions = index_payload.get("versions", ()) or ()
        versions: list[RuleReviewReportBaselineAuditVersionRecord] = []
        limit = max(0, int(version_limit))
        for item in raw_versions[:limit]:
            if not isinstance(item, Mapping):
                continue
            changed_at_raw = str(item.get("changed_at", "") or "")
            versions.append(
                RuleReviewReportBaselineAuditVersionRecord(
                    revision_id=str(item.get("revision_id", "") or ""),
                    action=str(item.get("action", "") or ""),
                    changed_at=datetime.fromisoformat(changed_at_raw) if changed_at_raw else None,
                    changed_by=str(item.get("changed_by", "") or ""),
                    report_id=str(item.get("report_id", "") or ""),
                    report_name=str(item.get("report_name", "") or ""),
                    audit_id=str(item.get("audit_id", "") or ""),
                    summary=dict(item.get("summary", {}) or {}),
                    detail_path=str(item.get("detail_path", "") or ""),
                    markdown_path=str(item.get("markdown_path", "") or ""),
                    html_path=str(item.get("html_path", "") or ""),
                )
            )
        created_at_raw = str(payload.get("created_at", "") or "")
        return RuleReviewReportBaselineAuditView(
            baseline=baseline,
            audit_id=str(payload.get("audit_id", "") or ""),
            audit_name=str(payload.get("name", "") or ""),
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else None,
            created_by=str(payload.get("created_by", "") or ""),
            summary=dict(payload.get("summary", {}) or {}),
            retention=dict(index_payload.get("retention", {}) or {}),
            version_count=int(index_payload.get("version_count", 0) or 0),
            versions=tuple(versions),
            detail_path=str(payload.get("detail_path", "") or ""),
            markdown_path=str(payload.get("markdown_path", "") or ""),
            html_path=str(payload.get("html_path", "") or ""),
            index_path=str(index_path),
        )

    def _write_latest_baseline_audit(
        self,
        *,
        baseline: RuleReviewReportBaselineRecord,
        history: Sequence[RuleReviewReportBaselineHistoryEntry],
        created_by: str,
    ) -> tuple[RuleReviewReportBaselineAuditRecord, str, int]:
        ordered = sorted(history, key=lambda item: item.changed_at or datetime.min)
        events = tuple(self._build_baseline_audit_events(ordered))
        current_report = self.get_report(baseline.report_id)
        summary = self._baseline_audit_summary(
            baseline_key=baseline.baseline_key,
            current=baseline,
            current_report=current_report,
            events=events,
        )
        audit_id = f"baseline_audit_latest_{self._slugify_baseline_key(baseline.baseline_key)}"
        report_dir = self._baseline_audit_root_dir / "latest" / self._slugify_baseline_key(baseline.baseline_key)
        report_dir.mkdir(parents=True, exist_ok=True)
        detail_path = report_dir / "report.json"
        markdown_path = report_dir / "summary.md"
        html_path = report_dir / "report.html"
        record = RuleReviewReportBaselineAuditRecord(
            audit_id=audit_id,
            name=f"Baseline Audit Latest | {baseline.baseline_key}",
            created_at=utcnow(),
            created_by=created_by,
            baseline_key=baseline.baseline_key,
            current_report_id=baseline.report_id,
            current_report_name=baseline.report_name,
            summary=summary,
            events=events,
            detail_path=str(detail_path),
            markdown_path=str(markdown_path),
            html_path=str(html_path),
        )
        detail_path.write_text(
            json.dumps(self._baseline_audit_payload(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_baseline_audit_markdown(record), encoding="utf-8")
        html_path.write_text(self._render_baseline_audit_html(record), encoding="utf-8")
        index_path, version_count = self._update_latest_baseline_audit_index(
            report_dir=report_dir,
            record=record,
            latest_event=ordered[-1] if ordered else None,
        )
        return record, index_path, version_count

    def _update_latest_baseline_audit_index(
        self,
        *,
        report_dir: Path,
        record: RuleReviewReportBaselineAuditRecord,
        latest_event: RuleReviewReportBaselineHistoryEntry | None,
    ) -> tuple[str, int]:
        versions_dir = report_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        revision_id = latest_event.revision_id if latest_event and latest_event.revision_id else "initial"
        version_dir = versions_dir / revision_id
        version_dir.mkdir(parents=True, exist_ok=True)
        version_detail_path = version_dir / "report.json"
        version_markdown_path = version_dir / "summary.md"
        version_html_path = version_dir / "report.html"
        payload = self._baseline_audit_payload(record)
        payload["detail_path"] = str(version_detail_path)
        payload["markdown_path"] = str(version_markdown_path)
        payload["html_path"] = str(version_html_path)
        version_detail_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        version_markdown_path.write_text(self._render_baseline_audit_markdown(record), encoding="utf-8")
        version_html_path.write_text(self._render_baseline_audit_html(record), encoding="utf-8")

        index_path = report_dir / "index.json"
        existing_entries: list[dict[str, Any]] = []
        if index_path.exists():
            try:
                loaded = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                loaded = {}
            if isinstance(loaded, Mapping):
                candidate_entries = loaded.get("versions", ()) or ()
                if isinstance(candidate_entries, Sequence):
                    for item in candidate_entries:
                        if isinstance(item, Mapping):
                            existing_entries.append(dict(item))
        new_entry = {
            "revision_id": revision_id,
            "action": latest_event.action if latest_event else "",
            "changed_at": latest_event.changed_at.isoformat() if latest_event and latest_event.changed_at else None,
            "changed_by": latest_event.changed_by if latest_event else "",
            "report_id": record.current_report_id,
            "report_name": record.current_report_name,
            "audit_id": record.audit_id,
            "summary": dict(record.summary),
            "detail_path": str(version_detail_path),
            "markdown_path": str(version_markdown_path),
            "html_path": str(version_html_path),
        }
        entries_by_revision = {str(item.get("revision_id", "") or ""): item for item in existing_entries}
        entries_by_revision[revision_id] = new_entry
        merged_entries = list(entries_by_revision.values())
        merged_entries.sort(key=lambda item: str(item.get("changed_at", "") or ""), reverse=True)
        kept_entries, pruned_entries = self._apply_latest_audit_retention(merged_entries)
        self._delete_pruned_latest_audit_versions(pruned_entries)
        index_payload = {
            "baseline_key": record.baseline_key,
            "current_audit_id": record.audit_id,
            "current_report_id": record.current_report_id,
            "updated_at": record.created_at.isoformat(),
            "version_count": len(kept_entries),
            "retention": {
                "max_versions": int(self._latest_audit_max_versions),
                "preserve_actions": sorted(self._latest_audit_preserve_actions),
                "pruned_count": len(pruned_entries),
            },
            "versions": kept_entries,
        }
        index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(index_path), len(kept_entries)

    def _apply_latest_audit_retention(
        self,
        entries: Sequence[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        max_versions = max(1, int(self._latest_audit_max_versions))
        if len(entries) <= max_versions:
            return [dict(item) for item in entries], []
        preserve_actions = set(self._latest_audit_preserve_actions)
        kept: list[dict[str, Any]] = []
        pruned: list[dict[str, Any]] = []
        for index, entry in enumerate(entries):
            item = dict(entry)
            action = str(item.get("action", "") or "")
            if index < max_versions or action in preserve_actions:
                kept.append(item)
            else:
                pruned.append(item)
        return kept, pruned

    @staticmethod
    def _delete_pruned_latest_audit_versions(entries: Sequence[Mapping[str, Any]]) -> None:
        for entry in entries:
            detail_path = str(entry.get("detail_path", "") or "")
            if not detail_path:
                continue
            version_dir = Path(detail_path).parent
            if version_dir.exists():
                shutil.rmtree(version_dir, ignore_errors=True)

    @staticmethod
    def _select_rollback_target(
        *,
        current: RuleReviewReportBaselineRecord,
        history: Sequence[RuleReviewReportBaselineHistoryEntry],
        target_report_id: str,
    ) -> RuleReviewReportBaselineHistoryEntry | None:
        ordered = sorted(history, key=lambda item: item.changed_at or datetime.min, reverse=True)
        if target_report_id:
            for entry in ordered:
                if entry.report_id == target_report_id and entry.report_id != current.report_id:
                    return entry
            return None
        for entry in ordered:
            if entry.report_id != current.report_id:
                return entry
        return None

    def _load_baseline_policy(self, raw_path: str) -> dict[str, Any]:
        path = Path(raw_path) if raw_path else self._baseline_policy_path
        if not path.exists():
            raise ValueError(f"Rule review baseline policy file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid rule review baseline policy file: {path}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError(f"Invalid rule review baseline policy file: {path}")
        return dict(payload)

    def _load_baseline_registry(self) -> dict[str, Any]:
        if not self._baseline_registry_path.exists():
            return {}
        try:
            payload = json.loads(self._baseline_registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid rule review report baseline registry.") from exc
        return dict(payload if isinstance(payload, Mapping) else {})

    def _save_baseline_registry(self, payload: Mapping[str, Any]) -> None:
        self._baseline_root_dir.mkdir(parents=True, exist_ok=True)
        self._baseline_registry_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _evaluate_baseline_promotion(
        *,
        comparison: RuleReviewReportComparisonRecord,
        target: RuleReviewReportRecord,
        policy: Mapping[str, Any],
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        summary = dict(comparison.summary)
        decision_counts = dict(target.summary.get("decision_counts", {}) or {})
        target_decisions = [key for key, value in decision_counts.items() if int(value or 0) > 0]
        allowed_report_decisions = set(policy.get("allowed_report_decisions", ()) or ())
        disallowed_decisions = sorted(decision for decision in target_decisions if decision not in allowed_report_decisions)
        if disallowed_decisions:
            reasons.append(
                "Target report decisions not allowed for promotion: " + ", ".join(disallowed_decisions)
            )

        change_limit = policy.get("max_changed_family_count_total_delta", None)
        if change_limit is not None and int(summary.get("changed_family_count_total_delta", 0) or 0) > int(change_limit):
            reasons.append(
                f"changed_family_count_total_delta={int(summary.get('changed_family_count_total_delta', 0) or 0)} exceeds limit {int(change_limit)}."
            )
        finding_limit = policy.get("max_finding_count_total_delta", None)
        if finding_limit is not None and int(summary.get("finding_count_total_delta", 0) or 0) > int(finding_limit):
            reasons.append(
                f"finding_count_total_delta={int(summary.get('finding_count_total_delta', 0) or 0)} exceeds limit {int(finding_limit)}."
            )
        high_risk_limit = policy.get("max_high_risk_family_count_delta", None)
        if high_risk_limit is not None and int(summary.get("high_risk_family_count_delta", 0) or 0) > int(high_risk_limit):
            reasons.append(
                f"high_risk_family_count_delta={int(summary.get('high_risk_family_count_delta', 0) or 0)} exceeds limit {int(high_risk_limit)}."
            )

        allowed_delta_statuses = set(policy.get("allowed_family_delta_statuses", ()) or ())
        disallowed_family_rows = [
            item.delta_status
            for item in comparison.family_diffs
            if item.delta_status not in allowed_delta_statuses
        ]
        if disallowed_family_rows:
            reasons.append(
                "Family delta statuses not allowed for promotion: "
                + ", ".join(sorted(set(disallowed_family_rows)))
            )
        return (len(reasons) == 0, reasons or ["Promotion policy checks passed."])

    @classmethod
    def _build_baseline_audit_events(
        cls,
        history: Sequence[RuleReviewReportBaselineHistoryEntry],
    ) -> list[RuleReviewReportBaselineAuditEvent]:
        events: list[RuleReviewReportBaselineAuditEvent] = []
        previous: RuleReviewReportBaselineHistoryEntry | None = None
        for entry in history:
            reasons = tuple(entry.reasons or ()) or tuple(cls._default_history_reasons(entry.action))
            events.append(
                RuleReviewReportBaselineAuditEvent(
                    revision_id=entry.revision_id,
                    action=entry.action or "set",
                    changed_at=entry.changed_at,
                    changed_by=entry.changed_by,
                    from_report_id=previous.report_id if previous else "",
                    from_report_name=previous.report_name if previous else "",
                    to_report_id=entry.report_id,
                    to_report_name=entry.report_name,
                    reason_summary=reasons[0] if reasons else "",
                    reasons=reasons,
                    comparison_id=entry.comparison_id,
                    comparison_detail_path=entry.comparison_detail_path,
                    policy_version=entry.policy_version,
                )
            )
            previous = entry
        return events

    @staticmethod
    def _default_history_reasons(action: str) -> tuple[str, ...]:
        normalized = action.strip() or "set"
        if normalized == "promote":
            return ("Promotion policy checks passed and baseline pointer was updated.",)
        if normalized == "rollback":
            return ("Baseline was rolled back to an earlier reviewed report.",)
        return ("Baseline pointer was updated manually.",)

    @classmethod
    def _baseline_audit_summary(
        cls,
        *,
        baseline_key: str,
        current: RuleReviewReportBaselineRecord,
        current_report: RuleReviewReportRecord,
        events: Sequence[RuleReviewReportBaselineAuditEvent],
    ) -> dict[str, Any]:
        action_counts = Counter(item.action for item in events)
        actor_counts = Counter(item.changed_by or "unknown" for item in events)
        report_ids = {item.to_report_id for item in events if item.to_report_id}
        comparison_linked_count = sum(1 for item in events if item.comparison_id)
        first_changed_at = events[0].changed_at.isoformat() if events and events[0].changed_at else None
        last_changed_at = events[-1].changed_at.isoformat() if events and events[-1].changed_at else None
        return {
            "baseline_key": baseline_key,
            "history_count": len(events),
            "action_counts": dict(action_counts),
            "actor_counts": dict(actor_counts),
            "distinct_report_count": len(report_ids),
            "comparison_linked_event_count": comparison_linked_count,
            "first_changed_at": first_changed_at,
            "last_changed_at": last_changed_at,
            "current_report_id": current.report_id,
            "current_report_name": current.report_name,
            "current_report_golden_suite": cls._golden_suite_summary_from_report_summary(current_report.summary),
        }
