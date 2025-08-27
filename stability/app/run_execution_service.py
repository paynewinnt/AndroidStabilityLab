from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import threading
import time
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence

from stability.artifact import IssueArtifactCollector
from stability.infrastructure import ArtifactPathPlanner, ArtifactScope, MonitoringAdapter
from stability.issue import MonkeyIssueDetector
from stability.scenario import (
    ColdStartLoopScenarioRunner,
    CustomAutomationScenarioRunner,
    ForegroundBackgroundLoopScenarioRunner,
    InstallUninstallLoopScenarioRunner,
    MonkeyScenarioRunner,
    RebootLoopScenarioRunner,
    ScenarioRunner,
    StandbyWakeLoopScenarioRunner,
)
from stability.time_utils import now_beijing_string, utcnow

from .execution_service import ExecutionService, ExecutionInstanceLike, TaskDefinitionLike, TaskRunLike
from .report_service import ReportService
from .run_execution.execution_loop import ExecutionLoopMixin
from .run_execution.host_commands import HostCommandResult, HostCommandRunner, SubprocessHostCommandRunner
from .run_execution.metadata import MetadataReportMixin
from .run_execution.monitoring import MonitoringHelpersMixin
from .run_execution.retry import RetryDecision, RetryHelpersMixin
from stability.domain import AppError
from .task_service import TaskRecordNotFound


class RunRepository(Protocol):
    def get(self, run_id: str) -> Optional[TaskRunLike]:
        """Load a persisted task run by id."""
        ...


def _display_now() -> str:
    return now_beijing_string()


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskDefinitionLike]:
        """Load a persisted task definition by id."""
        ...


class InstanceRepository(Protocol):
    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstanceLike]:
        """List all execution instances that belong to a run."""
        ...


class RunRecordNotFound(LookupError):
    """Raised when a requested run record does not exist."""


@dataclass(frozen=True)
class ExecutedRunResult:
    """Return object for one completed local execution pass over a task run."""

    task: TaskDefinitionLike
    run: TaskRunLike
    instances: Sequence[ExecutionInstanceLike]
    report_paths: Dict[str, str] = field(default_factory=dict)
    html_report_paths: Dict[str, str] = field(default_factory=dict)
    executed_instance_count: int = 0
    skipped_instance_count: int = 0
    skipped_reason: str = ""
    executed_at: datetime = field(default_factory=utcnow)


