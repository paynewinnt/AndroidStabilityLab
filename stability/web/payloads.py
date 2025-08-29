from __future__ import annotations

from typing import Any, Mapping, Sequence
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


def platform_surface() -> dict[str, list[dict[str, str]]]:
    return {
        "pages": [
            {"label": "首页", "path": "/"},
            {"label": "平台说明", "path": "/platform"},
            {"label": "诊断中心", "path": "/doctor"},
            {"label": "设备池", "path": "/device-pools"},
            {"label": "快捷 ADB", "path": "/quick-adb"},
            {"label": "任务大厅", "path": "/tasks"},
            {"label": "Run 列表", "path": "/runs"},
            {"label": "长稳模板", "path": "/long-run-templates"},
            {"label": "性能采样", "path": "/performance"},
            {"label": "产物中心", "path": "/artifacts"},
            {"label": "问题中心", "path": "/issues"},
            {"label": "巡检状态", "path": "/runner"},
            {"label": "集成 Outbox", "path": "/integration"},
            {"label": "Golden Suite", "path": "/goldens"},
            {"label": "准入中心", "path": "/admission"},
            {"label": "规则中心", "path": "/rules"},
            {"label": "接口中心", "path": "/json-api"},
        ],
        "api_endpoints": [
            {"label": "平台说明", "path": "/api/platform"},
            {"label": "平台健康", "path": "/api/platform-health"},
            {"label": "诊断中心", "path": "/api/doctor"},
            {"label": "API Manifest", "path": "/api/manifest"},
            {"label": "OpenAPI", "path": "/api/openapi.json"},
            {"label": "首页摘要", "path": "/api/home"},
            {"label": "用户目录", "path": "/api/users"},
            {"label": "责任同步", "path": "/api/responsibility"},
            {"label": "设备池", "path": "/api/device-pools"},
            {"label": "快捷 ADB", "path": "/api/quick-adb"},
            {"label": "快捷 ADB 包名查询", "path": "/api/quick-adb/packages"},
            {"label": "任务大厅", "path": "/api/tasks"},
            {"label": "Run 列表", "path": "/api/runs"},
            {"label": "长稳模板", "path": "/api/long-run-templates"},
            {"label": "性能采样", "path": "/api/performance"},
            {"label": "产物中心", "path": "/api/artifacts"},
            {"label": "提测请求", "path": "/api/release-submissions"},
            {"label": "集成 Outbox", "path": "/api/integration"},
            {"label": "问题中心", "path": "/api/issues"},
            {"label": "巡检状态", "path": "/api/runner"},
            {"label": "Golden Suite", "path": "/api/goldens"},
            {"label": "准入中心", "path": "/api/admission"},
            {"label": "Admission Cases", "path": "/api/admission/cases"},
            {"label": "Admission Reports", "path": "/api/admission/reports/<baseline_key>"},
            {"label": "规则中心", "path": "/api/rules"},
            {"label": "集成 Outbox 事件", "path": "/api/integration/outbox"},
            {"label": "Ready", "path": "/ready"},
            {"label": "Health", "path": "/health"},
        ],
        "write_actions": [
            {"label": "创建任务", "path": "/api/tasks/actions/create-task"},
            {"label": "创建 Run", "path": "/api/tasks/actions/create-run"},
            {"label": "执行 Run", "path": "/api/tasks/actions/execute-run"},
            {"label": "配置无人值守", "path": "/api/runner/actions/configure-unattended"},
            {"label": "巡检", "path": "/api/runner/actions/patrol-unattended"},
            {"label": "刷新设备", "path": "/api/device-pools/actions/refresh"},
            {"label": "连接设备", "path": "/api/device-pools/actions/connect"},
            {"label": "无线配对并连接设备", "path": "/api/device-pools/actions/pair-connect"},
            {"label": "设备标记", "path": "/api/device-pools/actions/update-profile"},
            {"label": "执行快捷 ADB", "path": "/api/quick-adb/actions/execute"},
            {"label": "创建提测请求", "path": "/api/release-submissions/actions/create"},
            {"label": "问题协作", "path": "/api/issues/actions/assign"},
            {"label": "准入协作", "path": "/api/admission/actions/transition"},
            {"label": "集成 worker", "path": "/api/integration/actions/run-worker"},
        ],
    }


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
