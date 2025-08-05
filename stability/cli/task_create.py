from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
from typing import Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.domain import AppError, normalize_app_error
from stability.cli.handlers.web import handle_serve_web as _web_handle_serve_web
from stability.cli.parser import build_parser as _build_parser
from stability.web import serve_web_portal

_IMPL_MODULE_NAMES = (
    "stability.cli.handlers.task_lifecycle",
    "stability.cli.handlers.analysis_queries",
    "stability.cli.handlers.analysis_rules",
    "stability.cli.handlers.admission",
    "stability.cli.handlers.integration_webhooks",
    "stability.cli.handlers.integration_delivery",
    "stability.cli.handlers.integration_workers",
    "stability.cli.handlers.runtime_lifecycle",
    "stability.cli.utils",
    "stability.cli.payloads_analysis",
    "stability.cli.payloads_rules",
    "stability.cli.payloads_admission",
    "stability.cli.payloads_longrun",
)
_IMPL_MODULES = tuple(importlib.import_module(name) for name in _IMPL_MODULE_NAMES)


def _is_exportable_symbol(name: str, value: object) -> bool:
    if name.startswith("__"):
        return False
    if name in {"argparse", "json", "sys", "time", "inspect", "importlib"}:
        return False
    return inspect.isfunction(value) or inspect.isclass(value)


def _export_impl_symbols() -> None:
    for module in _IMPL_MODULES:
        for name, value in vars(module).items():
            if _is_exportable_symbol(name, value):
                globals()[name] = value


def _sync_facade_symbols_to_impl() -> None:
    for module in _IMPL_MODULES:
        module_dict = vars(module)
        for name, value in list(globals().items()):
            if name.startswith("__") or name in {"_IMPL_MODULES", "_IMPL_MODULE_NAMES"}:
                continue
            if _is_exportable_symbol(name, value) or name in module_dict:
                module_dict[name] = value


def build_parser() -> argparse.ArgumentParser:
    """Create the V1 CLI parser while keeping the legacy import path stable."""
    _sync_facade_symbols_to_impl()
    return _build_parser(handler_module=sys.modules[__name__])


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the selected command handler."""
    _sync_facade_symbols_to_impl()
    parser = build_parser()
    args = parser.parse_args(argv)
    _sync_facade_symbols_to_impl()
    try:
        return args.handler(args)
    except AppError as exc:
        print(json.dumps({"error": exc.to_dict()}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except (ValueError, PermissionError, LookupError) as exc:
        error = normalize_app_error(exc)
        print(json.dumps({"error": error.to_dict()}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


def _handle_serve_web(args: argparse.Namespace) -> int:
    """Compatibility wrapper for the serve-web handler group."""
    _sync_facade_symbols_to_impl()
    return _web_handle_serve_web(
        args,
        create_persistent_bootstrap=create_v1_persistent_bootstrap,
        serve_web_portal_func=serve_web_portal,
        sync_devices_func=_maybe_sync_devices,
        is_local_web_host_func=_is_local_web_host,
    )


_export_impl_symbols()
_sync_facade_symbols_to_impl()
