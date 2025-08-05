from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from stability.domain import (
    ComparedIssue,
    ComparedMetricTrend,
    RegressionResult,
    RegressionRuleSet,
    RegressedIssue,
    RegressedMetric,
)

from .comparison_service import ComparisonService
from .performance_trend_service import PerformanceTrendService


@dataclass(frozen=True)
class RegressionQuery:
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
    rule_set: RegressionRuleSet = RegressionRuleSet()


class RegressionService:
    """Minimal rule-based regression judge on top of comparison results."""

    _SUPPRESSED_COMPARABILITY_NOTES = {
        "Performance metric comparison is not implemented in the current V2 phase.",
    }
    _RESULT_PRIORITY = {
        "new": 6,
        "worsened": 5,
        "insufficient_data": 4,
        "unchanged": 3,
        "improved": 2,
        "gone": 1,
    }
    _SEVERITY_PRIORITY = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    def __init__(
        self,
        *,
        comparison_service: ComparisonService,
        performance_trend_service: PerformanceTrendService | None = None,
        configured_rule_set: RegressionRuleSet | None = None,
    ) -> None:
        self._comparison_service = comparison_service
        self._performance_trend_service = performance_trend_service
        self._configured_rule_set = configured_rule_set or RegressionRuleSet()

    def evaluate_regression(self, **filters: Any) -> RegressionResult:
        query = self._build_query(filters)
        comparison = self._comparison_service.compare_issues(
            dimension=query.dimension,
            left_value=query.left_value,
            right_value=query.right_value,
            task_id=query.task_id,
            run_status=query.run_status,
            template_type=query.template_type,
            version=query.version,
            package_name=query.package_name,
            issue_type=query.issue_type,
            created_from=query.created_from,
            created_to=query.created_to,
            limit=query.limit,
        )
        judged_items = [self._judge_issue(item, query.rule_set) for item in comparison.issues]
        judged_items.sort(
            key=lambda item: (
                self._RESULT_PRIORITY.get(item.regression_result, 0),
                self._SEVERITY_PRIORITY.get(item.severity, 0),
                abs(item.occurrence_delta),
                item.comparison_key,
            ),
            reverse=True,
        )
        metric_items, metric_summary, metric_notes = self._evaluate_metrics(query)
        overall_result, reasons = self._overall_result(
            comparison.sample_summary,
            judged_items,
            metric_items,
            query.rule_set,
        )
        issue_result_summary = self._issue_result_summary(judged_items)
        return RegressionResult(
            dimension=comparison.dimension,
            left_scope=comparison.left_scope,
            right_scope=comparison.right_scope,
            base_filters=comparison.base_filters,
            rule_set=query.rule_set,
            overall_result=overall_result,
            issue_result_summary=issue_result_summary,
            metric_result_summary=metric_summary,
            summary={
                **comparison.sample_summary,
                "issue_count": len(judged_items),
                "metric_count": len(metric_items),
            },
            reasons=tuple(reasons),
            comparability_notes=tuple(
                note
                for note in (*comparison.comparability_notes, *metric_notes)
                if note not in self._SUPPRESSED_COMPARABILITY_NOTES
            ),
            issues=tuple(judged_items),
            metrics=tuple(metric_items),
        )

    def _build_query(self, filters: Mapping[str, Any]) -> RegressionQuery:
        return RegressionQuery(
            dimension=str(filters.get("dimension", "") or "").strip(),
            left_value=str(filters.get("left_value", "") or "").strip(),
            right_value=str(filters.get("right_value", "") or "").strip(),
            task_id=str(filters.get("task_id", "") or ""),
            run_status=str(filters.get("run_status", "") or ""),
            template_type=str(filters.get("template_type", "") or ""),
            version=str(filters.get("version", "") or ""),
            package_name=str(filters.get("package_name", "") or ""),
            issue_type=str(filters.get("issue_type", "") or ""),
            created_from=str(filters.get("created_from", "") or ""),
            created_to=str(filters.get("created_to", "") or ""),
            limit=int(filters.get("limit", 20) or 20),
            rule_set=self._resolve_rule_set(filters),
        )

    def _resolve_rule_set(self, filters: Mapping[str, Any]) -> RegressionRuleSet:
        defaults = self._default_rule_set()
        return RegressionRuleSet(
            version=defaults.version,
            min_side_issue_groups=self._override_int(
                filters.get("min_side_issue_groups"),
                defaults.min_side_issue_groups,
            ),
            significant_occurrence_delta=self._override_int(
                filters.get("significant_occurrence_delta"),
                defaults.significant_occurrence_delta,
            ),
            significant_affected_run_delta=self._override_int(
                filters.get("significant_affected_run_delta"),
                defaults.significant_affected_run_delta,
            ),
            significant_affected_device_delta=self._override_int(
                filters.get("significant_affected_device_delta"),
                defaults.significant_affected_device_delta,
            ),
            significant_affected_scenario_delta=self._override_int(
                filters.get("significant_affected_scenario_delta"),
                defaults.significant_affected_scenario_delta,
            ),
            min_side_metric_sessions=self._override_int(
                filters.get("min_side_metric_sessions"),
                defaults.min_side_metric_sessions,
            ),
            min_side_metric_samples=self._override_int(
                filters.get("min_side_metric_samples"),
                defaults.min_side_metric_samples,
            ),
            significant_metric_delta_ratio=self._override_float(
                filters.get("significant_metric_delta_ratio"),
                defaults.significant_metric_delta_ratio,
            ),
        )

    def _default_rule_set(self) -> RegressionRuleSet:
        return self._configured_rule_set

    @staticmethod
    def _override_int(value: Any, default: int) -> int:
        if value in (None, ""):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _override_float(value: Any, default: float) -> float:
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _evaluate_metrics(
        self,
        query: RegressionQuery,
    ) -> tuple[list[RegressedMetric], dict[str, Any], tuple[str, ...]]:
        if self._performance_trend_service is None:
            return (
                [],
                {
                    "available": False,
                    "reason": "Performance trend service is not available in the current bootstrap.",
                },
                (),
            )
        comparison = self._performance_trend_service.compare_performance_trends(
            dimension=query.dimension,
            left_value=query.left_value,
            right_value=query.right_value,
            task_id=query.task_id,
            run_status=query.run_status,
            template_type=query.template_type,
            version=query.version,
            package_name=query.package_name,
            created_from=query.created_from,
            created_to=query.created_to,
        )
        metrics = [self._judge_metric(item, query.rule_set) for item in comparison.metrics]
        metrics.sort(
            key=lambda item: (
                self._RESULT_PRIORITY.get(item.regression_result, 0),
                abs(item.average_delta or 0.0),
                item.metric_key,
            ),
            reverse=True,
        )
        return metrics, self._metric_result_summary(metrics), tuple(comparison.comparability_notes)

    @classmethod
    def _judge_issue(cls, item: ComparedIssue, rule_set: RegressionRuleSet) -> RegressedIssue:
        result = "unchanged"
        reason = "Issue counts and affected-scope counts remain unchanged."
        if item.change_type == "new":
            result = "new"
            reason = "The issue only exists on the target side."
        elif item.change_type == "gone":
            result = "gone"
            reason = "The issue only exists on the baseline side."
        elif item.change_type == "unchanged":
            result = "unchanged"
            reason = "The issue is present on both sides with the same occurrence and affected-scope counts."
        else:
            deltas = cls._delta_signals(item)
            if cls._is_significant_positive_change(deltas, rule_set):
                result = "worsened"
                reason = cls._delta_reason("Target side increased", deltas)
            elif cls._is_significant_negative_change(deltas, rule_set):
                result = "improved"
                reason = cls._delta_reason("Target side decreased", deltas)
            else:
                result = "unchanged"
                reason = "The issue changed, but the delta does not cross the current rule thresholds."
        return RegressedIssue(
            comparison_key=item.comparison_key,
            title=item.title,
            issue_type=item.issue_type,
            severity=item.severity,
            regression_result=result,
            change_type=item.change_type,
            reason=reason,
            occurrence_delta=item.occurrence_delta,
            left_fingerprint=item.left_fingerprint,
            right_fingerprint=item.right_fingerprint,
            left_occurrence_count=item.left_occurrence_count,
            right_occurrence_count=item.right_occurrence_count,
            left_affected_run_count=item.left_affected_run_count,
            right_affected_run_count=item.right_affected_run_count,
            left_affected_device_count=item.left_affected_device_count,
            right_affected_device_count=item.right_affected_device_count,
            left_affected_scenario_count=item.left_affected_scenario_count,
            right_affected_scenario_count=item.right_affected_scenario_count,
        )

    @classmethod
    def _judge_metric(cls, item: ComparedMetricTrend, rule_set: RegressionRuleSet) -> RegressedMetric:
        if (
            item.left_summary.session_count < rule_set.min_side_metric_sessions
            or item.right_summary.session_count < rule_set.min_side_metric_sessions
            or item.left_summary.sample_count < rule_set.min_side_metric_samples
            or item.right_summary.sample_count < rule_set.min_side_metric_samples
        ):
            result = "insufficient_data"
            reason = "At least one comparison side does not meet the minimum metric sample/session threshold."
        elif item.average_delta is None:
            result = "insufficient_data"
            reason = "Average metric delta is unavailable."
        else:
            baseline = abs(item.left_summary.average or 0.0)
            threshold = baseline * rule_set.significant_metric_delta_ratio
            if baseline <= 0:
                threshold = rule_set.significant_metric_delta_ratio
            threshold = max(threshold, 0.01)
            if abs(item.average_delta) < threshold:
                result = "unchanged"
                reason = (
                    f"Average delta {item.average_delta} does not cross the current metric threshold "
                    f"{round(threshold, 2)}."
                )
            else:
                if item.higher_is_worse:
                    result = "worsened" if item.average_delta > 0 else "improved"
                else:
                    result = "improved" if item.average_delta > 0 else "worsened"
                direction = "increased" if item.average_delta > 0 else "decreased"
                reason = (
                    f"Average metric value {direction} by {item.average_delta}, "
                    f"crossing threshold {round(threshold, 2)}."
                )
        return RegressedMetric(
            metric_key=item.metric_key,
            label=item.label,
            unit=item.unit,
            higher_is_worse=item.higher_is_worse,
            regression_result=result,
            change_type=item.change_type,
            reason=reason,
            left_summary=item.left_summary,
            right_summary=item.right_summary,
            average_delta=item.average_delta,
            peak_delta=item.peak_delta,
            p95_delta=item.p95_delta,
            latest_delta=item.latest_delta,
        )

    @staticmethod
    def _delta_signals(item: ComparedIssue) -> dict[str, int]:
        return {
            "occurrence_delta": item.occurrence_delta,
            "affected_run_delta": item.right_affected_run_count - item.left_affected_run_count,
            "affected_device_delta": item.right_affected_device_count - item.left_affected_device_count,
            "affected_scenario_delta": item.right_affected_scenario_count - item.left_affected_scenario_count,
        }

    @staticmethod
    def _delta_reason(prefix: str, deltas: Mapping[str, int]) -> str:
        active = [f"{key}={value}" for key, value in deltas.items() if value != 0]
        if not active:
            return prefix
        return f"{prefix}: {', '.join(active)}."

    @staticmethod
    def _is_significant_positive_change(deltas: Mapping[str, int], rule_set: RegressionRuleSet) -> bool:
        return (
            deltas["occurrence_delta"] >= rule_set.significant_occurrence_delta
            or deltas["affected_run_delta"] >= rule_set.significant_affected_run_delta
            or deltas["affected_device_delta"] >= rule_set.significant_affected_device_delta
            or deltas["affected_scenario_delta"] >= rule_set.significant_affected_scenario_delta
        )

    @staticmethod
    def _is_significant_negative_change(deltas: Mapping[str, int], rule_set: RegressionRuleSet) -> bool:
        return (
            deltas["occurrence_delta"] <= -rule_set.significant_occurrence_delta
            or deltas["affected_run_delta"] <= -rule_set.significant_affected_run_delta
            or deltas["affected_device_delta"] <= -rule_set.significant_affected_device_delta
            or deltas["affected_scenario_delta"] <= -rule_set.significant_affected_scenario_delta
        )

    @classmethod
    def _overall_result(
        cls,
        sample_summary: Mapping[str, Any],
        items: list[RegressedIssue],
        metrics: list[RegressedMetric],
        rule_set: RegressionRuleSet,
    ) -> tuple[str, list[str]]:
        left_groups = int(sample_summary.get("left_issue_group_count", 0) or 0)
        right_groups = int(sample_summary.get("right_issue_group_count", 0) or 0)
        reasons: list[str] = []
        worsened_metrics = [item for item in metrics if item.regression_result == "worsened"]
        if left_groups < rule_set.min_side_issue_groups or right_groups < rule_set.min_side_issue_groups:
            reasons.append("At least one comparison side does not meet the minimum issue-group sample threshold.")
            if worsened_metrics:
                reasons.append("Performance metrics show worsened signals despite limited issue-group comparability.")
                return "suspected_regression", reasons
            if metrics and all(item.regression_result == "insufficient_data" for item in metrics):
                return "insufficient_data", reasons
        if any(item.regression_result == "new" and item.severity in {"critical", "high"} for item in items):
            reasons.append("Found new high-severity issues on the target side.")
            return "obvious_regression", reasons
        if any(item.regression_result == "worsened" and item.severity in {"critical", "high"} for item in items):
            reasons.append("Found worsened high-severity issues on the target side.")
            return "obvious_regression", reasons
        if worsened_metrics:
            reasons.append(
                "Found worsened key performance metrics on the target side: "
                + ", ".join(item.metric_key for item in worsened_metrics[:3])
                + "."
            )
            return "suspected_regression", reasons
        if any(item.regression_result in {"new", "worsened"} for item in items):
            reasons.append("Found target-side issue deltas that exceed the current regression thresholds.")
            return "suspected_regression", reasons
        if left_groups < rule_set.min_side_issue_groups or right_groups < rule_set.min_side_issue_groups:
            return "insufficient_data", reasons
        reasons.append("No issue or metric delta crosses the current regression thresholds.")
        return "no_obvious_change", reasons

    @staticmethod
    def _issue_result_summary(items: list[RegressedIssue]) -> dict[str, int]:
        summary = {
            "new_count": 0,
            "worsened_count": 0,
            "unchanged_count": 0,
            "improved_count": 0,
            "gone_count": 0,
            "insufficient_data_count": 0,
        }
        for item in items:
            key = f"{item.regression_result}_count"
            summary[key] = summary.get(key, 0) + 1
        return summary

    @staticmethod
    def _metric_result_summary(items: list[RegressedMetric]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "available": True,
            "metric_count": len(items),
            "new_count": 0,
            "worsened_count": 0,
            "unchanged_count": 0,
            "improved_count": 0,
            "gone_count": 0,
            "insufficient_data_count": 0,
        }
        for item in items:
            key = f"{item.regression_result}_count"
            summary[key] = summary.get(key, 0) + 1
        return summary
