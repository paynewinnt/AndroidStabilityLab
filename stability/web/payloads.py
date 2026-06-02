from __future__ import annotations

from typing import Any, Mapping, Sequence
from stability.time_utils import now_beijing_string
from stability.web.manifest import platform_surface as manifest_platform_surface


def _generated_at_now() -> str:
    return now_beijing_string()


def platform_surface() -> dict[str, list[dict[str, str]]]:
    return manifest_platform_surface()


def api_manifest_payload(
    *,
    portal_mode: str,
    deployment_label: str,
    public_base_url: str,
    callback_contract: Mapping[str, Any],
    performance_risk_detail_fields: Sequence[str],
    request_context: Mapping[str, Any] | None = None,
    surface: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
) -> dict[str, Any]:
    api_surface = dict(surface or platform_surface())
    request_meta = dict(dict(request_context or {}).get("request", {}) or {})
    return {
        "contract_version": "asl.api_manifest.v1",
        "api_version": "v1",
        "generated_at": _generated_at_now(),
        "portal_mode": portal_mode,
        "deployment_label": deployment_label,
        "public_base_url": public_base_url,
        "request": request_meta,
        "pages": list(api_surface.get("pages", []) or []),
        "read_endpoints": list(api_surface.get("api_endpoints", []) or []),
        "write_endpoints": [
            {
                **dict(item),
                "method": "POST",
                "identity_boundary": "server_resolved_identity",
                "request_id_headers": ["X-Request-ID", "X-ASL-Request-ID"],
            }
            for item in (api_surface.get("write_actions", []) or [])
        ],
        "response_boundary": {
            "request_id_headers": ["X-Request-ID", "X-ASL-Request-ID"],
            "portal_mode_header": "X-ASL-Portal-Mode",
            "ready_endpoint": "/ready",
            "health_endpoint": "/health",
            "security_headers_enabled": True,
        },
        "advanced_anomaly_fields": {
            "issue_fields": ["evidence_signals", "confirmation_level"],
            "attribution_fields": [
                "direction",
                "direction_label",
                "confidence",
                "confidence_score",
                "matched_rule_id",
                "matched_rule_ids",
                "evidence_summary",
                "recommended_next_steps",
                "review_notes",
            ],
            "performance_risk_fields": list(performance_risk_detail_fields),
            "compatibility": "Fields are included when the underlying service payload exposes them; older payloads remain valid.",
        },
        "rule_entrypoint_contract": {
            "contract_version": "asl.rule_entrypoint.v1",
            "read_endpoint": "/api/rules",
            "page": "/rules",
            "cli_commands": ["describe-rule-entrypoint", "preview-analysis-rule-update"],
            "write_policy": "preview_only_no_config_write",
        },
        "callback_contract": dict(callback_contract),
        "documentation_paths": {
            "platform_page": "/platform",
            "platform_api": "/api/platform",
            "manifest": "/api/manifest",
            "openapi": "/api/openapi.json",
            "rules": "/rules",
            "rules_api": "/api/rules",
        },
    }


def openapi_payload(
    *,
    portal_mode: str,
    public_base_url: str,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    read_paths = [
        str(item.get("path", "") or "")
        for item in manifest.get("read_endpoints", [])
        if str(item.get("path", "") or "")
    ]
    write_paths = [
        str(item.get("path", "") or "")
        for item in manifest.get("write_endpoints", [])
        if str(item.get("path", "") or "")
    ]
    paths: dict[str, Any] = {}
    for path in read_paths:
        paths[path] = {
            "get": {
                "summary": path,
                "responses": {
                    "200": {"description": "Successful JSON response"},
                },
            }
        }
    for path in write_paths:
        paths[path] = {
            "post": {
                "summary": path,
                "responses": {
                    "200": {"description": "Successful action response"},
                    "400": {"description": "Bad request"},
                    "403": {"description": "Permission denied"},
                },
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Android Stability Lab API",
            "version": "v1",
            "description": "Shared API manifest for the local-first Android Stability Lab portal.",
        },
        "servers": [{"url": public_base_url.rstrip("/")}],
        "x-asl-manifest-version": "asl.api_manifest.v1",
        "x-asl-portal-mode": portal_mode,
        "x-asl-callback-contract-version": dict(manifest["callback_contract"])["contract_version"],
        "paths": paths,
    }
