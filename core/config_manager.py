"""Retired config manager API stub.

This module no longer owns active configuration logic. Use the typed config
files under `config/` together with the providers in `stability/`.
"""

# RETIRED MODULE — scheduled for removal in 2026-Q3.
# No code in the project imports this module anymore.
# If you are reading this after 2026-Q3, this file can be safely deleted.

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "core.config_manager has been retired. "
    "Use config/*.json directly or the providers under stability.infrastructure."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class ConfigManager:
    """Retired API stub kept only to fail fast on direct use."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


__all__ = [
    "ConfigManager",
    "RetiredModuleError",
    "STABLE_API_SHIM",
]
