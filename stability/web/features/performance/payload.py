from __future__ import annotations

from typing import Any, Mapping

from stability.time_utils import now_beijing_string

from ..tasks.monitoring_payload import MAX_PERFORMANCE_RUN_WINDOW_SECONDS, MonitoringPayloadMixin


def _generated_at_now() -> str:
    return now_beijing_string()


class PerformancePayloadMixin(MonitoringPayloadMixin):
    def _performance_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
        _entry_limit_override: int | None = None,
    ) -> dict[str, Any]:
        del request_context
        entry_limit = _entry_limit_override if _entry_limit_override is not None else self._int_query(query, "limit", default=20)
        run_limit = max(entry_limit * 2, self._int_query(query, "run_limit", default=30))
        requested_hours = self._int_query(query, "window_hours", default=24)
        window_hours = min(max(requested_hours, 1), 24)
        snapshot = self._recent_monitoring_snapshot(
            run_limit=run_limit,
            entry_limit=entry_limit,
            max_run_window_seconds=min(window_hours * 60 * 60, MAX_PERFORMANCE_RUN_WINDOW_SECONDS),
            limit_entries=False,
        )
        return {
            "page": "performance",
            "title": "性能采样",
            "generated_at": _generated_at_now(),
            "filters": {
                "limit": entry_limit,
                "run_limit": run_limit,
                "window_hours": window_hours,
            },
            "risk_detail_fields": self._performance_risk_detail_fields(),
            **snapshot,
        }


__all__ = ["PerformancePayloadMixin"]
