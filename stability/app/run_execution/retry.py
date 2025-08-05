from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING
from stability.time_utils import now_beijing_string

if TYPE_CHECKING:
    from ..execution_service import ExecutionInstanceLike, TaskDefinitionLike, TaskRunLike
    from stability.scenario import ScenarioRunner


def _display_now() -> str:
    return now_beijing_string()


@dataclass(frozen=True)
class RetryDecision:
    """Describe whether one failed attempt is worth retrying at execute-run level."""

    should_retry: bool
    category: str
    reason: str


class RetryHelpersMixin:
    """Retry classification and cleanup helpers for run execution."""

    RETRYABLE_TRANSPORT_MARKERS = (
        "device offline",
        "device not found",
        "no devices/emulators found",
        "transport error",
        "closed",
        "connection reset",
        "broken pipe",
        "adb: failed",
        "more than one device/emulator",
    )

    @staticmethod
    def _normalize_retry_count(retry_count: int) -> int:
        """Clamp requested retry count to a valid non-negative integer."""
        return max(0, int(retry_count or 0))

    def _execute_scenario_with_retries(
        self,
        *,
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instance: "ExecutionInstanceLike",
        layout,
        log_path: Path,
        scenario_runner: "ScenarioRunner",
        retry_count: int,
        cleanup_events: list[dict[str, Any]],
        execution_attempts: list[dict[str, Any]],
        package_name: str,
    ):
        """Execute one scenario and retry failed attempts before finalizing the instance state."""
        max_attempts = retry_count + 1
        for attempt_index in range(1, max_attempts + 1):
            self._append_log(
                log_path,
                [
                    (
                        f"[{_display_now()}] scenario attempt {attempt_index}/{max_attempts} "
                        f"started for instance {getattr(instance, 'instance_id', '')}"
                    )
                ],
            )
            try:
                scenario_result = scenario_runner.execute(task, run, instance, layout, log_path)
            except Exception as exc:
                retry_decision = self._classify_exception_retry(exc)
                execution_attempts.append(
                    {
                        "attempt": attempt_index,
                        "status": "exception",
                        "exception_type": exc.__class__.__name__,
                        "note": str(exc),
                        "retryable": retry_decision.should_retry,
                        "retry_category": retry_decision.category,
                        "retry_decision_reason": retry_decision.reason,
                    }
                )
                if attempt_index >= max_attempts or not retry_decision.should_retry:
                    raise
                self._cleanup_interrupted_execution(
                    instance=instance,
                    package_name=package_name,
                    log_path=log_path,
                    cleanup_events=cleanup_events,
                    reason=(
                        f"retry cleanup after attempt {attempt_index} raised {exc.__class__.__name__} "
                        f"({retry_decision.category})"
                    ),
                )
                continue

            retry_decision = self._classify_scenario_retry(scenario_result)
            execution_attempts.append(
                {
                    "attempt": attempt_index,
                    "status": "success" if getattr(scenario_result, "success", False) else "failed",
                    "exit_reason": getattr(scenario_result, "exit_reason", ""),
                    "result_level": getattr(scenario_result, "result_level", ""),
                    "note": getattr(scenario_result, "note", ""),
                    "retryable": retry_decision.should_retry,
                    "retry_category": retry_decision.category,
                    "retry_decision_reason": retry_decision.reason,
                }
            )
            if (
                scenario_result is None
                or scenario_result.success
                or attempt_index >= max_attempts
                or not retry_decision.should_retry
            ):
                return scenario_result

            self._cleanup_interrupted_execution(
                instance=instance,
                package_name=package_name,
                log_path=log_path,
                cleanup_events=cleanup_events,
                reason=(
                    f"retry cleanup after attempt {attempt_index} failed with "
                    f"{getattr(scenario_result, 'exit_reason', 'unknown')} ({retry_decision.category})"
                ),
            )
        return scenario_result

    def _cleanup_interrupted_execution(
        self,
        *,
        instance: "ExecutionInstanceLike",
        package_name: str,
        log_path: Path,
        cleanup_events: list[dict[str, Any]],
        reason: str,
    ) -> None:
        """Best-effort stop the target app after retries, failures, or interruptions."""
        if not package_name:
            cleanup_events.append(
                {
                    "reason": reason,
                    "action": "force_stop",
                    "performed": False,
                    "message": "missing package name",
                }
            )
            return

        command = [
            "adb",
            "-s",
            getattr(instance, "device_id", ""),
            "shell",
            "am",
            "force-stop",
            package_name,
        ]
        result = self._host_command_runner.run(command, timeout_seconds=15)
        cleanup_event = {
            "reason": reason,
            "action": "force_stop",
            "performed": True,
            "command": command,
            "return_code": result.returncode,
            "timed_out": result.timed_out,
            "stdout_tail": self._tail_text(result.stdout),
            "stderr_tail": self._tail_text(result.stderr),
        }
        cleanup_events.append(cleanup_event)
        self._append_log(
            log_path,
            [
                (
                    f"[{_display_now()}] cleanup reason={reason} action=force_stop "
                    f"return_code={result.returncode} timed_out={result.timed_out}"
                ),
                f"cleanup_stdout={self._tail_text(result.stdout, limit=200)}",
                f"cleanup_stderr={self._tail_text(result.stderr, limit=200)}",
            ],
        )

    @classmethod
    def _classify_scenario_retry(cls, scenario_result) -> RetryDecision:
        """Retry only clearly recoverable scenario failures."""
        if scenario_result is None:
            return RetryDecision(False, "missing_result", "scenario runner returned no result")
        if getattr(scenario_result, "success", False):
            return RetryDecision(False, "completed", "successful attempt does not need retry")

        metadata = dict(getattr(scenario_result, "metadata", {}) or {})
        exit_reason = str(getattr(scenario_result, "exit_reason", "") or "")
        note = str(getattr(scenario_result, "note", "") or "")
        startup_failure_kind = str(metadata.get("startup_failure_kind", "") or "")
        failure_reason = str(metadata.get("startup_failure_reason", "") or "")
        error_text = "\n".join(
            part.strip()
            for part in (
                note,
                failure_reason,
                str(metadata.get("stdout_tail", "") or ""),
                str(metadata.get("stderr_tail", "") or ""),
            )
            if part and part.strip()
        )

        if exit_reason == "device_offline":
            return RetryDecision(True, "device_offline", "device became unavailable during execution")
        if startup_failure_kind == "startup_timeout":
            return RetryDecision(True, "startup_timeout", "startup timeout is treated as transient once")
        if cls._looks_like_transport_failure(error_text):
            return RetryDecision(True, "adb_transport", "adb transport output looks transient")
        if exit_reason == "timeout":
            return RetryDecision(False, "timeout", "timeout is not classified as transient for this attempt")
        if exit_reason == "execution_error":
            return RetryDecision(False, "execution_error", "execution error is not retryable without transport markers")
        return RetryDecision(False, exit_reason or "unknown", "exit reason is not in retryable categories")

    @classmethod
    def _classify_exception_retry(cls, exc: Exception) -> RetryDecision:
        """Retry only exception paths that look like adb transport failures."""
        message = f"{exc.__class__.__name__}: {exc}"
        if cls._looks_like_transport_failure(message):
            return RetryDecision(
                True,
                "adb_transport_exception",
                "exception text looks like adb transport failure",
            )
        return RetryDecision(False, "exception", "exception does not match retryable transport markers")

    @classmethod
    def _looks_like_transport_failure(cls, text: str) -> bool:
        """Detect transient adb transport failures from one combined error blob."""
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        return any(marker in normalized for marker in cls.RETRYABLE_TRANSPORT_MARKERS)

    @staticmethod
    def _retry_policy_metadata(retry_count: int) -> dict[str, Any]:
        """Return one stable retry policy block for summaries and future analysis."""
        return {
            "retry_count": retry_count,
            "max_attempts": retry_count + 1,
            "strategy": "classified",
            "retryable_categories": [
                "device_offline",
                "startup_timeout",
                "adb_transport",
                "adb_transport_exception",
            ],
        }

    @staticmethod
    def _tail_text(value: str, limit: int = 2000) -> str:
        """Keep only the tail of large command output for report and metadata storage."""
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[-limit:]
