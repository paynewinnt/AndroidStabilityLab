from __future__ import annotations

from typing import Any, Mapping

from stability.app.unattended.template_payloads import (
    find_long_run_template,
    normalize_long_run_plan_mapping,
    normalize_long_run_template_mapping,
    normalize_long_run_templates,
    sanitize_actor_for_public_payload,
)
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class RunnerPayloadMixin:
    def _runner_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        runner = self._runner_snapshot()
        platform_health = self._platform_health_payload({}, request_context=request_context)
        unattended_service = getattr(self._bundle, "unattended_service", None)
        long_run_templates = self._long_run_templates_payload({}, request_context=request_context)
        unattended_tasks = []
        if unattended_service is not None and hasattr(unattended_service, "list_task_records"):
            try:
                unattended_tasks = [
                    self._unattended_task_payload(item)
                    for item in unattended_service.list_task_records(limit=30)
                ]
            except Exception:
                unattended_tasks = []
        last_patrol = self._runner_patrol_with_severity(dict(runner.get("last_patrol", {}) or {}))
        patrol_filter = self._str_query(query, "patrol_filter").lower()
        severity_filter = self._str_query(query, "severity_filter").lower()
        keyword = self._str_query(query, "keyword")
        page = max(self._int_query(query, "page", default=1), 1)
        page_size = min(max(self._int_query(query, "page_size", default=20), 1), 100)
        recent_patrols_all = [
            self._runner_patrol_with_severity(dict(item or {}))
            for item in list(runner.get("recent_patrols", []) or [])
        ]
        latest_patrol = self._runner_latest_patrol(last_patrol=last_patrol, recent_patrols=recent_patrols_all)
        recent_patrols = self._filter_runner_patrols(
            recent_patrols_all,
            patrol_filter=patrol_filter,
            severity_filter=severity_filter,
            keyword=keyword,
        )
        recent_patrols_page = recent_patrols[(page - 1) * page_size:page * page_size]
        latest_daily_report = dict(runner.get("latest_daily_report", {}) or {})
        latest_weekly_report = dict(runner.get("latest_weekly_report", {}) or {})
        latest_patrol_severity = dict(latest_patrol.get("severity", {}) or {})
        filter_counts = {
            "failed": len(self._filter_runner_patrols(recent_patrols_all, patrol_filter="failed", severity_filter="")),
            "offline": len(self._filter_runner_patrols(recent_patrols_all, patrol_filter="offline", severity_filter="")),
            "quarantined": len(
                self._filter_runner_patrols(recent_patrols_all, patrol_filter="quarantined", severity_filter="")
            ),
        }
        severity_counts = {
            "normal": len(self._filter_runner_patrols(recent_patrols_all, patrol_filter="", severity_filter="normal")),
            "medium": len(self._filter_runner_patrols(recent_patrols_all, patrol_filter="", severity_filter="medium")),
            "high": len(self._filter_runner_patrols(recent_patrols_all, patrol_filter="", severity_filter="high")),
            "critical": len(
                self._filter_runner_patrols(recent_patrols_all, patrol_filter="", severity_filter="critical")
            ),
        }
        return {
            "page": "runner",
            "title": "后台巡检状态",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "summary": {
                "status": str(runner.get("status", "missing") or "missing"),
                "platform_health_status": str(platform_health.get("status", "unknown") or "unknown"),
                "platform_health_fail_count": int(
                    dict(platform_health.get("summary", {}) or {}).get("fail_count", 0) or 0
                ),
                "lock_state": str(runner.get("lock_state", "released") or "released"),
                "cycle_count": int(runner.get("cycle_count", 0) or 0),
                "heartbeat_age_seconds": runner.get("heartbeat_age_seconds"),
                "executed_task_count": int(last_patrol.get("executed_task_count", 0) or 0),
                "quarantined_device_count": int(last_patrol.get("quarantined_device_count", 0) or 0),
                "failed_rate": float(last_patrol.get("failed_rate", 0.0) or 0.0),
                "offline_rate": float(last_patrol.get("offline_rate", 0.0) or 0.0),
                "recovery_success_rate": float(last_patrol.get("recovery_success_rate", 0.0) or 0.0),
                "latest_patrol_severity": str(latest_patrol_severity.get("label", "正常") or "正常"),
                "daily_report_date": str(latest_daily_report.get("report_date", "") or ""),
                "daily_report_round_count": int(latest_daily_report.get("round_count", 0) or 0),
                "daily_report_failed_round_count": int(latest_daily_report.get("failed_round_count", 0) or 0),
                "daily_report_quarantined_device_count": int(
                    latest_daily_report.get("quarantined_device_count", 0) or 0
                ),
                "weekly_report_week_key": str(latest_weekly_report.get("week_key", "") or ""),
                "weekly_report_round_count": int(latest_weekly_report.get("round_count", 0) or 0),
                "weekly_report_failed_round_count": int(latest_weekly_report.get("failed_round_count", 0) or 0),
                "weekly_report_active_day_count": int(latest_weekly_report.get("active_day_count", 0) or 0),
                "weekly_report_quarantined_device_count": int(
                    latest_weekly_report.get("quarantined_device_count", 0) or 0
                ),
            },
            "runner": runner,
            "platform_health": platform_health,
            "latest_daily_report": latest_daily_report,
            "latest_weekly_report": latest_weekly_report,
            "last_patrol": last_patrol,
            "recent_patrols": recent_patrols_page,
            "latest_patrol_relation": self._runner_latest_patrol_relation(latest_patrol),
            "unattended_tasks": unattended_tasks,
            "long_run_templates": {
                "source": long_run_templates.get("source", "fallback"),
                "template_count": long_run_templates.get("template_count", 0),
                "templates": long_run_templates.get("templates", []),
                "api_path": "/api/long-run-templates",
                "page_path": "/long-run-templates",
            },
            "filters": {
                "keyword": keyword,
                "patrol_filter": patrol_filter,
                "severity_filter": severity_filter,
                "page": page,
                "page_size": page_size,
                "history_count_total": len(recent_patrols_all),
                "history_count_filtered": len(recent_patrols),
                "filter_counts": filter_counts,
                "severity_counts": severity_counts,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(recent_patrols),
            },
        }

    def _long_run_templates_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "unattended_service", None)
        template_key = self._str_query(query, "template_key")
        overrides = self._query_overrides(query)
        preview_only = self._str_query(query, "preview_only").lower() in {"1", "true", "yes"}
        keyword = self._str_query(query, "keyword")
        template_type = self._str_query(query, "template_type")
        page = max(self._int_query(query, "page", default=1), 1)
        page_size = min(max(self._int_query(query, "page_size", default=20), 1), 100)
        source = "fallback"
        templates: list[dict[str, Any]] = []
        if service is not None and hasattr(service, "list_long_run_templates"):
            try:
                templates = normalize_long_run_templates(
                    [
                        self._jsonable_mapping(item)
                        for item in self._long_run_template_items(service.list_long_run_templates())
                    ]
                )
                source = "service"
            except Exception:
                templates = []
        if not templates:
            templates = normalize_long_run_templates(self._fallback_long_run_templates())
        all_templates = list(templates)
        filtered_templates = [
            item
            for item in all_templates
            if self._long_run_template_matches_admin_filters(
                item,
                keyword=keyword,
                template_type=template_type,
            )
        ]
        templates_page = filtered_templates[(page - 1) * page_size:page * page_size]
        selected = find_long_run_template(templates, template_key) if template_key else None
        if selected is None and template_key and source == "service":
            selected = self._service_long_run_template(service, template_key)
            if selected is not None:
                selected = normalize_long_run_template_mapping(selected)
        plan = None
        if template_key:
            plan = self._service_long_run_template_plan(service, template_key, overrides)
            if plan is not None:
                plan = normalize_long_run_plan_mapping(plan)
            if plan is None and selected is not None:
                defaults = dict(selected.get("defaults", {}) or {})
                plan = {
                    "template_key": template_key,
                    "effective_defaults": {**defaults, **overrides},
                    "overrides": overrides,
                }
        return {
            "page": "long_run_templates",
            "title": "长稳运行模板",
            "generated_at": _generated_at_now(),
            "current_actor": sanitize_actor_for_public_payload(
                dict(dict(request_context or {}).get("current_actor", {}) or {})
            ),
            "source": source,
            "template_count": len(filtered_templates),
            "total_template_count": len(all_templates),
            "templates": templates_page,
            "template_key": template_key,
            "template": selected,
            "overrides": overrides,
            "plan": plan,
            "preview_only": preview_only,
            "filters": {
                "keyword": keyword,
                "template_type": template_type,
                "page": page,
                "page_size": page_size,
            },
            "filter_options": {
                "template_types": sorted(
                    {
                        str(dict(item.get("defaults", {}) or {}).get("template_type", "") or item.get("template_type", "") or "")
                        for item in all_templates
                        if str(dict(item.get("defaults", {}) or {}).get("template_type", "") or item.get("template_type", "") or "").strip()
                    }
                ),
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(filtered_templates),
            },
            "links": {
                "page": "/long-run-templates",
                "api": "/api/long-run-templates",
                "runner": "/runner",
            },
        }

    @staticmethod
    def _long_run_template_matches_admin_filters(
        item: Mapping[str, Any],
        *,
        keyword: str,
        template_type: str,
    ) -> bool:
        template = dict(item or {})
        defaults = dict(template.get("defaults", {}) or {})
        expected_type = str(template_type or "").lower()
        actual_type = str(defaults.get("template_type", "") or template.get("template_type", "") or "").lower()
        if expected_type and expected_type != actual_type:
            return False
        query = str(keyword or "").lower()
        if query:
            haystack = " ".join(
                str(value or "")
                for value in (
                    template.get("template_key", ""),
                    template.get("template_id", ""),
                    template.get("key", ""),
                    template.get("name", ""),
                    template.get("description", ""),
                    template.get("chinese_explanation", ""),
                    template.get("chinese_purpose", ""),
                    actual_type,
                    " ".join(str(tag) for tag in list(template.get("default_tags", []) or defaults.get("tags", []) or [])),
                )
            ).lower()
            if query not in haystack:
                return False
        return True


__all__ = ["RunnerPayloadMixin"]
