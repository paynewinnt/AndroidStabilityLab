from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Dict, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..execution_service import ExecutionInstanceLike, TaskDefinitionLike, TaskRunLike


class ExecutionLoopMixin:
    """Bounded serial/parallel execution-loop helpers."""

    def _execute_serial_instances(
        self,
        *,
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instances: Sequence["ExecutionInstanceLike"],
        report_paths: Dict[str, str],
        html_report_paths: Dict[str, str],
        persist_monitoring: bool,
        collect_snapshot: bool,
        stop_on_failure: bool,
        retry_count: int,
    ) -> None:
        """Execute instances one by one and optionally cancel the remaining queue after a failure."""
        for index, instance in enumerate(instances):
            executed = self._execute_instance(
                task,
                run,
                instance,
                persist_monitoring=persist_monitoring,
                collect_snapshot=collect_snapshot,
                retry_count=retry_count,
            )
            self._collect_report_paths(executed, report_paths, html_report_paths)
            if stop_on_failure and getattr(executed, "instance_status", None) == "failed":
                self._cancel_pending_instances(
                    task=task,
                    run=run,
                    instances=instances[index + 1 :],
                    reason="前序实例失败，未开始的实例已取消。",
                )
                break

    def _execute_parallel_instances(
        self,
        *,
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instances: Sequence["ExecutionInstanceLike"],
        report_paths: Dict[str, str],
        html_report_paths: Dict[str, str],
        persist_monitoring: bool,
        collect_snapshot: bool,
        stop_on_failure: bool,
        max_concurrency: int,
        retry_count: int,
    ) -> None:
        """Execute instances with bounded parallelism while keeping lifecycle persistence serialized."""
        pending_instances = list(instances)
        in_flight: dict[Future["ExecutionInstanceLike"], "ExecutionInstanceLike"] = {}
        stop_scheduling = False

        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            while pending_instances and len(in_flight) < max_concurrency:
                self._submit_instance(
                    executor=executor,
                    in_flight=in_flight,
                    task=task,
                    run=run,
                    instance=pending_instances.pop(0),
                    persist_monitoring=persist_monitoring,
                    collect_snapshot=collect_snapshot,
                    retry_count=retry_count,
                )

            while in_flight:
                completed, _ = wait(tuple(in_flight.keys()), return_when=FIRST_COMPLETED)
                for future in completed:
                    in_flight.pop(future)
                    executed = future.result()
                    self._collect_report_paths(executed, report_paths, html_report_paths)
                    if stop_on_failure and getattr(executed, "instance_status", None) == "failed":
                        stop_scheduling = True

                if stop_scheduling and pending_instances:
                    self._cancel_pending_instances(
                        task=task,
                        run=run,
                        instances=pending_instances,
                        reason="并发执行中已有实例失败，未开始的实例已取消。",
                    )
                    pending_instances = []

                while not stop_scheduling and pending_instances and len(in_flight) < max_concurrency:
                    self._submit_instance(
                        executor=executor,
                        in_flight=in_flight,
                        task=task,
                        run=run,
                        instance=pending_instances.pop(0),
                        persist_monitoring=persist_monitoring,
                        collect_snapshot=collect_snapshot,
                        retry_count=retry_count,
                    )

    def _submit_instance(
        self,
        *,
        executor: ThreadPoolExecutor,
        in_flight: dict[Future["ExecutionInstanceLike"], "ExecutionInstanceLike"],
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instance: "ExecutionInstanceLike",
        persist_monitoring: bool,
        collect_snapshot: bool,
        retry_count: int,
    ) -> None:
        """Submit one instance execution to the shared thread pool."""
        future = executor.submit(
            self._execute_instance,
            task,
            run,
            instance,
            persist_monitoring=persist_monitoring,
            collect_snapshot=collect_snapshot,
            retry_count=retry_count,
        )
        in_flight[future] = instance

    def _cancel_pending_instances(
        self,
        *,
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instances: Sequence["ExecutionInstanceLike"],
        reason: str,
    ) -> None:
        """Cancel pending instances that were never started so run status stays truthful."""
        for instance in instances:
            if getattr(instance, "instance_status", None) != "pending":
                continue
            with self._lifecycle_lock:
                self._execution_service.cancel_instance(
                    task,
                    run,
                    instance,
                    exit_reason="cancelled",
                    summary={"note": reason},
                )

    @staticmethod
    def _normalize_concurrency(max_concurrency: int, *, instance_count: int) -> int:
        """Clamp requested concurrency to a valid range for the current run."""
        return max(1, min(int(max_concurrency or 1), instance_count))

    @staticmethod
    def _collect_report_paths(
        instance: "ExecutionInstanceLike",
        report_paths: Dict[str, str],
        html_report_paths: Dict[str, str],
    ) -> None:
        """Persist report path mapping when the executed instance wrote report files."""
        report_path = getattr(instance, "metadata", {}).get("report_path")
        if isinstance(report_path, str) and report_path:
            report_paths[getattr(instance, "instance_id", "")] = report_path
        html_report_path = getattr(instance, "metadata", {}).get("html_report_path")
        if isinstance(html_report_path, str) and html_report_path:
            html_report_paths[getattr(instance, "instance_id", "")] = html_report_path

