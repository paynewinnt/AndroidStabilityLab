from __future__ import annotations

from typing import Any, Mapping

from ...routes import (
    API_ARCHIVE_TASK_ROUTES,
    API_CREATE_RUN_ROUTES,
    API_CREATE_TASK_ROUTES,
    API_EXECUTE_RUN_ROUTES,
    API_RUN_ARTIFACTS_PREFIX,
    API_RUN_DETAIL_PREFIX,
    API_STOP_RUN_ROUTES,
    API_TASK_DETAIL_PREFIX,
    HTML_ARCHIVE_TASK_ROUTES,
    HTML_CREATE_RUN_ROUTES,
    HTML_CREATE_TASK_ROUTES,
    HTML_EXECUTE_RUN_ROUTES,
    HTML_RUN_ARTIFACTS_PREFIX,
    HTML_RUN_DETAIL_PREFIX,
    HTML_STOP_RUN_ROUTES,
    HTML_TASK_DETAIL_PREFIX,
    route_in,
    route_value_after_prefix,
)

Response = tuple[int, str, bytes]


def handle_tasks_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/tasks/actions/upload-apk":
        return None
    if route == "/tasks/actions/delete-apk":
        result = app._handle_apk_delete(form)
        return app._json_response(200, result)
    if route_in(route, HTML_CREATE_TASK_ROUTES):
        result = app._handle_task_create(form, request_context=request_context)
        payload = app._tasks_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已创建任务：{result.get('task_name', '') or result.get('task_id', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_tasks(payload))
    if route_in(route, HTML_ARCHIVE_TASK_ROUTES):
        result = app._handle_task_archive(form, request_context=request_context)
        payload = app._tasks_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": str(result.get("message", "") or "任务已归档。")}
        payload["operation_result"] = result
        return app._html_response(200, app._render_tasks(payload))
    if route_in(route, HTML_CREATE_RUN_ROUTES):
        result = app._handle_run_create(form, request_context=request_context)
        payload = app._tasks_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已创建 Run：{result.get('run_id', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_tasks(payload))
    if route_in(route, HTML_EXECUTE_RUN_ROUTES):
        result = app._handle_run_execute(form, request_context=request_context)
        payload = app._tasks_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已执行 Run：{result.get('run_id', '')} -> {result.get('run_status', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_tasks(payload))
    if route_in(route, HTML_STOP_RUN_ROUTES):
        result = app._handle_run_stop(form, request_context=request_context)
        payload = app._tasks_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "warning", "message": f"已请求停止 Run：{result.get('run_id', '')} -> {result.get('run_status', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_tasks(payload))
    if route_in(route, API_CREATE_TASK_ROUTES):
        return app._json_response(200, app._handle_task_create(form, request_context=request_context))
    if route_in(route, API_ARCHIVE_TASK_ROUTES):
        return app._json_response(200, app._handle_task_archive(form, request_context=request_context))
    if route_in(route, API_CREATE_RUN_ROUTES):
        return app._json_response(200, app._handle_run_create(form, request_context=request_context))
    if route_in(route, API_EXECUTE_RUN_ROUTES):
        return app._json_response(200, app._handle_run_execute(form, request_context=request_context))
    if route_in(route, API_STOP_RUN_ROUTES):
        return app._json_response(200, app._handle_run_stop(form, request_context=request_context))
    return None


def handle_tasks_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/tasks":
        payload = app._tasks_payload(query, request_context=request_context)
        return app._html_response(200, app._render_tasks(payload))
    if route == "/runs":
        payload = app._runs_payload(query, request_context=request_context)
        return app._html_response(200, app._render_runs(payload))
    if route == "/artifacts":
        payload = app._artifacts_payload(query, request_context=request_context)
        return app._html_response(200, app._render_artifacts(payload))
    if route == "/long-run-templates":
        payload = app._long_run_templates_payload(query, request_context=request_context)
        return app._html_response(200, app._render_long_run_templates(payload))
    if (run_id := route_value_after_prefix(route, HTML_RUN_ARTIFACTS_PREFIX)) is not None:
        payload = app._run_detail_payload(run_id, query=query)
        return app._html_response(200, app._render_run_artifacts(payload))
    if (run_id := route_value_after_prefix(route, HTML_RUN_DETAIL_PREFIX)) is not None:
        payload = app._run_detail_payload(run_id, query=query)
        return app._html_response(200, app._render_run_detail(payload))
    if (task_id := route_value_after_prefix(route, HTML_TASK_DETAIL_PREFIX)) is not None:
        payload = app._task_detail_payload(task_id, query=query, request_context=request_context)
        return app._html_response(200, app._render_task_detail(payload))
    if route == "/api/tasks":
        return app._json_response(200, app._tasks_payload(query, request_context=request_context))
    if route == "/api/runs":
        return app._json_response(200, app._runs_payload(query, request_context=request_context))
    if route == "/api/artifacts":
        return app._json_response(200, app._artifacts_payload(query, request_context=request_context))
    if route == "/api/long-run-templates":
        return app._json_response(200, app._long_run_templates_payload(query, request_context=request_context))
    if (run_id := route_value_after_prefix(route, API_RUN_ARTIFACTS_PREFIX)) is not None:
        payload = app._run_detail_payload(run_id, query=query)
        return app._json_response(200, app._run_artifacts_payload(payload))
    if (run_id := route_value_after_prefix(route, API_RUN_DETAIL_PREFIX)) is not None:
        return app._json_response(200, app._run_detail_payload(run_id, query=query))
    if (task_id := route_value_after_prefix(route, API_TASK_DETAIL_PREFIX)) is not None:
        return app._json_response(200, app._task_detail_payload(task_id, query=query, request_context=request_context))
    return None
