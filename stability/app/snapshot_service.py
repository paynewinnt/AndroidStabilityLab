from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import (
    AggregatedIssue,
    AnalysisSnapshotRecord,
    AnalysisSnapshotSummary,
    ComparedIssue,
    ComparisonResult,
    IssueEventReference,
    MetricTrendSummary,
    RuleReviewFinding,
    RuleReviewResult,
    ReplayedIssueFamily,
    RuleReplayResult,
    RegressionResult,
    RegressedIssue,
    RegressedMetric,
)
from stability.domain.value_objects import new_id, utcnow

from .analysis_service import AnalysisService
from .comparison_service import ComparisonService
from .regression_service import RegressionService
from .rule_review_service import RuleReviewService
from .rule_replay_service import RuleReplayService
from .snapshot_retention import SnapshotRetentionMixin


class SnapshotRecordNotFound(LookupError):
    """Raised when one requested analysis snapshot does not exist."""


class SnapshotService(SnapshotRetentionMixin):
    """File-backed analysis snapshot service for V2 query results."""

    def __init__(
        self,
        *,
        root_dir: Path,
        analysis_service: AnalysisService,
        comparison_service: ComparisonService,
        regression_service: RegressionService,
        rule_replay_service: RuleReplayService,
        rule_review_service: RuleReviewService,
    ) -> None:
        self._root_dir = Path(root_dir)
        self._analysis_service = analysis_service
        self._comparison_service = comparison_service
        self._regression_service = regression_service
        self._rule_replay_service = rule_replay_service
        self._rule_review_service = rule_review_service

    def create_top_issues_snapshot(
        self,
        *,
        name: str,
        created_by: str,
        tags: Sequence[str] = (),
        **filters: Any,
    ) -> AnalysisSnapshotRecord:
        items = self._analysis_service.list_top_issues(**filters)
        payload = {
            "filters": self._clean_mapping(filters),
            "top_issue_count": len(items),
            "issues": [self._aggregated_issue_payload(item, include_samples=True) for item in items],
        }
        rule_versions = self._top_issue_rule_versions(items)
        summary = {
            "top_issue_count": len(items),
            "first_issue_title": items[0].title if items else "",
        }
        return self._write_snapshot(
            snapshot_type="top_issues",
            name=name,
            created_by=created_by,
            scope={},
            filters=payload["filters"],
            data_range=self._data_range(filters),
            rule_versions=rule_versions,
            summary=summary,
            payload=payload,
            tags=tags,
        )

    def create_comparison_snapshot(
        self,
        *,
        name: str,
        created_by: str,
        tags: Sequence[str] = (),
        **filters: Any,
    ) -> AnalysisSnapshotRecord:
        result = self._comparison_service.compare_issues(**filters)
        payload = self._comparison_result_payload(result)
        summary = {
            "dimension": result.dimension,
            "issue_count": len(result.issues),
            "left_scope": result.left_scope.label,
            "right_scope": result.right_scope.label,
            **dict(result.issue_change_summary),
        }
        return self._write_snapshot(
            snapshot_type="comparison",
            name=name,
            created_by=created_by,
            scope={
                "dimension": result.dimension,
                "left_scope": result.left_scope.label,
                "right_scope": result.right_scope.label,
            },
            filters=self._clean_mapping(result.base_filters),
            data_range=self._data_range(filters),
            rule_versions={"fingerprint_rule_version": self._analysis_service.fingerprint_rule_version},
            summary=summary,
            payload=payload,
            tags=tags,
        )

    def create_regression_snapshot(
        self,
        *,
        name: str,
        created_by: str,
        tags: Sequence[str] = (),
        **filters: Any,
    ) -> AnalysisSnapshotRecord:
        result = self._regression_service.evaluate_regression(**filters)
        payload = self._regression_result_payload(result)
        summary = {
            "dimension": result.dimension,
            "overall_result": result.overall_result,
            "issue_count": len(result.issues),
            "metric_count": len(result.metrics),
            **dict(result.issue_result_summary),
            **dict(result.metric_result_summary),
        }
        return self._write_snapshot(
            snapshot_type="regression",
            name=name,
            created_by=created_by,
            scope={
                "dimension": result.dimension,
                "left_scope": result.left_scope.label,
                "right_scope": result.right_scope.label,
            },
            filters=self._clean_mapping(result.base_filters),
            data_range=self._data_range(filters),
            rule_versions={
                "fingerprint_rule_version": self._analysis_service.fingerprint_rule_version,
                "regression_rule_version": result.rule_set.version,
            },
            summary=summary,
            payload=payload,
            tags=tags,
        )

    def create_rule_replay_snapshot(
        self,
        *,
        name: str,
        created_by: str,
        tags: Sequence[str] = (),
        **filters: Any,
    ) -> AnalysisSnapshotRecord:
        result = self._rule_replay_service.replay_top_issues(**filters)
        payload = self._rule_replay_result_payload(result)
        summary = {
            "family_count": result.family_count,
            "changed_family_count": result.changed_family_count,
            "change_summary": dict(result.change_summary),
            "first_change_type": result.families[0].change_type if result.families else "",
        }
        return self._write_snapshot(
            snapshot_type="replay",
            name=name,
            created_by=created_by,
            scope={
                "baseline_path": result.baseline.path,
                "candidate_path": result.candidate.path,
            },
            filters=self._clean_mapping(result.filters),
            data_range=self._data_range(filters),
            rule_versions={
                "baseline_fingerprint_rule_version": result.baseline.fingerprint_rule_version,
                "candidate_fingerprint_rule_version": result.candidate.fingerprint_rule_version,
            },
            summary=summary,
            payload=payload,
            tags=tags,
        )

    def create_rule_review_snapshot(
        self,
        *,
        name: str,
        created_by: str,
        tags: Sequence[str] = (),
        **filters: Any,
    ) -> AnalysisSnapshotRecord:
        result = self._rule_review_service.review_rule_change(**filters)
        payload = self._rule_review_result_payload(result)
        performance_summary = dict(result.performance_summary)
        summary = {
            "decision": result.decision,
            "family_count": result.family_count,
            "changed_family_count": result.changed_family_count,
            "finding_count": len(result.findings),
            "change_summary": dict(result.change_summary),
            "performance_risk_count": len(result.performance_risk_items),
        }
        if performance_summary:
            summary["performance_summary"] = performance_summary
            metric_result_summary = dict(performance_summary.get("metric_result_summary", {}) or {})
            if metric_result_summary:
                summary["metric_result_summary"] = metric_result_summary
        return self._write_snapshot(
            snapshot_type="review",
            name=name,
            created_by=created_by,
            scope={
                "baseline_path": result.baseline_path,
                "candidate_path": result.candidate_path,
            },
            filters=self._clean_mapping(result.filters),
            data_range=self._data_range(filters),
            rule_versions={
                "policy_version": result.policy_version,
                "baseline_fingerprint_rule_version": result.baseline_rule_version,
                "candidate_fingerprint_rule_version": result.candidate_rule_version,
            },
            summary=summary,
            payload=payload,
            tags=tags,
        )

    def list_snapshots(
        self,
        *,
        snapshot_type: str = "",
        created_by: str = "",
        limit: int = 20,
    ) -> list[AnalysisSnapshotSummary]:
        items: list[AnalysisSnapshotSummary] = []
        for snapshot_path in self._root_dir.glob("*/snapshot.json"):
            record = self._load_record(snapshot_path)
            if snapshot_type and record.snapshot_type != snapshot_type:
                continue
            if created_by and record.created_by != created_by:
                continue
            items.append(record.to_summary())
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def get_snapshot(self, snapshot_id: str) -> AnalysisSnapshotRecord:
        path = self._root_dir / snapshot_id.strip() / "snapshot.json"
        if not path.exists():
            raise self._snapshot_not_found(snapshot_id)
        return self._load_record(path)

    @staticmethod
    def _snapshot_not_found(snapshot_id: str) -> SnapshotRecordNotFound:
        return SnapshotRecordNotFound(f"Analysis snapshot '{snapshot_id}' was not found.")

    def _write_snapshot(
        self,
        *,
        snapshot_type: str,
        name: str,
        created_by: str,
        scope: Mapping[str, Any],
        filters: Mapping[str, Any],
        data_range: Mapping[str, Any],
        rule_versions: Mapping[str, Any],
        summary: Mapping[str, Any],
        payload: Mapping[str, Any],
        tags: Sequence[str],
    ) -> AnalysisSnapshotRecord:
        snapshot_id = new_id("snapshot")
        created_at = utcnow()
        snapshot_dir = self._root_dir / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        detail_path = snapshot_dir / "snapshot.json"
        markdown_path = snapshot_dir / "summary.md"
        source_refs = self._build_source_refs(payload)
        record = AnalysisSnapshotRecord(
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            name=name.strip(),
            created_at=created_at,
            created_by=created_by.strip() or "cli",
            scope=dict(scope),
            filters=dict(filters),
            data_range=dict(data_range),
            rule_versions=dict(rule_versions),
            summary=dict(summary),
            source_refs=source_refs,
            detail_path=str(detail_path),
            markdown_path=str(markdown_path),
            payload=dict(payload),
            tags=tuple(tag for tag in tags if tag),
        )
        detail_path.write_text(
            json.dumps(self._snapshot_record_payload(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_markdown(record), encoding="utf-8")
        return record

    def _load_record(self, path: Path) -> AnalysisSnapshotRecord:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AnalysisSnapshotRecord(
            snapshot_id=str(payload["snapshot_id"]),
            snapshot_type=str(payload["snapshot_type"]),
            name=str(payload["name"]),
            created_at=self._parse_datetime(str(payload["created_at"])),
            created_by=str(payload["created_by"]),
            scope=dict(payload.get("scope", {}) or {}),
            filters=dict(payload.get("filters", {}) or {}),
            data_range=dict(payload.get("data_range", {}) or {}),
            rule_versions=dict(payload.get("rule_versions", {}) or {}),
            summary=dict(payload.get("summary", {}) or {}),
            source_refs=dict(payload.get("source_refs", {}) or {}),
            detail_path=str(payload.get("detail_path", path)),
            markdown_path=str(payload.get("markdown_path", path.with_name("summary.md"))),
            payload=dict(payload.get("payload", {}) or {}),
            tags=tuple(payload.get("tags", ()) or ()),
        )

    @staticmethod
    def _parse_datetime(raw: str):
        from datetime import datetime

        return datetime.fromisoformat(raw)

    @staticmethod
    def _clean_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in values.items():
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            if isinstance(value, (list, tuple, set, dict)) and not value:
                continue
            cleaned[key] = value
        return cleaned

    @classmethod
    def _data_range(cls, filters: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "created_from": filters.get("created_from") or None,
            "created_to": filters.get("created_to") or None,
        }

    @staticmethod
    def _top_issue_rule_versions(items: Sequence[AggregatedIssue]) -> dict[str, Any]:
        versions = sorted({item.fingerprint.rule_version for item in items})
        return {"fingerprint_rule_versions": versions or []}

    @staticmethod
    def _snapshot_record_payload(item: AnalysisSnapshotRecord) -> dict[str, Any]:
        return {
            "snapshot_id": item.snapshot_id,
            "snapshot_type": item.snapshot_type,
            "name": item.name,
            "created_at": item.created_at.isoformat(),
            "created_by": item.created_by,
            "scope": dict(item.scope),
            "filters": dict(item.filters),
            "data_range": dict(item.data_range),
            "rule_versions": dict(item.rule_versions),
            "summary": dict(item.summary),
            "source_refs": dict(item.source_refs),
            "detail_path": item.detail_path,
            "markdown_path": item.markdown_path,
            "payload": dict(item.payload),
            "tags": list(item.tags),
        }

    def _render_markdown(self, record: AnalysisSnapshotRecord) -> str:
        lines = [
            f"# {record.name}",
            "",
            f"- snapshot_id: {record.snapshot_id}",
            f"- snapshot_type: {record.snapshot_type}",
            f"- created_at: {record.created_at.isoformat()}",
            f"- created_by: {record.created_by}",
        ]
        if record.scope:
            lines.extend(["", "## Scope", ""])
            for key, value in record.scope.items():
                lines.append(f"- {key}: {value}")
        if record.filters:
            lines.extend(["", "## Filters", "", "```json", json.dumps(record.filters, ensure_ascii=False, indent=2), "```"])
        if record.rule_versions:
            lines.extend(["", "## Rule Versions", "", "```json", json.dumps(record.rule_versions, ensure_ascii=False, indent=2), "```"])
        if record.source_refs:
            lines.extend(["", "## Source Refs", "", "```json", json.dumps(record.source_refs, ensure_ascii=False, indent=2), "```"])
        if record.summary:
            lines.extend(["", "## Summary", "", "```json", json.dumps(record.summary, ensure_ascii=False, indent=2), "```"])
        lines.extend(["", "## Payload", "", "```json", json.dumps(record.payload, ensure_ascii=False, indent=2), "```", ""])
        return "\n".join(lines)

    @classmethod
    def _build_source_refs(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        refs = {
            "task_ids": set(),
            "run_ids": set(),
            "instance_ids": set(),
            "device_ids": set(),
            "report_paths": set(),
            "execution_log_paths": set(),
            "artifact_paths": set(),
        }

        def walk(node: Any) -> None:
            if isinstance(node, Mapping):
                cls._add_ref(refs["task_ids"], node.get("task_id"))
                cls._add_ref(refs["run_ids"], node.get("run_id"))
                cls._add_ref(refs["instance_ids"], node.get("instance_id"))
                cls._add_ref(refs["device_ids"], node.get("device_id"))
                cls._add_ref(refs["report_paths"], node.get("report_path"))
                cls._add_ref(refs["execution_log_paths"], node.get("execution_log_path"))
                artifact_paths = node.get("artifact_paths")
                if isinstance(artifact_paths, Sequence) and not isinstance(artifact_paths, (str, bytes)):
                    for item in artifact_paths:
                        cls._add_ref(refs["artifact_paths"], item)
                for value in node.values():
                    walk(value)
                return
            if isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
                for item in node:
                    walk(item)

        walk(payload)
        normalized = {
            "task_ids": sorted(refs["task_ids"]),
            "run_ids": sorted(refs["run_ids"]),
            "instance_ids": sorted(refs["instance_ids"]),
            "device_ids": sorted(refs["device_ids"]),
            "report_paths": sorted(refs["report_paths"]),
            "execution_log_paths": sorted(refs["execution_log_paths"]),
            "artifact_paths": sorted(refs["artifact_paths"]),
        }
        normalized["summary"] = {
            "task_count": len(normalized["task_ids"]),
            "run_count": len(normalized["run_ids"]),
            "instance_count": len(normalized["instance_ids"]),
            "device_count": len(normalized["device_ids"]),
            "report_count": len(normalized["report_paths"]),
            "execution_log_count": len(normalized["execution_log_paths"]),
            "artifact_count": len(normalized["artifact_paths"]),
        }
        return normalized

    @staticmethod
    def _add_ref(bucket: set[str], value: Any) -> None:
        if isinstance(value, str) and value:
            bucket.add(value)

    @classmethod
    def _aggregated_issue_payload(cls, item: AggregatedIssue, *, include_samples: bool) -> dict[str, Any]:
        payload = {
            "fingerprint": item.fingerprint.value,
            "rule_version": item.fingerprint.rule_version,
            "fingerprint_components": dict(item.fingerprint.components),
            "issue_type": item.issue_type.value,
            "title": item.title,
            "severity": item.severity.value,
            "first_seen_at": cls._iso(item.first_seen_at),
            "last_seen_at": cls._iso(item.last_seen_at),
            "occurrence_count": item.occurrence_count,
            "affected_run_count": item.affected_run_count,
            "affected_device_count": item.affected_device_count,
            "affected_scenario_count": item.affected_scenario_count,
            "affected_version_count": item.affected_version_count,
            "affected_packages": list(item.affected_packages),
            "affected_devices": list(item.affected_devices),
            "affected_scenarios": list(item.affected_scenarios),
            "affected_versions": list(item.affected_versions),
            "sample_event_ids": list(item.sample_event_ids),
            "score": item.score,
            "score_breakdown": dict(item.score_breakdown),
        }
        if include_samples:
            payload["sample_events"] = [cls._issue_event_payload(sample) for sample in item.sample_events]
        return payload

    @classmethod
    def _comparison_result_payload(cls, item: ComparisonResult) -> dict[str, Any]:
        return {
            "dimension": item.dimension,
            "left_scope": {
                "dimension": item.left_scope.dimension,
                "value": item.left_scope.value,
                "label": item.left_scope.label,
                "filters": dict(item.left_scope.filters),
            },
            "right_scope": {
                "dimension": item.right_scope.dimension,
                "value": item.right_scope.value,
                "label": item.right_scope.label,
                "filters": dict(item.right_scope.filters),
            },
            "base_filters": dict(item.base_filters),
            "sample_summary": dict(item.sample_summary),
            "issue_change_summary": dict(item.issue_change_summary),
            "metric_change_summary": dict(item.metric_change_summary),
            "comparability_notes": list(item.comparability_notes),
            "issue_count": len(item.issues),
            "issues": [cls._compared_issue_payload(issue) for issue in item.issues],
        }

    @classmethod
    def _regression_result_payload(cls, item: RegressionResult) -> dict[str, Any]:
        return {
            "dimension": item.dimension,
            "left_scope": {
                "dimension": item.left_scope.dimension,
                "value": item.left_scope.value,
                "label": item.left_scope.label,
                "filters": dict(item.left_scope.filters),
            },
            "right_scope": {
                "dimension": item.right_scope.dimension,
                "value": item.right_scope.value,
                "label": item.right_scope.label,
                "filters": dict(item.right_scope.filters),
            },
            "base_filters": dict(item.base_filters),
            "rule_set": item.rule_set.as_dict(),
            "overall_result": item.overall_result,
            "issue_result_summary": dict(item.issue_result_summary),
            "metric_result_summary": dict(item.metric_result_summary),
            "summary": dict(item.summary),
            "reasons": list(item.reasons),
            "comparability_notes": list(item.comparability_notes),
            "issue_count": len(item.issues),
            "metric_count": len(item.metrics),
            "issues": [cls._regressed_issue_payload(issue) for issue in item.issues],
            "metrics": [cls._regressed_metric_payload(metric) for metric in item.metrics],
        }

    @classmethod
    def _rule_replay_result_payload(cls, item: RuleReplayResult) -> dict[str, Any]:
        return {
            "baseline": {
                "path": item.baseline.path,
                "fingerprint_rule_version": item.baseline.fingerprint_rule_version,
            },
            "candidate": {
                "path": item.candidate.path,
                "fingerprint_rule_version": item.candidate.fingerprint_rule_version,
            },
            "filters": dict(item.filters),
            "family_count": item.family_count,
            "changed_family_count": item.changed_family_count,
            "change_summary": dict(item.change_summary),
            "families": [cls._replayed_issue_family_payload(family) for family in item.families],
        }

    @classmethod
    def _rule_review_result_payload(cls, item: RuleReviewResult) -> dict[str, Any]:
        return {
            "decision": item.decision,
            "policy_version": item.policy_version,
            "policy_path": item.policy_path,
            "baseline_path": item.baseline_path,
            "candidate_path": item.candidate_path,
            "baseline_rule_version": item.baseline_rule_version,
            "candidate_rule_version": item.candidate_rule_version,
            "filters": dict(item.filters),
            "family_count": item.family_count,
            "changed_family_count": item.changed_family_count,
            "change_summary": dict(item.change_summary),
            "issue_type_change_summary": {
                key: dict(value) for key, value in dict(item.issue_type_change_summary).items()
            },
            "findings": [cls._rule_review_finding_payload(finding) for finding in item.findings],
            "reasons": list(item.reasons),
            "baseline_valid": item.baseline_valid,
            "candidate_valid": item.candidate_valid,
            "baseline_errors": list(item.baseline_errors),
            "candidate_errors": list(item.candidate_errors),
            "golden_suite": cls._rule_replay_golden_suite_payload(item.golden_suite),
            "performance_summary": dict(item.performance_summary),
            "performance_risk_items": [
                cls._quality_gate_risk_item_payload(entry) for entry in (item.performance_risk_items or ())
            ],
            "families": [cls._replayed_issue_family_payload(family) for family in item.families],
        }

    @staticmethod
    def _quality_gate_risk_item_payload(item: object) -> dict[str, Any]:
        return {
            "risk_key": getattr(item, "risk_key", ""),
            "category": getattr(item, "category", ""),
            "severity": getattr(item, "severity", ""),
            "summary": getattr(item, "summary", ""),
            "details": dict(getattr(item, "details", {}) or {}),
            "source": getattr(item, "source", ""),
            "blocks_admission": bool(getattr(item, "blocks_admission", False)),
        }

    @classmethod
    def _issue_event_payload(cls, item: IssueEventReference) -> dict[str, Any]:
        return {
            "event_id": item.event_id,
            "run_id": item.run_id,
            "task_id": item.task_id,
            "task_name": item.task_name,
            "instance_id": item.instance_id,
            "device_id": item.device_id,
            "package_name": item.package_name,
            "scenario_name": item.scenario_name,
            "issue_type": item.issue_type.value,
            "severity": item.severity.value,
            "detected_at": cls._iso(item.detected_at),
            "summary": item.summary,
            "report_path": item.report_path,
            "execution_log_path": item.execution_log_path,
            "artifact_paths": list(item.artifact_paths),
            "metadata": dict(item.metadata),
        }

    @classmethod
    def _replayed_issue_family_payload(cls, item: ReplayedIssueFamily) -> dict[str, Any]:
        return {
            "comparison_key": item.comparison_key,
            "issue_type": item.issue_type,
            "package_name": item.package_name,
            "process_name": item.process_name,
            "scenario_name": item.scenario_name,
            "title": item.title,
            "change_type": item.change_type,
            "left_group_count": item.left_group_count,
            "right_group_count": item.right_group_count,
            "left_occurrence_count": item.left_occurrence_count,
            "right_occurrence_count": item.right_occurrence_count,
            "left_fingerprints": list(item.left_fingerprints),
            "right_fingerprints": list(item.right_fingerprints),
            "left_sample_event_ids": list(item.left_sample_event_ids),
            "right_sample_event_ids": list(item.right_sample_event_ids),
            "left_sample_events": [cls._issue_event_payload(event) for event in item.left_sample_events],
            "right_sample_events": [cls._issue_event_payload(event) for event in item.right_sample_events],
            "notes": list(item.notes),
        }

    @classmethod
    def _rule_replay_golden_suite_payload(cls, item: object | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return {
            "suite_path": getattr(item, "suite_path", ""),
            "suite_version": getattr(item, "suite_version", ""),
            "case_count": int(getattr(item, "case_count", 0) or 0),
            "passed_case_count": int(getattr(item, "passed_case_count", 0) or 0),
            "failed_case_count": int(getattr(item, "failed_case_count", 0) or 0),
            "layer_summaries": {
                str(key): dict(value)
                for key, value in dict(getattr(item, "layer_summaries", {}) or {}).items()
            },
            "passed": int(getattr(item, "failed_case_count", 0) or 0) == 0,
            "cases": [
                {
                    "case_id": getattr(case, "case_id", ""),
                    "description": getattr(case, "description", ""),
                    "layer": getattr(case, "layer", ""),
                    "expectation": getattr(case, "expectation", ""),
                    "issue_type": getattr(case, "issue_type", ""),
                    "passed": bool(getattr(case, "passed", False)),
                    "mismatches": list(getattr(case, "mismatches", ()) or ()),
                }
                for case in (getattr(item, "cases", ()) or ())
            ],
        }

    @staticmethod
    def _rule_review_finding_payload(item: RuleReviewFinding) -> dict[str, Any]:
        return {
            "level": item.level,
            "scope": item.scope,
            "issue_type": item.issue_type,
            "change_type": item.change_type,
            "observed_count": item.observed_count,
            "threshold": item.threshold,
            "message": item.message,
        }

    @staticmethod
    def _compared_issue_payload(item: ComparedIssue) -> dict[str, Any]:
        return {
            "comparison_key": item.comparison_key,
            "title": item.title,
            "issue_type": item.issue_type,
            "severity": item.severity,
            "change_type": item.change_type,
            "occurrence_delta": item.occurrence_delta,
            "left_fingerprint": item.left_fingerprint,
            "right_fingerprint": item.right_fingerprint,
            "left_occurrence_count": item.left_occurrence_count,
            "right_occurrence_count": item.right_occurrence_count,
            "left_affected_run_count": item.left_affected_run_count,
            "right_affected_run_count": item.right_affected_run_count,
            "left_affected_device_count": item.left_affected_device_count,
            "right_affected_device_count": item.right_affected_device_count,
            "left_affected_scenario_count": item.left_affected_scenario_count,
            "right_affected_scenario_count": item.right_affected_scenario_count,
            "left_sample_event_ids": list(item.left_sample_event_ids),
            "right_sample_event_ids": list(item.right_sample_event_ids),
            "left_sample_events": [SnapshotService._issue_event_payload(event) for event in item.left_sample_events],
            "right_sample_events": [SnapshotService._issue_event_payload(event) for event in item.right_sample_events],
        }

    @staticmethod
    def _regressed_issue_payload(item: RegressedIssue) -> dict[str, Any]:
        return {
            "comparison_key": item.comparison_key,
            "title": item.title,
            "issue_type": item.issue_type,
            "severity": item.severity,
            "regression_result": item.regression_result,
            "change_type": item.change_type,
            "reason": item.reason,
            "occurrence_delta": item.occurrence_delta,
            "left_fingerprint": item.left_fingerprint,
            "right_fingerprint": item.right_fingerprint,
            "left_occurrence_count": item.left_occurrence_count,
            "right_occurrence_count": item.right_occurrence_count,
            "left_affected_run_count": item.left_affected_run_count,
            "right_affected_run_count": item.right_affected_run_count,
            "left_affected_device_count": item.left_affected_device_count,
            "right_affected_device_count": item.right_affected_device_count,
            "left_affected_scenario_count": item.left_affected_scenario_count,
            "right_affected_scenario_count": item.right_affected_scenario_count,
        }

    @staticmethod
    def _metric_trend_summary_payload(item: MetricTrendSummary) -> dict[str, Any]:
        return {
            "metric_key": item.metric_key,
            "label": item.label,
            "unit": item.unit,
            "sample_count": item.sample_count,
            "session_count": item.session_count,
            "average": item.average,
            "peak": item.peak,
            "p95": item.p95,
            "latest": item.latest,
        }

    @classmethod
    def _regressed_metric_payload(cls, item: RegressedMetric) -> dict[str, Any]:
        return {
            "metric_key": item.metric_key,
            "label": item.label,
            "unit": item.unit,
            "higher_is_worse": item.higher_is_worse,
            "regression_result": item.regression_result,
            "change_type": item.change_type,
            "reason": item.reason,
            "left_summary": cls._metric_trend_summary_payload(item.left_summary),
            "right_summary": cls._metric_trend_summary_payload(item.right_summary),
            "average_delta": item.average_delta,
            "peak_delta": item.peak_delta,
            "p95_delta": item.p95_delta,
            "latest_delta": item.latest_delta,
        }

    @staticmethod
    def _iso(value: Any) -> str | None:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return None
