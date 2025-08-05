"""Retired optimized config API stub."""

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "core.optimized_config has been retired. "
    "Use the active configuration files under config/ and stability-owned providers instead."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class OptimizedConfigManager:
    """Retired API stub kept only to block direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


optimized_config = None


__all__ = [
    "OptimizedConfigManager",
    "RetiredModuleError",
    "STABLE_API_SHIM",
    "optimized_config",
]
