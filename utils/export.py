"""Retired export API stub."""

STABLE_API_SHIM = True

_RETIREMENT_MESSAGE = (
    "utils.export has been retired. "
    "Use stability.app.report_service and the stability Web/CLI entry points "
    "for active report generation and export workflows."
)


class RetiredModuleError(RuntimeError):
    """Raised when a retired module is used."""


class DataExporter:
    """Retired data exporter API stub."""

    def __init__(self, *args, **kwargs) -> None:
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


class _RetiredExporterProxy:
    """Proxy kept only to fail fast on direct use."""

    def __getattr__(self, name):
        raise RetiredModuleError(_RETIREMENT_MESSAGE)


data_exporter = _RetiredExporterProxy()


__all__ = [
    "DataExporter",
    "RetiredModuleError",
    "STABLE_API_SHIM",
    "data_exporter",
]
