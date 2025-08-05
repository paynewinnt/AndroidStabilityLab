from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class AppErrorCode:
    """Stable application error codes shared by Web, API and CLI boundaries."""

    VALIDATION_ERROR = "validation_error"
    INVALID_JSON = "invalid_json"
    UNSUPPORTED_TEMPLATE = "unsupported_template"
    INVALID_TASK_PARAMS = "invalid_task_params"
    UNSUPPORTED_METRIC = "unsupported_metric"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    PERMISSION_DENIED = "permission_denied"
    CONFLICT = "conflict"
    EXTERNAL_DEPENDENCY_FAILED = "external_dependency_failed"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class AppError(Exception):
    """One serializable error contract for application boundaries."""

    code: str
    message: str
    hint: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)
    http_status: int = 400
    request_id: str = ""
    audit_event_id: str = ""

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    def with_context(self, *, request_id: str = "", audit_event_id: str = "") -> "AppError":
        return AppError(
            code=self.code,
            message=self.message,
            hint=self.hint,
            details=dict(self.details),
            http_status=self.http_status,
            request_id=request_id or self.request_id,
            audit_event_id=audit_event_id or self.audit_event_id,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "details": dict(self.details),
        }
        if self.request_id:
            payload["request_id"] = self.request_id
        if self.audit_event_id:
            payload["audit_event_id"] = self.audit_event_id
        return payload

    @classmethod
    def validation(
        cls,
        message: str,
        *,
        code: str = AppErrorCode.VALIDATION_ERROR,
        hint: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> "AppError":
        return cls(code=code, message=message, hint=hint, details=dict(details or {}), http_status=400)

    @classmethod
    def not_found(cls, message: str, *, details: Mapping[str, Any] | None = None) -> "AppError":
        return cls(code=AppErrorCode.NOT_FOUND, message=message, details=dict(details or {}), http_status=404)

    @classmethod
    def permission_denied(cls, message: str, *, details: Mapping[str, Any] | None = None) -> "AppError":
        return cls(
            code=AppErrorCode.PERMISSION_DENIED,
            message=message,
            details=dict(details or {}),
            http_status=403,
        )


def normalize_app_error(exc: Exception) -> AppError:
    """Convert existing exception types into the shared AppError shape."""

    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, PermissionError):
        return AppError.permission_denied(str(exc))
    if isinstance(exc, LookupError):
        return AppError.not_found(str(exc))
    if isinstance(exc, ValueError):
        return AppError.validation(str(exc))
    return AppError(
        code=AppErrorCode.INTERNAL_ERROR,
        message=str(exc) or exc.__class__.__name__,
        http_status=500,
        details={"exception_type": exc.__class__.__name__},
    )
