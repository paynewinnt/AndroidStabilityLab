"""Public wrapper for the ADB collector."""

from stability.infrastructure.adb import ADBCollector

STABLE_API_SHIM = True

__all__ = ["ADBCollector", "STABLE_API_SHIM"]
