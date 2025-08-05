from __future__ import annotations

from typing import Any, Mapping

Response = tuple[int, str, bytes]


def handle_performance_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/performance":
        payload = app._performance_payload(query, request_context=request_context)
        return app._html_response(200, app._render_performance(payload))
    if route == "/api/performance":
        return app._json_response(200, app._performance_payload(query, request_context=request_context))
    return None

