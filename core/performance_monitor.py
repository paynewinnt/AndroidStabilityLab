"""Retired performance monitor API stub."""

# RETIRED MODULE — scheduled for removal in 2026-Q3.
# No code in the project imports this module anymore.
# If you are reading this after 2026-Q3, this file can be safely deleted.

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "core.performance_monitor has been retired. "
    "Use stability execution/reporting/analysis services for active runtime observability."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class PerformanceMonitor:
    """Retired API stub kept only to block direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


class PerformanceDecorator:
    """Retired API stub kept only to block direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


performance_monitor = None


def monitor_performance(metric_name: str):
    """Retired decorator helper."""

    raise RetiredModuleError(_RETIREMENT_MESSAGE)


__all__ = [
    "PerformanceDecorator",
    "PerformanceMonitor",
    "RetiredModuleError",
    "STABLE_API_SHIM",
    "monitor_performance",
    "performance_monitor",
]
