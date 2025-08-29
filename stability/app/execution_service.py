from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

from stability.execution.hooks import LifecycleHookContext, LifecycleHookRegistry
from stability.execution.plan import DispatchItem, ExecutionPlan, build_execution_plan
from stability.execution.state_machine import ExecutionStateMachine
from stability.time_utils import utcnow


class TaskDefinitionLike(Protocol):
    """Minimal task shape required by the execution service."""

    task_id: Optional[str]
    task_name: str
    target_app: str | None


class TaskRunLike(Protocol):
    """Minimal run shape required by the execution service."""

    run_id: Optional[str]
    run_status: Optional[str]


class ExecutionInstanceLike(Protocol):
    """Minimal execution-instance shape required by the execution service."""

    instance_id: Optional[str]
    device_id: str
    instance_status: str
    issues: list | tuple
    artifacts: list | tuple
    summary: Any | None
    exit_reason: str | None
    result_level: str | None


class TaskPlanner(Protocol):
    """Selects devices for a task within the V1 local-execution boundary."""

    def select_devices(
        self,
        task: TaskDefinitionLike,
        requested_devices: Optional[Sequence[str]] = None,
    ) -> Sequence[str]:
        ...


class TaskRunFactory(Protocol):
    """Constructs a domain run aggregate for a plan."""

    def create_run(
        self,
        task: TaskDefinitionLike,
        planned_device_count: int,
        target_device_ids: Optional[Sequence[str]] = None,
        requested_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskRunLike:
        ...


class ExecutionInstanceFactory(Protocol):
    """Constructs domain instances for each dispatch target."""

    def create_instance(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        dispatch: DispatchItem,
    ) -> ExecutionInstanceLike:
        ...


class RunRepository(Protocol):
    def add(self, run: TaskRunLike) -> TaskRunLike:
        """Persist a new task run."""
        ...

    def save(self, run: TaskRunLike) -> TaskRunLike:
        """Persist updates to an existing task run."""
        ...


class InstanceRepository(Protocol):
    def add_many(
        self,
        instances: Sequence[ExecutionInstanceLike],
    ) -> Sequence[ExecutionInstanceLike]:
        """Persist a batch of new execution instances."""
        ...

    def save(self, instance: ExecutionInstanceLike) -> ExecutionInstanceLike:
        """Persist updates to one execution instance."""
        ...

    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstanceLike]:
        """Load all instances that belong to a task run."""
        ...


@dataclass(frozen=True)
class CreatedExecutionBatch:
    """Return object for a newly materialized execution run."""

    plan: ExecutionPlan
    run: TaskRunLike
    instances: Sequence[ExecutionInstanceLike]
    created_at: datetime = field(default_factory=utcnow)


