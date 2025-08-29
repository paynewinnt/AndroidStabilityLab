from __future__ import annotations

from .features.devices.actions import DevicesActionsMixin
from .features.runner.actions import RunnerActionsMixin
from .features.tasks.actions import TasksActionsMixin


class ApplicationTaskActionsMixin(TasksActionsMixin, RunnerActionsMixin, DevicesActionsMixin):
    """Compatibility mixin for legacy imports from ``stability.web.application_actions_tasks``."""


__all__ = ["ApplicationTaskActionsMixin"]
