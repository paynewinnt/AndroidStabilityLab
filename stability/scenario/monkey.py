from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict

from stability.infrastructure.adb import ADBCollector
from stability.domain import TaskTemplateType
from stability.infrastructure.command_runner import (
    CommandResult as _CommandResult,
    CommandRunner,
    SubprocessCommandRunner,
)

from .base import ScenarioExecutionResult
from .tcp_recovery import TCPReconnectHelper


@dataclass(frozen=True)
class MonkeyExecutionConfig:
    """Normalized Monkey parameters loaded from task settings."""

    event_count: int = 100
    throttle_ms: int = 300
    seed: int | None = None
    ignore_crashes: bool = True
    ignore_timeouts: bool = True
    ignore_security_exceptions: bool = True
    force_stop_before_start: bool = True
    timeout_seconds: int = 180
    verbosity: int = 1


class MonkeyScenarioRunner:
    """Execute a real adb monkey command for V1 Monkey tasks."""

    def __init__(
        self,
        collector_factory=ADBCollector,
        command_runner: CommandRunner | None = None,
    ) -> None:
        """Bind the runner to the existing ADB collector factory for device/package checks."""
        self._collector_factory = collector_factory
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._tcp_recovery = TCPReconnectHelper(
            command_runner=self._command_runner,
            availability_checker=self._is_device_available,
            log_label="monkey",
        )

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        """Validate the task and run Monkey on the target device."""
        if getattr(task, "template_type", None) != TaskTemplateType.MONKEY:
            raise ValueError("MonkeyScenarioRunner only supports monkey template tasks.")

        device_id = getattr(instance, "device_id", "") or ""
        package_name = getattr(task.target_app, "package_name", "") if getattr(task, "target_app", None) else ""
        if not device_id:
            return ScenarioExecutionResult(
                success=False,
                note="Monkey 模板执行失败：缺少目标设备。",
                exit_reason="execution_error",
                result_level="failed",
            )
        if not package_name:
            return ScenarioExecutionResult(
                success=False,
                note="Monkey 模板执行失败：缺少目标应用包名。",
                exit_reason="execution_error",
                result_level="failed",
            )

        collector = self._collector_factory(timeout=10, retry_count=1)
        collector.device_id = device_id
        if not self._tcp_recovery.ensure_device_available(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label="execution",
            reason="device unavailable before monkey start",
        ):
            return ScenarioExecutionResult(
                success=False,
                note=f"Monkey 模板执行失败：设备 {device_id} 当前不可用或未连接。",
                exit_reason="device_offline",
                result_level="failed",
                metadata={
                    "device_id": device_id,
                    "package_name": package_name,
                    "template_type": TaskTemplateType.MONKEY.value,
                },
            )
        if not self._is_package_installed(collector, package_name):
            return ScenarioExecutionResult(
                success=False,
                note=f"Monkey 模板执行失败：设备 {device_id} 上未安装应用 {package_name}。",
                exit_reason="execution_error",
                result_level="failed",
                metadata={
                    "device_id": device_id,
                    "package_name": package_name,
                },
        )

        config = self._config_from_task(task)
        command = self._build_monkey_command(device_id, package_name, config)
        execution = self._execute_command_with_reconnect_retry(
            collector=collector,
            device_id=device_id,
            package_name=package_name,
            config=config,
            command=command,
            log_path=log_path,
        )
        result = execution.result
        metadata = {
            "command": command,
            "stdout_tail": self._tail_text(result.stdout),
            "stderr_tail": self._tail_text(result.stderr),
            "command_attempts": execution.command_attempts,
            "recovered_after_disconnect": execution.recovered_after_disconnect,
            "template_type": TaskTemplateType.MONKEY.value,
        }

        if execution.reconnect_failed:
            return ScenarioExecutionResult(
                success=False,
                note=f"Monkey 模板执行过程中设备 {device_id} 断开，自动重连失败。",
                exit_reason="device_offline",
                result_level="failed",
                highlights=("Monkey 执行期间设备离线",),
                metadata=metadata,
            )

        if result.timed_out:
            metadata["timeout_seconds"] = config.timeout_seconds
            return ScenarioExecutionResult(
                success=False,
                note=f"Monkey 模板执行超时，超过 {config.timeout_seconds} 秒。",
                exit_reason="timeout",
                result_level="failed",
                highlights=("Monkey 命令执行超时",),
                metadata=metadata,
            )

        if result.returncode != 0:
            metadata["return_code"] = result.returncode
            return ScenarioExecutionResult(
                success=False,
                note=f"Monkey 模板执行失败，退出码 {result.returncode}。",
                exit_reason="execution_error",
                result_level="failed",
                highlights=("Monkey 命令退出非 0",),
                metadata=metadata,
            )

        events_injected = self._parse_events_injected(result.stdout)
        metadata["return_code"] = result.returncode
        metadata["events_injected"] = events_injected
        return ScenarioExecutionResult(
            success=True,
            note=f"Monkey 模板执行完成，共注入 {events_injected} 个事件。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"Monkey events injected: {events_injected}",),
            metadata=metadata,
        )

    @staticmethod
    def _config_from_task(task) -> MonkeyExecutionConfig:
        """Load Monkey config from task params with safe defaults."""
        params = getattr(task, "task_params", {}) or {}

        def _int_value(name: str, default: int) -> int:
            value = params.get(name, default)
            try:
                return max(int(value), 1)
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

        seed = params.get("seed")
        try:
            normalized_seed = int(seed) if seed is not None and seed != "" else None
        except (TypeError, ValueError):
            normalized_seed = None

        timeout_seconds = _int_value("timeout_seconds", getattr(task, "timeout_seconds", 0) or 180)
        return MonkeyExecutionConfig(
            event_count=_int_value("event_count", 100),
            throttle_ms=_int_value("throttle_ms", 300),
            seed=normalized_seed,
            ignore_crashes=_bool_value("ignore_crashes", True),
            ignore_timeouts=_bool_value("ignore_timeouts", True),
            ignore_security_exceptions=_bool_value("ignore_security_exceptions", True),
            force_stop_before_start=_bool_value("force_stop_before_start", True),
            timeout_seconds=timeout_seconds,
            verbosity=_int_value("verbosity", 1),
        )

    @staticmethod
    def _build_monkey_command(device_id: str, package_name: str, config: MonkeyExecutionConfig) -> list[str]:
        """Build the adb monkey command line from normalized parameters."""
        command = [
            "adb",
            "-s",
            device_id,
            "shell",
            "monkey",
            "-p",
            package_name,
            "--throttle",
            str(config.throttle_ms),
        ]
        if config.seed is not None:
            command.extend(["-s", str(config.seed)])
        if config.ignore_crashes:
            command.append("--ignore-crashes")
        if config.ignore_timeouts:
            command.append("--ignore-timeouts")
        if config.ignore_security_exceptions:
            command.append("--ignore-security-exceptions")
        for _ in range(max(config.verbosity, 0)):
            command.append("-v")
        command.append(str(config.event_count))
        return command

    def _execute_command_with_reconnect_retry(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        package_name: str,
        config: MonkeyExecutionConfig,
        command: list[str],
        log_path: Path,
    ) -> "_MonkeyExecutionOutcome":
        """Retry one failed Monkey command once after reconnecting a dropped TCP device."""
        recovered_after_disconnect = False
        for attempt_index in range(1, 3):
            if config.force_stop_before_start:
                collector._run_adb_command(f"shell am force-stop {package_name}", log_errors=False)

            result = self._command_runner.run(command, timeout_seconds=config.timeout_seconds)
            self._append_command_output(log_path, attempt_index=attempt_index, result=result)
            if attempt_index >= 2 or not self._tcp_recovery.should_retry_after_disconnect(
                collector=collector,
                device_id=device_id,
                command_result=result,
            ):
                return _MonkeyExecutionOutcome(
                    result=result,
                    command_attempts=attempt_index,
                    recovered_after_disconnect=recovered_after_disconnect,
                    reconnect_failed=False,
                )

            if not self._tcp_recovery.attempt_reconnect(
                collector=collector,
                device_id=device_id,
                log_path=log_path,
                loop_label="execution",
                reason="monkey command failed or timed out while device was offline",
            ):
                return _MonkeyExecutionOutcome(
                    result=result,
                    command_attempts=attempt_index,
                    recovered_after_disconnect=False,
                    reconnect_failed=True,
                )

            recovered_after_disconnect = True
            TCPReconnectHelper.append_runtime_log(
                log_path,
                "[monkey] execution reconnect recovered command path, retrying current execution",
            )

        return _MonkeyExecutionOutcome(
            result=result,
            command_attempts=2,
            recovered_after_disconnect=recovered_after_disconnect,
            reconnect_failed=False,
        )

    @staticmethod
    def _append_command_output(path: Path, *, attempt_index: int, result: "_CommandResult") -> None:
        """Append one Monkey command attempt payload to the execution log."""
        lines = [f"[monkey] attempt={attempt_index} return_code={result.returncode} timed_out={result.timed_out}"]
        if result.stdout.strip():
            lines.append(result.stdout.strip())
        if result.stderr.strip():
            lines.append(result.stderr.strip())
        if not lines:
            return
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
            handle.write("\n")

    @staticmethod
    def _is_package_installed(collector: ADBCollector, package_name: str) -> bool:
        """Check whether the target package exists on the target device."""
        result = collector._run_adb_command(f"shell pm list packages {package_name}", log_errors=False)
        return bool(result and package_name in result)

    @staticmethod
    def _is_device_available(collector: ADBCollector) -> bool:
        """Check whether adb can reach the target device before starting Monkey."""
        result = collector._run_adb_command("get-state", log_errors=False)
        return bool(result and result.strip() == "device")

    @staticmethod
    def _parse_events_injected(stdout: str) -> int:
        """Extract the injected event count from monkey stdout when available."""
        for line in stdout.splitlines():
            if "Events injected:" not in line:
                continue
            try:
                return int(line.split("Events injected:", 1)[1].strip())
            except (IndexError, ValueError):
                continue
        return 0

    @staticmethod
    def _tail_text(value: str, limit: int = 2000) -> str:
        """Keep only the tail of large command output for DB/report storage."""
        text = value.strip()
        if len(text) <= limit:
            return text
        return text[-limit:]


@dataclass(frozen=True)
class _CommandResult:
    """Internal subprocess result shape for Monkey execution."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


@dataclass(frozen=True)
class _MonkeyExecutionOutcome:
    """Final Monkey result for one execution, including one optional reconnect retry."""

    result: _CommandResult
    command_attempts: int
    recovered_after_disconnect: bool
    reconnect_failed: bool
