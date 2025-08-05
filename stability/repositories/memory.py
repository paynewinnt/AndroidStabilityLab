from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from stability.domain import (
    Device,
    DeviceAvailabilityState,
    ExecutionInstance,
    TaskDefinition,
    TaskRun,
)
from stability.execution.plan import DispatchItem


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskDefinition] = {}

    def add(self, task: TaskDefinition) -> TaskDefinition:
        self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> Optional[TaskDefinition]:
        return self._tasks.get(task_id)

    def list(self) -> Sequence[TaskDefinition]:
        return tuple(self._tasks.values())

    def save(self, task: TaskDefinition) -> TaskDefinition:
        self._tasks[task.task_id] = task
        return task


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self._devices: Dict[str, Device] = {}

    def add(self, device: Device) -> Device:
        self._devices[device.device_id] = device
        return device

    def get(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)

    def list(self) -> Sequence[Device]:
        return tuple(self._devices.values())

    def save(self, device: Device) -> Device:
        self._devices[device.device_id] = device
        return device


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._runs: Dict[str, TaskRun] = {}

    def add(self, run: TaskRun) -> TaskRun:
        self._runs[run.run_id] = run
        return run

    def save(self, run: TaskRun) -> TaskRun:
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[TaskRun]:
        return self._runs.get(run_id)

    def list(self) -> Sequence[TaskRun]:
        return tuple(self._runs.values())


class InMemoryInstanceRepository:
    def __init__(self) -> None:
        self._instances: Dict[str, ExecutionInstance] = {}

    def add_many(self, instances: Sequence[ExecutionInstance]) -> Sequence[ExecutionInstance]:
        for instance in instances:
            self._instances[instance.instance_id] = instance
        return tuple(instances)

    def save(self, instance: ExecutionInstance) -> ExecutionInstance:
        self._instances[instance.instance_id] = instance
        return instance

    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstance]:
        return tuple(instance for instance in self._instances.values() if instance.run_id == run_id)


@dataclass
class StaticDevicePlanner:
    devices: Dict[str, Device] = field(default_factory=dict)

    def select_devices(
        self,
        task: TaskDefinition,
        requested_devices: Optional[Sequence[str]] = None,
    ) -> Sequence[str]:
        device_ids = list(requested_devices or task.selected_device_ids)
        if device_ids:
            return tuple(device_id for device_id in device_ids if device_id in self.devices)
        return tuple(
            device.device_id
            for device in self.devices.values()
            if device.is_online() and device.availability_state == DeviceAvailabilityState.IDLE
        )


class DomainTaskRunFactory:
    def create_run(
        self,
        task: TaskDefinition,
        planned_device_count: int,
        target_device_ids: Optional[Sequence[str]] = None,
        requested_by: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> TaskRun:
        return TaskRun(
            task_definition_id=task.task_id,
            task_name=task.task_name,
            planned_device_count=planned_device_count,
            target_device_ids=list(target_device_ids or task.selected_device_ids),
            started_by=requested_by or task.created_by,
            metadata=dict(metadata or {}),
        )


@dataclass
class DomainExecutionInstanceFactory:
    devices: Dict[str, Device] = field(default_factory=dict)

    def create_instance(
        self,
        task: TaskDefinition,
        run: TaskRun,
        dispatch: DispatchItem,
    ) -> ExecutionInstance:
        device = self.devices.get(dispatch.device_id)
        snapshot = device.snapshot() if device is not None else None
        return ExecutionInstance(
            run_id=run.run_id,
            task_definition_id=task.task_id,
            device_id=dispatch.device_id,
            device_snapshot=snapshot,
            template_type=task.template_type,
            target_app_package=task.target_app.package_name,
            metadata=dict(dispatch.payload),
        )
