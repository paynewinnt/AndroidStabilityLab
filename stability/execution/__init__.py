"""Execution pipeline primitives for Android Stability Lab."""

from .hooks import LifecycleHookContext, LifecycleHookRegistry
from .plan import DispatchItem, ExecutionPlan, build_execution_plan
from .state_machine import ExecutionStateMachine, ExecutionTransitionError

__all__ = [
    "DispatchItem",
    "ExecutionPlan",
    "ExecutionStateMachine",
    "ExecutionTransitionError",
    "LifecycleHookContext",
    "LifecycleHookRegistry",
    "build_execution_plan",
]
