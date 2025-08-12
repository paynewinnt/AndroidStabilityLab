from __future__ import annotations

import unittest

from stability.app import RegressionService
from stability.domain import (
    ComparedIssue,
    ComparedMetricTrend,
    ComparisonResult,
    ComparisonScope,
    MetricTrendSummary,
    PerformanceTrendComparison,
)

from tests.test_comparison_service import build_comparison_service_fixture


class RegressionServiceTest(unittest.TestCase):
    def test_evaluate_regression_reports_obvious_regression_for_new_high_severity_issue(self) -> None:
        service = build_regression_service_fixture()

        result = service.evaluate_regression(
            dimension="scenario",
            left_value="monkey",
            right_value="cold_start_loop",
            version="1.0.0(100)",
            package_name="com.example.app",
        )

        self.assertEqual(result.overall_result, "obvious_regression")
        self.assertEqual(result.issue_result_summary["new_count"], 1)
        self.assertTrue(result.metric_result_summary["available"])
        issues = {item.issue_type: item for item in result.issues}
        self.assertEqual(issues["reboot"].regression_result, "new")
        self.assertEqual(issues["crash"].regression_result, "improved")

    def test_evaluate_regression_reports_suspected_regression_for_non_critical_new_issue(self) -> None:
        comparison_service = _FakeComparisonService(
            ComparisonResult(
                dimension="device",
                left_scope=ComparisonScope(
                    dimension="device",
                    value="device-a",
                    label="device:device-a",
                    filters={"device_id": "device-a"},
                ),
                right_scope=ComparisonScope(
                    dimension="device",
                    value="device-b",
                    label="device:device-b",
                    filters={"device_id": "device-b"},
                ),
                base_filters={"package_name": "com.example.app"},
                sample_summary={
                    "left_issue_group_count": 1,
                    "right_issue_group_count": 2,
                    "left_occurrence_count": 1,
                    "right_occurrence_count": 2,
                },
                issue_change_summary={"new_count": 1},
                metric_change_summary={"available": False},
                comparability_notes=(),
                issues=(
                    ComparedIssue(
                        comparison_key="cmp-medium-new",
                        title="进程异常退出",
                        issue_type="process_exit",
                        severity="medium",
                        change_type="new",
                        occurrence_delta=1,
                        right_fingerprint="ifp_process_exit",
                        right_occurrence_count=1,
                        right_affected_run_count=1,
                        right_affected_device_count=1,
                        right_affected_scenario_count=1,
                    ),
                ),
            )
        )
        service = RegressionService(comparison_service=comparison_service)

        result = service.evaluate_regression(
            dimension="device",
            left_value="device-a",
            right_value="device-b",
            package_name="com.example.app",
        )

        self.assertEqual(result.overall_result, "suspected_regression")
        self.assertEqual(result.issues[0].regression_result, "new")

    def test_evaluate_regression_reports_no_obvious_change_when_only_improvements_exist(self) -> None:
        service = build_regression_service_fixture()

        result = service.evaluate_regression(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        self.assertEqual(result.overall_result, "no_obvious_change")
        self.assertEqual(result.metric_result_summary["worsened_count"], 0)
        issues = {item.issue_type: item for item in result.issues}
        self.assertEqual(issues["crash"].regression_result, "improved")
        self.assertEqual(issues["device_offline"].regression_result, "gone")
        self.assertEqual(issues["startup_timeout"].regression_result, "unchanged")

    def test_evaluate_regression_reports_insufficient_data_when_one_side_is_empty(self) -> None:
        service = build_regression_service_fixture()

        result = service.evaluate_regression(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="3.0.0(300)",
            template_type="monkey",
            package_name="com.example.app",
        )

        self.assertEqual(result.overall_result, "insufficient_data")
        self.assertIn("minimum issue-group sample threshold", " ".join(result.reasons))

    def test_evaluate_regression_reports_suspected_regression_for_worsened_metrics(self) -> None:
        comparison_service = _FakeComparisonService(
            ComparisonResult(
                dimension="version",
                left_scope=ComparisonScope(
                    dimension="version",
                    value="1.0.0(100)",
                    label="version:1.0.0(100)",
                    filters={"version": "1.0.0(100)"},
                ),
                right_scope=ComparisonScope(
                    dimension="version",
                    value="2.0.0(200)",
                    label="version:2.0.0(200)",
                    filters={"version": "2.0.0(200)"},
                ),
                base_filters={"package_name": "com.example.app"},
                sample_summary={
                    "left_issue_group_count": 1,
                    "right_issue_group_count": 1,
                },
                issue_change_summary={"unchanged_count": 1},
                metric_change_summary={},
                comparability_notes=(),
                issues=(
                    ComparedIssue(
                        comparison_key="cmp-unchanged",
                        title="启动超时",
                        issue_type="startup_timeout",
                        severity="medium",
                        change_type="unchanged",
                        occurrence_delta=0,
                        left_fingerprint="ifp_a",
                        right_fingerprint="ifp_a",
                        left_occurrence_count=1,
                        right_occurrence_count=1,
                        left_affected_run_count=1,
                        right_affected_run_count=1,
                        left_affected_device_count=1,
                        right_affected_device_count=1,
                        left_affected_scenario_count=1,
                        right_affected_scenario_count=1,
                    ),
                ),
            )
        )
        performance_service = _FakePerformanceTrendService(
            PerformanceTrendComparison(
                dimension="version",
                left_scope=ComparisonScope(
                    dimension="version",
                    value="1.0.0(100)",
                    label="version:1.0.0(100)",
                    filters={"version": "1.0.0(100)"},
                ),
                right_scope=ComparisonScope(
                    dimension="version",
                    value="2.0.0(200)",
                    label="version:2.0.0(200)",
                    filters={"version": "2.0.0(200)"},
                ),
                base_filters={"package_name": "com.example.app"},
                sample_summary={"left_session_count": 1, "right_session_count": 1},
                metric_change_summary={},
                comparability_notes=("metric compare",),
                metrics=(
                    ComparedMetricTrend(
                        metric_key="memory_pss",
                        label="Memory PSS",
                        unit="MB",
                        higher_is_worse=True,
                        left_summary=MetricTrendSummary(
                            metric_key="memory_pss",
                            label="Memory PSS",
                            unit="MB",
                            sample_count=10,
                            session_count=1,
                            average=100.0,
                            peak=120.0,
                            p95=118.0,
                            latest=105.0,
                        ),
                        right_summary=MetricTrendSummary(
                            metric_key="memory_pss",
                            label="Memory PSS",
                            unit="MB",
                            sample_count=10,
                            session_count=1,
                            average=130.0,
                            peak=160.0,
                            p95=158.0,
                            latest=132.0,
                        ),
                        average_delta=30.0,
                        peak_delta=40.0,
                        p95_delta=40.0,
                        latest_delta=27.0,
                        change_type="worsened",
                    ),
                ),
            )
        )
        service = RegressionService(
            comparison_service=comparison_service,
            performance_trend_service=performance_service,
        )

        result = service.evaluate_regression(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            package_name="com.example.app",
        )

        self.assertEqual(result.overall_result, "suspected_regression")
        self.assertEqual(result.metric_result_summary["worsened_count"], 1)
        self.assertEqual(result.metrics[0].regression_result, "worsened")
        self.assertIn("performance metrics", " ".join(result.reasons).lower())


def build_regression_service_fixture() -> RegressionService:
    return RegressionService(
        comparison_service=build_comparison_service_fixture(),
        performance_trend_service=_FakePerformanceTrendService(
            PerformanceTrendComparison(
                dimension="version",
                left_scope=ComparisonScope(
                    dimension="version",
                    value="1.0.0(100)",
                    label="version:1.0.0(100)",
                    filters={"version": "1.0.0(100)"},
                ),
                right_scope=ComparisonScope(
                    dimension="version",
                    value="2.0.0(200)",
                    label="version:2.0.0(200)",
                    filters={"version": "2.0.0(200)"},
                ),
                base_filters={"package_name": "com.example.app"},
                sample_summary={"left_session_count": 1, "right_session_count": 1},
                metric_change_summary={},
                comparability_notes=(),
                metrics=(
                    ComparedMetricTrend(
                        metric_key="cpu_usage",
                        label="CPU Usage",
                        unit="%",
                        higher_is_worse=True,
                        left_summary=MetricTrendSummary(
                            metric_key="cpu_usage",
                            label="CPU Usage",
                            unit="%",
                            sample_count=10,
                            session_count=1,
                            average=30.0,
                            peak=40.0,
                            p95=39.0,
                            latest=32.0,
                        ),
                        right_summary=MetricTrendSummary(
                            metric_key="cpu_usage",
                            label="CPU Usage",
                            unit="%",
                            sample_count=10,
                            session_count=1,
                            average=31.0,
                            peak=42.0,
                            p95=40.0,
                            latest=30.0,
                        ),
                        average_delta=1.0,
                        peak_delta=2.0,
                        p95_delta=1.0,
                        latest_delta=-2.0,
                        change_type="changed",
                    ),
                    ComparedMetricTrend(
                        metric_key="fps",
                        label="FPS",
                        unit="fps",
                        higher_is_worse=False,
                        left_summary=MetricTrendSummary(
                            metric_key="fps",
                            label="FPS",
                            unit="fps",
                            sample_count=10,
                            session_count=1,
                            average=55.0,
                            peak=60.0,
                            p95=59.0,
                            latest=56.0,
                        ),
                        right_summary=MetricTrendSummary(
                            metric_key="fps",
                            label="FPS",
                            unit="fps",
                            sample_count=10,
                            session_count=1,
                            average=58.0,
                            peak=62.0,
                            p95=61.0,
                            latest=57.0,
                        ),
                        average_delta=3.0,
                        peak_delta=2.0,
                        p95_delta=2.0,
                        latest_delta=1.0,
                        change_type="changed",
                    ),
                ),
            )
        ),
    )


class _FakeComparisonService:
    def __init__(self, result: ComparisonResult) -> None:
        self._result = result

    def compare_issues(self, **filters):
        return self._result


class _FakePerformanceTrendService:
    def __init__(self, result: PerformanceTrendComparison) -> None:
        self._result = result

    def compare_performance_trends(self, **filters):
        return self._result


if __name__ == "__main__":
    unittest.main()
