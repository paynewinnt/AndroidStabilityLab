from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable

from stability.infrastructure.adb import ADBCollector
from stability.domain import TaskTemplateType

from .base import ScenarioExecutionResult
from .cold_start_command import CommandResult, CommandRunner, SubprocessCommandRunner
from .tcp_recovery import TCPReconnectHelper


@dataclass(frozen=True)
class ColdStartLoopConfig:
    """Normalized cold-start loop parameters loaded from task settings."""

    loop_count: int = 3
    launch_wait_ms: int = 1000
    kill_before_launch: bool = True
    target_activity: str = ""
    interval_ms: int = 1000
    startup_timeout_ms: int = 10000
    launch_timeout_seconds: int = 20


class ColdStartLoopScenarioRunner:
    """Execute repeated cold launches and summarize startup timing outcomes."""

    def __init__(
        self,
        collector_factory=ADBCollector,
        command_runner: CommandRunner | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self._collector_factory = collector_factory
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._sleep = sleep_func or time.sleep
        self._tcp_recovery = TCPReconnectHelper(
            command_runner=self._command_runner,
            availability_checker=self._is_device_available,
            log_label="cold_start_loop",
        )

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        """Validate inputs and execute repeated cold launches on the target device."""
        if getattr(task, "template_type", None) != TaskTemplateType.COLD_START_LOOP:
            raise ValueError("ColdStartLoopScenarioRunner only supports cold_start_loop template tasks.")

        device_id = getattr(instance, "device_id", "") or ""
        package_name = getattr(task.target_app, "package_name", "") if getattr(task, "target_app", None) else ""
        if not device_id:
            return ScenarioExecutionResult(
                success=False,
                note="冷启动循环执行失败：缺少目标设备。",
                exit_reason="execution_error",
                result_level="failed",
            )
        if not package_name:
            return ScenarioExecutionResult(
                success=False,
                note="冷启动循环执行失败：缺少目标应用包名。",
                exit_reason="execution_error",
                result_level="failed",
            )

        collector = self._collector_factory(timeout=10, retry_count=1)
        collector.device_id = device_id
        if not self._is_device_available(collector):
            return ScenarioExecutionResult(
                success=False,
                note=f"冷启动循环执行失败：设备 {device_id} 当前不可用或未连接。",
                exit_reason="device_offline",
                result_level="failed",
                metadata={
                    "device_id": device_id,
                    "package_name": package_name,
                    "template_type": TaskTemplateType.COLD_START_LOOP.value,
                },
            )
        if not self._is_package_installed(collector, package_name):
            return ScenarioExecutionResult(
                success=False,
                note=f"冷启动循环执行失败：设备 {device_id} 上未安装应用 {package_name}。",
                exit_reason="execution_error",
                result_level="failed",
                metadata={
                    "device_id": device_id,
                    "package_name": package_name,
                    "template_type": TaskTemplateType.COLD_START_LOOP.value,
                },
            )

        config = self._config_from_task(task)
        launch_command, launch_target = self._build_launch_command(
            collector=collector,
            device_id=device_id,
            package_name=package_name,
            config=config,
            default_launch_activity=getattr(getattr(task, "target_app", None), "launch_activity", "") or "",
        )
        iterations: list[dict[str, object]] = []
        last_stdout = ""
        last_stderr = ""
        for loop_index in range(1, config.loop_count + 1):
            if not self._ensure_device_available_for_loop(
                collector=collector,
                device_id=device_id,
                log_path=log_path,
                loop_index=loop_index,
            ):
                return self._device_offline_result(
                    task=task,
                    config=config,
                    launch_command=launch_command,
                    launch_target=launch_target,
                    iterations=iterations,
                    device_id=device_id,
                    package_name=package_name,
                    note=f"冷启动循环第 {loop_index} 轮前设备 {device_id} 断开，自动重连失败。",
                )
            launch_outcome = self._execute_launch_with_reconnect_retry(
                collector=collector,
                device_id=device_id,
                package_name=package_name,
                config=config,
                launch_command=launch_command,
                launch_target=launch_target,
                log_path=log_path,
                loop_index=loop_index,
            )
            command_result = launch_outcome.command_result
            last_stdout = command_result.stdout or ""
            last_stderr = command_result.stderr or ""
            parsed = launch_outcome.parsed
            iteration_result = self._build_iteration_result(
                loop_index=loop_index,
                launch_target=launch_target,
                parsed=parsed,
                command_result=command_result,
                launch_attempts=launch_outcome.launch_attempts,
                recovered_after_disconnect=launch_outcome.recovered_after_disconnect,
            )

            if launch_outcome.reconnect_failed:
                iteration_result["status"] = "device_offline"
                iterations.append(iteration_result)
                return self._device_offline_result(
                    task=task,
                    config=config,
                    launch_command=launch_command,
                    launch_target=launch_target,
                    iterations=iterations,
                    device_id=device_id,
                    package_name=package_name,
                    note=f"冷启动循环第 {loop_index} 轮启动时设备 {device_id} 断开，自动重连失败。",
                    last_stdout=last_stdout,
                    last_stderr=last_stderr,
                )

            if command_result.timed_out:
                iteration_result["status"] = "timeout"
                iterations.append(iteration_result)
                return self._timeout_result(
                    task=task,
                    instance=instance,
                    config=config,
                    launch_command=launch_command,
                    launch_target=launch_target,
                    iterations=iterations,
                    loop_index=loop_index,
                    last_stdout=last_stdout,
                    last_stderr=last_stderr,
                    note=f"冷启动循环第 {loop_index} 轮启动超时，超过 {config.launch_timeout_seconds} 秒。",
                )

            if command_result.returncode not in {0, None} or parsed.has_error:
                iteration_result["status"] = "failed"
                iterations.append(iteration_result)
                return self._failure_result(
                    task=task,
                    instance=instance,
                    config=config,
                    launch_command=launch_command,
                    launch_target=launch_target,
                    iterations=iterations,
                    loop_index=loop_index,
                    last_stdout=last_stdout,
                    last_stderr=last_stderr,
                    note=f"冷启动循环第 {loop_index} 轮启动失败。",
                    failure_reason=parsed.error_message or f"return code {command_result.returncode}",
                    timeout_exceeded=False,
                )

            measured_wait_ms = parsed.wait_time_ms or parsed.total_time_ms or parsed.this_time_ms
            if config.startup_timeout_ms > 0 and measured_wait_ms is not None and measured_wait_ms > config.startup_timeout_ms:
                iteration_result["status"] = "timeout"
                iterations.append(iteration_result)
                return self._timeout_result(
                    task=task,
                    instance=instance,
                    config=config,
                    launch_command=launch_command,
                    launch_target=launch_target,
                    iterations=iterations,
                    loop_index=loop_index,
                    last_stdout=last_stdout,
                    last_stderr=last_stderr,
                    note=(
                        f"冷启动循环第 {loop_index} 轮启动超时：启动耗时 {measured_wait_ms} ms，"
                        f"超过阈值 {config.startup_timeout_ms} ms。"
                    ),
                )

            iterations.append(iteration_result)
            if config.launch_wait_ms > 0:
                self._sleep(config.launch_wait_ms / 1000.0)
            if config.interval_ms > 0 and loop_index < config.loop_count:
                self._sleep(config.interval_ms / 1000.0)

        summary = self._startup_summary(
            config=config,
            iterations=iterations,
            launch_target=launch_target,
        )
        average_wait_ms = summary.get("average_wait_time_ms")
        note = (
            f"冷启动循环执行完成，共执行 {config.loop_count} 轮，平均启动耗时 {average_wait_ms} ms。"
            if average_wait_ms is not None
            else f"冷启动循环执行完成，共执行 {config.loop_count} 轮。"
        )
        return ScenarioExecutionResult(
            success=True,
            note=note,
            exit_reason="completed",
            result_level="passed",
            highlights=(
                f"Cold start loops completed: {config.loop_count}",
                f"Average wait time: {average_wait_ms} ms" if average_wait_ms is not None else "Average wait time: n/a",
            ),
            metadata={
                "template_type": TaskTemplateType.COLD_START_LOOP.value,
                "package_name": package_name,
                "process_name": package_name,
                "launch_target": launch_target,
                "command": launch_command,
                "stdout_tail": self._tail_text(last_stdout),
                "stderr_tail": self._tail_text(last_stderr),
                "startup_summary": summary,
            },
        )

    @staticmethod
    def _config_from_task(task) -> ColdStartLoopConfig:
        """Load cold-start loop config from task params with safe defaults."""
        params = getattr(task, "task_params", {}) or {}

        def _int_value(name: str, default: int, minimum: int = 0) -> int:
            value = params.get(name, default)
            try:
                return max(int(value), minimum)
            except (TypeError, ValueError):
                return default

        def _bool_value(name: str, default: bool) -> bool:
            value = params.get(name, default)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "on"}:
                    return True
                if lowered in {"0", "false", "no", "off"}:
                    return False
            return default

        task_timeout_seconds = getattr(task, "timeout_seconds", 0) or 0
        default_launch_timeout = max(int(task_timeout_seconds), 20) if task_timeout_seconds else 20
        return ColdStartLoopConfig(
            loop_count=_int_value("loop_count", 3, minimum=1),
            launch_wait_ms=_int_value("launch_wait_ms", 1000, minimum=0),
            kill_before_launch=_bool_value("kill_before_launch", True),
            target_activity=str(params.get("target_activity", "") or "").strip(),
            interval_ms=_int_value("interval_ms", 1000, minimum=0),
            startup_timeout_ms=_int_value("startup_timeout_ms", 10000, minimum=0),
            launch_timeout_seconds=_int_value("launch_timeout_seconds", default_launch_timeout, minimum=1),
        )

    def _build_launch_command(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        package_name: str,
        config: ColdStartLoopConfig,
        default_launch_activity: str,
    ) -> tuple[list[str], str]:
        """Resolve the launch target and build one `am start -W` command."""
        component = self._normalize_activity_component(
            package_name=package_name,
            activity=config.target_activity or default_launch_activity,
        )
        if not component:
            resolved = collector._run_adb_command(
                f"shell cmd package resolve-activity --brief {package_name}",
                log_errors=False,
            )
            component = self._parse_resolved_component(package_name, resolved or "")

        if component:
            return (
                [
                    "adb",
                    "-s",
                    device_id,
                    "shell",
                    "am",
                    "start",
                    "-W",
                    "-n",
                    component,
                ],
                component,
            )
        return (
            [
                "adb",
                "-s",
                device_id,
                "shell",
                "am",
                "start",
                "-W",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LAUNCHER",
                package_name,
            ],
            package_name,
        )

    @staticmethod
    def _normalize_activity_component(*, package_name: str, activity: str) -> str:
        """Normalize an optional activity name into a launchable component string."""
        normalized = activity.strip()
        if not normalized:
            return ""
        if "/" in normalized:
            return normalized
        if normalized.startswith("."):
            return f"{package_name}/{normalized}"
        return f"{package_name}/{normalized}"

    @staticmethod
    def _parse_resolved_component(package_name: str, output: str) -> str:
        """Extract a component name from `cmd package resolve-activity --brief` output."""
        for line in output.splitlines():
            candidate = line.strip()
            if not candidate or "No activity found" in candidate or "unable to" in candidate.lower():
                continue
            if "/" in candidate:
                return ColdStartLoopScenarioRunner._normalize_activity_component(
                    package_name=package_name,
                    activity=candidate,
                )
        return ""

    @staticmethod
    def _parse_launch_output(stdout: str) -> "_ParsedLaunchOutput":
        """Extract startup timing and failure hints from `am start -W` output."""
        status = ""
        activity = ""
        error_message = ""
        wait_time_ms = None
        total_time_ms = None
        this_time_ms = None
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Status:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("Activity:"):
                activity = line.split(":", 1)[1].strip()
            elif line.startswith("WaitTime:"):
                wait_time_ms = ColdStartLoopScenarioRunner._parse_int_value(line)
            elif line.startswith("TotalTime:"):
                total_time_ms = ColdStartLoopScenarioRunner._parse_int_value(line)
            elif line.startswith("ThisTime:"):
                this_time_ms = ColdStartLoopScenarioRunner._parse_int_value(line)
            elif line.startswith("Error:") or "Exception occurred while executing" in line:
                error_message = line
        has_error = bool(error_message) or (status not in {"", "ok"} and status.lower() != "success")
        return _ParsedLaunchOutput(
            status=status or "ok",
            activity=activity,
            wait_time_ms=wait_time_ms,
            total_time_ms=total_time_ms,
            this_time_ms=this_time_ms,
            error_message=error_message,
            has_error=has_error,
        )

    @staticmethod
    def _parse_int_value(line: str) -> int | None:
        try:
            return int(line.split(":", 1)[1].strip())
        except (IndexError, ValueError):
            return None

    @staticmethod
    def _startup_summary(
        *,
        config: ColdStartLoopConfig,
        iterations: list[dict[str, object]],
        launch_target: str,
    ) -> dict[str, object]:
        """Build a normalized startup summary for reports and issue mapping."""
        wait_times = [
            int(value)
            for item in iterations
            for value in [item.get("wait_time_ms") or item.get("total_time_ms") or item.get("this_time_ms")]
            if isinstance(value, int)
        ]
        successful_loops = sum(1 for item in iterations if item.get("status") == "success")
        failed_loop = next((item.get("iteration") for item in iterations if item.get("status") == "failed"), None)
        timed_out_loop = next((item.get("iteration") for item in iterations if item.get("status") == "timeout"), None)
        average_wait_time_ms = round(sum(wait_times) / len(wait_times), 2) if wait_times else None
        return {
            "configured_loops": config.loop_count,
            "completed_loops": len(iterations),
            "successful_loops": successful_loops,
            "failed_loop": failed_loop,
            "timed_out_loop": timed_out_loop,
            "launch_wait_ms": config.launch_wait_ms,
            "interval_ms": config.interval_ms,
            "startup_timeout_ms": config.startup_timeout_ms,
            "kill_before_launch": config.kill_before_launch,
            "launch_target": launch_target,
            "average_wait_time_ms": average_wait_time_ms,
            "min_wait_time_ms": min(wait_times) if wait_times else None,
            "max_wait_time_ms": max(wait_times) if wait_times else None,
            "iterations": iterations,
        }

    def _failure_result(
        self,
        *,
        task,
        instance,
        config: ColdStartLoopConfig,
        launch_command: list[str],
        launch_target: str,
        iterations: list[dict[str, object]],
        loop_index: int,
        last_stdout: str,
        last_stderr: str,
        note: str,
        failure_reason: str,
        timeout_exceeded: bool,
    ) -> ScenarioExecutionResult:
        """Build a failed cold-start result that will map into the issue/artifact chain."""
        summary = self._startup_summary(
            config=config,
            iterations=iterations,
            launch_target=launch_target,
        )
        metadata = {
            "template_type": TaskTemplateType.COLD_START_LOOP.value,
            "package_name": getattr(getattr(task, "target_app", None), "package_name", "") or "",
            "process_name": getattr(getattr(task, "target_app", None), "package_name", "") or "",
            "launch_target": launch_target,
            "command": launch_command,
            "stdout_tail": self._tail_text(last_stdout),
            "stderr_tail": self._tail_text(last_stderr),
            "startup_failure": True,
            "startup_failure_kind": "startup_timeout" if timeout_exceeded else "startup_failure",
            "startup_failure_loop": loop_index,
            "startup_failure_reason": failure_reason,
            "startup_summary": summary,
        }
        return ScenarioExecutionResult(
            success=False,
            note=note,
            exit_reason="timeout" if timeout_exceeded else "execution_error",
            result_level="failed",
            highlights=(
                f"Cold start failed at loop {loop_index}",
                failure_reason,
            ),
            metadata=metadata,
        )

    def _timeout_result(
        self,
        *,
        task,
        instance,
        config: ColdStartLoopConfig,
        launch_command: list[str],
        launch_target: str,
        iterations: list[dict[str, object]],
        loop_index: int,
        last_stdout: str,
        last_stderr: str,
        note: str,
    ) -> ScenarioExecutionResult:
        """Build a timeout-specific result for cold-start failures."""
        failure_reason = f"startup timeout on loop {loop_index}"
        return self._failure_result(
            task=task,
            instance=instance,
            config=config,
            launch_command=launch_command,
            launch_target=launch_target,
            iterations=iterations,
            loop_index=loop_index,
            last_stdout=last_stdout,
            last_stderr=last_stderr,
            note=note,
            failure_reason=failure_reason,
            timeout_exceeded=True,
        )

    def _device_offline_result(
        self,
        *,
        task,
        config: ColdStartLoopConfig,
        launch_command: list[str],
        launch_target: str,
        iterations: list[dict[str, object]],
        device_id: str,
        package_name: str,
        note: str,
        last_stdout: str = "",
        last_stderr: str = "",
    ) -> ScenarioExecutionResult:
        """Build a device-offline result after retrying one TCP reconnect."""
        summary = self._startup_summary(
            config=config,
            iterations=iterations,
            launch_target=launch_target,
        )
        return ScenarioExecutionResult(
            success=False,
            note=note,
            exit_reason="device_offline",
            result_level="failed",
            metadata={
                "device_id": device_id,
                "package_name": package_name,
                "process_name": package_name,
                "template_type": TaskTemplateType.COLD_START_LOOP.value,
                "launch_target": launch_target,
                "command": launch_command,
                "stdout_tail": self._tail_text(last_stdout),
                "stderr_tail": self._tail_text(last_stderr),
                "startup_summary": summary,
            },
        )

    @staticmethod
    def _build_iteration_result(
        *,
        loop_index: int,
        launch_target: str,
        parsed: "_ParsedLaunchOutput",
        command_result: CommandResult,
        launch_attempts: int,
        recovered_after_disconnect: bool,
    ) -> dict[str, object]:
        """Build one loop-level result entry for report and issue rendering."""
        return {
            "iteration": loop_index,
            "status": "success",
            "return_code": command_result.returncode,
            "wait_time_ms": parsed.wait_time_ms,
            "total_time_ms": parsed.total_time_ms,
            "this_time_ms": parsed.this_time_ms,
            "status_text": parsed.status,
            "launch_target": launch_target,
            "stdout_tail": ColdStartLoopScenarioRunner._tail_text(command_result.stdout),
            "stderr_tail": ColdStartLoopScenarioRunner._tail_text(command_result.stderr),
            "launch_attempts": launch_attempts,
            "recovered_after_disconnect": recovered_after_disconnect,
        }

    @staticmethod
    def _append_iteration_log(
        path: Path,
        *,
        loop_index: int,
        attempt_index: int,
        launch_target: str,
        parsed: "_ParsedLaunchOutput",
        command_result: CommandResult,
    ) -> None:
        """Append one cold-start iteration snapshot to the execution log."""
        lines = [
            f"[cold_start_loop] loop={loop_index} attempt={attempt_index} target={launch_target} status={parsed.status}",
            (
                f"[cold_start_loop] loop={loop_index} attempt={attempt_index} wait_time_ms={parsed.wait_time_ms} "
                f"total_time_ms={parsed.total_time_ms} this_time_ms={parsed.this_time_ms}"
            ),
            (
                f"[cold_start_loop] loop={loop_index} attempt={attempt_index} "
                f"return_code={command_result.returncode} timed_out={command_result.timed_out}"
            ),
        ]
        text = "\n".join(line for line in lines if line)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")

    def _execute_launch_with_reconnect_retry(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        package_name: str,
        config: ColdStartLoopConfig,
        launch_command: list[str],
        launch_target: str,
        log_path: Path,
        loop_index: int,
    ) -> "_LoopLaunchOutcome":
        """Retry one failed launch once after reconnecting a dropped TCP device."""
        recovered_after_disconnect = False
        for attempt_index in range(1, 3):
            if config.kill_before_launch:
                collector._run_adb_command(f"shell am force-stop {package_name}", log_errors=False)

            command_result = self._command_runner.run(
                launch_command,
                timeout_seconds=config.launch_timeout_seconds,
            )
            parsed = self._parse_launch_output(command_result.stdout)
            self._append_iteration_log(
                log_path,
                loop_index=loop_index,
                attempt_index=attempt_index,
                launch_target=launch_target,
                parsed=parsed,
                command_result=command_result,
            )
            if attempt_index >= 2 or not self._should_retry_launch_after_disconnect(
                collector=collector,
                device_id=device_id,
                command_result=command_result,
                parsed=parsed,
            ):
                return _LoopLaunchOutcome(
                    command_result=command_result,
                    parsed=parsed,
                    launch_attempts=attempt_index,
                    recovered_after_disconnect=recovered_after_disconnect,
                    reconnect_failed=False,
                )

            if not self._tcp_recovery.attempt_reconnect(
                collector=collector,
                device_id=device_id,
                log_path=log_path,
                loop_label=f"loop={loop_index}",
                reason="launch command failed or timed out while device was offline",
            ):
                return _LoopLaunchOutcome(
                    command_result=command_result,
                    parsed=parsed,
                    launch_attempts=attempt_index,
                    recovered_after_disconnect=False,
                    reconnect_failed=True,
                )

            recovered_after_disconnect = True
            TCPReconnectHelper.append_runtime_log(
                log_path,
                f"[cold_start_loop] loop={loop_index} reconnect recovered launch path, retrying current loop",
            )

        return _LoopLaunchOutcome(
            command_result=command_result,
            parsed=parsed,
            launch_attempts=2,
            recovered_after_disconnect=recovered_after_disconnect,
            reconnect_failed=False,
        )

    def _ensure_device_available_for_loop(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        log_path: Path,
        loop_index: int,
    ) -> bool:
        """Best-effort recover one dropped TCP device before starting the next launch loop."""
        return self._tcp_recovery.ensure_device_available(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label=f"loop={loop_index}",
            reason="device unavailable before launch",
        )

    def _should_retry_launch_after_disconnect(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        command_result: CommandResult,
        parsed: "_ParsedLaunchOutput",
    ) -> bool:
        """Retry once only when a TCP launch failed because the device actually dropped."""
        return self._tcp_recovery.should_retry_after_disconnect(
            collector=collector,
            device_id=device_id,
            command_result=command_result,
            had_command_error=parsed.has_error,
            extra_output=(parsed.error_message,),
        )

    @staticmethod
    def _is_package_installed(collector: ADBCollector, package_name: str) -> bool:
        """Check whether the target package exists on the target device."""
        result = collector._run_adb_command(f"shell pm list packages {package_name}", log_errors=False)
        return bool(result and package_name in result)

    @staticmethod
    def _is_device_available(collector: ADBCollector) -> bool:
        """Check whether adb can reach the target device before starting launches."""
        result = collector._run_adb_command("get-state", log_errors=False)
        return bool(result and result.strip() == "device")

    @staticmethod
    def _tail_text(value: str, limit: int = 2000) -> str:
        """Keep only the tail of large command output for DB/report storage."""
        text = value.strip()
        if len(text) <= limit:
            return text
        return text[-limit:]


@dataclass(frozen=True)
class _ParsedLaunchOutput:
    """Normalized parsed payload from one `am start -W` execution."""

    status: str
    activity: str
    wait_time_ms: int | None
    total_time_ms: int | None
    this_time_ms: int | None
    error_message: str
    has_error: bool


@dataclass(frozen=True)
class _LoopLaunchOutcome:
    """Final launch result for one loop, including one optional reconnect retry."""

    command_result: CommandResult
    parsed: _ParsedLaunchOutput
    launch_attempts: int
    recovered_after_disconnect: bool
    reconnect_failed: bool
