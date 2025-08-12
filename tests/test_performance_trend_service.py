from __future__ import annotations

from datetime import datetime
import unittest

from stability.app.performance_trend_service import PerformanceTrendService
from stability.domain import (
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    ExecutionInstance,
    ExecutionStatus,
    ExitReason,
    PerformanceRiskThresholdConfig,
    PerformanceRiskThresholdOverride,
    ResultLevel,
    TaskDefinition,
    TaskRun,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.repositories import InMemoryInstanceRepository, InMemoryRunRepository, InMemoryTaskRepository


class PerformanceTrendServiceTest(unittest.TestCase):
    def test_compare_versions_returns_metric_deltas(self) -> None:
        service = build_performance_trend_fixture()

        result = service.compare_performance_trends(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        self.assertEqual(result.dimension, "version")
        self.assertEqual(result.sample_summary["left_session_count"], 1)
        self.assertEqual(result.sample_summary["right_session_count"], 1)

        metrics = {item.metric_key: item for item in result.metrics}
        self.assertEqual(metrics["cpu_usage"].change_type, "worsened")
        self.assertEqual(metrics["cpu_usage"].left_summary.average, 20.0)
        self.assertEqual(metrics["cpu_usage"].right_summary.average, 40.0)
        self.assertEqual(metrics["cpu_usage"].right_summary.latest, 20.0)
        self.assertEqual(metrics["memory_pss"].change_type, "worsened")
        self.assertEqual(metrics["fps"].change_type, "improved")
        self.assertEqual(metrics["power_usage"].change_type, "worsened")
        self.assertEqual(result.metric_change_summary["worsened_count"], 3)
        self.assertEqual(result.metric_change_summary["improved_count"], 1)

    def test_compare_devices_marks_missing_side_as_insufficient_data(self) -> None:
        service = build_performance_trend_fixture()

        result = service.compare_performance_trends(
            dimension="device",
            left_value="device-a",
            right_value="device-c",
            template_type="monkey",
            version="1.0.0(100)",
            package_name="com.example.app",
        )

        self.assertEqual(result.sample_summary["left_session_count"], 1)
        self.assertEqual(result.sample_summary["right_session_count"], 0)
        self.assertTrue(
            any("no usable monitoring session data" in note for note in result.comparability_notes)
        )
        for metric in result.metrics:
            self.assertEqual(metric.change_type, "insufficient_data")

    def test_compare_versions_reports_oom_risk_for_high_memory_pss(self) -> None:
        service = build_performance_trend_fixture(
            right_app_rows=[
                {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "cpu_usage": 20.0, "memory_pss": 1100.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "cpu_usage": 22.0, "memory_pss": 1600.0},
            ]
        )

        result = service.compare_performance_trends(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        risks = {item.risk_key: item for item in result.performance_risk_items}
        self.assertIn("performance_oom_risk", risks)
        self.assertEqual(risks["performance_oom_risk"].details["right_peak_mb"], 1600.0)
        self.assertEqual(risks["performance_oom_risk"].details["threshold_source"], "default")
        self.assertEqual(risks["performance_oom_risk"].details["matched_scope"], {})
        self.assertEqual(risks["performance_oom_risk"].details["peak_threshold_mb"], 1536.0)
        self.assertEqual(result.metric_change_summary["performance_risk_count"], len(result.performance_risk_items))

    def test_compare_versions_applies_package_threshold_override_to_oom_risk(self) -> None:
        service = build_performance_trend_fixture(
            right_app_rows=[
                {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "cpu_usage": 20.0, "memory_pss": 820.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "cpu_usage": 22.0, "memory_pss": 900.0},
            ],
            risk_threshold_config=PerformanceRiskThresholdConfig(
                overrides=(
                    PerformanceRiskThresholdOverride(
                        package_name="com.example.app",
                        source="package:com.example.app",
                        oom_memory_pss_peak_mb=850.0,
                        oom_memory_pss_p95_mb=840.0,
                    ),
                )
            ),
        )

        result = service.compare_performance_trends(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        risks = {item.risk_key: item for item in result.performance_risk_items}
        self.assertIn("performance_oom_risk", risks)
        details = risks["performance_oom_risk"].details
        self.assertEqual(details["threshold_source"], "package:com.example.app")
        self.assertEqual(details["matched_scope"], {"package_name": "com.example.app"})
        self.assertEqual(details["peak_threshold_mb"], 850.0)
        self.assertEqual(details["p95_threshold_mb"], 840.0)
        self.assertEqual(details["threshold_values"]["oom_memory_pss_peak_mb"], 850.0)

    def test_compare_versions_reports_sustained_memory_growth(self) -> None:
        service = build_performance_trend_fixture(
            right_app_rows=[
                {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "cpu_usage": 20.0, "memory_pss": 400.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "cpu_usage": 22.0, "memory_pss": 430.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 3), "cpu_usage": 24.0, "memory_pss": 520.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 4), "cpu_usage": 23.0, "memory_pss": 610.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 5), "cpu_usage": 25.0, "memory_pss": 700.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 6), "cpu_usage": 21.0, "memory_pss": 760.0},
            ]
        )

        result = service.compare_performance_trends(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        risks = {item.risk_key: item for item in result.performance_risk_items}
        self.assertIn("performance_memory_growth", risks)
        self.assertGreaterEqual(risks["performance_memory_growth"].details["growth_delta_mb"], 128.0)
        self.assertGreaterEqual(risks["performance_memory_growth"].details["growth_ratio"], 0.2)
        self.assertEqual(risks["performance_memory_growth"].details["threshold_source"], "default")

    def test_compare_versions_reports_frame_jank_regression(self) -> None:
        service = build_performance_trend_fixture(
            left_fps_rows=[
                {"timestamp": datetime(2025, 7, 20, 10, 0, 1), "fps": 58.0, "frame_time_ms": 16.0},
                {"timestamp": datetime(2025, 7, 20, 10, 0, 2), "fps": 56.0, "frame_time_ms": 18.0},
                {"timestamp": datetime(2025, 7, 20, 10, 0, 3), "fps": 55.0, "frame_time_ms": 20.0},
            ],
            right_fps_rows=[
                {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "fps": 38.0, "frame_time_ms": 30.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "fps": 35.0, "frame_time_ms": 34.0},
                {"timestamp": datetime(2025, 7, 20, 11, 0, 3), "fps": 32.0, "frame_time_ms": 40.0},
            ],
        )

        result = service.compare_performance_trends(
            dimension="version",
            left_value="1.0.0(100)",
            right_value="2.0.0(200)",
            template_type="monkey",
            package_name="com.example.app",
        )

        risks = {item.risk_key: item for item in result.performance_risk_items}
        self.assertIn("performance_frame_jank_regression", risks)
        self.assertEqual(risks["performance_frame_jank_regression"].details["metric_key"], "frame_time_ms")
        self.assertGreater(risks["performance_frame_jank_regression"].details["p95_delta_ms"], 8.0)
        self.assertEqual(risks["performance_frame_jank_regression"].details["threshold_source"], "default")


class _FakeMonitoringDataProvider:
    def __init__(self, payloads: dict[int, dict]):
        self._payloads = payloads

    def get_monitoring_data(
        self,
        session_id: int,
        start_time=None,
        end_time=None,
        data_types=None,
        package_names=None,
    ) -> dict:
        return self._payloads.get(session_id, {})


def build_performance_trend_fixture(
    *,
    left_app_rows: list[dict] | None = None,
    right_app_rows: list[dict] | None = None,
    left_fps_rows: list[dict] | None = None,
    right_fps_rows: list[dict] | None = None,
    risk_threshold_config: PerformanceRiskThresholdConfig | None = None,
) -> PerformanceTrendService:
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()

    task_monkey_v1 = TaskDefinition(
        task_id="task-monkey-v1",
        task_name="Monkey V1",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(
            package_name="com.example.app",
            version_name="1.0.0",
            version_code="100",
        ),
    )
    task_monkey_v2 = TaskDefinition(
        task_id="task-monkey-v2",
        task_name="Monkey V2",
        template_type=TaskTemplateType.MONKEY,
        target_app=TaskTargetApp(
            package_name="com.example.app",
            version_name="2.0.0",
            version_code="200",
        ),
    )
    for task in (task_monkey_v1, task_monkey_v2):
        task_repository.add(task)

    run_v1 = TaskRun(
        run_id="run-v1",
        task_definition_id=task_monkey_v1.task_id,
        task_name=task_monkey_v1.task_name,
        status=TaskRunStatus.SUCCESS,
        created_at=datetime(2025, 7, 20, 10, 0, 0),
    )
    run_v2 = TaskRun(
        run_id="run-v2",
        task_definition_id=task_monkey_v2.task_id,
        task_name=task_monkey_v2.task_name,
        status=TaskRunStatus.SUCCESS,
        created_at=datetime(2025, 7, 20, 11, 0, 0),
    )
    run_repository.add(run_v1)
    run_repository.add(run_v2)

    instance_repository.add_many(
        [
            ExecutionInstance(
                instance_id="instance-v1",
                run_id=run_v1.run_id,
                task_definition_id=task_monkey_v1.task_id,
                device_id="device-a",
                device_snapshot=_device("device-a"),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.SUCCESS,
                exit_reason=ExitReason.COMPLETED,
                result_level=ResultLevel.PASSED,
                monitoring_session_id="101",
            ),
            ExecutionInstance(
                instance_id="instance-v2",
                run_id=run_v2.run_id,
                task_definition_id=task_monkey_v2.task_id,
                device_id="device-b",
                device_snapshot=_device("device-b"),
                template_type=TaskTemplateType.MONKEY,
                target_app_package="com.example.app",
                status=ExecutionStatus.SUCCESS,
                exit_reason=ExitReason.COMPLETED,
                result_level=ResultLevel.PASSED,
                monitoring_session_id="202",
            ),
        ]
    )

    left_app_rows = left_app_rows or [
        {"timestamp": datetime(2025, 7, 20, 10, 0, 1), "cpu_usage": 10.0, "memory_pss": 100.0},
        {"timestamp": datetime(2025, 7, 20, 10, 0, 2), "cpu_usage": 30.0, "memory_pss": 120.0},
    ]
    right_app_rows = right_app_rows or [
        {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "cpu_usage": 60.0, "memory_pss": 130.0},
        {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "cpu_usage": 20.0, "memory_pss": 150.0},
    ]
    left_fps_rows = left_fps_rows or [
        {"timestamp": datetime(2025, 7, 20, 10, 0, 1), "fps": 45.0},
        {"timestamp": datetime(2025, 7, 20, 10, 0, 2), "fps": 55.0},
    ]
    right_fps_rows = right_fps_rows or [
        {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "fps": 58.0},
        {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "fps": 62.0},
    ]

    provider = _FakeMonitoringDataProvider(
        {
            101: {
                "app_performance": {
                    "com.example.app": left_app_rows
                },
                "fps_data": {
                    "com.example.app": left_fps_rows
                },
                "power_consumption": {
                    "com.example.app": [
                        {"timestamp": datetime(2025, 7, 20, 10, 0, 1), "power_usage": 5.0},
                        {"timestamp": datetime(2025, 7, 20, 10, 0, 2), "power_usage": 7.0},
                    ]
                },
            },
            202: {
                "app_performance": {
                    "com.example.app": right_app_rows
                },
                "fps_data": {
                    "com.example.app": right_fps_rows
                },
                "power_consumption": {
                    "com.example.app": [
                        {"timestamp": datetime(2025, 7, 20, 11, 0, 1), "power_usage": 8.0},
                        {"timestamp": datetime(2025, 7, 20, 11, 0, 2), "power_usage": 9.0},
                    ]
                },
            },
        }
    )

    return PerformanceTrendService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        monitoring_data_provider=provider,
        risk_threshold_config=risk_threshold_config,
    )


def _device(device_id: str) -> Device:
    return Device(
        device_id=device_id,
        serial=device_id,
        connection_state=DeviceConnectionState.ONLINE,
        availability_state=DeviceAvailabilityState.IDLE,
    )


if __name__ == "__main__":
    unittest.main()
