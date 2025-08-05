from __future__ import annotations

import argparse

from stability.infrastructure import SUPPORTED_MONITORING_BACKENDS


def _add_monitoring_backend_override_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--monitoring-backend",
        default="default",
        choices=["default", *SUPPORTED_MONITORING_BACKENDS],
        help="Override monitoring backend for this execution. Default uses config/monitoring.json.",
    )
