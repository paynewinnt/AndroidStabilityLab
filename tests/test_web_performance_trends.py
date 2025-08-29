from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.web.features.performance.metrics_cards import PerformanceMetricsCardsMixin
from stability.web.features.tasks.monitoring_payload import MonitoringPayloadMixin


class _FakeRunHistoryService:
    def __init__(self, detail: dict) -> None:
        self._detail = detail

    def list_runs(self, limit: int):
        return [{"run_id": self._detail["run_id"]}]

    def get_run_detail(self, run_id: str):
        if run_id != self._detail["run_id"]:
            raise LookupError(run_id)
        return self._detail


class _FakeBundle:
    def __init__(self, detail: dict) -> None:
        self.run_history_service = _FakeRunHistoryService(detail)


class _PayloadHarness(MonitoringPayloadMixin):
    def __init__(self, detail: dict) -> None:
        self._bundle = _FakeBundle(detail)


class _ChartHarness(PerformanceMetricsCardsMixin):
    @staticmethod
    def _notice(message: str, **_: object) -> str:
        return message

    @staticmethod
    def _artifact_links(_: str, __: list[tuple[str, object]]) -> str:
        return ""

    @staticmethod
    def _route_link(label: str, path: object) -> str:
        return f"{label}:{path}"


class WebPerformanceTrendTest(unittest.TestCase):
    def test_performance_snapshot_can_return_full_run_samples_without_entry_limit(self) -> None:
        with TemporaryDirectory() as tempdir:
            detail = self._build_detail(Path(tempdir), sample_count=5)
            payload = _PayloadHarness(detail)._recent_monitoring_snapshot(
                run_limit=1,
                entry_limit=1,
                max_run_window_seconds=24 * 60 * 60,
                limit_entries=False,
            )

        self.assertEqual(payload["summary"]["sample_count"], 5)
        self.assertEqual(len(payload["entries"]), 5)
        self.assertEqual({entry["run_id"] for entry in payload["entries"]}, {"run-full"})

    def test_performance_snapshot_caps_each_run_window(self) -> None:
        with TemporaryDirectory() as tempdir:
            detail = self._build_detail(
                Path(tempdir),
                timestamps=(
                    "2026-05-16T00:00:00",
                    "2026-05-16T00:00:30",
                    "2026-05-16T00:01:01",
                ),
            )
            payload = _PayloadHarness(detail)._recent_monitoring_snapshot(
                run_limit=1,
                entry_limit=10,
                max_run_window_seconds=60,
                limit_entries=False,
            )

        self.assertEqual(payload["summary"]["sample_count"], 2)
        self.assertEqual(len(payload["entries"]), 2)

    def test_metric_series_uses_all_chronological_samples(self) -> None:
        items = [
            {
                "captured_at": f"2026-05-16 18:{minute:02d}:00.000000",
                "sample_index": minute,
                "metrics": {"cpu_usage": minute},
            }
            for minute in range(20)
        ]

        series = _ChartHarness._performance_metric_series(list(reversed(items)), "cpu_usage")

        self.assertEqual(len(series), 20)
        self.assertEqual(series[0]["value"], 0)
        self.assertEqual(series[-1]["value"], 19)

    def test_solox_jank_frames_are_exposed_in_monitoring_payload(self) -> None:
        with TemporaryDirectory() as tempdir:
            monitoring_dir = Path(tempdir) / "monitoring"
            monitoring_dir.mkdir(parents=True)
            snapshot = {
                "timestamp": "2026-05-16T00:00:00",
                "system": {"battery_level": 80},
                "apps": [{"package_name": "com.example.app", "fps": 55, "jank_frames": 7}],
                "metadata": {"backend": "solox", "profile_name": "solox_perfetto"},
            }
            (monitoring_dir / "samples.json").write_text(json.dumps([snapshot]), encoding="utf-8")
            (monitoring_dir / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            detail = {
                "run_id": "run-jank",
                "run_status": "success",
                "created_at": "2026-05-16T00:00:00",
                "task_id": "task-jank",
                "task_name": "Jank Trend",
                "task": {"task_name": "Jank Trend", "template_type": "monkey", "package_name": "com.example.app"},
                "instances": [
                    {
                        "instance_id": "instance-jank",
                        "device_id": "device-1",
                        "status": "success",
                        "monitoring_snapshot_path": str(monitoring_dir / "snapshot.json"),
                    }
                ],
            }

            payload = _PayloadHarness(detail)._recent_monitoring_snapshot(
                run_limit=1,
                entry_limit=10,
                max_run_window_seconds=24 * 60 * 60,
                limit_entries=False,
            )

        entry = payload["entries"][0]
        self.assertEqual(entry["metrics"]["jank_frames"], 7)
        self.assertEqual(entry["app_packages"], ["com.example.app"])
        self.assertIn("jank_frames=7", entry["summary_line"])

    def test_chart_panel_renders_jank_frame_series(self) -> None:
        items = [
            {
                "captured_at": f"2026-05-16 18:00:{index:02d}.000000",
                "sample_index": index,
                "metrics": {"jank_frames": index + 1},
            }
            for index in range(3)
        ]

        html = _ChartHarness()._performance_chart_panel(items)

        self.assertIn("Jank Frames", html)
        self.assertIn(">3.0<", html)

    def test_task_panel_uses_latest_non_empty_metric_values(self) -> None:
        items = [
            {
                "run_id": "run-mixed",
                "task_id": "task-mixed",
                "task_name": "Mixed Backend",
                "package_name": "com.example.app",
                "captured_at": "2026-05-16 18:00:00.000000",
                "sample_index": 0,
                "backend": "solox",
                "metrics": {"gpu_p95_ms": 6, "memory_java": 120, "cpu_usage": 20},
            },
            {
                "run_id": "run-mixed",
                "task_id": "task-mixed",
                "task_name": "Mixed Backend",
                "package_name": "com.example.app",
                "captured_at": "2026-05-16 18:01:00.000000",
                "sample_index": 1,
                "backend": "perfetto",
                "metrics": {"gpu_p95_ms": None, "memory_java": None, "cpu_usage": 10, "perfetto_trace_size_bytes": 1024},
            },
        ]

        html = _ChartHarness()._performance_task_panels(items)

        self.assertIn("GPU P95", html)
        self.assertIn(">6.0<", html)
        self.assertIn("Java Heap", html)
        self.assertIn("Trace", html)

    def _build_detail(
        self,
        root: Path,
        *,
        sample_count: int | None = None,
        timestamps: tuple[str, ...] | None = None,
    ) -> dict:
        monitoring_dir = root / "monitoring"
        monitoring_dir.mkdir(parents=True)
        if timestamps is None:
            count = int(sample_count or 1)
            timestamps = tuple(f"2026-05-16T00:00:{index:02d}" for index in range(count))
        samples = [
            {
                "timestamp": timestamp,
                "system": {"cpu_usage": index},
                "apps": [{"app_package": "com.example.app", "memory_pss": 100 + index}],
                "metadata": {"backend": "adb_collector"},
            }
            for index, timestamp in enumerate(timestamps)
        ]
        (monitoring_dir / "samples.json").write_text(json.dumps(samples), encoding="utf-8")
        (monitoring_dir / "snapshot.json").write_text(json.dumps(samples[-1]), encoding="utf-8")
        return {
            "run_id": "run-full",
            "run_status": "success",
            "created_at": "2026-05-16T00:00:00",
            "started_at": "2026-05-16T00:00:00",
            "finished_at": "2026-05-16T00:05:00",
            "task_id": "task-full",
            "task_name": "Full Trend",
            "task": {
                "task_name": "Full Trend",
                "template_type": "monkey",
                "package_name": "com.example.app",
            },
            "instances": [
                {
                    "instance_id": "instance-full",
                    "device_id": "device-1",
                    "status": "success",
                    "monitoring_snapshot_path": str(monitoring_dir / "snapshot.json"),
                    "monitoring_trace_path": "",
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
