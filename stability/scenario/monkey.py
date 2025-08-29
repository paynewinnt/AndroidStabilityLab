from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
import math
import re
import subprocess
import threading
import time
from typing import Any, Dict, Sequence

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
    event_percentages: dict[str, int] = field(default_factory=dict)
    recover_inject_events: bool = True
    inject_events_retry_count: int = 50
    relaunch_wait_seconds: float = 2.0
    recover_adb_transport: bool = True
    adb_transport_retry_count: int = 1
    adb_transport_wait_seconds: float = 10.0
    foreground_guard_enabled: bool = True
    foreground_guard_interval_seconds: float = 1.0
    foreground_guard_grace_seconds: float = 5.0
    foreground_drift_retry_count: int = 50
    foreground_guard_stop_foreign_app: bool = True
    foreground_guard_allowed_packages: tuple[str, ...] = ()
    block_notification_shade: bool = True


class MonkeyScenarioRunner:
    """Execute a real adb monkey command for V1 Monkey tasks."""

    _active_processes_lock = threading.Lock()
    _active_processes: dict[tuple[str, str], set[subprocess.Popen]] = {}

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

    @classmethod
    def stop_active_processes(
        cls,
        *,
        device_ids: Sequence[str],
        package_name: str = "",
        timeout_seconds: float = 1.0,
    ) -> list[dict[str, Any]]:
        """Terminate host-side adb monkey processes currently tracked by this process."""
        normalized_devices = {str(item or "").strip() for item in device_ids if str(item or "").strip()}
        normalized_package = str(package_name or "").strip()
        with cls._active_processes_lock:
            matches = [
                (device_id, package, process)
                for (device_id, package), processes in cls._active_processes.items()
                for process in tuple(processes)
                if process.poll() is None
                and (not normalized_devices or device_id in normalized_devices)
                and (not normalized_package or package == normalized_package)
            ]

        results: list[dict[str, Any]] = []
        for device_id, package, process in matches:
            result: dict[str, Any] = {
                "device_id": device_id,
                "package_name": package,
                "pid": process.pid,
                "action": "host_adb_monkey_terminate",
                "ok": False,
                "killed": False,
            }
            try:
                process.terminate()
                try:
                    process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    result["killed"] = True
                    process.wait(timeout=timeout_seconds)
                result["return_code"] = process.returncode
                result["ok"] = process.poll() is not None
            except Exception as exc:  # pragma: no cover - best-effort cleanup path
                result["error"] = str(exc)
            results.append(result)
        return results

    @classmethod
    def _register_active_process(cls, *, device_id: str, package_name: str, process: subprocess.Popen) -> None:
        key = (str(device_id or ""), str(package_name or ""))
        with cls._active_processes_lock:
            cls._active_processes.setdefault(key, set()).add(process)

    @classmethod
    def _unregister_active_process(cls, *, device_id: str, package_name: str, process: subprocess.Popen) -> None:
        key = (str(device_id or ""), str(package_name or ""))
        with cls._active_processes_lock:
            processes = cls._active_processes.get(key)
            if processes is None:
                return
            processes.discard(process)
            if not processes:
                cls._active_processes.pop(key, None)

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
        launch_activity = getattr(task.target_app, "launch_activity", "") if getattr(task, "target_app", None) else ""
        execution = self._execute_command_with_reconnect_retry(
            collector=collector,
            device_id=device_id,
            package_name=package_name,
            launch_activity=launch_activity,
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
            "recovered_after_adb_transport": execution.recovered_after_adb_transport,
            "adb_transport_recovery_count": execution.adb_transport_recovery_count,
            "recovered_after_inject_events": execution.recovered_after_inject_events,
            "inject_events_recovery_count": execution.inject_events_recovery_count,
            "recovered_after_foreground_drift": execution.recovered_after_foreground_drift,
            "foreground_drift_recovery_count": execution.foreground_drift_recovery_count,
            "block_notification_shade": config.block_notification_shade,
            "effective_event_percentages": dict(config.event_percentages),
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

        def _percentage_value(name: str) -> int | None:
            value = params.get(name)
            if value in (None, ""):
                return None
            try:
                return min(max(int(value), 0), 100)
            except (TypeError, ValueError):
                return None

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

        def _float_value(name: str, default: float) -> float:
            value = params.get(name, default)
            try:
                return max(float(value), 0.0)
            except (TypeError, ValueError):
                return default

        def _tuple_value(name: str) -> tuple[str, ...]:
            value = params.get(name)
            if not value:
                return ()
            if isinstance(value, (list, tuple, set)):
                return tuple(str(item).strip() for item in value if str(item).strip())
            return tuple(part.strip() for part in str(value).split(",") if part.strip())

        seed = params.get("seed")
        try:
            normalized_seed = int(seed) if seed is not None and seed != "" else None
        except (TypeError, ValueError):
            normalized_seed = None

        timeout_seconds = _int_value("timeout_seconds", getattr(task, "timeout_seconds", 0) or 180)
        percentage_options = {
            key: value
            for key in (
                "pct_touch",
                "pct_motion",
                "pct_trackball",
                "pct_syskeys",
                "pct_nav",
                "pct_majornav",
                "pct_appswitch",
                "pct_flip",
                "pct_anyevent",
                "pct_pinchzoom",
                "pct_permission",
            )
            if (value := _percentage_value(key)) is not None
        }
        block_notification_shade = _bool_value("block_notification_shade", True)
        if block_notification_shade:
            percentage_options = MonkeyScenarioRunner._disable_status_bar_drag_events(percentage_options)
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
            event_percentages=percentage_options,
            recover_inject_events=_bool_value("recover_inject_events", True),
            inject_events_retry_count=_int_value("inject_events_retry_count", 50),
            relaunch_wait_seconds=_float_value("relaunch_wait_seconds", 2.0),
            recover_adb_transport=_bool_value("recover_adb_transport", True),
            adb_transport_retry_count=_int_value("adb_transport_retry_count", 1),
            adb_transport_wait_seconds=_float_value("adb_transport_wait_seconds", 10.0),
            foreground_guard_enabled=_bool_value("foreground_guard_enabled", True),
            foreground_guard_interval_seconds=_float_value("foreground_guard_interval_seconds", 1.0),
            foreground_guard_grace_seconds=_float_value("foreground_guard_grace_seconds", 5.0),
            foreground_drift_retry_count=_int_value("foreground_drift_retry_count", 50),
            foreground_guard_stop_foreign_app=_bool_value("foreground_guard_stop_foreign_app", True),
            foreground_guard_allowed_packages=_tuple_value("foreground_guard_allowed_packages"),
            block_notification_shade=block_notification_shade,
        )

    @staticmethod
    def _disable_status_bar_drag_events(event_percentages: dict[str, int]) -> dict[str, int]:
        """Avoid drag gestures that can pull down notification shade or quick settings."""
        adjusted = dict(event_percentages)
        motion = int(adjusted.get("pct_motion", 0) or 0)
        if motion > 0:
            adjusted["pct_touch"] = min(100, int(adjusted.get("pct_touch", 0) or 0) + motion)
        elif "pct_touch" not in adjusted:
            adjusted["pct_touch"] = 100
        adjusted["pct_motion"] = 0
        return adjusted

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
        for key, value in config.event_percentages.items():
            command.extend([f"--{key.replace('_', '-')}", str(value)])
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
        launch_activity: str,
        config: MonkeyExecutionConfig,
        command: list[str],
        log_path: Path,
    ) -> "_MonkeyExecutionOutcome":
        """Retry failed Monkey commands after scoped INJECT_EVENTS or adb transport recovery."""
        recovered_after_disconnect = False
        recovered_after_adb_transport = False
        adb_transport_recovery_count = 0
        recovered_after_inject_events = False
        inject_events_recovery_count = 0
        recovered_after_foreground_drift = False
        foreground_drift_recovery_count = 0
        just_relaunched_target = False
        overall_deadline = time.monotonic() + max(config.timeout_seconds, 1)
        result = _CommandResult(returncode=None, stdout="", stderr="", timed_out=True)
        max_attempts = max(
            2,
            1
            + max(config.inject_events_retry_count, 0)
            + max(config.adb_transport_retry_count, 0)
            + max(config.foreground_drift_retry_count, 0),
        )
        for attempt_index in range(1, max_attempts + 1):
            remaining_timeout_seconds = self._remaining_timeout_seconds(overall_deadline)
            if remaining_timeout_seconds <= 0:
                result = self._overall_timeout_result(result, timeout_seconds=config.timeout_seconds)
                self._append_recovery_log(
                    log_path,
                    f"[monkey] overall timeout reached after {config.timeout_seconds} seconds; stopping retry loop",
                )
                return _MonkeyExecutionOutcome(
                    result=result,
                    command_attempts=attempt_index - 1,
                    recovered_after_disconnect=recovered_after_disconnect,
                    recovered_after_adb_transport=recovered_after_adb_transport,
                    adb_transport_recovery_count=adb_transport_recovery_count,
                    recovered_after_inject_events=recovered_after_inject_events,
                    inject_events_recovery_count=inject_events_recovery_count,
                    recovered_after_foreground_drift=recovered_after_foreground_drift,
                    foreground_drift_recovery_count=foreground_drift_recovery_count,
                    reconnect_failed=False,
                )
            self._stop_device_monkey_processes(collector, log_path=log_path)
            if config.force_stop_before_start and not just_relaunched_target:
                collector._run_adb_command(f"shell am force-stop {package_name}", log_errors=False)
            just_relaunched_target = False

            result = self._run_monkey_command(
                collector=collector,
                package_name=package_name,
                config=config,
                command=command,
                timeout_seconds=remaining_timeout_seconds,
                log_path=log_path,
                attempt_index=attempt_index,
            )
            self._append_command_output(log_path, attempt_index=attempt_index, result=result)
            if result.returncode != 0 and self._overall_timeout_reached(overall_deadline):
                result = self._overall_timeout_result(result, timeout_seconds=config.timeout_seconds)
                self._append_recovery_log(
                    log_path,
                    f"[monkey] overall timeout reached after {config.timeout_seconds} seconds; skipping recovery retry",
                )
                return _MonkeyExecutionOutcome(
                    result=result,
                    command_attempts=attempt_index,
                    recovered_after_disconnect=recovered_after_disconnect,
                    recovered_after_adb_transport=recovered_after_adb_transport,
                    adb_transport_recovery_count=adb_transport_recovery_count,
                    recovered_after_inject_events=recovered_after_inject_events,
                    inject_events_recovery_count=inject_events_recovery_count,
                    recovered_after_foreground_drift=recovered_after_foreground_drift,
                    foreground_drift_recovery_count=foreground_drift_recovery_count,
                    reconnect_failed=False,
                )
            if (
                config.recover_inject_events
                and attempt_index < max_attempts
                and inject_events_recovery_count < config.inject_events_retry_count
                and self._is_inject_events_failure(result)
            ):
                inject_events_recovery_count += 1
                recovered_after_inject_events = True
                just_relaunched_target = self._recover_after_inject_events(
                    collector=collector,
                    package_name=package_name,
                    launch_activity=launch_activity,
                    wait_seconds=config.relaunch_wait_seconds,
                    log_path=log_path,
                    attempt_index=attempt_index,
                )
                continue

            if (
                config.foreground_guard_enabled
                and attempt_index < max_attempts
                and foreground_drift_recovery_count < config.foreground_drift_retry_count
                and self._is_foreground_drift_failure(result)
            ):
                foreground_drift_recovery_count += 1
                recovered_after_foreground_drift = True
                just_relaunched_target = self._recover_after_foreground_drift(
                    collector=collector,
                    package_name=package_name,
                    launch_activity=launch_activity,
                    foreground_package=self._extract_foreground_drift_package(result),
                    config=config,
                    log_path=log_path,
                    attempt_index=attempt_index,
                )
                continue

            if (
                config.recover_adb_transport
                and attempt_index < max_attempts
                and adb_transport_recovery_count < config.adb_transport_retry_count
                and self._should_recover_after_adb_transport_failure(collector, result)
            ):
                adb_transport_recovery_count += 1
                just_relaunched_target = self._recover_after_adb_transport_failure(
                    collector=collector,
                    device_id=device_id,
                    package_name=package_name,
                    launch_activity=launch_activity,
                    wait_seconds=config.adb_transport_wait_seconds,
                    relaunch_wait_seconds=config.relaunch_wait_seconds,
                    log_path=log_path,
                    attempt_index=attempt_index,
                )
                if just_relaunched_target:
                    recovered_after_adb_transport = True
                    if self._tcp_recovery.is_tcp_device(device_id):
                        recovered_after_disconnect = True
                    continue
                return _MonkeyExecutionOutcome(
                    result=result,
                    command_attempts=attempt_index,
                    recovered_after_disconnect=recovered_after_disconnect,
                    recovered_after_adb_transport=recovered_after_adb_transport,
                    adb_transport_recovery_count=adb_transport_recovery_count,
                    recovered_after_inject_events=recovered_after_inject_events,
                    inject_events_recovery_count=inject_events_recovery_count,
                    recovered_after_foreground_drift=recovered_after_foreground_drift,
                    foreground_drift_recovery_count=foreground_drift_recovery_count,
                    reconnect_failed=True,
                )

            if attempt_index >= max_attempts or not self._tcp_recovery.should_retry_after_disconnect(
                collector=collector,
                device_id=device_id,
                command_result=result,
            ):
                return _MonkeyExecutionOutcome(
                    result=result,
                    command_attempts=attempt_index,
                    recovered_after_disconnect=recovered_after_disconnect,
                    recovered_after_adb_transport=recovered_after_adb_transport,
                    adb_transport_recovery_count=adb_transport_recovery_count,
                    recovered_after_inject_events=recovered_after_inject_events,
                    inject_events_recovery_count=inject_events_recovery_count,
                    recovered_after_foreground_drift=recovered_after_foreground_drift,
                    foreground_drift_recovery_count=foreground_drift_recovery_count,
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
                    recovered_after_adb_transport=recovered_after_adb_transport,
                    adb_transport_recovery_count=adb_transport_recovery_count,
                    recovered_after_inject_events=recovered_after_inject_events,
                    inject_events_recovery_count=inject_events_recovery_count,
                    recovered_after_foreground_drift=recovered_after_foreground_drift,
                    foreground_drift_recovery_count=foreground_drift_recovery_count,
                    reconnect_failed=True,
                )

            recovered_after_disconnect = True
            TCPReconnectHelper.append_runtime_log(
                log_path,
                "[monkey] execution reconnect recovered command path, retrying current execution",
            )

        return _MonkeyExecutionOutcome(
            result=result,
            command_attempts=max_attempts,
            recovered_after_disconnect=recovered_after_disconnect,
            recovered_after_adb_transport=recovered_after_adb_transport,
            adb_transport_recovery_count=adb_transport_recovery_count,
            recovered_after_inject_events=recovered_after_inject_events,
            inject_events_recovery_count=inject_events_recovery_count,
            recovered_after_foreground_drift=recovered_after_foreground_drift,
            foreground_drift_recovery_count=foreground_drift_recovery_count,
            reconnect_failed=False,
        )

    @staticmethod
    def _remaining_timeout_seconds(deadline: float) -> int:
        return max(math.ceil(deadline - time.monotonic()), 0)

    @staticmethod
    def _overall_timeout_reached(deadline: float) -> bool:
        return time.monotonic() >= deadline

    @staticmethod
    def _overall_timeout_result(result: "_CommandResult", *, timeout_seconds: int) -> "_CommandResult":
        marker = f"[monkey] overall_timeout_reached timeout_seconds={timeout_seconds}"
        stderr = f"{result.stderr.rstrip()}\n{marker}".strip()
        return _CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=stderr,
            timed_out=True,
        )

    def _run_monkey_command(
        self,
        *,
        collector: ADBCollector,
        package_name: str,
        config: MonkeyExecutionConfig,
        command: list[str],
        timeout_seconds: int,
        log_path: Path,
        attempt_index: int,
    ) -> "_CommandResult":
        if not config.foreground_guard_enabled or type(self._command_runner) is not SubprocessCommandRunner:
            return self._command_runner.run(command, timeout_seconds=timeout_seconds)
        return self._run_command_with_foreground_guard(
            collector=collector,
            package_name=package_name,
            allowed_packages=(package_name, *config.foreground_guard_allowed_packages),
            command=command,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=config.foreground_guard_interval_seconds,
            grace_seconds=config.foreground_guard_grace_seconds,
            log_path=log_path,
            attempt_index=attempt_index,
        )

    def _run_command_with_foreground_guard(
        self,
        *,
        collector: ADBCollector,
        package_name: str,
        allowed_packages: tuple[str, ...],
        command: list[str],
        timeout_seconds: int,
        poll_interval_seconds: float,
        grace_seconds: float,
        log_path: Path,
        attempt_index: int,
    ) -> "_CommandResult":
        start_time = time.monotonic()
        deadline = start_time + max(timeout_seconds, 1)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        device_id = str(getattr(collector, "device_id", "") or "")
        self._register_active_process(device_id=device_id, package_name=package_name, process=process)
        try:
            while True:
                remaining_seconds = max(deadline - time.monotonic(), 0.0)
                try:
                    stdout, stderr = process.communicate(
                        timeout=min(max(poll_interval_seconds, 0.2), remaining_seconds or 0.2)
                    )
                    return _CommandResult(
                        returncode=process.returncode,
                        stdout=stdout or "",
                        stderr=stderr or "",
                        timed_out=False,
                    )
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        process.kill()
                        self._stop_device_monkey_processes(collector, log_path=log_path)
                        stdout, stderr = process.communicate()
                        return _CommandResult(
                            returncode=None,
                            stdout=stdout or "",
                            stderr=stderr or "",
                            timed_out=True,
                        )
                    if time.monotonic() - start_time < grace_seconds:
                        continue
                    foreground_package = self._current_foreground_package(collector)
                    if not foreground_package or foreground_package in allowed_packages:
                        continue
                    self._append_recovery_log(
                        log_path,
                        (
                            f"[monkey] attempt={attempt_index} foreground drift detected: "
                            f"{foreground_package} while target is {package_name}"
                        ),
                    )
                    process.kill()
                    self._stop_device_monkey_processes(collector, log_path=log_path)
                    stdout, stderr = process.communicate()
                    guarded_stderr = (
                        f"{stderr or ''}\n"
                        f"[monkey] foreground_drift_detected foreground_package={foreground_package} target_package={package_name}"
                    ).strip()
                    return _CommandResult(
                        returncode=245,
                        stdout=stdout or "",
                        stderr=guarded_stderr,
                        timed_out=False,
                    )
        finally:
            self._unregister_active_process(device_id=device_id, package_name=package_name, process=process)

    @classmethod
    def _recover_after_inject_events(
        cls,
        *,
        collector: ADBCollector,
        package_name: str,
        launch_activity: str,
        wait_seconds: float,
        log_path: Path,
        attempt_index: int,
    ) -> bool:
        return cls._recover_target_app(
            collector=collector,
            package_name=package_name,
            launch_activity=launch_activity,
            wait_seconds=wait_seconds,
            log_path=log_path,
            attempt_index=attempt_index,
            reason="hit INJECT_EVENTS",
        )

    @classmethod
    def _recover_after_foreground_drift(
        cls,
        *,
        collector: ADBCollector,
        package_name: str,
        launch_activity: str,
        foreground_package: str,
        config: MonkeyExecutionConfig,
        log_path: Path,
        attempt_index: int,
    ) -> bool:
        return cls._recover_target_app(
            collector=collector,
            package_name=package_name,
            launch_activity=launch_activity,
            wait_seconds=config.relaunch_wait_seconds,
            log_path=log_path,
            attempt_index=attempt_index,
            reason=f"foreground drift to {foreground_package or 'unknown'}",
            foreign_package=foreground_package,
            stop_foreign_app=config.foreground_guard_stop_foreign_app,
        )

    @classmethod
    def _recover_target_app(
        cls,
        *,
        collector: ADBCollector,
        package_name: str,
        launch_activity: str,
        wait_seconds: float,
        log_path: Path,
        attempt_index: int,
        reason: str,
        foreign_package: str = "",
        stop_foreign_app: bool = False,
    ) -> bool:
        cls._append_recovery_log(
            log_path,
            f"[monkey] attempt={attempt_index} {reason}; force-stopping and relaunching {package_name}",
        )
        cls._stop_device_monkey_processes(collector, log_path=log_path)
        cls._collapse_system_surfaces(collector, log_path=log_path)
        if stop_foreign_app and cls._should_force_stop_foreign_package(foreign_package, package_name):
            collector._run_adb_command(f"shell am force-stop {foreign_package}", log_errors=False)
        collector._run_adb_command(f"shell am force-stop {package_name}", log_errors=False)
        collector._run_adb_command("shell input keyevent HOME", log_errors=False)
        launch_command = (
            f"shell am start -W -n {launch_activity}"
            if str(launch_activity or "").strip()
            else f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        )
        launch_result = collector._run_adb_command(launch_command, log_errors=False)
        cls._append_recovery_log(log_path, f"[monkey] relaunch_command={launch_command}\n{str(launch_result or '').strip()}")
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        return True

    def _recover_after_adb_transport_failure(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        package_name: str,
        launch_activity: str,
        wait_seconds: float,
        relaunch_wait_seconds: float,
        log_path: Path,
        attempt_index: int,
    ) -> bool:
        self._append_recovery_log(
            log_path,
            f"[monkey] attempt={attempt_index} hit adb transport interruption; waiting for {device_id}",
        )
        available = (
            self._tcp_recovery.attempt_reconnect(
                collector=collector,
                device_id=device_id,
                log_path=log_path,
                loop_label=f"attempt={attempt_index}",
                reason="adb transport interrupted during monkey",
            )
            if self._tcp_recovery.is_tcp_device(device_id)
            else self._wait_for_device_available(collector, wait_seconds=wait_seconds, log_path=log_path)
        )
        if not available:
            self._append_recovery_log(
                log_path,
                f"[monkey] attempt={attempt_index} adb transport recovery failed for {device_id}",
            )
            return False
        return self._recover_after_inject_events(
            collector=collector,
            package_name=package_name,
            launch_activity=launch_activity,
            wait_seconds=relaunch_wait_seconds,
            log_path=log_path,
            attempt_index=attempt_index,
        )

    @staticmethod
    def _is_inject_events_failure(result: "_CommandResult") -> bool:
        output = f"{result.stdout}\n{result.stderr}".lower()
        return "inject_events" in output or "injecting to another application" in output

    @staticmethod
    def _is_foreground_drift_failure(result: "_CommandResult") -> bool:
        output = f"{result.stdout}\n{result.stderr}".lower()
        return "foreground_drift_detected" in output

    @staticmethod
    def _extract_foreground_drift_package(result: "_CommandResult") -> str:
        output = f"{result.stdout}\n{result.stderr}"
        match = re.search(r"foreground_package=([A-Za-z0-9_.$]+)", output)
        return match.group(1) if match else ""

    def _should_recover_after_adb_transport_failure(self, collector: ADBCollector, result: "_CommandResult") -> bool:
        if not (result.timed_out or result.returncode not in {0, None}):
            return False
        if self._tcp_recovery.looks_like_disconnect(command_result=result):
            return True
        return result.returncode == 255 and not self._is_device_available(collector)

    def _wait_for_device_available(self, collector: ADBCollector, *, wait_seconds: float, log_path: Path) -> bool:
        deadline = time.monotonic() + max(wait_seconds, 0.0)
        while True:
            if self._is_device_available(collector):
                self._append_recovery_log(log_path, "[monkey] adb transport is available again")
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(1.0)

    @classmethod
    def _current_foreground_package(cls, collector: ADBCollector) -> str:
        output = collector._run_adb_command("shell dumpsys window", log_errors=False) or ""
        return cls._parse_foreground_package(str(output))

    @staticmethod
    def _parse_foreground_package(output: str) -> str:
        for pattern in (
            r"mCurrentFocus=.*?\s([A-Za-z0-9_.$]+)/(?:[^\s}]+)",
            r"mFocusedApp=.*?\s([A-Za-z0-9_.$]+)/(?:[^\s}]+)",
            r"topApp=.*?\s([A-Za-z0-9_.$]+)/(?:[^\s}]+)",
        ):
            match = re.search(pattern, output or "")
            if match:
                return match.group(1)
        focus_lines = "\n".join(
            line
            for line in (output or "").splitlines()
            if any(token in line for token in ("mCurrentFocus", "mFocusedApp", "topApp"))
        )
        if re.search(r"com\.android\.systemui|NotificationShade|StatusBar|QuickSettings|QSPanel", focus_lines, re.I):
            return "com.android.systemui"
        return ""

    @staticmethod
    def _should_force_stop_foreign_package(foreign_package: str, package_name: str) -> bool:
        if not foreign_package or foreign_package == package_name:
            return False
        protected_prefixes = (
            "android",
            "com.android.systemui",
            "com.google.android.permissioncontroller",
            "com.android.permissioncontroller",
        )
        protected_packages = {
            "com.hihonor.android.launcher",
            "com.huawei.android.launcher",
            "com.google.android.apps.nexuslauncher",
        }
        return foreign_package not in protected_packages and not any(
            foreign_package == prefix or foreign_package.startswith(f"{prefix}.") for prefix in protected_prefixes
        )

    @classmethod
    def _stop_device_monkey_processes(cls, collector: ADBCollector, *, log_path: Path | None = None) -> None:
        output = collector._run_adb_command("shell pidof com.android.commands.monkey", log_errors=False) or ""
        pids: list[str] = []
        for part in str(output).replace("\n", " ").split():
            if part.isdigit():
                pids.append(part)
        if not pids:
            ps_output = collector._run_adb_command("shell ps -A", log_errors=False) or ""
            for line in str(ps_output).splitlines():
                if "com.android.commands.monkey" not in line:
                    continue
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    pids.append(parts[1])
        if not pids:
            return
        collector._run_adb_command(f"shell kill {' '.join(pids)}", log_errors=False)
        remaining = collector._run_adb_command("shell pidof com.android.commands.monkey", log_errors=False) or ""
        remaining_pids = [part for part in str(remaining).replace("\n", " ").split() if part.isdigit()]
        if remaining_pids:
            collector._run_adb_command(f"shell kill -9 {' '.join(remaining_pids)}", log_errors=False)
        if log_path is not None:
            cls._append_recovery_log(log_path, f"[monkey] stopped residual device monkey processes: {','.join(pids)}")

    @classmethod
    def _collapse_system_surfaces(cls, collector: ADBCollector, *, log_path: Path | None = None) -> None:
        collector._run_adb_command("shell cmd statusbar collapse", log_errors=False)
        collector._run_adb_command("shell input keyevent BACK", log_errors=False)
        if log_path is not None:
            cls._append_recovery_log(log_path, "[monkey] collapsed notification shade / quick settings surfaces")

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
    def _append_recovery_log(path: Path, message: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip())
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
    recovered_after_adb_transport: bool
    adb_transport_recovery_count: int
    recovered_after_inject_events: bool
    inject_events_recovery_count: int
    recovered_after_foreground_drift: bool
    foreground_drift_recovery_count: int
    reconnect_failed: bool
