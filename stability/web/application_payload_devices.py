from __future__ import annotations

from .features.devices.payload import DevicesPayloadMixin
from .features.integration.payload import IntegrationPayloadMixin
from .features.performance.payload import PerformancePayloadMixin
from .features.tasks.payload import TasksPayloadMixin


class ApplicationPayloadDevicesMixin(
    DevicesPayloadMixin,
    TasksPayloadMixin,
    PerformancePayloadMixin,
    IntegrationPayloadMixin,
):
    """Compatibility mixin for legacy imports from ``stability.web.application_payload_devices``."""


__all__ = ["ApplicationPayloadDevicesMixin"]
