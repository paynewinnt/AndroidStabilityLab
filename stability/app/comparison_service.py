from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from stability.domain import AggregatedIssue, ComparedIssue, ComparisonResult, ComparisonScope, IssueEventReference

from .analysis_service import AnalysisService


@dataclass(frozen=True)
class ComparisonQuery:
    dimension: str
    left_value: str
    right_value: str
    task_id: str = ""
    run_status: str = ""
    template_type: str = ""
    version: str = ""
    package_name: str = ""
    issue_type: str = ""
    created_from: str = ""
    created_to: str = ""
    limit: int = 20


class ComparisonService:
    """Minimal multi-dimension comparison service built on top of aggregated issues."""

    _DIMENSIONS = {"version", "device", "scenario"}
    _CHANGE_PRIORITY = {
        "new": 4,
        "changed": 3,
        "gone": 2,
        "unchanged": 1,
    }

    def __init__(self, *, analysis_service: AnalysisService) -> None:
        self._analysis_service = analysis_service

    def compare_issues(self, **filters: Any) -> ComparisonResult:
        query = self._build_query(filters)
        left_scope_filters = self._scope_filters(query, side="left")
        right_scope_filters = self._scope_filters(query, side="right")

        left_items = self._analysis_service.query_aggregated_issues(include_samples=True, **left_scope_filters)
        right_items = self._analysis_service.query_aggregated_issues(include_samples=True, **right_scope_filters)

        left_scope = ComparisonScope(
            dimension=query.dimension,
            value=query.left_value,
            label=self._scope_label(query.dimension, query.left_value),
            filters=left_scope_filters,
        )
        right_scope = ComparisonScope(
            dimension=query.dimension,
            value=query.right_value,
            label=self._scope_label(query.dimension, query.right_value),
            filters=right_scope_filters,
        )

        compared = self._compare_groups(query.dimension, left_items, right_items)
        limited_items = compared[: self._normalize_limit(query.limit)]
        return ComparisonResult(
            dimension=query.dimension,
            left_scope=left_scope,
            right_scope=right_scope,
            base_filters=self._base_filter_payload(query),
            sample_summary=self._sample_summary(left_items, right_items),
            issue_change_summary=self._issue_change_summary(compared),
            metric_change_summary={
                "available": False,
                "reason": "Performance metric comparison is not implemented in the current V2 phase.",
            },
            comparability_notes=self._comparability_notes(query, left_items, right_items),
            issues=tuple(limited_items),
        )

    @classmethod
    def _build_query(cls, filters: Mapping[str, Any]) -> ComparisonQuery:
        dimension = str(filters.get("dimension", "") or "").strip()
        if dimension not in cls._DIMENSIONS:
            raise ValueError(
                f"Unsupported comparison dimension '{dimension}'. "
                f"Expected one of: {', '.join(sorted(cls._DIMENSIONS))}."
            )
        left_value = str(filters.get("left_value", "") or "").strip()
        right_value = str(filters.get("right_value", "") or "").strip()
        if not left_value or not right_value:
            raise ValueError("Both left_value and right_value are required for comparison.")
        return ComparisonQuery(
            dimension=dimension,
            left_value=left_value,
            right_value=right_value,
            task_id=str(filters.get("task_id", "") or ""),
            run_status=str(filters.get("run_status", "") or ""),
            template_type=str(filters.get("template_type", "") or ""),
            version=str(filters.get("version", "") or ""),
            package_name=str(filters.get("package_name", "") or ""),
            issue_type=str(filters.get("issue_type", "") or ""),
            created_from=str(filters.get("created_from", "") or ""),
            created_to=str(filters.get("created_to", "") or ""),
            limit=int(filters.get("limit", 20) or 20),
        )

    @classmethod
    def _scope_filters(cls, query: ComparisonQuery, *, side: str) -> dict[str, Any]:
        filters: dict[str, Any] = {
            "task_id": query.task_id,
            "run_status": query.run_status,
            "package_name": query.package_name,
            "issue_type": query.issue_type,
            "created_from": query.created_from,
            "created_to": query.created_to,
        }
        if query.dimension != "scenario" and query.template_type:
            filters["template_type"] = query.template_type
        if query.dimension != "version" and query.version:
            filters["version"] = query.version

        scope_value = query.left_value if side == "left" else query.right_value
        if query.dimension == "version":
            filters["version"] = scope_value
        elif query.dimension == "device":
            filters["device_id"] = scope_value
            if query.template_type:
                filters["template_type"] = query.template_type
            if query.version:
                filters["version"] = query.version
        else:
            filters["template_type"] = scope_value
            if query.version:
                filters["version"] = query.version
        return filters

    @classmethod
    def _scope_label(cls, dimension: str, value: str) -> str:
        if dimension == "scenario":
            return f"scenario:{value}"
        if dimension == "device":
            return f"device:{value}"
        return f"version:{value}"

    @classmethod
    def _base_filter_payload(cls, query: ComparisonQuery) -> dict[str, Any]:
        payload = {
            "task_id": query.task_id or None,
            "run_status": query.run_status or None,
            "package_name": query.package_name or None,
            "issue_type": query.issue_type or None,
            "created_from": query.created_from or None,
            "created_to": query.created_to or None,
        }
        if query.dimension != "scenario":
            payload["template_type"] = query.template_type or None
        if query.dimension != "version":
            payload["version"] = query.version or None
        return payload

    @classmethod
    def _compare_groups(
        cls,
        dimension: str,
        left_items: Sequence[AggregatedIssue],
        right_items: Sequence[AggregatedIssue],
    ) -> list[ComparedIssue]:
        left_map = {cls._alignment_key(dimension, item): item for item in left_items}
        right_map = {cls._alignment_key(dimension, item): item for item in right_items}
        compared: list[ComparedIssue] = []
        for comparison_key in sorted(set(left_map) | set(right_map)):
            left_issue = left_map.get(comparison_key)
            right_issue = right_map.get(comparison_key)
            compared.append(cls._build_compared_issue(comparison_key, left_issue, right_issue))
        compared.sort(
            key=lambda item: (
                cls._CHANGE_PRIORITY.get(item.change_type, 0),
                abs(item.occurrence_delta),
                max(item.left_occurrence_count, item.right_occurrence_count),
                item.comparison_key,
            ),
            reverse=True,
        )
        return compared

    @classmethod
    def _build_compared_issue(
        cls,
        comparison_key: str,
        left_issue: AggregatedIssue | None,
        right_issue: AggregatedIssue | None,
    ) -> ComparedIssue:
        source = right_issue or left_issue
        if source is None:
            raise ValueError("Compared issue requires at least one side.")
        change_type = cls._change_type(left_issue, right_issue)
        return ComparedIssue(
            comparison_key=comparison_key,
            title=source.title,
            issue_type=source.issue_type.value,
            severity=source.severity.value,
            change_type=change_type,
            occurrence_delta=(right_issue.occurrence_count if right_issue is not None else 0)
            - (left_issue.occurrence_count if left_issue is not None else 0),
            left_fingerprint=left_issue.fingerprint.value if left_issue is not None else "",
            right_fingerprint=right_issue.fingerprint.value if right_issue is not None else "",
            left_occurrence_count=left_issue.occurrence_count if left_issue is not None else 0,
            right_occurrence_count=right_issue.occurrence_count if right_issue is not None else 0,
            left_affected_run_count=left_issue.affected_run_count if left_issue is not None else 0,
            right_affected_run_count=right_issue.affected_run_count if right_issue is not None else 0,
            left_affected_device_count=left_issue.affected_device_count if left_issue is not None else 0,
            right_affected_device_count=right_issue.affected_device_count if right_issue is not None else 0,
            left_affected_scenario_count=left_issue.affected_scenario_count if left_issue is not None else 0,
            right_affected_scenario_count=right_issue.affected_scenario_count if right_issue is not None else 0,
            left_sample_event_ids=tuple(left_issue.sample_event_ids if left_issue is not None else ()),
            right_sample_event_ids=tuple(right_issue.sample_event_ids if right_issue is not None else ()),
            left_sample_events=tuple(cls._sample_events(left_issue)),
            right_sample_events=tuple(cls._sample_events(right_issue)),
            left_issue=left_issue,
            right_issue=right_issue,
        )

    @staticmethod
    def _sample_events(item: AggregatedIssue | None) -> Sequence[IssueEventReference]:
        if item is None:
            return ()
        return tuple(item.sample_events[:2])

    @staticmethod
    def _change_type(left_issue: AggregatedIssue | None, right_issue: AggregatedIssue | None) -> str:
        if left_issue is None and right_issue is not None:
            return "new"
        if left_issue is not None and right_issue is None:
            return "gone"
        if left_issue is None or right_issue is None:
            return "changed"
        if (
            left_issue.occurrence_count == right_issue.occurrence_count
            and left_issue.affected_run_count == right_issue.affected_run_count
            and left_issue.affected_device_count == right_issue.affected_device_count
            and left_issue.affected_scenario_count == right_issue.affected_scenario_count
        ):
            return "unchanged"
        return "changed"

    @staticmethod
    def _sample_summary(
        left_items: Sequence[AggregatedIssue],
        right_items: Sequence[AggregatedIssue],
    ) -> dict[str, Any]:
        return {
            "left_issue_group_count": len(left_items),
            "right_issue_group_count": len(right_items),
            "left_occurrence_count": sum(item.occurrence_count for item in left_items),
            "right_occurrence_count": sum(item.occurrence_count for item in right_items),
            "left_latest_seen_at": ComparisonService._latest_seen_at(left_items),
            "right_latest_seen_at": ComparisonService._latest_seen_at(right_items),
        }

    @classmethod
    def _issue_change_summary(cls, items: Sequence[ComparedIssue]) -> dict[str, int]:
        summary = {
            "new_count": 0,
            "gone_count": 0,
            "changed_count": 0,
            "unchanged_count": 0,
        }
        for item in items:
            summary[f"{item.change_type}_count"] = summary.get(f"{item.change_type}_count", 0) + 1
        return summary

    @classmethod
    def _alignment_key(cls, dimension: str, item: AggregatedIssue) -> str:
        if dimension != "scenario":
            return item.fingerprint.value
        components = dict(item.fingerprint.components)
        components["scenario_name"] = ""
        return json.dumps(
            {
                "rule_version": item.fingerprint.rule_version,
                "components": components,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @classmethod
    def _comparability_notes(
        cls,
        query: ComparisonQuery,
        left_items: Sequence[AggregatedIssue],
        right_items: Sequence[AggregatedIssue],
    ) -> tuple[str, ...]:
        notes = [
            "Issue comparison is based on the current fingerprint rule version and current query filters.",
            "Performance metric comparison is not implemented in the current V2 phase.",
        ]
        if query.dimension == "version":
            notes.append("Version comparison currently uses task target-app version_name/version_code snapshots.")
        elif query.dimension == "device":
            notes.append("Device comparison currently operates on single device_id scopes, not persisted device groups.")
        else:
            notes.append("Scenario comparison currently maps scenario scope to task template_type.")
        if not left_items or not right_items:
            notes.append("One comparison side has no aggregated issues under the current filters; treat the result carefully.")
        return tuple(notes)

    @staticmethod
    def _latest_seen_at(items: Sequence[AggregatedIssue]) -> str | None:
        seen = [item.last_seen_at for item in items if item.last_seen_at is not None]
        if not seen:
            return None
        latest = max(seen)
        return latest.isoformat() if hasattr(latest, "isoformat") else str(latest)

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        return max(0, int(limit))
