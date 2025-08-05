"""Stable top-level package for core-facing imports.

The active Android Stability Lab implementation lives under `stability/`.
Modules in this package intentionally expose only narrow public API shims for
older import paths that may still be referenced by local tooling.

Current status:
- `adb_collector.py`: public wrapper for the ADB collector
- `config_manager.py`: retired API stub
- `data_manager.py`: retired API stub
- `optimized_config.py`: retired API stub
- `performance_monitor.py`: retired API stub
"""

STABLE_API_SHIM = True

__all__ = ["STABLE_API_SHIM"]
