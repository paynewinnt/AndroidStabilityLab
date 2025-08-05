from __future__ import annotations

from pathlib import Path
import time
from dataclasses import dataclass
from typing import Callable

from stability.domain import TaskTemplateType
from stability.infrastructure.adb import ADBCollector
from stability.infrastructure.command_runner import CommandResult, CommandRunner, SubprocessCommandRunner

from .base import ScenarioExecutionResult
from .tcp_recovery import TCPReconnectHelper


@dataclass(frozen=True)
class _ExecutedCommand:
    result: CommandResult
    command_attempts: int
    recovered_after_disconnect: bool
    reconnect_failed: bool


class _BaseDeviceCycleRunner:
    def __init__(
        self,
        *,
        collector_factory=ADBCollector,
        command_runner: CommandRunner | None = None,
        sleep_func: Callable[[float], None] | None = None,
        log_label: str,
    ) -> None:
        self._collector_factory = collector_factory
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._sleep = sleep_func or time.sleep
        self._tcp_recovery = TCPReconnectHelper(
            command_runner=self._command_runner,
            availability_checker=self._is_device_available,
            log_label=log_label,
        )

    def _collector_for_device(self, device_id: str) -> ADBCollector:
        collector = self._collector_factory(timeout=10, retry_count=1)
        collector.device_id = device_id
        return collector

    @staticmethod
    def _append_log(path: Path, line: str) -> None:
        if not line:
            return
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line.strip())
            handle.write("\n")

    def _sleep_ms(self, millis: int) -> None:
        if millis > 0:
            self._sleep(millis / 1000.0)

    @staticmethod
    def _is_device_available(collector: ADBCollector) -> bool:
        result = collector._run_adb_command("get-state", log_errors=False)
        return "device" in str(result or "").lower()

    @staticmethod
    def _is_package_installed(collector: ADBCollector, package_name: str) -> bool:
        result = collector._run_adb_command(f"shell pm list packages {package_name}", log_errors=False)
        return f"package:{package_name}" in str(result or "")

    @staticmethod
    def _normalize_activity(package_name: str, activity: str) -> str:
        normalized = activity.strip()
        if not normalized:
            return package_name
        if "/" in normalized:
            return normalized
        if normalized.startswith("."):
            return f"{package_name}/{normalized}"
        return f"{package_name}/{normalized}"

    def _resolve_launch_target(self, collector: ADBCollector, package_name: str, explicit_activity: str = "") -> str:
        normalized = self._normalize_activity(package_name, explicit_activity)
        if normalized != package_name:
            return normalized
        resolved = collector._run_adb_command(
            f"shell cmd package resolve-activity --brief {package_name}",
            log_errors=False,
        )
        for line in reversed(str(resolved or "").splitlines()):
            candidate = line.strip()
            if "/" in candidate and candidate.startswith(package_name):
                return candidate
        return package_name

    def _execute_command_with_reconnect(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        command: Sequence[str],
        timeout_seconds: int,
        log_path: Path,
        loop_label: str,
        reason: str,
    ) -> _ExecutedCommand:
        result = self._command_runner.run(command, timeout_seconds=timeout_seconds)
        attempts = 1
        recovered = False
        reconnect_failed = False
        if self._tcp_recovery.should_retry_after_disconnect(
            collector=collector,
            device_id=device_id,
            command_result=result,
        ):
            if self._tcp_recovery.attempt_reconnect(
                collector=collector,
                device_id=device_id,
                log_path=log_path,
                loop_label=loop_label,
                reason=reason,
            ):
                result = self._command_runner.run(command, timeout_seconds=timeout_seconds)
                attempts += 1
                recovered = True
            else:
                reconnect_failed = True
        return _ExecutedCommand(
            result=result,
            command_attempts=attempts,
            recovered_after_disconnect=recovered,
            reconnect_failed=reconnect_failed,
        )


