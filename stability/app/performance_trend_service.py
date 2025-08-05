from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, Sequence

from stability.domain import (
    ComparedMetricTrend,
    ComparisonScope,
    MetricTrendSummary,
    PerformanceRiskThresholdConfig,
    PerformanceRiskThresholdMatch,
    PerformanceTrendComparison,
    QualityGateRiskItem,
)


class TaskDefinitionLike(Protocol):
    task_id: str
    task_name: str
    template_type: object
    target_app: object


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskDefinitionLike]:
        ...


class TaskRunLike(Protocol):
    run_id: str
    task_definition_id: str
    run_status: str
    created_at: datetime | None


class RunRepository(Protocol):
    def list(self) -> Sequence[TaskRunLike]:
        ...


class ExecutionInstanceLike(Protocol):
    instance_id: str
    run_id: str
    task_definition_id: str
    device_id: str
    template_type: object
    target_app_package: str
    monitoring_session_id: str | None


class InstanceRepository(Protocol):
    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstanceLike]:
        ...


class MonitoringDataProvider(Protocol):
    def get_monitoring_data(
        self,
        session_id: int,
        start_time=None,
        end_time=None,
        data_types=None,
        package_names=None,
    ) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class PerformanceTrendQuery:
    dimension: str
    left_value: str
    right_value: str
    task_id: str = ""
    run_status: str = ""
    template_type: str = ""
    version: str = ""
    package_name: str = ""
    created_from: str = ""
    created_to: str = ""


@dataclass(frozen=True)
class _MetricSpec:
    key: str
    label: str
    unit: str
    higher_is_worse: bool


