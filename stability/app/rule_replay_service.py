from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from stability.domain import AggregatedIssue, ReplayedIssueFamily, RuleReplayResult, RuleReplaySide
from stability.infrastructure import FileBackedRuleConfigProvider

from .analysis_service import AnalysisService


class TaskRepository(Protocol):
    def get(self, task_id: str):
        ...


class RunRepository(Protocol):
    def list(self):
        ...


class InstanceRepository(Protocol):
    def list_by_run(self, run_id: str):
        ...


@dataclass(frozen=True)
class RuleReplayQuery:
    baseline_path: str = ""
    candidate_path: str = ""
    task_id: str = ""
    run_status: str = ""
    template_type: str = ""
    version: str = ""
    package_name: str = ""
    device_id: str = ""
    issue_type: str = ""
    created_from: str = ""
    created_to: str = ""
    limit: int = 20
    include_unchanged: bool = False


class RuleReplayService:
    """Replay one aggregated Top Issue query under two rule configurations."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
        default_rule_path: str = "config/stability_rules.json",
    ) -> None:
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._default_rule_path = default_rule_path

    def replay_top_issues(self, **filters: Any) -> RuleReplayResult:
        query = self._build_query(filters)
        baseline_path = query.baseline_path or self._default_rule_path
        candidate_path = query.candidate_path
        if not candidate_path:
            raise ValueError("candidate_path is required for rule replay.")

        baseline_analysis = self._analysis_service(baseline_path)
        candidate_analysis = self._analysis_service(candidate_path)
        top_issue_filters = self._top_issue_filters(query)
        baseline_items = baseline_analysis.query_aggregated_issues(include_samples=True, **top_issue_filters)
        candidate_items = candidate_analysis.query_aggregated_issues(include_samples=True, **top_issue_filters)
        compared = self._compare_families(baseline_items, candidate_items)
        if not query.include_unchanged:
            compared = [item for item in compared if item.change_type != "unchanged"]
        limited = compared[: self._normalize_limit(query.limit)]
        change_summary = Counter(item.change_type for item in compared)
        return RuleReplayResult(
            baseline=RuleReplaySide(
                path=baseline_path,
                fingerprint_rule_version=baseline_analysis.fingerprint_rule_version,
            ),
            candidate=RuleReplaySide(
                path=candidate_path,
                fingerprint_rule_version=candidate_analysis.fingerprint_rule_version,
            ),
            filters=top_issue_filters,
            family_count=len(self._compare_families(baseline_items, candidate_items)),
            changed_family_count=sum(1 for item in self._compare_families(baseline_items, candidate_items) if item.change_type != "unchanged"),
            change_summary=dict(change_summary),
            families=tuple(limited),
        )

    def _analysis_service(self, rule_path: str) -> AnalysisService:
        rule_config = FileBackedRuleConfigProvider(rule_path).load()
        return AnalysisService(
            task_repository=self._task_repository,
            run_repository=self._run_repository,
            instance_repository=self._instance_repository,
            rule_config=rule_config,
        )

    @classmethod
    def _build_query(cls, filters: Mapping[str, Any]) -> RuleReplayQuery:
        return RuleReplayQuery(
            baseline_path=str(filters.get("baseline_path", "") or "").strip(),
            candidate_path=str(filters.get("candidate_path", "") or "").strip(),
            task_id=str(filters.get("task_id", "") or "").strip(),
            run_status=str(filters.get("run_status", "") or "").strip(),
            template_type=str(filters.get("template_type", "") or "").strip(),
            version=str(filters.get("version", "") or "").strip(),
            package_name=str(filters.get("package_name", "") or "").strip(),
            device_id=str(filters.get("device_id", "") or "").strip(),
            issue_type=str(filters.get("issue_type", "") or "").strip(),
            created_from=str(filters.get("created_from", "") or "").strip(),
            created_to=str(filters.get("created_to", "") or "").strip(),
            limit=int(filters.get("limit", 20) or 20),
            include_unchanged=bool(filters.get("include_unchanged", False)),
        )

    @staticmethod
    def _normalize_limit(value: int) -> int:
        return max(0, int(value))

    @staticmethod
    def _top_issue_filters(query: RuleReplayQuery) -> dict[str, object]:
        return {
            "task_id": query.task_id,
            "run_status": query.run_status,
            "template_type": query.template_type,
            "version": query.version,
            "package_name": query.package_name,
            "device_id": query.device_id,
            "issue_type": query.issue_type,
            "created_from": query.created_from,
            "created_to": query.created_to,
        }

    @classmethod
    def _compare_families(
        cls,
        baseline_items: Sequence[AggregatedIssue],
        candidate_items: Sequence[AggregatedIssue],
    ) -> list[ReplayedIssueFamily]:
        baseline_map = cls._family_map(baseline_items)
        candidate_map = cls._family_map(candidate_items)
        results: list[ReplayedIssueFamily] = []
        for key in sorted(set(baseline_map) | set(candidate_map)):
            left_items = baseline_map.get(key, ())
            right_items = candidate_map.get(key, ())
            source = right_items[0] if right_items else left_items[0]
            change_type, notes = cls._change_type(left_items, right_items)
            results.append(
                ReplayedIssueFamily(
                    comparison_key=key,
                    issue_type=source.issue_type.value,
                    package_name=str(source.fingerprint.components.get("package_name", "") or ""),
                    process_name=str(source.fingerprint.components.get("process_name", "") or ""),
                    scenario_name=str(source.fingerprint.components.get("scenario_name", "") or ""),
                    title=source.title,
                    change_type=change_type,
                    left_group_count=len(left_items),
                    right_group_count=len(right_items),
                    left_occurrence_count=sum(item.occurrence_count for item in left_items),
                    right_occurrence_count=sum(item.occurrence_count for item in right_items),
                    left_fingerprints=tuple(item.fingerprint.value for item in left_items),
                    right_fingerprints=tuple(item.fingerprint.value for item in right_items),
                    left_sample_event_ids=tuple(
                        event_id for item in left_items for event_id in item.sample_event_ids[:2]
                    ),
                    right_sample_event_ids=tuple(
                        event_id for item in right_items for event_id in item.sample_event_ids[:2]
                    ),
                    left_sample_events=tuple(
                        sample for item in left_items for sample in item.sample_events[:2]
                    ),
                    right_sample_events=tuple(
                        sample for item in right_items for sample in item.sample_events[:2]
                    ),
                    notes=tuple(notes),
                )
            )
        results.sort(
            key=lambda item: (
                cls._priority(item.change_type),
                item.left_group_count != item.right_group_count,
                abs(item.right_occurrence_count - item.left_occurrence_count),
                item.comparison_key,
            ),
            reverse=True,
        )
        return results

    @staticmethod
    def _priority(change_type: str) -> int:
        order = {
            "regrouped": 5,
            "fingerprint_changed": 4,
            "added": 3,
            "removed": 2,
            "count_changed": 1,
            "unchanged": 0,
        }
        return order.get(change_type, 0)

    @classmethod
    def _family_map(cls, items: Sequence[AggregatedIssue]) -> dict[str, list[AggregatedIssue]]:
        families: dict[str, list[AggregatedIssue]] = defaultdict(list)
        for item in items:
            key = cls._family_key(item)
            families[key].append(item)
        return families

    @classmethod
    def _family_key(cls, item: AggregatedIssue) -> str:
        payload = {
            "issue_type": item.issue_type.value,
            "package_name": item.fingerprint.components.get("package_name", ""),
            "process_name": item.fingerprint.components.get("process_name", ""),
            "scenario_name": item.fingerprint.components.get("scenario_name", ""),
            "title": item.title,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @classmethod
    def _change_type(
        cls,
        left_items: Sequence[AggregatedIssue],
        right_items: Sequence[AggregatedIssue],
    ) -> tuple[str, Sequence[str]]:
        if not left_items and right_items:
            return "added", ("The issue family only exists under the candidate rule.",)
        if left_items and not right_items:
            return "removed", ("The issue family only exists under the baseline rule.",)
        left_group_count = len(left_items)
        right_group_count = len(right_items)
        left_occurrences = sum(item.occurrence_count for item in left_items)
        right_occurrences = sum(item.occurrence_count for item in right_items)
        left_fingerprints = {item.fingerprint.value for item in left_items}
        right_fingerprints = {item.fingerprint.value for item in right_items}
        if left_group_count != right_group_count:
            direction = "merged" if right_group_count < left_group_count else "split"
            return "regrouped", (f"The candidate rule {direction} this issue family.",)
        if left_fingerprints != right_fingerprints:
            return "fingerprint_changed", ("The candidate rule changed fingerprint identities for this family.",)
        if left_occurrences != right_occurrences:
            return "count_changed", ("The family occurrence count changed under the candidate rule.",)
        return "unchanged", ()
