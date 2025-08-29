from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Sequence, Set

from stability.time_utils import utcnow


class TaskRunLike(Protocol):
    run_status: Optional[str]


class ExecutionInstanceLike(Protocol):
    instance_status: Optional[str]


class ExecutionTransitionError(ValueError):
    """Raised when a run or instance transition is invalid."""


class ExecutionStateMachine:
    """Centralized run and instance lifecycle transitions for the V1 execution pipeline."""

    DEFAULT_INSTANCE_TRANSITIONS: Dict[Optional[str], Set[str]] = {
        None: {"pending"},
        "pending": {"preparing", "running", "stopping", "failed", "cancelled"},
        "preparing": {"running", "stopping", "failed", "cancelled"},
        "running": {"stopping", "collecting", "success", "failed", "cancelled"},
        "stopping": {"cancelled", "failed"},
        "collecting": {"stopping", "success", "failed", "cancelled"},
        "success": set(),
        "failed": set(),
        "cancelled": set(),
    }

    DEFAULT_RUN_TRANSITIONS: Dict[Optional[str], Set[str]] = {
        None: {"queued"},
        "draft": {"queued", "cancelled"},
        "queued": {"running", "success", "partial_failed", "failed", "cancelled"},
        "running": {"success", "partial_failed", "failed", "cancelled"},
        "success": set(),
        "partial_failed": set(),
        "failed": set(),
        "cancelled": set(),
    }

    TERMINAL_INSTANCE_STATES = {"success", "failed", "cancelled"}
    TERMINAL_RUN_STATES = {"success", "partial_failed", "failed", "cancelled"}

    def __init__(
        self,
        instance_transitions: Optional[Dict[Optional[str], Set[str]]] = None,
        run_transitions: Optional[Dict[Optional[str], Set[str]]] = None,
    ) -> None:
        self._instance_transitions = instance_transitions or self.DEFAULT_INSTANCE_TRANSITIONS
        self._run_transitions = run_transitions or self.DEFAULT_RUN_TRANSITIONS

    def can_transition_instance(self, current: Optional[str], target: str) -> bool:
        return target in self._instance_transitions.get(current, set())

    def can_transition_run(self, current: Optional[str], target: str) -> bool:
        return target in self._run_transitions.get(current, set())

    def transition_instance(
        self,
        instance: ExecutionInstanceLike,
        target: str,
        *,
        exit_reason: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> ExecutionInstanceLike:
        current = self._get_instance_status(instance)
        if current == target:
            return instance
        if not self.can_transition_instance(current, target):
            raise ExecutionTransitionError(
                f"Invalid instance transition: {current!r} -> {target!r}"
            )
        now = occurred_at or utcnow()
        self._set_instance_status(instance, target)
        if target in {"preparing", "running"} and not getattr(instance, "started_at", None):
            setattr(instance, "started_at", now)
        if current is None and not getattr(instance, "queued_at", None):
            setattr(instance, "queued_at", now)
        if target in self.TERMINAL_INSTANCE_STATES:
            setattr(instance, "finished_at", now)
        if exit_reason is not None:
            self._set_optional_enum_attr(instance, "exit_reason", exit_reason)
        if summary is not None:
            self._apply_summary(instance, summary)
        return instance

    def transition_run(
        self,
        run: TaskRunLike,
        target: str,
        *,
        summary: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> TaskRunLike:
        current = self._get_run_status(run)
        if current == target:
            return run
        if not self.can_transition_run(current, target):
            raise ExecutionTransitionError(f"Invalid run transition: {current!r} -> {target!r}")
        now = occurred_at or utcnow()
        self._set_run_status(run, target)
        if target == "running" and not getattr(run, "started_at", None):
            setattr(run, "started_at", now)
        if target in self.TERMINAL_RUN_STATES:
            setattr(run, "finished_at", now)
        if summary is not None:
            self._apply_summary(run, summary)
        return run

    def derive_run_status(self, instances: Sequence[ExecutionInstanceLike]) -> Optional[str]:
        if not instances:
            return None

        statuses = [self._get_instance_status(instance) for instance in instances]
        pending_states = {"pending", "preparing"}
        running_states = {"running", "stopping", "collecting"}
        terminal_states = self.TERMINAL_INSTANCE_STATES

        if any(status in running_states for status in statuses):
            return "running"
        if all(status == "success" for status in statuses):
            return "success"
        if all(status == "failed" for status in statuses):
            return "failed"
        if all(status == "cancelled" for status in statuses):
            return "cancelled"
        if any(status in terminal_states for status in statuses) and any(
            status == "success" for status in statuses
        ):
            return "partial_failed"
        if any(status == "failed" for status in statuses) and any(
            status in {"success", "cancelled"} for status in statuses
        ):
            return "partial_failed"
        if all(status in terminal_states for status in statuses):
            return "partial_failed"
        if any(status in pending_states for status in statuses):
            return "queued"
        return "queued"

    @staticmethod
    def _get_instance_status(instance: ExecutionInstanceLike) -> Optional[str]:
        return getattr(instance, "instance_status", getattr(instance, "status", None))

    @staticmethod
    def _set_instance_status(instance: ExecutionInstanceLike, target: str) -> None:
        if hasattr(instance, "instance_status"):
            setattr(instance, "instance_status", target)
            return
        setattr(instance, "status", target)

    @staticmethod
    def _get_run_status(run: TaskRunLike) -> Optional[str]:
        return getattr(run, "run_status", getattr(run, "status", None))

    @staticmethod
    def _set_run_status(run: TaskRunLike, target: str) -> None:
        if hasattr(run, "run_status"):
            setattr(run, "run_status", target)
            return
        setattr(run, "status", target)

    @staticmethod
    def _apply_summary(target_obj: Any, summary: Dict[str, Any]) -> None:
        if hasattr(target_obj, "apply_summary_payload"):
            target_obj.apply_summary_payload(summary)
            return
        setattr(target_obj, "summary", summary)

    @staticmethod
    def _set_optional_enum_attr(target_obj: Any, attr_name: str, value: Any) -> None:
        current_value = getattr(target_obj, attr_name, None)
        enum_type = current_value.__class__ if hasattr(current_value, "value") else None
        if enum_type is not None:
            try:
                setattr(target_obj, attr_name, enum_type(value))
                return
            except Exception:
                pass
        setattr(target_obj, attr_name, value)
