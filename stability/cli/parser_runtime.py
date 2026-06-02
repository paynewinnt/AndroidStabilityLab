from __future__ import annotations

import argparse


def register_runtime_commands(subparsers: argparse._SubParsersAction, handler_module: object) -> None:
    platform_doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run full local platform diagnostics for Python, ADB, runtime, Web, monitoring and outbox.",
    )
    platform_doctor_parser.add_argument("--runtime-root", default=None, help="Runtime root directory. Default: ConfigProvider runtime.root or runtime")
    platform_doctor_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR")
    platform_doctor_parser.add_argument("--web-host", default=None, help="Web host to probe. Default: ConfigProvider web.host or 127.0.0.1")
    platform_doctor_parser.add_argument("--web-port", type=int, default=None, help="Web port to probe. Default: ConfigProvider web.port or 8030")
    platform_doctor_parser.add_argument(
        "--device-id",
        default="",
        help="Optional target device serial for deep diagnostics, for example 192.168.31.99:5555.",
    )
    platform_doctor_parser.add_argument(
        "--package-name",
        default="",
        help="Optional package name to verify on the target device when --device-id is provided.",
    )
    platform_doctor_parser.add_argument(
        "--outbox-root",
        default=None,
        help="Integration outbox root. Default: ConfigProvider outbox.root_dir or runtime/integration_outbox",
    )
    platform_doctor_parser.add_argument(
        "--check-webhooks",
        action="store_true",
        help="Send explicit diagnostic pings to configured IM webhooks. Default is config-only validation.",
    )
    platform_doctor_parser.set_defaults(handler=handler_module._handle_doctor)

    platform_health_parser = subparsers.add_parser(
        "platform-health",
        help="Record and print the persisted platform self-monitoring snapshot.",
    )
    platform_health_parser.add_argument("--runtime-root", default=None, help="Runtime root directory. Default: ConfigProvider runtime.root or runtime")
    platform_health_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR")
    platform_health_parser.add_argument(
        "--no-record",
        action="store_true",
        help="Calculate the snapshot without appending it to runtime/platform_health/snapshots.json.",
    )
    platform_health_parser.add_argument(
        "--publish-alert",
        action="store_true",
        help="When the snapshot reaches the configured alert threshold, publish a platform-health alert event to integration outbox.",
    )
    platform_health_parser.set_defaults(handler=handler_module._handle_platform_health)

    doctor_parser = subparsers.add_parser(
        "runtime-doctor",
        help="Inspect local runtime data size, category coverage and basic health.",
    )
    doctor_parser.add_argument("--runtime-root", default=None, help="Runtime root directory. Default: ConfigProvider runtime.root or runtime")
    doctor_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR")
    doctor_parser.set_defaults(handler=handler_module._handle_runtime_doctor)

    export_parser = subparsers.add_parser(
        "export-runtime",
        help="Export selected local runtime categories into a zip archive.",
    )
    export_parser.add_argument("--runtime-root", default=None, help="Runtime root directory. Default: ConfigProvider runtime.root or runtime")
    export_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR")
    export_parser.add_argument("--output", required=True, help="Output zip path or target directory.")
    export_parser.add_argument(
        "--category",
        dest="categories",
        action="append",
        default=[],
        help="Runtime category to include. Repeat or comma-separate. Defaults to all.",
    )
    export_parser.set_defaults(handler=handler_module._handle_export_runtime)

    cleanup_parser = subparsers.add_parser(
        "cleanup-runtime",
        help="Find or delete old runtime data. Defaults to dry-run.",
    )
    cleanup_parser.add_argument("--runtime-root", default=None, help="Runtime root directory. Default: ConfigProvider runtime.root or runtime")
    cleanup_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR")
    cleanup_parser.add_argument("--max-age-days", type=int, default=14, help="Delete candidates older than N days.")
    cleanup_parser.add_argument(
        "--category",
        dest="categories",
        action="append",
        default=[],
        help="Runtime category to clean. Repeat or comma-separate. Defaults to all.",
    )
    cleanup_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete candidates. Omit this flag for safe dry-run.",
    )
    cleanup_parser.set_defaults(handler=handler_module._handle_cleanup_runtime)

    evidence_parser = subparsers.add_parser(
        "cleanup-evidence",
        help="Apply per-evidence-type retention (age + size cap) to runtime/tasks. Defaults to dry-run.",
    )
    evidence_parser.add_argument("--runtime-root", default=None, help="Runtime root directory. Default: ConfigProvider runtime.root or runtime")
    evidence_parser.add_argument("--config-dir", default="config", help="Config directory. Default: config or ASL_CONFIG_DIR")
    evidence_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete candidates. Omit this flag for safe dry-run.",
    )
    evidence_parser.set_defaults(handler=handler_module._handle_cleanup_evidence)
