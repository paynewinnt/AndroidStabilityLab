from __future__ import annotations

from typing import Any, Mapping

from ...routes import (
    API_CONFIGURE_UNATTENDED_ROUTES,
    API_PATROL_UNATTENDED_ROUTES,
    API_RUN_UNATTENDED_ROUND_ROUTES,
    API_UNATTENDED_DETAIL_PREFIX,
    HTML_CONFIGURE_UNATTENDED_ROUTES,
    HTML_PATROL_UNATTENDED_ROUTES,
    HTML_RUN_UNATTENDED_ROUND_ROUTES,
    HTML_UNATTENDED_DETAIL_PREFIX,
    route_in,
    route_value_after_prefix,
)

Response = tuple[int, str, bytes]


def handle_runner_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route_in(route, HTML_CONFIGURE_UNATTENDED_ROUTES):
        result = app._handle_unattended_configure(form, request_context=request_context)
        payload = app._runner_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已更新无人值守配置：{result.get('task_name', '') or result.get('task_id', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_runner(payload))
    if route_in(route, HTML_RUN_UNATTENDED_ROUND_ROUTES):
        result = app._handle_unattended_run_round(form, request_context=request_context)
        payload = app._runner_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已触发无人值守轮次：{result.get('task', {}).get('task_id', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_runner(payload))
    if route_in(route, HTML_PATROL_UNATTENDED_ROUTES):
        result = app._handle_unattended_patrol(form, request_context=request_context)
        payload = app._runner_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已触发巡检：executed={result.get('patrol', {}).get('executed_task_count', 0)}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_runner(payload))
    if route_in(route, API_CONFIGURE_UNATTENDED_ROUTES):
        return app._json_response(200, app._handle_unattended_configure(form, request_context=request_context))
    if route_in(route, API_RUN_UNATTENDED_ROUND_ROUTES):
        return app._json_response(200, app._handle_unattended_run_round(form, request_context=request_context))
    if route_in(route, API_PATROL_UNATTENDED_ROUTES):
        return app._json_response(200, app._handle_unattended_patrol(form, request_context=request_context))
    return None


def handle_runner_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/runner":
        payload = app._runner_payload(query, request_context=request_context)
        return app._html_response(200, app._render_runner(payload))
    if (task_id := route_value_after_prefix(route, HTML_UNATTENDED_DETAIL_PREFIX)) is not None:
        payload = app._unattended_detail_payload(task_id, query=query, request_context=request_context)
        return app._html_response(200, app._render_unattended_detail(payload))
    if route == "/api/runner":
        return app._json_response(200, app._runner_payload(query, request_context=request_context))
    if (task_id := route_value_after_prefix(route, API_UNATTENDED_DETAIL_PREFIX)) is not None:
        return app._json_response(200, app._unattended_detail_payload(task_id, query=query, request_context=request_context))
    return None

