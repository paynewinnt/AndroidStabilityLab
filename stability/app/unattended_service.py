from __future__ import annotations

from .unattended import (
    DeviceServiceLike,
    ExecutionServiceLike,
    LONG_RUN_TEMPLATES,
    LongRunPlan,
    LongRunTemplate,
    LongRunTemplateNotFound,
    RunExecutionServiceLike,
    TaskDefinitionLike,
    TaskRepository,
    UnattendedConfigMixin,
    UnattendedDailyReport,
    UnattendedPatrolSummary,
    UnattendedReportsMixin,
    UnattendedRotationMixin,
    UnattendedRoundExecutionMixin,
    UnattendedRoundExecutionResult,
    UnattendedSchedulerMixin,
    UnattendedTaskRecord,
    UnattendedTaskRecordNotFound,
    UnattendedTemplatesMixin,
    UnattendedWeeklyReport,
    _UnattendedConfig,
)


class UnattendedService(
    UnattendedTemplatesMixin,
    UnattendedSchedulerMixin,
    UnattendedRoundExecutionMixin,
    UnattendedReportsMixin,
    UnattendedConfigMixin,
    UnattendedRotationMixin,
):
    """Minimal V3 stage-1 backend loop over the existing V1 execution backbone."""

    ROOT_KEY = "unattended"
    _LONG_RUN_TEMPLATES = LONG_RUN_TEMPLATES

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        device_service: DeviceServiceLike,
        execution_service: ExecutionServiceLike,
        run_execution_service: RunExecutionServiceLike,
    ) -> None:
        self._task_repository = task_repository
        self._device_service = device_service
        self._execution_service = execution_service
        self._run_execution_service = run_execution_service


__all__ = [
    "DeviceServiceLike",
    "ExecutionServiceLike",
    "LongRunPlan",
    "LongRunTemplate",
    "LongRunTemplateNotFound",
    "RunExecutionServiceLike",
    "TaskDefinitionLike",
    "TaskRepository",
    "UnattendedDailyReport",
    "UnattendedPatrolSummary",
    "UnattendedRoundExecutionResult",
    "UnattendedService",
    "UnattendedTaskRecord",
    "UnattendedTaskRecordNotFound",
    "UnattendedWeeklyReport",
    "_UnattendedConfig",
]