class ForegroundBackgroundLoopScenarioRunner(_BaseDeviceCycleRunner):
    def __init__(self, collector_factory=ADBCollector, command_runner: CommandRunner | None = None, sleep_func=None) -> None:
        super().__init__(
            collector_factory=collector_factory,
            command_runner=command_runner,
            sleep_func=sleep_func,
            log_label="foreground_background_loop",
        )

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        if getattr(task, "template_type", None) != TaskTemplateType.FOREGROUND_BACKGROUND_LOOP:
            raise ValueError("ForegroundBackgroundLoopScenarioRunner only supports foreground_background_loop tasks.")

        params = getattr(task, "task_params", {}) or {}
        loop_count = max(int(params.get("loop_count", 3) or 3), 1)
        foreground_wait_ms = max(int(params.get("foreground_wait_ms", 1000) or 1000), 0)
        background_wait_ms = max(int(params.get("background_wait_ms", 1000) or 1000), 0)
        launch_timeout_seconds = max(int(params.get("launch_timeout_seconds", 20) or 20), 1)
        home_timeout_seconds = max(int(params.get("home_timeout_seconds", 10) or 10), 1)
        device_id = str(getattr(instance, "device_id", "") or "")
        package_name = str(getattr(getattr(task, "target_app", None), "package_name", "") or "")
        if not device_id:
            return ScenarioExecutionResult(success=False, note="前后台切换模板执行失败：缺少目标设备。", exit_reason="execution_error", result_level="failed")
        if not package_name:
            return ScenarioExecutionResult(success=False, note="前后台切换模板执行失败：缺少目标应用包名。", exit_reason="execution_error", result_level="failed")

        collector = self._collector_for_device(device_id)
        if not self._tcp_recovery.ensure_device_available(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label="startup",
            reason="device unavailable before foreground/background loop start",
        ):
            return ScenarioExecutionResult(
                success=False,
                note=f"前后台切换模板执行失败：设备 {device_id} 当前不可用或未连接。",
                exit_reason="device_offline",
                result_level="failed",
                metadata={"template_type": TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value, "device_id": device_id},
            )
        if not self._is_package_installed(collector, package_name):
            return ScenarioExecutionResult(
                success=False,
                note=f"前后台切换模板执行失败：设备 {device_id} 上未安装应用 {package_name}。",
                exit_reason="execution_error",
                result_level="failed",
                metadata={"template_type": TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value, "device_id": device_id},
            )

        launch_target = self._resolve_launch_target(
            collector,
            package_name,
            explicit_activity=str(getattr(getattr(task, "target_app", None), "launch_activity", "") or ""),
        )
        launch_command = ("adb", "-s", device_id, "shell", "am", "start", "-W", "-n", launch_target)
        home_command = ("adb", "-s", device_id, "shell", "input", "keyevent", "KEYCODE_HOME")
        iterations: list[dict[str, object]] = []
        for loop_index in range(1, loop_count + 1):
            launched = self._execute_command_with_reconnect(
                collector=collector,
                device_id=device_id,
                command=launch_command,
                timeout_seconds=launch_timeout_seconds,
                log_path=log_path,
                loop_label=f"loop-{loop_index}-launch",
                reason="foreground launch disconnected",
            )
            if launched.reconnect_failed or launched.result.timed_out or launched.result.returncode not in {0, None}:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"前后台切换模板第 {loop_index} 轮前台拉起失败。",
                    exit_reason="device_offline" if launched.reconnect_failed else "execution_error",
                    result_level="failed",
                    metadata={
                        "template_type": TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value,
                        "launch_target": launch_target,
                        "iterations": iterations,
                        "failed_loop": loop_index,
                    },
                )
            self._sleep_ms(foreground_wait_ms)
            background = self._execute_command_with_reconnect(
                collector=collector,
                device_id=device_id,
                command=home_command,
                timeout_seconds=home_timeout_seconds,
                log_path=log_path,
                loop_label=f"loop-{loop_index}-background",
                reason="background switch disconnected",
            )
            if background.reconnect_failed or background.result.timed_out or background.result.returncode not in {0, None}:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"前后台切换模板第 {loop_index} 轮切回后台失败。",
                    exit_reason="device_offline" if background.reconnect_failed else "execution_error",
                    result_level="failed",
                    metadata={
                        "template_type": TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value,
                        "launch_target": launch_target,
                        "iterations": iterations,
                        "failed_loop": loop_index,
                    },
                )
            self._sleep_ms(background_wait_ms)
            iterations.append(
                {
                    "loop_index": loop_index,
                    "status": "completed",
                    "launch_attempts": launched.command_attempts,
                    "background_attempts": background.command_attempts,
                    "recovered_after_disconnect": bool(
                        launched.recovered_after_disconnect or background.recovered_after_disconnect
                    ),
                }
            )
        return ScenarioExecutionResult(
            success=True,
            note=f"前后台切换模板执行完成，共执行 {loop_count} 轮。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"foreground/background loops completed: {loop_count}",),
            metadata={
                "template_type": TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value,
                "launch_target": launch_target,
                "loop_summary": {
                    "configured_loops": loop_count,
                    "completed_loops": len(iterations),
                    "iterations": iterations,
                },
            },
        )