class PerformanceTrendService:
    """Minimal V2 performance trend comparison on top of monitoring sessions."""

    _DIMENSIONS = {"version", "device", "scenario"}
    _METRICS = (
        _MetricSpec("cpu_usage", "CPU Usage", "%", True),
        _MetricSpec("memory_pss", "Memory PSS", "MB", True),
        _MetricSpec("fps", "FPS", "fps", False),
        _MetricSpec("power_usage", "Power Usage", "raw", True),
    )

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
        monitoring_data_provider: MonitoringDataProvider,
        risk_threshold_config: PerformanceRiskThresholdConfig | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._monitoring_data_provider = monitoring_data_provider
        self._risk_threshold_config = risk_threshold_config or PerformanceRiskThresholdConfig()

    def compare_performance_trends(self, **filters: Any) -> PerformanceTrendComparison:
        query = self._build_query(filters)
        left_scope_filters = self._scope_filters(query, side="left")
        right_scope_filters = self._scope_filters(query, side="right")

        left_records = self._collect_metric_values(left_scope_filters)
        right_records = self._collect_metric_values(right_scope_filters)
        metrics = [self._compare_metric(spec, left_records, right_records) for spec in self._METRICS]
        performance_risk_items = self._performance_risk_items(
            query=query,
            left_records=left_records,
            right_records=right_records,
            metrics=metrics,
        )

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
        return PerformanceTrendComparison(
            dimension=query.dimension,
            left_scope=left_scope,
            right_scope=right_scope,
            base_filters=self._base_filter_payload(query),
            sample_summary=self._sample_summary(left_records, right_records),
            metric_change_summary={
                **self._metric_change_summary(metrics),
                "performance_risk_count": len(performance_risk_items),
            },
            comparability_notes=self._comparability_notes(query, left_records, right_records),
            performance_risk_items=tuple(performance_risk_items),
            metrics=tuple(metrics),
        )

    @classmethod
    def _build_query(cls, filters: Mapping[str, Any]) -> PerformanceTrendQuery:
        dimension = str(filters.get("dimension", "") or "").strip()
        if dimension not in cls._DIMENSIONS:
            raise ValueError(
                f"Unsupported performance comparison dimension '{dimension}'. "
                f"Expected one of: {', '.join(sorted(cls._DIMENSIONS))}."
            )
        left_value = str(filters.get("left_value", "") or "").strip()
        right_value = str(filters.get("right_value", "") or "").strip()
        if not left_value or not right_value:
            raise ValueError("Both left_value and right_value are required for performance comparison.")
        return PerformanceTrendQuery(
            dimension=dimension,
            left_value=left_value,
            right_value=right_value,
            task_id=str(filters.get("task_id", "") or ""),
            run_status=str(filters.get("run_status", "") or ""),
            template_type=str(filters.get("template_type", "") or ""),
            version=str(filters.get("version", "") or ""),
            package_name=str(filters.get("package_name", "") or ""),
            created_from=str(filters.get("created_from", "") or ""),
            created_to=str(filters.get("created_to", "") or ""),
        )

    @classmethod
    def _scope_filters(cls, query: PerformanceTrendQuery, *, side: str) -> dict[str, Any]:
        filters: dict[str, Any] = {
            "task_id": query.task_id,
            "run_status": query.run_status,
            "package_name": query.package_name,
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
        else:
            filters["template_type"] = scope_value
        return filters

    @classmethod
    def _scope_label(cls, dimension: str, value: str) -> str:
        if dimension == "scenario":
            return f"scenario:{value}"
        if dimension == "device":
            return f"device:{value}"
        return f"version:{value}"

    @classmethod
    def _base_filter_payload(cls, query: PerformanceTrendQuery) -> dict[str, Any]:
        payload = {
            "task_id": query.task_id or None,
            "run_status": query.run_status or None,
            "package_name": query.package_name or None,
            "created_from": query.created_from or None,
            "created_to": query.created_to or None,
        }
        if query.dimension != "scenario":
            payload["template_type"] = query.template_type or None
        if query.dimension != "version":
            payload["version"] = query.version or None
        return payload

    def _collect_metric_values(self, filters: Mapping[str, Any]) -> dict[str, Any]:
        created_from = self._parse_iso_datetime(str(filters.get("created_from", "") or ""))
        created_to = self._parse_iso_datetime(str(filters.get("created_to", "") or ""))
        session_ids: list[int] = []
        package_names: set[str] = set()
        for run in self._run_repository.list():
            if filters.get("task_id") and getattr(run, "task_definition_id", "") != filters["task_id"]:
                continue
            if filters.get("run_status") and getattr(run, "run_status", "") != filters["run_status"]:
                continue
            created_at = getattr(run, "created_at", None)
            if created_from is not None and (created_at or datetime.min) < created_from:
                continue
            if created_to is not None and (created_at or datetime.min) > created_to:
                continue
            task = self._task_repository.get(getattr(run, "task_definition_id", "") or "")
            if task is None:
                continue
            task_template_type = self._task_template_type(task)
            task_version = self._task_version_key(task)
            task_package = self._task_package_name(task)
            if filters.get("template_type") and task_template_type != filters["template_type"]:
                continue
            if filters.get("version") and task_version != filters["version"]:
                continue
            if filters.get("package_name") and task_package != filters["package_name"]:
                continue

            for instance in self._instance_repository.list_by_run(getattr(run, "run_id", "") or ""):
                if filters.get("device_id") and getattr(instance, "device_id", "") != filters["device_id"]:
                    continue
                session_raw = getattr(instance, "monitoring_session_id", "") or ""
                if str(session_raw).isdigit():
                    session_ids.append(int(str(session_raw)))
                    package_names.add(task_package or getattr(instance, "target_app_package", "") or "")

        metrics: dict[str, list[tuple[datetime | None, float]]] = {spec.key: [] for spec in self._METRICS}
        metrics["frame_time_ms"] = []
        active_sessions = 0
        for session_id in sorted(set(session_ids)):
            data = self._monitoring_data_provider.get_monitoring_data(
                session_id,
                data_types=["apps", "fps", "power"],
                package_names=sorted(item for item in package_names if item),
            )
            if not data:
                continue
            active_sessions += 1
            app_performance = dict(data.get("app_performance", {}) or {})
            fps_data = dict(data.get("fps_data", {}) or {})
            power_data = dict(data.get("power_consumption", {}) or {})
            for package_name in package_names:
                for row in app_performance.get(package_name, []) or []:
                    self._append_metric(metrics["cpu_usage"], row.get("timestamp"), row.get("cpu_usage"))
                    self._append_metric(metrics["memory_pss"], row.get("timestamp"), row.get("memory_pss"))
                for row in fps_data.get(package_name, []) or []:
                    self._append_metric(metrics["fps"], row.get("timestamp"), row.get("fps"))
                    self._append_metric(
                        metrics["frame_time_ms"],
                        row.get("timestamp"),
                        row.get("frame_time_ms", row.get("frame_time")),
                    )
                for row in power_data.get(package_name, []) or []:
                    self._append_metric(metrics["power_usage"], row.get("timestamp"), row.get("power_usage"))
        return {
            "session_count": active_sessions,
            "requested_session_count": len(set(session_ids)),
            "metrics": metrics,
        }

    @classmethod
    def _compare_metric(
        cls,
        spec: _MetricSpec,
        left_records: Mapping[str, Any],
        right_records: Mapping[str, Any],
    ) -> ComparedMetricTrend:
        left_summary = cls._metric_summary(spec, left_records)
        right_summary = cls._metric_summary(spec, right_records)
        average_delta = cls._delta(left_summary.average, right_summary.average)
        peak_delta = cls._delta(left_summary.peak, right_summary.peak)
        p95_delta = cls._delta(left_summary.p95, right_summary.p95)
        latest_delta = cls._delta(left_summary.latest, right_summary.latest)
        change_type = cls._change_type(spec, average_delta, left_summary, right_summary)
        return ComparedMetricTrend(
            metric_key=spec.key,
            label=spec.label,
            unit=spec.unit,
            higher_is_worse=spec.higher_is_worse,
            left_summary=left_summary,
            right_summary=right_summary,
            average_delta=average_delta,
            peak_delta=peak_delta,
            p95_delta=p95_delta,
            latest_delta=latest_delta,
            change_type=change_type,
        )

    @classmethod
    def _metric_summary(cls, spec: _MetricSpec, records: Mapping[str, Any]) -> MetricTrendSummary:
        points = list(records.get("metrics", {}).get(spec.key, []) or [])
        values = [value for _, value in points]
        sorted_values = sorted(values)
        sample_count = len(values)
        latest = cls._latest_point_value(points)
        return MetricTrendSummary(
            metric_key=spec.key,
            label=spec.label,
            unit=spec.unit,
            sample_count=sample_count,
            session_count=int(records.get("session_count", 0) or 0),
            average=cls._round(sum(sorted_values) / sample_count) if sample_count else None,
            peak=cls._round(max(sorted_values)) if sample_count else None,
            p95=cls._round(cls._percentile(sorted_values, 0.95)) if sample_count else None,
            latest=cls._round(latest) if latest is not None else None,
        )

    @classmethod
    def _change_type(
        cls,
        spec: _MetricSpec,
        average_delta: float | None,
        left_summary: MetricTrendSummary,
        right_summary: MetricTrendSummary,
    ) -> str:
        if left_summary.sample_count == 0 or right_summary.sample_count == 0:
            return "insufficient_data"
        if average_delta is None or abs(average_delta) < 0.01:
            return "unchanged"
        if spec.higher_is_worse:
            return "worsened" if average_delta > 0 else "improved"
        return "improved" if average_delta > 0 else "worsened"

    @classmethod
    def _sample_summary(cls, left_records: Mapping[str, Any], right_records: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "left_session_count": int(left_records.get("session_count", 0) or 0),
            "right_session_count": int(right_records.get("session_count", 0) or 0),
            "left_requested_session_count": int(left_records.get("requested_session_count", 0) or 0),
            "right_requested_session_count": int(right_records.get("requested_session_count", 0) or 0),
        }

    @classmethod
    def _metric_change_summary(cls, metrics: Sequence[ComparedMetricTrend]) -> dict[str, Any]:
        summary = {
            "worsened_count": 0,
            "improved_count": 0,
            "unchanged_count": 0,
            "insufficient_data_count": 0,
        }
        for metric in metrics:
            key = f"{metric.change_type}_count"
            summary[key] = summary.get(key, 0) + 1
        return summary

    @classmethod
    def _comparability_notes(
        cls,
        query: PerformanceTrendQuery,
        left_records: Mapping[str, Any],
        right_records: Mapping[str, Any],
    ) -> tuple[str, ...]:
        notes = [
            "Performance trend comparison is based on persisted monitoring sessions linked from execution instances.",
            "Current metrics cover CPU, memory PSS, FPS, and power usage from app-level monitoring samples.",
        ]
        if query.dimension == "version":
            notes.append("Version comparison currently uses task target-app version_name/version_code snapshots.")
        elif query.dimension == "device":
            notes.append("Device comparison currently operates on single device_id scopes, not persisted device groups.")
        else:
            notes.append("Scenario comparison currently maps scenario scope to task template_type.")
        if int(left_records.get("session_count", 0) or 0) == 0 or int(right_records.get("session_count", 0) or 0) == 0:
            notes.append("One comparison side has no usable monitoring session data under the current filters.")
        return tuple(notes)

    def _performance_risk_items(
        self,
        *,
        query: PerformanceTrendQuery,
        left_records: Mapping[str, Any],
        right_records: Mapping[str, Any],
        metrics: Sequence[ComparedMetricTrend],
    ) -> list[QualityGateRiskItem]:
        items: list[QualityGateRiskItem] = []
        metric_by_key = {item.metric_key: item for item in metrics}
        memory = metric_by_key.get("memory_pss")
        fps = metric_by_key.get("fps")
        threshold_match = self._risk_threshold_match(query)

        oom_item = self._oom_risk_item(query=query, memory=memory, threshold_match=threshold_match)
        if oom_item is not None:
            items.append(oom_item)

        growth_item = self._memory_growth_item(
            query=query,
            records=right_records,
            memory=memory,
            threshold_match=threshold_match,
        )
        if growth_item is not None:
            items.append(growth_item)

        jank_item = self._frame_jank_regression_item(
            query=query,
            left_records=left_records,
            right_records=right_records,
            fps=fps,
            threshold_match=threshold_match,
        )
        if jank_item is not None:
            items.append(jank_item)
        return items

    def _risk_threshold_match(self, query: PerformanceTrendQuery) -> PerformanceRiskThresholdMatch:
        scenario = query.right_value if query.dimension == "scenario" else ""
        template_type = scenario or query.template_type
        context = {
            "package_name": query.package_name,
            "device_id": query.right_value if query.dimension == "device" else "",
            "scenario": scenario,
            "template_type": template_type,
        }
        return self._risk_threshold_config.resolve(context)

    @classmethod
    def _threshold_detail_payload(cls, threshold_match: PerformanceRiskThresholdMatch) -> dict[str, Any]:
        return {
            "threshold_source": threshold_match.threshold_source,
            "matched_scope": dict(threshold_match.matched_scope),
            "threshold_values": threshold_match.values.as_details(),
        }

    def _oom_risk_item(
        self,
        *,
        query: PerformanceTrendQuery,
        memory: ComparedMetricTrend | None,
        threshold_match: PerformanceRiskThresholdMatch,
    ) -> QualityGateRiskItem | None:
        if memory is None or memory.right_summary.sample_count == 0:
            return None
        thresholds = threshold_match.values
        peak = memory.right_summary.peak
        p95 = memory.right_summary.p95
        if (
            (peak or 0.0) < thresholds.oom_memory_pss_peak_mb
            and (p95 or 0.0) < thresholds.oom_memory_pss_p95_mb
        ):
            return None
        severity = "high" if (peak or 0.0) >= thresholds.oom_memory_pss_peak_mb else "medium"
        return QualityGateRiskItem(
            risk_key="performance_oom_risk",
            category="performance",
            severity=severity,
            summary=f"Memory PSS in {query.right_value} is close to OOM-risk territory.",
            details={
                "metric_key": "memory_pss",
                "right_peak_mb": peak,
                "right_p95_mb": p95,
                "peak_threshold_mb": thresholds.oom_memory_pss_peak_mb,
                "p95_threshold_mb": thresholds.oom_memory_pss_p95_mb,
                "right_sample_count": memory.right_summary.sample_count,
                **self._threshold_detail_payload(threshold_match),
            },
            source="performance_trend_service.compare_performance_trends",
            blocks_admission=False,
        )

    @classmethod
    def _memory_growth_item(
        cls,
        *,
        query: PerformanceTrendQuery,
        records: Mapping[str, Any],
        memory: ComparedMetricTrend | None,
        threshold_match: PerformanceRiskThresholdMatch,
    ) -> QualityGateRiskItem | None:
        thresholds = threshold_match.values
        points = cls._sorted_metric_points(records, "memory_pss")
        if len(points) < 4:
            return None
        window_size = max(2, min(5, len(points) // 3))
        start_average = cls._average(value for _, value in points[:window_size])
        end_average = cls._average(value for _, value in points[-window_size:])
        if start_average is None or end_average is None or start_average <= 0:
            return None
        growth_delta = end_average - start_average
        growth_ratio = growth_delta / start_average
        if (
            growth_delta < thresholds.memory_growth_min_delta_mb
            or growth_ratio < thresholds.memory_growth_min_ratio
        ):
            return None
        return QualityGateRiskItem(
            risk_key="performance_memory_growth",
            category="performance",
            severity="high" if growth_ratio >= 0.5 else "medium",
            summary=f"Memory PSS in {query.right_value} shows sustained growth across the sampled window.",
            details={
                "metric_key": "memory_pss",
                "start_window_average_mb": cls._round(start_average),
                "end_window_average_mb": cls._round(end_average),
                "growth_delta_mb": cls._round(growth_delta),
                "growth_ratio": cls._round(growth_ratio),
                "min_growth_delta_mb": thresholds.memory_growth_min_delta_mb,
                "min_growth_ratio": thresholds.memory_growth_min_ratio,
                "right_p95_mb": getattr(getattr(memory, "right_summary", None), "p95", None),
                "right_sample_count": len(points),
                **cls._threshold_detail_payload(threshold_match),
            },
            source="performance_trend_service.compare_performance_trends",
            blocks_admission=False,
        )

    @classmethod
    def _frame_jank_regression_item(
        cls,
        *,
        query: PerformanceTrendQuery,
        left_records: Mapping[str, Any],
        right_records: Mapping[str, Any],
        fps: ComparedMetricTrend | None,
        threshold_match: PerformanceRiskThresholdMatch,
    ) -> QualityGateRiskItem | None:
        thresholds = threshold_match.values
        left_frame_p95 = cls._metric_p95(left_records, "frame_time_ms")
        right_frame_p95 = cls._metric_p95(right_records, "frame_time_ms")
        if left_frame_p95 is not None and right_frame_p95 is not None and left_frame_p95 > 0:
            p95_delta = right_frame_p95 - left_frame_p95
            p95_ratio = p95_delta / left_frame_p95
            if (
                p95_delta >= thresholds.frame_time_p95_delta_ms
                and p95_ratio >= thresholds.frame_time_p95_delta_ratio
            ):
                return QualityGateRiskItem(
                    risk_key="performance_frame_jank_regression",
                    category="performance",
                    severity="high" if p95_ratio >= 0.5 else "medium",
                    summary=f"Frame time P95 in {query.right_value} regressed versus {query.left_value}.",
                    details={
                        "metric_key": "frame_time_ms",
                        "left_p95_ms": cls._round(left_frame_p95),
                        "right_p95_ms": cls._round(right_frame_p95),
                        "p95_delta_ms": cls._round(p95_delta),
                        "p95_delta_ratio": cls._round(p95_ratio),
                        "min_p95_delta_ms": thresholds.frame_time_p95_delta_ms,
                        "min_p95_delta_ratio": thresholds.frame_time_p95_delta_ratio,
                        **cls._threshold_detail_payload(threshold_match),
                    },
                    source="performance_trend_service.compare_performance_trends",
                    blocks_admission=False,
                )

        if fps is None or fps.left_summary.average in (None, 0) or fps.right_summary.average is None:
            return None
        fps_drop = fps.left_summary.average - fps.right_summary.average
        fps_drop_ratio = fps_drop / fps.left_summary.average
        if fps_drop_ratio < thresholds.fps_drop_ratio:
            return None
        return QualityGateRiskItem(
            risk_key="performance_frame_jank_regression",
            category="performance",
            severity="high" if fps_drop_ratio >= 0.3 else "medium",
            summary=f"FPS in {query.right_value} dropped enough to indicate frame/jank regression.",
            details={
                "metric_key": "fps",
                "left_average_fps": fps.left_summary.average,
                "right_average_fps": fps.right_summary.average,
                "average_delta_fps": fps.average_delta,
                "fps_drop_ratio": cls._round(fps_drop_ratio),
                "min_fps_drop_ratio": thresholds.fps_drop_ratio,
                **cls._threshold_detail_payload(threshold_match),
            },
            source="performance_trend_service.compare_performance_trends",
            blocks_admission=False,
        )

    @staticmethod
    def _parse_iso_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        return datetime.fromisoformat(raw)

    @staticmethod
    def _task_template_type(task: TaskDefinitionLike) -> str:
        template_type = getattr(task, "template_type", "")
        return str(getattr(template_type, "value", template_type) or "")

    @staticmethod
    def _task_package_name(task: TaskDefinitionLike) -> str:
        target_app = getattr(task, "target_app", None)
        return str(getattr(target_app, "package_name", "") or "")

    @staticmethod
    def _task_version_key(task: TaskDefinitionLike) -> str:
        target_app = getattr(task, "target_app", None)
        version_name = str(getattr(target_app, "version_name", "") or "")
        version_code = str(getattr(target_app, "version_code", "") or "")
        if version_name and version_code:
            return f"{version_name}({version_code})"
        return version_name or version_code

    @staticmethod
    def _append_metric(bucket: list[tuple[datetime | None, float]], timestamp: Any, value: Any) -> None:
        if value is None:
            return
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        if math.isnan(numeric):
            return
        point_time = timestamp if isinstance(timestamp, datetime) else None
        bucket.append((point_time, numeric))

    @staticmethod
    def _sorted_metric_points(records: Mapping[str, Any], metric_key: str) -> list[tuple[datetime | None, float]]:
        points = list(records.get("metrics", {}).get(metric_key, []) or [])
        return [
            point
            for _, point in sorted(
                enumerate(points),
                key=lambda item: (item[1][0] or datetime.min, item[0]),
            )
        ]

    @classmethod
    def _metric_p95(cls, records: Mapping[str, Any], metric_key: str) -> float | None:
        values = sorted(value for _, value in list(records.get("metrics", {}).get(metric_key, []) or []))
        if not values:
            return None
        return cls._percentile(values, 0.95)

    @staticmethod
    def _average(values: Sequence[float]) -> float | None:
        items = list(values)
        if not items:
            return None
        return sum(items) / len(items)

    @staticmethod
    def _latest_point_value(points: Sequence[tuple[datetime | None, float]]) -> float | None:
        if not points:
            return None
        latest_point = max(
            enumerate(points),
            key=lambda item: (item[1][0] or datetime.min, item[0]),
        )[1]
        return latest_point[1]

    @staticmethod
    def _percentile(values: Sequence[float], quantile: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        index = (len(values) - 1) * quantile
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return values[int(index)]
        fraction = index - lower
        return values[lower] * (1.0 - fraction) + values[upper] * fraction

    @staticmethod
    def _round(value: float | None) -> float | None:
        if value is None:
            return None
        return round(float(value), 2)

    @staticmethod
    def _delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return round(right - left, 2)
