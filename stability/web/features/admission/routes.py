from __future__ import annotations

from typing import Any, Mapping

from ...routes import (
    API_ADMISSION_BASELINE_PREFIX,
    API_ADMISSION_CASE_PREFIX,
    API_ADMISSION_REPORT_PREFIX,
    API_GOLDEN_CASE_PREFIX,
    HTML_ADMISSION_BASELINE_PREFIX,
    HTML_GOLDEN_CASE_PREFIX,
    route_value_after_prefix,
)

Response = tuple[int, str, bytes]


def handle_admission_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    issue_routes = {
        "/issues/actions/assign": (app._handle_issue_assign, app._issues_payload, app._render_issues, lambda r: f"已更新问题认领：{r['fingerprint']} -> {r['assignee_display_name'] or r['assignee_id']}"),
        "/issues/actions/comment": (app._handle_issue_comment, app._issues_payload, app._render_issues, lambda r: f"已记录问题评论：{r['fingerprint']}"),
        "/issues/actions/transition": (app._handle_issue_transition, app._issues_payload, app._render_issues, lambda r: f"已更新问题状态：{r['fingerprint']} -> {r['workflow_state']}"),
        "/issues/actions/create-defect": (app._handle_issue_create_defect, app._issues_payload, app._render_issues, lambda r: f"已创建缺陷请求：{r['fingerprint']} -> {r.get('latest_defect_system_key', '')}"),
        "/issues/actions/sync-defect": (app._handle_issue_sync_defect, app._issues_payload, app._render_issues, lambda r: f"已同步缺陷状态：{r['fingerprint']} -> {r.get('latest_defect_status', '')}"),
    }
    if route in issue_routes:
        handler, payload_builder, renderer, message_builder = issue_routes[route]
        result = handler(form, request_context=request_context)
        payload = payload_builder(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": message_builder(result)}
        return app._html_response(200, renderer(payload))
    admission_routes = {
        "/admission/actions/assign": (app._handle_admission_assign, lambda r: f"已更新准入单认领：{r['baseline_key']} -> {r['assignee_display_name'] or r['assignee_id']}"),
        "/admission/actions/comment": (app._handle_admission_comment, lambda r: f"已记录准入单评论：{r['baseline_key']}"),
        "/admission/actions/transition": (app._handle_admission_transition, lambda r: f"已更新准入单状态：{r['baseline_key']} -> {r['workflow_state']}"),
    }
    if route == "/admission/actions/override":
        result = app._handle_admission_override(form, request_context=request_context)
        payload = app._baseline_detail_payload(str(result["baseline_key"]), query=query, request_context=request_context)
        payload["flash"] = {
            "tone": "ok",
            "message": f"已记录人工覆盖：{result['baseline_key']} {result['automatic_decision']} -> {result['final_decision']}",
        }
        return app._html_response(200, app._render_admission_detail(payload))
    if route in admission_routes:
        handler, message_builder = admission_routes[route]
        result = handler(form, request_context=request_context)
        payload = app._baseline_detail_payload(str(result["baseline_key"]), query=query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": message_builder(result)}
        return app._html_response(200, app._render_admission_detail(payload))
    api_routes = {
        "/api/issues/actions/assign": app._handle_issue_assign,
        "/api/issues/actions/comment": app._handle_issue_comment,
        "/api/issues/actions/transition": app._handle_issue_transition,
        "/api/issues/actions/create-defect": app._handle_issue_create_defect,
        "/api/issues/actions/sync-defect": app._handle_issue_sync_defect,
        "/api/admission/actions/override": app._handle_admission_override,
        "/api/admission/actions/assign": app._handle_admission_assign,
        "/api/admission/actions/comment": app._handle_admission_comment,
        "/api/admission/actions/transition": app._handle_admission_transition,
    }
    if route in api_routes:
        return app._json_response(200, api_routes[route](form, request_context=request_context))
    return None


def handle_admission_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/issues":
        payload = app._issues_payload(query, request_context=request_context)
        return app._html_response(200, app._render_issues(payload))
    if route == "/goldens":
        payload = app._goldens_payload(query, request_context=request_context)
        return app._html_response(200, app._render_goldens(payload))
    if route == "/goldens/diff":
        payload = app._golden_diff_payload(query, request_context=request_context)
        return app._html_response(200, app._render_golden_diff(payload))
    if route == "/admission":
        payload = app._admission_payload(query, request_context=request_context)
        return app._html_response(200, app._render_admission(payload))
    if (case_id := route_value_after_prefix(route, HTML_GOLDEN_CASE_PREFIX)) is not None:
        payload = app._golden_case_detail_payload(case_id, query=query)
        return app._html_response(200, app._render_golden_case_detail(payload))
    if (baseline_key := route_value_after_prefix(route, HTML_ADMISSION_BASELINE_PREFIX)) is not None:
        payload = app._baseline_detail_payload(baseline_key, query=query, request_context=request_context)
        return app._html_response(200, app._render_admission_detail(payload))
    if route == "/api/issues":
        return app._json_response(200, app._issues_payload(query, request_context=request_context))
    if route == "/api/goldens":
        return app._json_response(200, app._goldens_payload(query, request_context=request_context))
    if route == "/api/goldens/diff":
        return app._json_response(200, app._golden_diff_payload(query, request_context=request_context))
    if route == "/api/admission":
        return app._json_response(200, app._admission_payload(query, request_context=request_context))
    if route == "/api/admission/cases":
        return app._json_response(200, app._admission_payload(query, request_context=request_context))
    if (baseline_key := route_value_after_prefix(route, API_ADMISSION_REPORT_PREFIX)) is not None:
        return app._json_response(200, app._admission_report_response_payload(baseline_key))
    if (case_id := route_value_after_prefix(route, API_GOLDEN_CASE_PREFIX)) is not None:
        return app._json_response(200, app._golden_case_detail_payload(case_id, query=query))
    if (baseline_key := route_value_after_prefix(route, API_ADMISSION_BASELINE_PREFIX)) is not None:
        return app._json_response(200, app._baseline_detail_payload(baseline_key, query=query, request_context=request_context))
    if (baseline_key := route_value_after_prefix(route, API_ADMISSION_CASE_PREFIX)) is not None:
        return app._json_response(200, app._baseline_detail_payload(baseline_key, query=query, request_context=request_context))
    return None

