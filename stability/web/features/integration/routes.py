from __future__ import annotations

from typing import Any, Mapping

from ...routes import (
    API_RELEASE_SUBMISSION_DETAIL_PREFIX,
    API_REPLAY_DEAD_LETTERS_ROUTES,
    API_RUN_INTEGRATION_WORKER_ROUTES,
    API_SYNC_CI_DECISIONS_ROUTES,
    HTML_REPLAY_DEAD_LETTERS_ROUTES,
    HTML_RUN_INTEGRATION_WORKER_ROUTES,
    HTML_SYNC_CI_DECISIONS_ROUTES,
    route_in,
    route_value_after_prefix,
)

Response = tuple[int, str, bytes]


def _integration_html(app: Any, query: dict[str, list[str]], request_context: Mapping[str, Any], result: dict[str, Any], message: str) -> Response:
    payload = app._integration_payload(query, request_context=request_context)
    payload["flash"] = {"tone": "ok", "message": message}
    payload["operation_result"] = result
    return app._html_response(200, app._render_integration(payload))


def handle_integration_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    html_actions = {
        "/integration/actions/register-webhook": (app._handle_register_integration_webhook, lambda r: f"已注册 webhook：{r.get('webhook', {}).get('name', '')}"),
        "/integration/actions/register-im-webhook": (app._handle_register_im_webhook, lambda r: f"已注册 IM 通知 webhook：{r.get('webhook', {}).get('name', '')}"),
        "/integration/actions/register-defect-webhook": (app._handle_register_defect_webhook, lambda r: f"已注册缺陷同步 webhook：{r.get('webhook', {}).get('name', '')}"),
        "/integration/actions/create-release-submission": (app._handle_create_release_submission, lambda r: f"已创建提测请求：{r.get('release_submission', {}).get('submission_id', '')}"),
        "/integration/actions/sync-release-admission": (app._handle_sync_release_submission_admission, lambda r: f"已同步提测准入：{r.get('release_submission', {}).get('submission_id', '')}"),
        "/integration/actions/register-release-webhook": (app._handle_register_release_webhook, lambda r: f"已注册提测 webhook：{r.get('webhook', {}).get('name', '')}"),
        "/integration/actions/deliver-outbox": (app._handle_deliver_integration_outbox, lambda r: f"已执行单轮投递：{r.get('delivery', {}).get('webhook_name', '')}"),
        "/integration/actions/run-ci-worker": (app._handle_run_ci_sync_worker, lambda r: f"已执行 CI 回传 worker：rounds={r.get('delivery', {}).get('rounds_executed', 0)}"),
        "/integration/actions/run-im-worker": (app._handle_run_im_notify_worker, lambda r: f"已执行 IM 通知 worker：rounds={r.get('delivery', {}).get('rounds_executed', 0)}"),
        "/integration/actions/run-defect-worker": (app._handle_run_defect_sync_worker, lambda r: f"已执行缺陷同步 worker：rounds={r.get('delivery', {}).get('rounds_executed', 0)}"),
        "/integration/actions/run-release-worker": (app._handle_run_release_sync_worker, lambda r: f"已执行提测同步 worker：rounds={r.get('delivery', {}).get('rounds_executed', 0)}"),
    }
    if route in html_actions:
        handler, message = html_actions[route]
        result = handler(form, request_context=request_context)
        return _integration_html(app, query, request_context, result, message(result))
    if route_in(route, HTML_RUN_INTEGRATION_WORKER_ROUTES):
        result = app._handle_run_integration_worker(form, request_context=request_context)
        return _integration_html(app, query, request_context, result, f"已执行 worker：rounds={result.get('delivery', {}).get('rounds_executed', 0)}")
    if route_in(route, HTML_REPLAY_DEAD_LETTERS_ROUTES):
        result = app._handle_replay_dead_letters(form, request_context=request_context)
        return _integration_html(app, query, request_context, result, f"dead-letter 处理完成：replayed={result.get('dead_letter_replay', {}).get('replayed_count', 0)}")
    if route_in(route, HTML_SYNC_CI_DECISIONS_ROUTES):
        result = app._handle_sync_ci_decisions(form, request_context=request_context)
        return _integration_html(app, query, request_context, result, f"CI 准入同步完成：pending={result.get('query', {}).get('pending_count', 0)}")
    api_actions = {
        "/api/integration/actions/register-webhook": app._handle_register_integration_webhook,
        "/api/integration/actions/register-im-webhook": app._handle_register_im_webhook,
        "/api/integration/actions/register-defect-webhook": app._handle_register_defect_webhook,
        "/api/release-submissions/actions/create": app._handle_create_release_submission,
        "/api/release-submissions/actions/sync-admission": app._handle_sync_release_submission_admission,
        "/api/integration/actions/register-release-webhook": app._handle_register_release_webhook,
        "/api/integration/actions/deliver-outbox": app._handle_deliver_integration_outbox,
        "/api/integration/actions/run-ci-worker": app._handle_run_ci_sync_worker,
        "/api/integration/actions/run-im-worker": app._handle_run_im_notify_worker,
        "/api/integration/actions/run-defect-worker": app._handle_run_defect_sync_worker,
        "/api/integration/actions/run-release-worker": app._handle_run_release_sync_worker,
    }
    if route in api_actions:
        return app._json_response(200, api_actions[route](form, request_context=request_context))
    if route_in(route, API_RUN_INTEGRATION_WORKER_ROUTES):
        return app._json_response(200, app._handle_run_integration_worker(form, request_context=request_context))
    if route_in(route, API_REPLAY_DEAD_LETTERS_ROUTES):
        return app._json_response(200, app._handle_replay_dead_letters(form, request_context=request_context))
    if route_in(route, API_SYNC_CI_DECISIONS_ROUTES):
        return app._json_response(200, app._handle_sync_ci_decisions(form, request_context=request_context))
    return None


def handle_integration_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/integration":
        payload = app._integration_payload(query, request_context=request_context)
        return app._html_response(200, app._render_integration(payload))
    if route == "/api/release-submissions":
        return app._json_response(200, app._release_submissions_payload(query, request_context=request_context))
    if route == "/api/integration":
        return app._json_response(200, app._integration_payload(query, request_context=request_context))
    if route == "/api/integration/outbox":
        return app._json_response(200, app._integration_payload(query, request_context=request_context))
    if (submission_id := route_value_after_prefix(route, API_RELEASE_SUBMISSION_DETAIL_PREFIX)) is not None:
        return app._json_response(200, app._release_submission_detail_payload(submission_id, query=query, request_context=request_context))
    return None

