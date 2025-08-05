"""Retired database maintenance API stub."""

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "database.maintenance has been retired. "
    "Use persistence and runtime management flows under stability/ instead."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class DatabaseMaintenanceTools:
    """Retired API stub kept only to block direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


__all__ = [
    "DatabaseMaintenanceTools",
    "RetiredModuleError",
    "STABLE_API_SHIM",
]