class RunExecutionService(ExecutionLoopMixin, RetryHelpersMixin, MonitoringHelpersMixin, MetadataReportMixin):
    """Best-effort local executor for the V1 task/run/instance backbone."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
        execution_service: ExecutionService,
        monitoring_adapter: MonitoringAdapter | None = None,
        artifact_path_planner: ArtifactPathPlanner | None = None,
        scenario_runners: Mapping[str, ScenarioRunner] | None = None,
        artifact_collector: IssueArtifactCollector | None = None,
        host_command_runner: HostCommandRunner | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        """Wire repositories, lifecycle service, and optional monitoring/artifact adapters."""
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._execution_service = execution_service
        self._monitoring_adapter = monitoring_adapter
        self._artifact_planner = artifact_path_planner or ArtifactPathPlanner()
        self._scenario_runners = dict(
            scenario_runners
            or {
                "monkey": MonkeyScenarioRunner(),
                "cold_start_loop": ColdStartLoopScenarioRunner(),
                "foreground_background_loop": ForegroundBackgroundLoopScenarioRunner(),
                "install_uninstall_loop": InstallUninstallLoopScenarioRunner(),
                "reboot_loop": RebootLoopScenarioRunner(),
                "standby_wake_loop": StandbyWakeLoopScenarioRunner(),
                "custom": CustomAutomationScenarioRunner(),
            }
        )
        self._issue_detector = MonkeyIssueDetector()
        self._artifact_collector = artifact_collector or IssueArtifactCollector()
        self._host_command_runner = host_command_runner or SubprocessHostCommandRunner()
        self._report_service = report_service or ReportService()
        self._lifecycle_lock = threading.Lock()

    def execute_run(
        self,
        run_id: str,
        *,
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ) -> ExecutedRunResult:
        """Execute all instances under a run and return the refreshed run-level result."""
        run = self._get_run(run_id)
        task = self._get_task(getattr(run, "task_definition_id", ""))
        instances = list(self._instance_repository.list_by_run(run_id))
        if not instances:
            raise AppError.not_found(f"Run '{run_id}' does not contain any execution instances.")

        report_paths: Dict[str, str] = {}
        html_report_paths: Dict[str, str] = {}
        for instance in instances:
            self._collect_report_paths(instance, report_paths, html_report_paths)

        executable_instances = [instance for instance in instances if self._is_executable_instance(instance)]
        skipped_instance_count = len(instances) - len(executable_instances)
        skipped_reason = self._skipped_execution_reason(instances, executable_instances)
        if not executable_instances:
            persisted_run = self._run_repository.get(run_id) or run
            return ExecutedRunResult(
                task=task,
                run=persisted_run,
                instances=tuple(self._instance_repository.list_by_run(run_id)),
                report_paths=report_paths,
                html_report_paths=html_report_paths,
                executed_instance_count=0,
                skipped_instance_count=skipped_instance_count,
                skipped_reason=skipped_reason,
            )

        concurrency = self._normalize_concurrency(max_concurrency, instance_count=len(executable_instances))
        normalized_retry_count = self._normalize_retry_count(retry_count)
        if concurrency == 1:
            self._execute_serial_instances(
                task=task,
                run=run,
                instances=executable_instances,
                report_paths=report_paths,
                html_report_paths=html_report_paths,
                persist_monitoring=persist_monitoring,
                collect_snapshot=collect_snapshot,
                stop_on_failure=stop_on_failure,
                retry_count=normalized_retry_count,
            )
        else:
            self._execute_parallel_instances(
                task=task,
                run=run,
                instances=executable_instances,
                report_paths=report_paths,
                html_report_paths=html_report_paths,
                persist_monitoring=persist_monitoring,
                collect_snapshot=collect_snapshot,
                stop_on_failure=stop_on_failure,
                max_concurrency=concurrency,
                retry_count=normalized_retry_count,
            )

        persisted_run = self._run_repository.get(run_id) or run
        return ExecutedRunResult(
            task=task,
            run=persisted_run,
            instances=tuple(self._instance_repository.list_by_run(run_id)),
            report_paths=report_paths,
            html_report_paths=html_report_paths,
            executed_instance_count=len(executable_instances),
            skipped_instance_count=skipped_instance_count,
            skipped_reason=skipped_reason,
        )

    @classmethod
    def _is_executable_instance(cls, instance: ExecutionInstanceLike) -> bool:
        return cls._instance_status(instance) in {"pending", "preparing"}

    @classmethod
    def _skipped_execution_reason(
        cls,
        instances: Sequence[ExecutionInstanceLike],
        executable_instances: Sequence[ExecutionInstanceLike],
    ) -> str:
        skipped_count = len(instances) - len(executable_instances)
        if skipped_count <= 0:
            return ""
        statuses = {cls._instance_status(instance) for instance in instances}
        terminal_statuses = {"success", "failed", "cancelled", "precheck_failed"}
        active_statuses = {"running", "collecting", "stopping"}
        if statuses and statuses.issubset(terminal_statuses):
            return "Run 已处于终态，execute-run 不会重复执行同一批实例；如需重跑，请新建 Run。"
        if statuses and statuses.issubset(active_statuses):
            return "Run 当前已有实例正在执行或采集中，已跳过重复启动。"
        return "已跳过非待执行实例，只执行 pending/preparing 实例。"

    @staticmethod
    def _instance_status(instance: ExecutionInstanceLike) -> str:
        return str(getattr(instance, "instance_status", getattr(instance, "status", "")) or "")

    def _execute_instance(
        self,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        *,
        persist_monitoring: bool,
        collect_snapshot: bool,
        retry_count: int,
    ) -> ExecutionInstanceLike:
        """Drive a single instance through the minimal V1 local execution lifecycle."""
        # 先为本次实例执行规划稳定的运行目录，后续日志、监控快照和报告都挂到这里。
        scope = ArtifactScope(
            task_id=getattr(task, "task_id", ""),
            run_id=getattr(run, "run_id", ""),
            execution_id=getattr(instance, "instance_id", ""),
            device_id=getattr(instance, "device_id", ""),
        )
        layout = self._artifact_planner.plan(scope, ensure_exists=True)
        log_path = layout.logs_dir / "execution.log"
        report_path = self._artifact_planner.default_report_path(scope, ensure_parent=True)
        html_report_path = self._artifact_planner.default_report_path(scope, extension="html", ensure_parent=True)

        metadata = getattr(instance, "metadata", {})
        metadata["runtime_root"] = str(layout.root)
        metadata["report_path"] = str(report_path)
        metadata["html_report_path"] = str(html_report_path)
        metadata["execution_log_path"] = str(log_path)
        metadata["log_path"] = str(log_path)

        self._append_log(
            log_path,
            [
                f"[{_display_now()}] preparing instance {getattr(instance, 'instance_id', '')}",
                f"device={getattr(instance, 'device_id', '')}",
            ],
        )
        with self._lifecycle_lock:
            instance = self._execution_service.mark_instance_preparing(task, run, instance)

        monitoring_handle = None
        monitoring_error = ""
        snapshot_payload: Dict[str, Any] | None = None
        monitoring_samples: list[Dict[str, Any]] = []
        monitoring_stop_event: threading.Event | None = None
        monitoring_thread: threading.Thread | None = None
        scenario_result = None
        package_name = getattr(getattr(task, "target_app", None), "package_name", "") or ""
        execution_attempts: list[dict[str, Any]] = []
        cleanup_events: list[dict[str, Any]] = []
        try:
            if collect_snapshot and self._monitoring_adapter is not None:
                try:
                    # 监控是最佳努力能力，失败时只记录错误，不阻断主执行链路。
                    monitoring_handle = self._start_monitoring_session(
                        task,
                        instance,
                        layout=layout,
                        persist_monitoring=persist_monitoring,
                    )
                    if monitoring_handle is not None:
                        setattr(
                            instance,
                            "monitoring_session_id",
                            str(monitoring_handle.session_id or monitoring_handle.session_name),
                        )
                        metadata["monitoring_profile"] = str(
                            getattr(getattr(monitoring_handle, "config", None), "profile_name", "") or ""
                        )
                        monitoring_stop_event = threading.Event()
                        monitoring_thread = self._start_periodic_monitoring_sampler(
                            monitoring_handle=monitoring_handle,
                            layout=layout,
                            persist_monitoring=persist_monitoring,
                            stop_event=monitoring_stop_event,
                            samples=monitoring_samples,
                        )
                except Exception as exc:  # pragma: no cover - depends on connected devices
                    monitoring_error = str(exc)

            with self._lifecycle_lock:
                instance = self._execution_service.mark_instance_running(task, run, instance)
            self._append_log(
                log_path,
                [f"[{_display_now()}] instance entered running state"],
            )

            scenario_runner = self._resolve_scenario_runner(task)
            if scenario_runner is not None:
                scenario_result = self._execute_scenario_with_retries(
                    task=task,
                    run=run,
                    instance=instance,
                    layout=layout,
                    log_path=log_path,
                    scenario_runner=scenario_runner,
                    retry_count=retry_count,
                    cleanup_events=cleanup_events,
                    execution_attempts=execution_attempts,
                    package_name=package_name,
                )
                for issue in self._issue_detector.detect(task, run, instance, scenario_result):
                    instance.add_issue(issue)

            self._stop_periodic_monitoring_sampler(monitoring_stop_event, monitoring_thread)
            monitoring_stop_event = None
            monitoring_thread = None
            if collect_snapshot and monitoring_handle is not None and self._monitoring_adapter is not None:
                try:
                    snapshot_payload = self._collect_and_store_monitoring_snapshot(
                        monitoring_handle=monitoring_handle,
                        layout=layout,
                        persist_monitoring=persist_monitoring,
                        samples=monitoring_samples,
                    )
                    metadata["monitoring_snapshot_path"] = str(layout.monitoring_dir / "snapshot.json")
                    metadata["monitoring_backend"] = str(
                        dict(snapshot_payload.get("metadata", {}) or {}).get("backend", "") or ""
                    )
                    trace_path = self._monitoring_trace_path(snapshot_payload)
                    if trace_path:
                        metadata["monitoring_trace_path"] = trace_path
                except Exception as exc:  # pragma: no cover - depends on connected devices
                    monitoring_error = str(exc)

            with self._lifecycle_lock:
                instance = self._execution_service.mark_instance_collecting(task, run, instance)
            artifact_capture_errors: list[str] = []
            if getattr(instance, "issues", None):
                captured_artifacts, artifact_capture_errors = self._artifact_collector.capture(
                    task=task,
                    run=run,
                    instance=instance,
                    scope=scope,
                    artifact_path_planner=self._artifact_planner,
                    log_path=log_path,
                    monitoring_snapshot_path=metadata.get("monitoring_snapshot_path"),
                )
                for artifact in captured_artifacts:
                    instance.add_artifact(artifact)
            if scenario_result is not None and not scenario_result.success:
                self._cleanup_interrupted_execution(
                    instance=instance,
                    package_name=package_name,
                    log_path=log_path,
                    cleanup_events=cleanup_events,
                    reason=f"final scenario failure after {len(execution_attempts) or 1} attempt(s)",
                )
            # 先把摘要落到实例，再写报告，避免报告和最终状态不一致。
            summary = {
                "note": (
                    scenario_result.note
                    if scenario_result is not None and scenario_result.note
                    else "Minimal local execution completed."
                ),
                "highlights": list(getattr(scenario_result, "highlights", ()) or ()),
                "metadata": {
                    "runtime_root": str(layout.root),
                    "report_path": str(report_path),
                    "html_report_path": str(html_report_path),
                    "execution_log_path": str(log_path),
                    "monitoring_enabled": bool(self._monitoring_adapter and collect_snapshot),
                    "monitoring_error": monitoring_error,
                    "monitoring_sample_count": len(monitoring_samples),
                    "monitoring_samples_path": str(layout.monitoring_dir / "samples.json") if monitoring_samples else "",
                    "monitoring_snapshot": snapshot_payload or {},
                    "scenario_result": dict(getattr(scenario_result, "metadata", {}) or {}),
                    "artifact_capture_errors": artifact_capture_errors,
                    "execution_attempts": execution_attempts,
                    "cleanup_events": cleanup_events,
                    "retry_policy": self._retry_policy_metadata(retry_count),
                    "analysis_ready": self._build_analysis_ready_metadata(
                        task=task,
                        run=run,
                        instance=instance,
                        scenario_result=scenario_result,
                        report_path=report_path,
                        html_report_path=html_report_path,
                        log_path=log_path,
                        monitoring_enabled=bool(self._monitoring_adapter and collect_snapshot),
                        snapshot_payload=snapshot_payload,
                    ),
                },
            }
            if scenario_result is not None and not scenario_result.success:
                with self._lifecycle_lock:
                    instance = self._execution_service.fail_instance(
                        task,
                        run,
                        instance,
                        exit_reason=scenario_result.exit_reason,
                        summary=summary,
                    )
            else:
                with self._lifecycle_lock:
                    instance = self._execution_service.complete_instance(task, run, instance, summary=summary)
            metadata = getattr(instance, "metadata", {})
            metadata["report_path"] = str(report_path)
            metadata["html_report_path"] = str(html_report_path)
            self._write_reports(
                report_path=report_path,
                html_report_path=html_report_path,
                task=task,
                run=run,
                instance=instance,
                monitoring_error=monitoring_error,
                snapshot_payload=snapshot_payload,
                scenario_result=scenario_result,
            )
            self._append_log(
                log_path,
                [
                    f"[{_display_now()}] execution finished with status {getattr(instance, 'instance_status', '')}"
                ],
            )
            return instance
        except Exception as exc:
            self._append_log(
                log_path,
                [f"[{_display_now()}] execution failed: {exc}"],
            )
            self._cleanup_interrupted_execution(
                instance=instance,
                package_name=package_name,
                log_path=log_path,
                cleanup_events=cleanup_events,
                reason=f"exception cleanup after {exc.__class__.__name__}: {exc}",
            )
            # 失败路径也要补齐报告和摘要，保证后续能追溯失败原因。
            with self._lifecycle_lock:
                instance = self._execution_service.fail_instance(
                    task,
                    run,
                    instance,
                    exit_reason="execution_error",
                    summary={
                        "note": str(exc),
                        "metadata": {
                            "runtime_root": str(layout.root),
                            "report_path": str(report_path),
                            "html_report_path": str(html_report_path),
                            "execution_log_path": str(log_path),
                            "execution_attempts": execution_attempts,
                            "cleanup_events": cleanup_events,
                            "retry_policy": self._retry_policy_metadata(retry_count),
                            "analysis_ready": self._build_analysis_ready_metadata(
                                task=task,
                                run=run,
                                instance=instance,
                                scenario_result=scenario_result,
                                report_path=report_path,
                                html_report_path=html_report_path,
                                log_path=log_path,
                                monitoring_enabled=bool(self._monitoring_adapter and collect_snapshot),
                                snapshot_payload=snapshot_payload,
                                exception=exc,
                            ),
                        },
                    },
                )
            metadata = getattr(instance, "metadata", {})
            metadata["report_path"] = str(report_path)
            metadata["html_report_path"] = str(html_report_path)
            self._write_reports(
                report_path=report_path,
                html_report_path=html_report_path,
                task=task,
                run=run,
                instance=instance,
                monitoring_error=monitoring_error or str(exc),
                snapshot_payload=snapshot_payload,
                scenario_result=scenario_result,
            )
            return instance
        except BaseException as exc:
            self._append_log(
                log_path,
                [f"[{_display_now()}] execution interrupted: {exc.__class__.__name__}: {exc}"],
            )
            self._cleanup_interrupted_execution(
                instance=instance,
                package_name=package_name,
                log_path=log_path,
                cleanup_events=cleanup_events,
                reason=f"interrupted cleanup after {exc.__class__.__name__}",
            )
            raise
        finally:
            self._stop_periodic_monitoring_sampler(monitoring_stop_event, monitoring_thread)
            if monitoring_handle is not None and self._monitoring_adapter is not None:
                status = getattr(instance, "instance_status", "success")
                try:
                    self._monitoring_adapter.stop_session(monitoring_handle, status=status)
                except Exception:
                    pass

    def _start_periodic_monitoring_sampler(
        self,
        *,
        monitoring_handle,
        layout,
        persist_monitoring: bool,
        stop_event: threading.Event,
        samples: list[Dict[str, Any]],
    ) -> threading.Thread:
        interval = max(float(getattr(monitoring_handle.config, "sample_interval", 3.0) or 3.0), 0.2)

        def _sample_loop() -> None:
            while not stop_event.is_set():
                try:
                    self._collect_and_store_monitoring_snapshot(
                        monitoring_handle=monitoring_handle,
                        layout=layout,
                        persist_monitoring=persist_monitoring,
                        samples=samples,
                    )
                except Exception as exc:  # pragma: no cover - depends on connected devices
                    samples.append(
                        {
                            "timestamp": _display_now(),
                            "persisted": False,
                            "system": None,
                            "apps": [],
                            "metadata": {
                                "backend": str(getattr(monitoring_handle, "backend_name", "") or ""),
                                "sampling_error": str(exc),
                            },
                        }
                    )
                stop_event.wait(interval)

        thread = threading.Thread(
            target=_sample_loop,
            name=f"monitoring-sampler-{getattr(monitoring_handle, 'session_name', 'session')}",
            daemon=True,
        )
        thread.start()
        return thread

    @staticmethod
    def _stop_periodic_monitoring_sampler(
        stop_event: threading.Event | None,
        thread: threading.Thread | None,
    ) -> None:
        if stop_event is None or thread is None:
            return
        stop_event.set()
        thread.join(timeout=2.0)

    def _collect_and_store_monitoring_snapshot(
        self,
        *,
        monitoring_handle,
        layout,
        persist_monitoring: bool,
        samples: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        snapshot = self._monitoring_adapter.collect_snapshot(monitoring_handle)
        persisted = self._monitoring_adapter.persist_snapshot(monitoring_handle, snapshot) if persist_monitoring else False
        snapshot_payload = self._snapshot_payload(snapshot, persisted=persisted)
        samples.append(snapshot_payload)
        snapshot_path = layout.monitoring_dir / "snapshot.json"
        snapshot_path.write_text(
            json.dumps(snapshot_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        samples_path = layout.monitoring_dir / "samples.json"
        samples_path.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return snapshot_payload

    def _get_run(self, run_id: str) -> TaskRunLike:
        """Load a run and raise a domain-friendly error when it does not exist."""
        run = self._run_repository.get(run_id)
        if run is None:
            raise RunRecordNotFound(f"Run '{run_id}' was not found.")
        return run

    def _resolve_scenario_runner(self, task: TaskDefinitionLike):
        """Pick the registered scenario runner for the task template type when available."""
        template_type = getattr(task, "template_type", None)
        key = getattr(template_type, "value", template_type)
        if not isinstance(key, str):
            return None
        return self._scenario_runners.get(key)

    def _get_task(self, task_id: str) -> TaskDefinitionLike:
        """Load the task definition that owns the run being executed."""
        task = self._task_repository.get(task_id)
        if task is None:
            raise TaskRecordNotFound(f"Task '{task_id}' was not found.")
        return task
