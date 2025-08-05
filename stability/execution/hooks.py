from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, DefaultDict, Dict, Iterable, List, Optional, Protocol, Sequence

from stability.time_utils import utcnow

from .plan import ExecutionPlan


class TaskDefinitionLike(Protocol):
    task_id: Optional[str]


class TaskRunLike(Protocol):
    run_id: Optional[str]


class ExecutionInstanceLike(Protocol):
    instance_id: Optional[str]


@dataclass(frozen=True)
class LifecycleHookContext:
    """Shared hook context for scenario, monitoring, issue, and artifact adapters."""

    stage: str
    task: TaskDefinitionLike
    run: TaskRunLike
    instance: Optional[ExecutionInstanceLike] = None
    plan: Optional[ExecutionPlan] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=utcnow)


LifecycleHook = Callable[[LifecycleHookContext], None]


class LifecycleHookRegistry:
    """Stage-based hook registry used by the V1 execution mainline."""

    def __init__(
        self,
        stage_hooks: Optional[Dict[str, Iterable[LifecycleHook]]] = None,
    ) -> None:
        self._hooks: DefaultDict[str, List[LifecycleHook]] = defaultdict(list)
        for stage, hooks in (stage_hooks or {}).items():
            for hook in hooks:
                self.register(stage, hook)

    def register(self, stage: str, hook: LifecycleHook) -> None:
        self._hooks[stage].append(hook)

    def register_many(self, stage: str, hooks: Iterable[LifecycleHook]) -> None:
        for hook in hooks:
            self.register(stage, hook)

    def dispatch(self, context: LifecycleHookContext) -> None:
        for hook in self._hooks.get(context.stage, []):
            hook(context)

    def dispatch_stage(
        self,
        stage: str,
        *,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: Optional[ExecutionInstanceLike] = None,
        plan: Optional[ExecutionPlan] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.dispatch(
            LifecycleHookContext(
                stage=stage,
                task=task,
                run=run,
                instance=instance,
                plan=plan,
                payload=payload or {},
            )
        )

    def registered_stages(self) -> Sequence[str]:
        return tuple(sorted(self._hooks.keys()))
