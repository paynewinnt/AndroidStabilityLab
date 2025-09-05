from __future__ import annotations

from typing import Any, Mapping

Response = tuple[int, str, bytes]


def handle_core_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/health":
        return app._json_response(200, {"ok": True, "service": "web_portal"})
    if route == "/ready":
        readiness = app._platform_readiness()
        payload = {
            "ok": bool(readiness.get("ok", False)),
            "service": "web_portal",
            "mode": app._portal_mode(),
            "public_base_url": app._portal_base_url(),
            "deployment_label": app._portal_deployment_label(),
            "readiness": readiness,
        }
        return app._json_response(200 if payload["ok"] else 503, payload)
    if route == "/":
        payload = app._home_payload(query, request_context=request_context)
        return app._html_response(200, app._render_home(payload))
    if route == "/platform":
        payload = app._platform_payload(query, request_context=request_context)
        return app._html_response(200, app._render_platform(payload))
    if route == "/doctor":
        payload = app._doctor_payload(query, request_context=request_context)
        return app._html_response(200, app._render_doctor(payload))
    if route == "/json-api":
        payload = app._home_payload(query, request_context=request_context)
        payload["json_api_query"] = dict(query)
        return app._html_response(200, app._render_json_api_index(payload))
    if route == "/rules":
        payload = app._rules_payload(query, request_context=request_context)
        return app._html_response(200, app._render_rules(payload))
    if route == "/admission/view":
        file_path = app._required_query_value(query, "path")
        return app._file_response(file_path)
    if route == "/api/home":
        return app._json_response(200, app._home_payload(query, request_context=request_context))
    if route == "/api/platform":
        return app._json_response(200, app._platform_payload(query, request_context=request_context))
    if route == "/api/platform-health":
        return app._json_response(200, app._platform_health_payload(query, request_context=request_context))
    if route == "/api/doctor":
        return app._json_response(200, app._doctor_payload(query, request_context=request_context))
    if route == "/api/users":
        return app._json_response(200, app._users_payload(query, request_context=request_context))
    if route == "/api/responsibility":
        return app._json_response(200, app._responsibility_payload(query, request_context=request_context))
    if route == "/api/manifest":
        return app._json_response(200, app._api_manifest_payload(request_context=request_context))
    if route == "/api/openapi.json":
        return app._json_response(200, app._openapi_payload(request_context=request_context))
    if route == "/api/rules":
        return app._json_response(200, app._rules_payload(query, request_context=request_context))
    return None


__all__ = ["handle_core_get"]
