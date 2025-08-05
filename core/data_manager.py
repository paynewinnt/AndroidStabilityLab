"""Retired data manager API stub."""

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "core.data_manager has been retired. "
    "Use stability app/repository services for active data access and orchestration."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class DataManager:
    """Retired API stub kept only to block direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


__all__ = [
    "DataManager",
    "RetiredModuleError",
    "STABLE_API_SHIM",
]