class ExecutionService:
    """Application service that owns the V1 task/run/instance orchestration."""

    def __init__(
        self,
        planner: TaskPlanner,
        run_factory: TaskRunFactory,
        instance_factory: ExecutionInstanceFactory,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
        state_machine: Optional[ExecutionStateMachine] = None,
        hooks: Optional[LifecycleHookRegistry] = None,
    ) -> None:
        """Compose planning, factories, persistence, and lifecycle hooks for V1 execution."""
        self._planner = planner
        self._run_factory = run_factory
        self._instance_factory = instance_factory
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._state_machine = state_machine or ExecutionStateMachine()
        self._hooks = hooks or LifecycleHookRegistry()

    def plan_run(
        self,
        task: TaskDefinitionLike,
        requested_devices: Optional[Sequence[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Build an execution plan by selecting devices and expanding dispatch items."""
        device_ids = self._planner.select_devices(task, requested_devices)
        return build_execution_plan(task, device_ids, metadata=metadata)

    def create_run(
        self,
        task: TaskDefinitionLike,
        requested_devices: Optional[Sequence[str]] = None,
        requested_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CreatedExecutionBatch:
        """Create a persisted run and its pending instances from a task definition."""
        plan = self.plan_run(task, requested_devices=requested_devices, metadata=metadata)
        run = self._run_factory.create_run(
            task=task,
            planned_device_count=plan.planned_device_count,
            # 这里记录本次计划出的真实设备集合，而不是仅回填任务默认设备。
            target_device_ids=[dispatch.device_id for dispatch in plan.dispatches],
            requested_by=requested_by,
            metadata=plan.metadata,
        )
        self._state_machine.transition_run(run, "queued")
        persisted_run = self._run_repository.add(run)

        instances = [
            self._instance_factory.create_instance(task=task, run=persisted_run, dispatch=dispatch)
            for dispatch in plan.dispatches
        ]
        for instance in instances:
            self._state_machine.transition_instance(instance, "pending")
        persisted_instances = self._instance_repository.add_many(instances)
        # run刚创建时还没有实例摘要，这里立即同步一次，保证外部读到的统计值正确。
        persisted_run = self.sync_run_status(persisted_run)

        self._emit("run_created", task=task, run=persisted_run, plan=plan)
        return CreatedExecutionBatch(plan=plan, run=persisted_run, instances=persisted_instances)

    def list_run_instances(self, run: TaskRunLike) -> List[ExecutionInstanceLike]:
        """Return all persisted instances for a task run."""
        run_id = getattr(run, "run_id", None)
        if not run_id:
            return []
        return list(self._instance_repository.list_by_run(run_id))

    def mark_instance_preparing(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
    ) -> ExecutionInstanceLike:
        """Move one instance into the preparing state and emit lifecycle hooks."""
        self._state_machine.transition_instance(instance, "preparing")
        self._instance_repository.save(instance)
        self._emit("before_prepare", task=task, run=run, instance=instance)
        return instance

    def mark_instance_running(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
    ) -> ExecutionInstanceLike:
        """Move one instance and its parent run into the running state."""
        self._state_machine.transition_instance(instance, "running")
        self._state_machine.transition_run(run, "running")
        self._run_repository.save(run)
        self._instance_repository.save(instance)
        self._emit("before_start", task=task, run=run, instance=instance)
        return instance

    def mark_instance_collecting(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
    ) -> ExecutionInstanceLike:
        """Move one instance into the collecting state before final completion."""
        self._state_machine.transition_instance(instance, "collecting")
        self._instance_repository.save(instance)
        self._emit("before_collect", task=task, run=run, instance=instance)
        return instance

    def mark_instance_stopping(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        summary: Optional[Dict[str, Any]] = None,
    ) -> ExecutionInstanceLike:
        """Mark one active instance as stopping while device-side cleanup is requested."""
        self._state_machine.transition_instance(instance, "stopping", summary=summary)
        self._instance_repository.save(instance)
        self._emit(
            "on_finish",
            task=task,
            run=run,
            instance=instance,
            payload={"exit_reason": "user_stopped", "summary": summary or {}},
        )
        self.sync_run_status(run)
        return instance

    def complete_instance(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        summary: Optional[Dict[str, Any]] = None,
    ) -> ExecutionInstanceLike:
        """Complete one instance successfully and refresh the parent run summary."""
        self._state_machine.transition_instance(instance, "success", summary=summary)
        self._instance_repository.save(instance)
        self._emit("on_finish", task=task, run=run, instance=instance, payload={"summary": summary or {}})
        self.sync_run_status(run)
        return instance

    def fail_instance(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        exit_reason: str,
        summary: Optional[Dict[str, Any]] = None,
    ) -> ExecutionInstanceLike:
        """Complete one instance as failed and refresh the parent run summary."""
        self._state_machine.transition_instance(
            instance,
            "failed",
            exit_reason=exit_reason,
            summary=summary,
        )
        self._instance_repository.save(instance)
        self._emit(
            "on_issue_detected",
            task=task,
            run=run,
            instance=instance,
            payload={"exit_reason": exit_reason, "summary": summary or {}},
        )
        self.sync_run_status(run)
        return instance

    def cancel_instance(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        exit_reason: str = "cancelled",
        summary: Optional[Dict[str, Any]] = None,
    ) -> ExecutionInstanceLike:
        """Cancel one instance and refresh the parent run summary."""
        self._state_machine.transition_instance(
            instance,
            "cancelled",
            exit_reason=exit_reason,
            summary=summary,
        )
        self._instance_repository.save(instance)
        self._emit(
            "on_finish",
            task=task,
            run=run,
            instance=instance,
            payload={"exit_reason": exit_reason, "summary": summary or {}},
        )
        self.sync_run_status(run)
        return instance

    def sync_run_status(self, run: TaskRunLike) -> TaskRunLike:
        """Recalculate run status and aggregated summary from persisted instances."""
        run_id = getattr(run, "run_id", None)
        if not run_id:
            return run
        instances = list(self._instance_repository.list_by_run(run_id))
        if hasattr(run, "sync_from_instances"):
            run.sync_from_instances(instances)
            self._run_repository.save(run)
            return run
        target_status = self._state_machine.derive_run_status(instances)
        current_status = getattr(run, "run_status", None)
        if target_status and target_status != current_status:
            self._state_machine.transition_run(run, target_status)
            self._run_repository.save(run)
        return run

    def _emit(
        self,
        stage: str,
        *,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: Optional[ExecutionInstanceLike] = None,
        plan: Optional[ExecutionPlan] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Dispatch one lifecycle hook event to the registered listeners."""
        context = LifecycleHookContext(
            stage=stage,
            task=task,
            run=run,
            instance=instance,
            plan=plan,
            payload=payload or {},
        )
        self._hooks.dispatch(context)
