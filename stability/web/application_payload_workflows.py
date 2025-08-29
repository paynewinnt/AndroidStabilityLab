from __future__ import annotations

from .features.admission.workflow_payload import AdmissionWorkflowPayloadMixin
from .features.runner.payload import RunnerPayloadMixin


class ApplicationPayloadWorkflowsMixin(RunnerPayloadMixin, AdmissionWorkflowPayloadMixin):
    """Compatibility mixin for legacy imports from ``stability.web.application_payload_workflows``."""


__all__ = ["ApplicationPayloadWorkflowsMixin"]
