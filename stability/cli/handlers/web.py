from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from stability.app import ConfigProvider
from stability import create_v1_persistent_bootstrap
from stability.web import serve_web_portal


BootstrapFactory = Callable[[], object]
ServeWebPortal = Callable[..., object]
SyncDevices = Callable[[object], dict[str, object] | None]
IsLocalWebHost = Callable[[str], bool]


def handle_serve_web(
    args: argparse.Namespace,
    *,
    create_persistent_bootstrap: BootstrapFactory = create_v1_persistent_bootstrap,
    serve_web_portal_func: ServeWebPortal = serve_web_portal,
    sync_devices_func: SyncDevices | None = None,
    is_local_web_host_func: IsLocalWebHost | None = None,
) -> int:
    """Start the dependency-free V3 Web portal backed by the persistent runtime bundle."""
    is_local_web_host = is_local_web_host_func or _is_local_web_host
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    web_config = provider.web()
    host = str(getattr(args, "host", None) or web_config.host)
    port = int(getattr(args, "port", None) or web_config.port)
    allow_remote_access = bool(getattr(args, "allow_remote_access", False) or web_config.allow_remote_access)
    portal_mode = str(getattr(args, "portal_mode", None) or web_config.portal_mode)
    public_base_url = str(getattr(args, "public_base_url", None) or web_config.public_base_url).strip()
    deployment_label = str(getattr(args, "deployment_label", None) or web_config.deployment_label).strip()
    sync_devices_on_start = bool(getattr(args, "sync_devices_on_start", False) or web_config.sync_devices_on_start)
    if not is_local_web_host(host) and not allow_remote_access:
        raise SystemExit(
            "Refusing to bind Web portal to a non-local host without --allow-remote-access. "
            "The current portal is designed as a local ops console and does not provide production-grade auth or authorization."
        )
    if portal_mode == "team_entry" and not public_base_url:
        raise SystemExit(
            "team_entry mode requires --public-base-url so the shared team entry can publish a stable external address."
        )
    local_base_url = f"http://{host}:{port}/"
    bundle = create_persistent_bootstrap(config_provider=provider)
    sync_devices = sync_devices_func or _maybe_sync_devices
    sync_payload = sync_devices(bundle, enabled=sync_devices_on_start)
    payload: dict[str, Any] = {
        "storage_mode": "persistent",
        "web": {
            "title": "Android Stability Lab Web Portal",
            "mode": portal_mode,
            "host": host,
            "port": port,
            "allow_remote_access": allow_remote_access,
            "deployment_label": deployment_label,
            "public_base_url": public_base_url or local_base_url,
            "local_base_url": local_base_url,
            "team_boundary_version": "team_portal_boundary_v1",
            "warning": (
                "Shared team entry mode enabled. Read surfaces stay unified for all viewers; write actions still rely on server-resolved identity, request ids, and audit records."
                if portal_mode == "team_entry"
                else "Remote access explicitly enabled; this portal still lacks production-grade auth, authorization, and audit boundaries."
                if allow_remote_access
                else "Bound to a local interface by default; this portal is intended for local ops and triage."
            ),
            "url": public_base_url or local_base_url,
            "pages": [
                "/",
                "/platform",
                "/tasks",
                "/runs",
                "/long-run-templates",
                "/performance",
                "/artifacts",
                "/issues",
                "/runner",
                "/integration",
                "/goldens",
                "/admission",
                "/json-api",
            ],
            "api_endpoints": [
                "/api/platform",
                "/api/manifest",
                "/api/openapi.json",
                "/api/home",
                "/api/tasks",
                "/api/runs",
                "/api/long-run-templates",
                "/api/performance",
                "/api/artifacts",
                "/api/integration",
                "/api/issues",
                "/api/runner",
                "/api/goldens",
                "/api/admission",
                "/api/admission/cases",
                "/api/admission/reports/<baseline_key>",
                "/api/integration/outbox",
                "/ready",
                "/health",
            ],
        },
        "device_sync": sync_payload,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    serve_web_portal_func(
        host=host,
        port=port,
        bundle=bundle,
        allow_remote_access=allow_remote_access,
        portal_mode=portal_mode,
        public_base_url=public_base_url,
        deployment_label=deployment_label,
    )
    return 0


def _is_local_web_host(host: str) -> bool:
    value = str(host or "").strip().lower()
    if value in {"127.0.0.1", "localhost", "::1"}:
        return True
    return value.startswith("127.")


def _maybe_sync_devices(
    bundle: object,
    *,
    enabled: bool,
    target_device_id: str = "",
) -> dict[str, object] | None:
    if (not enabled and not target_device_id) or getattr(bundle, "device_service", None) is None:
        return None
    if target_device_id:
        synced_device = bundle.device_service.sync_device(target_device_id)
        return {
            "mode": "target_device",
            "target_device_id": target_device_id,
            "found": synced_device is not None,
            "updated_device_id": getattr(synced_device, "device_id", None),
        }

    sync_result = bundle.device_service.sync_devices(include_unavailable=True, mark_missing_offline=True)
    return {
        "mode": "full_registry",
        "scanned_count": sync_result.scanned_count,
        "created_count": len(sync_result.created),
        "updated_count": len(sync_result.updated),
        "refreshed_count": len(sync_result.refreshed),
        "marked_offline_count": len(sync_result.marked_offline),
    }
