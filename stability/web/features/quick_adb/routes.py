from __future__ import annotations

from typing import Any, Mapping

Response = tuple[int, str, bytes]


def handle_quick_adb_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/quick-adb/actions/execute":
        payload = app._quick_adb_payload(query, request_context=request_context)
        payload["selected_device_ids"] = [
            device_id for device_id in app._quick_adb_device_ids(form) if device_id
        ]
        payload["selected_package_names"] = app._quick_adb_package_names(form)
        try:
            result = app._handle_quick_adb_execute(form, request_context=request_context)
        except ValueError as exc:
            payload["flash"] = {
                "tone": "danger",
                "message": "Package 类命令需要先在上方选择设备包名，或在“手动输入包名”里填写包名。",
            }
            payload["validation_error"] = str(exc)
            return app._html_response(200, app._render_quick_adb(payload))
        payload["flash"] = {
            "tone": "ok" if bool(result.get("result", {}).get("ok", False)) else "danger",
            "message": f"已执行：{result.get('command', {}).get('title', '')}",
        }
        payload["operation_result"] = result
        return app._html_response(200, app._render_quick_adb(payload))
    if route == "/api/quick-adb/actions/execute":
        return app._json_response(200, app._handle_quick_adb_execute(form, request_context=request_context))
    return None


def handle_quick_adb_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/quick-adb":
        return app._html_response(200, app._render_quick_adb(app._quick_adb_payload(query, request_context=request_context)))
    if route == "/api/quick-adb/packages":
        return app._json_response(200, app._handle_quick_adb_packages(query, request_context=request_context))
    if route == "/api/quick-adb":
        return app._json_response(200, app._quick_adb_payload(query, request_context=request_context))
    return None