class InstallUninstallLoopScenarioRunner(_BaseDeviceCycleRunner):
    def __init__(self, collector_factory=ADBCollector, command_runner: CommandRunner | None = None, sleep_func=None) -> None:
        super().__init__(
            collector_factory=collector_factory,
            command_runner=command_runner,
            sleep_func=sleep_func,
            log_label="install_uninstall_loop",
        )

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        if getattr(task, "template_type", None) != TaskTemplateType.INSTALL_UNINSTALL_LOOP:
            raise ValueError("InstallUninstallLoopScenarioRunner only supports install_uninstall_loop tasks.")

        params = getattr(task, "task_params", {}) or {}
        loop_count = max(int(params.get("loop_count", 2) or 2), 1)
        apk_path = str(params.get("apk_path", "") or "").strip()
        install_timeout_seconds = max(int(params.get("install_timeout_seconds", 180) or 180), 1)
        uninstall_timeout_seconds = max(int(params.get("uninstall_timeout_seconds", 60) or 60), 1)
        settle_ms = max(int(params.get("settle_ms", 1000) or 1000), 0)
        device_id = str(getattr(instance, "device_id", "") or "")
        package_name = str(getattr(getattr(task, "target_app", None), "package_name", "") or "")
        if not device_id:
            return ScenarioExecutionResult(success=False, note="安装卸载循环模板执行失败：缺少目标设备。", exit_reason="execution_error", result_level="failed")
        if not package_name:
            return ScenarioExecutionResult(success=False, note="安装卸载循环模板执行失败：缺少目标应用包名。", exit_reason="execution_error", result_level="failed")
        if not apk_path:
            return ScenarioExecutionResult(success=False, note="安装卸载循环模板执行失败：缺少 apk_path。", exit_reason="execution_error", result_level="failed")
        if not Path(apk_path).exists():
            return ScenarioExecutionResult(success=False, note=f"安装卸载循环模板执行失败：APK 不存在 {apk_path}。", exit_reason="execution_error", result_level="failed")

        collector = self._collector_for_device(device_id)
        if not self._tcp_recovery.ensure_device_available(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label="startup",
            reason="device unavailable before install/uninstall loop start",
        ):
            return ScenarioExecutionResult(
                success=False,
                note=f"安装卸载循环模板执行失败：设备 {device_id} 当前不可用或未连接。",
                exit_reason="device_offline",
                result_level="failed",
                metadata={"template_type": TaskTemplateType.INSTALL_UNINSTALL_LOOP.value, "device_id": device_id},
            )

        iterations: list[dict[str, object]] = []
        uninstall_command = ("adb", "-s", device_id, "uninstall", package_name)
        install_command = ("adb", "-s", device_id, "install", "-r", apk_path)
        for loop_index in range(1, loop_count + 1):
            was_installed = self._is_package_installed(collector, package_name)
            uninstall_attempts = 0
            install_attempts = 0
            if was_installed:
                uninstall = self._execute_command_with_reconnect(
                    collector=collector,
                    device_id=device_id,
                    command=uninstall_command,
                    timeout_seconds=uninstall_timeout_seconds,
                    log_path=log_path,
                    loop_label=f"loop-{loop_index}-uninstall",
                    reason="uninstall disconnected",
                )
                uninstall_attempts = uninstall.command_attempts
                uninstall_output = "\n".join((uninstall.result.stdout, uninstall.result.stderr)).lower()
                if uninstall.reconnect_failed or uninstall.result.timed_out:
                    return ScenarioExecutionResult(
                        success=False,
                        note=f"安装卸载循环模板第 {loop_index} 轮卸载失败。",
                        exit_reason="device_offline" if uninstall.reconnect_failed else "execution_error",
                        result_level="failed",
                        metadata={"template_type": TaskTemplateType.INSTALL_UNINSTALL_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                    )
                if uninstall.result.returncode not in {0, None} and "unknown package" not in uninstall_output and "not installed" not in uninstall_output:
                    return ScenarioExecutionResult(
                        success=False,
                        note=f"安装卸载循环模板第 {loop_index} 轮卸载失败，退出码 {uninstall.result.returncode}。",
                        exit_reason="execution_error",
                        result_level="failed",
                        metadata={"template_type": TaskTemplateType.INSTALL_UNINSTALL_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                    )

            install = self._execute_command_with_reconnect(
                collector=collector,
                device_id=device_id,
                command=install_command,
                timeout_seconds=install_timeout_seconds,
                log_path=log_path,
                loop_label=f"loop-{loop_index}-install",
                reason="install disconnected",
            )
            install_attempts = install.command_attempts
            if install.reconnect_failed or install.result.timed_out or install.result.returncode not in {0, None}:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"安装卸载循环模板第 {loop_index} 轮安装失败。",
                    exit_reason="device_offline" if install.reconnect_failed else "execution_error",
                    result_level="failed",
                    metadata={"template_type": TaskTemplateType.INSTALL_UNINSTALL_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                )
            self._sleep_ms(settle_ms)
            installed = self._is_package_installed(collector, package_name)
            if not installed:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"安装卸载循环模板第 {loop_index} 轮安装后校验失败：应用未出现在包列表中。",
                    exit_reason="execution_error",
                    result_level="failed",
                    metadata={"template_type": TaskTemplateType.INSTALL_UNINSTALL_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                )
            iterations.append(
                {
                    "loop_index": loop_index,
                    "status": "completed",
                    "was_installed": was_installed,
                    "uninstall_attempts": uninstall_attempts,
                    "install_attempts": install_attempts,
                    "install_verified": installed,
                }
            )

        return ScenarioExecutionResult(
            success=True,
            note=f"安装卸载循环模板执行完成，共执行 {loop_count} 轮。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"install/uninstall loops completed: {loop_count}",),
            metadata={
                "template_type": TaskTemplateType.INSTALL_UNINSTALL_LOOP.value,
                "loop_summary": {
                    "configured_loops": loop_count,
                    "completed_loops": len(iterations),
                    "apk_path": apk_path,
                    "iterations": iterations,
                },
            },
        )


class RebootLoopScenarioRunner(_BaseDeviceCycleRunner):
    def __init__(self, collector_factory=ADBCollector, command_runner: CommandRunner | None = None, sleep_func=None) -> None:
        super().__init__(
            collector_factory=collector_factory,
            command_runner=command_runner,
            sleep_func=sleep_func,
            log_label="reboot_loop",
        )

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        if getattr(task, "template_type", None) != TaskTemplateType.REBOOT_LOOP:
            raise ValueError("RebootLoopScenarioRunner only supports reboot_loop tasks.")

        params = getattr(task, "task_params", {}) or {}
        loop_count = max(int(params.get("loop_count", 1) or 1), 1)
        reboot_timeout_seconds = max(int(params.get("reboot_timeout_seconds", 15) or 15), 1)
        boot_wait_timeout_seconds = max(int(params.get("boot_wait_timeout_seconds", 120) or 120), 1)
        poll_interval_seconds = max(int(params.get("poll_interval_seconds", 5) or 5), 1)
        settle_ms = max(int(params.get("settle_ms", 3000) or 3000), 0)
        device_id = str(getattr(instance, "device_id", "") or "")
        if not device_id:
            return ScenarioExecutionResult(success=False, note="重启循环模板执行失败：缺少目标设备。", exit_reason="execution_error", result_level="failed")

        collector = self._collector_for_device(device_id)
        if not self._tcp_recovery.ensure_device_available(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label="startup",
            reason="device unavailable before reboot loop start",
        ):
            return ScenarioExecutionResult(
                success=False,
                note=f"重启循环模板执行失败：设备 {device_id} 当前不可用或未连接。",
                exit_reason="device_offline",
                result_level="failed",
                metadata={"template_type": TaskTemplateType.REBOOT_LOOP.value, "device_id": device_id},
            )

        reboot_command = ("adb", "-s", device_id, "reboot")
        iterations: list[dict[str, object]] = []
        for loop_index in range(1, loop_count + 1):
            rebooted = self._command_runner.run(reboot_command, timeout_seconds=reboot_timeout_seconds)
            if rebooted.timed_out or rebooted.returncode not in {0, None}:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"重启循环模板第 {loop_index} 轮触发 reboot 失败。",
                    exit_reason="execution_error",
                    result_level="failed",
                    metadata={"template_type": TaskTemplateType.REBOOT_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                )
            self._sleep_ms(settle_ms)
            recovered = self._wait_for_device_ready(
                collector=collector,
                device_id=device_id,
                timeout_seconds=boot_wait_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                log_path=log_path,
                loop_index=loop_index,
            )
            if not recovered:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"重启循环模板第 {loop_index} 轮等待设备恢复超时。",
                    exit_reason="device_offline",
                    result_level="failed",
                    metadata={"template_type": TaskTemplateType.REBOOT_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                )
            iterations.append({"loop_index": loop_index, "status": "completed"})

        return ScenarioExecutionResult(
            success=True,
            note=f"重启循环模板执行完成，共执行 {loop_count} 轮。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"reboot loops completed: {loop_count}",),
            metadata={
                "template_type": TaskTemplateType.REBOOT_LOOP.value,
                "loop_summary": {"configured_loops": loop_count, "completed_loops": len(iterations), "iterations": iterations},
            },
        )

    def _wait_for_device_ready(
        self,
        *,
        collector: ADBCollector,
        device_id: str,
        timeout_seconds: int,
        poll_interval_seconds: int,
        log_path: Path,
        loop_index: int,
    ) -> bool:
        attempts = max(int(timeout_seconds / poll_interval_seconds), 1)
        for attempt_index in range(1, attempts + 1):
            if self._is_device_available(collector):
                boot_completed = str(
                    collector._run_adb_command("shell getprop sys.boot_completed", log_errors=False) or ""
                ).strip()
                if boot_completed in {"", "1"}:
                    return True
            if self._tcp_recovery.is_tcp_device(device_id):
                self._tcp_recovery.attempt_reconnect(
                    collector=collector,
                    device_id=device_id,
                    log_path=log_path,
                    loop_label=f"loop-{loop_index}-poll-{attempt_index}",
                    reason="device still offline after reboot",
                )
            self._sleep(poll_interval_seconds)
        return False


class StandbyWakeLoopScenarioRunner(_BaseDeviceCycleRunner):
    def __init__(self, collector_factory=ADBCollector, command_runner: CommandRunner | None = None, sleep_func=None) -> None:
        super().__init__(
            collector_factory=collector_factory,
            command_runner=command_runner,
            sleep_func=sleep_func,
            log_label="standby_wake_loop",
        )

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        if getattr(task, "template_type", None) != TaskTemplateType.STANDBY_WAKE_LOOP:
            raise ValueError("StandbyWakeLoopScenarioRunner only supports standby_wake_loop tasks.")

        params = getattr(task, "task_params", {}) or {}
        loop_count = max(int(params.get("loop_count", 2) or 2), 1)
        standby_wait_ms = max(int(params.get("standby_wait_ms", 1000) or 1000), 0)
        wake_wait_ms = max(int(params.get("wake_wait_ms", 1000) or 1000), 0)
        command_timeout_seconds = max(int(params.get("command_timeout_seconds", 10) or 10), 1)
        unlock_after_wake = str(params.get("unlock_after_wake", "true")).strip().lower() not in {"0", "false", "no", "off"}
        device_id = str(getattr(instance, "device_id", "") or "")
        if not device_id:
            return ScenarioExecutionResult(success=False, note="待机唤醒循环模板执行失败：缺少目标设备。", exit_reason="execution_error", result_level="failed")

        collector = self._collector_for_device(device_id)
        if not self._tcp_recovery.ensure_device_available(
            collector=collector,
            device_id=device_id,
            log_path=log_path,
            loop_label="startup",
            reason="device unavailable before standby/wake loop start",
        ):
            return ScenarioExecutionResult(
                success=False,
                note=f"待机唤醒循环模板执行失败：设备 {device_id} 当前不可用或未连接。",
                exit_reason="device_offline",
                result_level="failed",
                metadata={"template_type": TaskTemplateType.STANDBY_WAKE_LOOP.value, "device_id": device_id},
            )

        sleep_command = ("adb", "-s", device_id, "shell", "input", "keyevent", "KEYCODE_SLEEP")
        wake_command = ("adb", "-s", device_id, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
        unlock_command = ("adb", "-s", device_id, "shell", "input", "keyevent", "KEYCODE_MENU")
        iterations: list[dict[str, object]] = []
        for loop_index in range(1, loop_count + 1):
            sleep_result = self._execute_command_with_reconnect(
                collector=collector,
                device_id=device_id,
                command=sleep_command,
                timeout_seconds=command_timeout_seconds,
                log_path=log_path,
                loop_label=f"loop-{loop_index}-sleep",
                reason="sleep transition disconnected",
            )
            if sleep_result.reconnect_failed or sleep_result.result.timed_out or sleep_result.result.returncode not in {0, None}:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"待机唤醒循环模板第 {loop_index} 轮进入待机失败。",
                    exit_reason="device_offline" if sleep_result.reconnect_failed else "execution_error",
                    result_level="failed",
                    metadata={"template_type": TaskTemplateType.STANDBY_WAKE_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                )
            self._sleep_ms(standby_wait_ms)
            wake_result = self._execute_command_with_reconnect(
                collector=collector,
                device_id=device_id,
                command=wake_command,
                timeout_seconds=command_timeout_seconds,
                log_path=log_path,
                loop_label=f"loop-{loop_index}-wake",
                reason="wake transition disconnected",
            )
            if wake_result.reconnect_failed or wake_result.result.timed_out or wake_result.result.returncode not in {0, None}:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"待机唤醒循环模板第 {loop_index} 轮唤醒失败。",
                    exit_reason="device_offline" if wake_result.reconnect_failed else "execution_error",
                    result_level="failed",
                    metadata={"template_type": TaskTemplateType.STANDBY_WAKE_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                )
            unlock_attempted = False
            if unlock_after_wake:
                unlock_attempted = True
                unlock_result = self._execute_command_with_reconnect(
                    collector=collector,
                    device_id=device_id,
                    command=unlock_command,
                    timeout_seconds=command_timeout_seconds,
                    log_path=log_path,
                    loop_label=f"loop-{loop_index}-unlock",
                    reason="unlock transition disconnected",
                )
                if unlock_result.reconnect_failed or unlock_result.result.timed_out or unlock_result.result.returncode not in {0, None}:
                    return ScenarioExecutionResult(
                        success=False,
                        note=f"待机唤醒循环模板第 {loop_index} 轮解锁失败。",
                        exit_reason="device_offline" if unlock_result.reconnect_failed else "execution_error",
                        result_level="failed",
                        metadata={"template_type": TaskTemplateType.STANDBY_WAKE_LOOP.value, "iterations": iterations, "failed_loop": loop_index},
                    )
            self._sleep_ms(wake_wait_ms)
            iterations.append({"loop_index": loop_index, "status": "completed", "unlock_attempted": unlock_attempted})

        return ScenarioExecutionResult(
            success=True,
            note=f"待机唤醒循环模板执行完成，共执行 {loop_count} 轮。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"standby/wake loops completed: {loop_count}",),
            metadata={
                "template_type": TaskTemplateType.STANDBY_WAKE_LOOP.value,
                "loop_summary": {"configured_loops": loop_count, "completed_loops": len(iterations), "iterations": iterations},
            },
        )
