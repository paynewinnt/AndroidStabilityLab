from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any
from stability.domain import AppError


class ApplicationResponseMixin:
    @staticmethod
    def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, str, bytes]:
        return status, "application/json; charset=utf-8", json.dumps(
            payload, ensure_ascii=False, indent=2
        ).encode("utf-8")

    @staticmethod
    def _html_response(status: int, html: str) -> tuple[int, str, bytes]:
        return status, "text/html; charset=utf-8", html.encode("utf-8")

    @staticmethod
    def _app_error_payload(error: AppError, *, path: str = "") -> dict[str, Any]:
        detail = error.to_dict()
        payload: dict[str, Any] = {
            "error": error.message,
            "error_code": error.code,
            "message": error.message,
            "hint": error.hint,
            "details": dict(error.details),
            "app_error": detail,
        }
        if path:
            payload["path"] = path
        if error.request_id:
            payload["request_id"] = error.request_id
        if error.audit_event_id:
            payload["audit_event_id"] = error.audit_event_id
        return payload

    def _file_response(self, path_value: str) -> tuple[int, str, bytes]:
        resolved = self._resolve_portal_file_path(path_value)
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Portal file not found: {resolved}")
        content_type = mimetypes.guess_type(str(resolved))[0] or "text/plain"
        if resolved.suffix.lower() in {".md", ".log", ".txt"}:
            content_type = "text/plain"
        if resolved.suffix.lower() == ".json":
            content_type = "application/json"
        return 200, f"{content_type}; charset=utf-8", resolved.read_bytes()

    @staticmethod
    def _required_query_value(query: dict[str, list[str]], key: str) -> str:
        values = query.get(key, [])
        if not values or not str(values[0]).strip():
            raise ValueError(f"Missing query parameter: {key}")
        return str(values[0]).strip()

    def _response_boundary_headers(self, request_id: str) -> dict[str, str]:
        return {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Request-ID": request_id,
            "X-ASL-Request-ID": request_id,
            "X-ASL-Portal-Mode": self._portal_mode(),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cross-Origin-Resource-Policy": "same-origin",
            "X-Robots-Tag": "noindex, nofollow",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'self'; "
                "img-src 'self' data:; "
                "object-src 'none'; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "connect-src 'self'"
            ),
        }

    @staticmethod
    def _resolve_portal_file_path(path_value: str) -> Path:
        candidate = Path(path_value)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        resolved = candidate.resolve(strict=False)
        root = Path.cwd().resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Portal file path is outside workspace: {resolved}") from exc
        return resolved
