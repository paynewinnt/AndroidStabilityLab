from __future__ import annotations

from typing import Any, Mapping

Response = tuple[int, str, bytes]


def handle_devices_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/device-pools/actions/update-profile":
        result = app._handle_device_profile_update(form, request_context=request_context)
        payload = app._device_pools_payload(query, request_context=request_context)
        payload["flash"] = {"tone": "ok", "message": f"已更新设备标记：{result.get('device_id', '')}"}
        payload["operation_result"] = result
        return app._html_response(200, app._render_device_pools(payload))
    if route == "/device-pools/actions/refresh":
        result = app._handle_device_registry_refresh(form, request_context=request_context)
        payload = app._device_pools_payload(query, request_context=request_context)
        payload["flash"] = {
            "tone": "ok",
            "message": f"已刷新设备快照：scanned={result.get('scanned_count', 0)} updated={result.get('updated_count', 0)}",
        }
        payload["operation_result"] = result
        return app._html_response(200, app._render_device_pools(payload))
    if route == "/device-pools/actions/connect":
        result = app._handle_device_connect(form, request_context=request_context)
        payload = app._device_pools_payload(query, request_context=request_context)
        payload["flash"] = {
            "tone": "ok" if bool(result.get("connected", False)) else "warning",
            "message": f"已尝试连接设备：{result.get('serial', '')} -> {'connected' if result.get('connected') else 'not connected'}",
        }
        payload["operation_result"] = result
        return app._html_response(200, app._render_device_pools(payload))
    if route == "/device-pools/actions/pair-connect":
        result = app._handle_device_pair_connect(form, request_context=request_context)
        payload = app._device_pools_payload(query, request_context=request_context)
        payload["flash"] = {
            "tone": "ok" if bool(result.get("paired", False)) and bool(result.get("connected", False)) else "warning",
            "message": (
                f"已执行无线配对并连接：pair={'ok' if result.get('paired') else 'failed'} / "
                f"connect={'ok' if result.get('connected') else 'failed'}"
            ),
        }
        payload["operation_result"] = result
        return app._html_response(200, app._render_device_pools(payload))
    if route == "/api/device-pools/actions/update-profile":
        return app._json_response(200, app._handle_device_profile_update(form, request_context=request_context))
    if route == "/api/device-pools/actions/refresh":
        return app._json_response(200, app._handle_device_registry_refresh(form, request_context=request_context))
    if route == "/api/device-pools/actions/connect":
        return app._json_response(200, app._handle_device_connect(form, request_context=request_context))
    if route == "/api/device-pools/actions/pair-connect":
        return app._json_response(200, app._handle_device_pair_connect(form, request_context=request_context))
    return None


def handle_devices_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    if route == "/device-pools":
        payload = app._device_pools_payload(query, request_context=request_context)
        return app._html_response(200, app._render_device_pools(payload))
    if route == "/api/device-pools":
        return app._json_response(200, app._device_pools_payload(query, request_context=request_context))
    return None

