from __future__ import annotations

from typing import Any, Callable, Mapping

from .features.admission.routes import handle_admission_get, handle_admission_post
from .features.core.routes import handle_core_get
from .features.devices.routes import handle_devices_get, handle_devices_post
from .features.integration.routes import handle_integration_get, handle_integration_post
from .features.performance.routes import handle_performance_get
from .features.quick_adb.routes import handle_quick_adb_get, handle_quick_adb_post
from .features.runner.routes import handle_runner_get, handle_runner_post
from .features.tasks.routes import handle_tasks_get, handle_tasks_post

Response = tuple[int, str, bytes]
PostHandler = Callable[[Any, str, dict[str, list[str]], Mapping[str, list[str]], Mapping[str, Any]], Response | None]
GetHandler = Callable[[Any, str, dict[str, list[str]], Mapping[str, Any]], Response | None]

POST_HANDLERS: tuple[PostHandler, ...] = (
    handle_tasks_post,
    handle_devices_post,
    handle_quick_adb_post,
    handle_runner_post,
    handle_integration_post,
    handle_admission_post,
)

GET_HANDLERS: tuple[GetHandler, ...] = (
    handle_core_get,
    handle_devices_get,
    handle_quick_adb_get,
    handle_tasks_get,
    handle_runner_get,
    handle_integration_get,
    handle_performance_get,
    handle_admission_get,
)


def dispatch_post(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    form: Mapping[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    for handler in POST_HANDLERS:
        response = handler(app, route, query, form, request_context)
        if response is not None:
            return response
    return None


def dispatch_get(
    app: Any,
    route: str,
    query: dict[str, list[str]],
    request_context: Mapping[str, Any],
) -> Response | None:
    for handler in GET_HANDLERS:
        response = handler(app, route, query, request_context)
        if response is not None:
            return response
    return None


__all__ = ["GET_HANDLERS", "POST_HANDLERS", "dispatch_get", "dispatch_post"]
