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
        filters = self._admin_list_filters(query, default_page_size=20)
        entry_limit = _entry_limit_override if _entry_limit_override is not None else self._int_query(query, "limit", default=200)
        run_limit = max(entry_limit * 2, self._int_query(query, "run_limit", default=30))
        requested_hours = self._int_query(query, "window_hours", default=24)
        window_hours = min(max(requested_hours, 1), 24)
        snapshot = self._recent_monitoring_snapshot(
            run_limit=run_limit,
            entry_limit=entry_limit,
            max_run_window_seconds=min(window_hours * 60 * 60, MAX_PERFORMANCE_RUN_WINDOW_SECONDS),
            limit_entries=False,
        )
        entries = [item for item in list(snapshot.get("entries", []) or []) if self._performance_entry_matches_filters(item, filters)]
        paged_entries = self._page_slice(entries, page=int(filters["page"]), page_size=int(filters["page_size"]))
        return {
            "page": "performance",
            "title": "性能采样",
            "generated_at": _generated_at_now(),
            "filters": {
                **filters,
                "limit": entry_limit,
                "run_limit": run_limit,
                "window_hours": window_hours,
            },
            "pagination": {
                "page": int(filters["page"]),
                "page_size": int(filters["page_size"]),
                "total": len(entries),
            },
            "risk_detail_fields": self._performance_risk_detail_fields(),
            "summary": self._performance_entries_summary(entries),
            "entries": paged_entries,
            "all_entries": entries,
        }

    @classmethod
    def _performance_entry_matches_filters(cls, entry: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        keyword = str(filters.get("keyword", "") or "").lower()
        if keyword:
            haystack = " ".join(
                str(value or "")
                for value in (
                    entry.get("run_id", ""),
                    entry.get("task_id", ""),
                    entry.get("task_name", ""),
                    entry.get("package_name", ""),
                    entry.get("template_type", ""),
                    entry.get("run_status", ""),
                    entry.get("instance_status", ""),
                    entry.get("backend", ""),
                    entry.get("device_id", ""),
                )
            ).lower()
            if keyword not in haystack:
                return False
        status = str(filters.get("status", "") or "").lower()
        if status and status not in {
            str(entry.get("run_status", "") or "").lower(),
            str(entry.get("instance_status", "") or "").lower(),
        }:
            return False
        package_name = str(filters.get("package_name", "") or "").lower()
        if package_name and package_name not in str(entry.get("package_name", "") or "").lower():
            return False
        scenario = str(filters.get("scenario", "") or "").lower()
        if scenario and scenario != str(entry.get("template_type", "") or "").lower():
            return False
        device_id = str(filters.get("device_id", "") or "").lower()
        if device_id and device_id not in str(entry.get("device_id", "") or "").lower():
            return False
        backend = str(filters.get("backend", "") or "").lower()
        if backend and backend != str(entry.get("backend", "") or "").lower():
            return False
        return cls._created_at_in_range(str(entry.get("captured_at", "") or entry.get("run_created_at", "") or ""), filters)

    @staticmethod
    def _performance_entries_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
        backend_counts: dict[str, int] = {}
        monitored_run_ids: set[str] = set()
        trace_count = 0
        latest_sample_at = ""
        for entry in entries:
            run_id = str(entry.get("run_id", "") or "")
            if run_id:
                monitored_run_ids.add(run_id)
            backend = str(entry.get("backend", "") or "unknown")
            backend_counts[backend] = backend_counts.get(backend, 0) + 1
            if bool(entry.get("trace_available", False)):
                trace_count += 1
            captured_at = str(entry.get("captured_at", "") or "")
            if captured_at and (not latest_sample_at or captured_at > latest_sample_at):
                latest_sample_at = captured_at
        return {
            "sample_count": len(entries),
            "monitored_run_count": len(monitored_run_ids),
            "trace_count": trace_count,
            "backend_counts": dict(sorted(backend_counts.items())),
            "latest_sample_at": latest_sample_at,
        }


__all__ = ["PerformancePayloadMixin"]
