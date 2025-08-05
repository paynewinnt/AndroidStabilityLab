"""Retired database operations API stub."""

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "database.operations has been retired. "
    "Use stability.app.run_history_service, report_service, snapshot_service, "
    "and persistence-backed repositories instead."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class DatabaseOperations:
    """Retired API stub kept only to block direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


__all__ = [
    "DatabaseOperations",
    "RetiredModuleError",
    "STABLE_API_SHIM",
]
