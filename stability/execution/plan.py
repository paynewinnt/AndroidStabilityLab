from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence


class TaskDefinitionLike(Protocol):
    task_id: Optional[str]


@dataclass(frozen=True)
class DispatchItem:
    """One device-targeted dispatch produced from a V1 task run."""

    device_id: str
    order_index: int
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    """Minimal plan object shared by services, GUI adapters, and future CLI entry points."""

    task: TaskDefinitionLike
    requested_devices: Sequence[str]
    dispatches: Sequence[DispatchItem]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def planned_device_count(self) -> int:
        return len(self.dispatches)


def build_dispatch_items(
    device_ids: Iterable[str],
    payload_by_device: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[DispatchItem]:
    """Expand device ids into stable dispatch items."""
    dispatches: List[DispatchItem] = []
    seen = set()
    for index, device_id in enumerate(device_ids):
        if not device_id or device_id in seen:
            continue
        seen.add(device_id)
        dispatches.append(
            DispatchItem(
                device_id=device_id,
                order_index=index,
                payload=dict((payload_by_device or {}).get(device_id, {})),
            )
        )
    return dispatches


def build_execution_plan(
    task: TaskDefinitionLike,
    device_ids: Iterable[str],
    metadata: Optional[Dict[str, Any]] = None,
    payload_by_device: Optional[Dict[str, Dict[str, Any]]] = None,
) -> ExecutionPlan:
    """Create a V1 execution plan from a task definition and selected devices."""
    requested_devices = [device_id for device_id in device_ids if device_id]
    dispatches = build_dispatch_items(requested_devices, payload_by_device=payload_by_device)
    return ExecutionPlan(
        task=task,
        requested_devices=tuple(requested_devices),
        dispatches=tuple(dispatches),
        metadata=dict(metadata or {}),
    )
