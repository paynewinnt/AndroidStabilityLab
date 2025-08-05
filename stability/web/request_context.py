from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs

from stability.domain.value_objects import new_id


TRUSTED_SSO_HEADERS = {
    "provider": "X-ASL-SSO-Provider",
    "external_subject_id": "X-ASL-External-Subject",
    "external_email": "X-ASL-External-Email",
    "organization_id": "X-ASL-Org",
    "team_ids": "X-ASL-Team",
    "role_claims": "X-ASL-Role",
}
REQUIRED_TRUSTED_SSO_CLAIMS = ("provider", "external_subject_id")

WRITABLE_IDENTITY_FORM_FIELDS = frozenset({
    "actor_id",
    "as_actor",
    "as_session",
    "identity_id",
    "session_token",
    "role_key",
    "created_by",
    "updated_by",
    "requested_actor_id",
    "requested_session_token",
})

STRICT_TRUSTED_IDENTITY_SOURCES = [
    "header:trusted_sso",
    "header:x-asl-actor",
    "header:x-asl-session-token",
    "header:authorization",
    "cookie:asl_session",
    "query:as_session",
]
READ_TRUSTED_IDENTITY_SOURCES = [
    *STRICT_TRUSTED_IDENTITY_SOURCES,
    "cookie:asl_actor",
    "query:as_actor",
]


def parse_request_payload(*, method: str, body: bytes, content_type: str) -> dict[str, list[str]]:
    if method != "POST" or not body:
        return {}
    lowered = str(content_type or "").lower()
    if "application/json" in lowered:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, Mapping):
            return {}
        normalized: dict[str, list[str]] = {}
        for key, value in payload.items():
            if isinstance(value, (list, tuple)):
                normalized[str(key)] = [str(item) for item in value if str(item).strip()]
            elif value is not None and str(value).strip():
                normalized[str(key)] = [str(value)]
        return normalized
    try:
        return parse_qs(body.decode("utf-8"), keep_blank_values=False)
    except UnicodeDecodeError:
        return {}


def request_id_from_headers(headers: Mapping[str, str]) -> str:
    for key in ("X-ASL-Request-ID", "x-asl-request-id", "X-Request-ID", "x-request-id"):
        value = str(headers.get(key, "") or "").strip()
        if value:
            return value
    return new_id("portal_req")


def build_request_context(
    *,
    form: Mapping[str, list[str]],
    headers: Mapping[str, str],
    client_address: str,
    method: str,
    route: str,
    current_actor: Mapping[str, Any],
    strict_actor_resolution: bool,
    token_hint: Callable[[object], str],
) -> dict[str, Any]:
    request_id = request_id_from_headers(headers)
    return {
        "request": {
            "request_id": request_id,
            "request_method": method,
            "request_path": route,
            "client_address": client_address,
        },
        "current_actor": dict(current_actor),
        "audit_source": {
            "audit_event_id": new_id("audit_event") if strict_actor_resolution else "",
            "request_id": request_id,
            "request_method": method,
            "request_path": route,
            "client_address": client_address,
            "user_agent": str(headers.get("User-Agent", "") or headers.get("user-agent", "") or ""),
            "actor_session_source": str(current_actor.get("session_source", "") or ""),
            "resolved_actor_id": str(current_actor.get("actor_id", "") or ""),
            "resolved_identity_id": str(current_actor.get("identity_id", "") or ""),
            "resolved_role_key": str(current_actor.get("role_key", "") or ""),
            "resolved_session_id": str(current_actor.get("session_id", "") or ""),
            "resolved_session_token_hint": token_hint(current_actor.get("session_token", "")),
            "resolved_session_expires_at": str(current_actor.get("session_expires_at", "") or ""),
            "identity_source_type": str(current_actor.get("identity_source_type", "") or ""),
            "auth_mechanism": str(current_actor.get("auth_mechanism", "") or ""),
            "identity_provider": str(current_actor.get("identity_provider", "") or ""),
            "external_identity_id": str(current_actor.get("external_identity_id", "") or ""),
            "external_subject_id": str(current_actor.get("external_subject_id", "") or ""),
            "external_email": str(current_actor.get("external_email", "") or ""),
            "organization_id": str(current_actor.get("organization_id", "") or ""),
            "team_ids": list(current_actor.get("team_ids", []) or []),
            "role_claims": list(current_actor.get("role_claims", []) or []),
            "identity_resolution_mode": "strict_write_identity" if strict_actor_resolution else "best_effort_read_identity",
            "identity_boundary": "portal_write_identity_v1" if strict_actor_resolution else "portal_read_identity_v1",
            "trusted_identity_sources": (
                STRICT_TRUSTED_IDENTITY_SOURCES
                if strict_actor_resolution
                else READ_TRUSTED_IDENTITY_SOURCES
            ),
            "requested_actor_id": str(current_actor.get("requested_actor_id", "") or ""),
            "requested_actor_source": str(current_actor.get("requested_actor_source", "") or ""),
            "requested_session_token_hint": token_hint(current_actor.get("requested_session_token", "")),
            "requested_session_source": str(current_actor.get("requested_session_source", "") or ""),
            "request_identity_override_fields": identity_override_fields(form),
        },
    }


def cookie_value(headers: Mapping[str, str], name: str) -> str:
    raw_cookie = str(headers.get("Cookie", "") or headers.get("cookie", "") or "")
    if not raw_cookie:
        return ""
    for chunk in raw_cookie.split(";"):
        key, _, value = chunk.partition("=")
        if key.strip() == name:
            return value.strip()
    return ""


def bearer_token(headers: Mapping[str, str]) -> str:
    authorization = str(headers.get("Authorization", "") or headers.get("authorization", "") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def header_value(headers: Mapping[str, str], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value or "").strip()
    return ""


def has_trusted_sso_headers(
    headers: Mapping[str, str],
    trusted_sso_headers: Mapping[str, str] = TRUSTED_SSO_HEADERS,
) -> bool:
    return any(header_value(headers, header) for header in trusted_sso_headers.values())


def trusted_sso_claims_from_headers(
    headers: Mapping[str, str],
    trusted_sso_headers: Mapping[str, str] = TRUSTED_SSO_HEADERS,
) -> dict[str, Any]:
    role_claims = split_header_claims(header_value(headers, trusted_sso_headers["role_claims"]))
    return {
        "provider": header_value(headers, trusted_sso_headers["provider"]),
        "external_subject_id": header_value(headers, trusted_sso_headers["external_subject_id"]),
        "external_email": header_value(headers, trusted_sso_headers["external_email"]),
        "organization_id": header_value(headers, trusted_sso_headers["organization_id"]),
        "team_ids": split_header_claims(header_value(headers, trusted_sso_headers["team_ids"])),
        "role_claims": role_claims,
        "role_key": role_claims[0] if role_claims else "",
    }


def split_header_claims(value: str) -> list[str]:
    normalized = str(value or "").replace(";", ",")
    return [chunk.strip() for chunk in normalized.split(",") if chunk.strip()]


def identity_override_fields(payload: Mapping[str, list[str]]) -> list[str]:
    return sorted(
        key
        for key in payload.keys()
        if str(key).strip() in WRITABLE_IDENTITY_FORM_FIELDS
        and list(payload.get(key, []) or [])
    )


def assert_no_identity_override_fields(payload: Mapping[str, list[str]]) -> None:
    reserved_fields = identity_override_fields(payload)
    if not reserved_fields:
        return
    raise ValueError(
        "Writable requests do not accept identity fields in form body: "
        + ", ".join(reserved_fields)
        + ". Use X-ASL-Actor or a stable session token instead."
    )
