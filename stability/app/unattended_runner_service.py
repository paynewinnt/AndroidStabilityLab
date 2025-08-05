from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from stability.domain.value_objects import utcnow


class UnattendedServiceLike(Protocol):
    def run_due_tasks(
        self,
        *,
        task_id: str = "",
        force: bool = False,
        requested_by: str = "automation",
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ):
        ...

    def build_daily_report(
        self,
        *,
        report_date: str = "",
        task_id: str = "",
    ):
        ...

    def build_weekly_report(
        self,
        *,
        report_date: str = "",
        task_id: str = "",
    ):
        ...


@dataclass(frozen=True)
class UnattendedPatrolRunnerCycle:
    cycle_index: int
    started_at: datetime
    finished_at: datetime
    patrol: object


@dataclass(frozen=True)
class UnattendedPatrolRunnerPaths:
    root_dir: str
    lock_path: str
    heartbeat_path: str
    daily_reports_dir: str
    weekly_reports_dir: str


@dataclass(frozen=True)
class UnattendedPatrolRunnerResult:
    started_at: datetime
    finished_at: datetime
    interval_seconds: int
    max_iterations: int
    cycle_count: int
    stopped_reason: str
    task_id: str = ""
    force: bool = False
    paths: UnattendedPatrolRunnerPaths | None = None
    latest_daily_report: dict[str, Any] = field(default_factory=dict)
    daily_report_paths: dict[str, str] = field(default_factory=dict)
    latest_weekly_report: dict[str, Any] = field(default_factory=dict)
    weekly_report_paths: dict[str, str] = field(default_factory=dict)
    patrols: tuple[UnattendedPatrolRunnerCycle, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UnattendedPatrolRunnerStatus:
    observed_at: datetime
    root_dir: str
    lock_path: str
    heartbeat_path: str
    lock_present: bool
    heartbeat_present: bool
    lock_state: str
    status: str
    pid: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: int | None = None
    stale_after_seconds: int = 0
    is_stale: bool = False
    interval_seconds: int = 0
    max_iterations: int = 0
    task_id: str = ""
    force: bool = False
    cycle_count: int = 0
    active_cycle_index: int = 0
    stopped_reason: str = ""
    latest_daily_report: dict[str, Any] = field(default_factory=dict)
    daily_report_paths: dict[str, str] = field(default_factory=dict)
    latest_weekly_report: dict[str, Any] = field(default_factory=dict)
    weekly_report_paths: dict[str, str] = field(default_factory=dict)
    last_patrol: dict[str, Any] = field(default_factory=dict)
    recent_patrols: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class UnattendedPatrolRunnerAlreadyRunning(RuntimeError):
    """Raised when another patrol runner instance is already active."""


class UnattendedPatrolRunnerService:
    """Minimal timed runner over the unattended patrol entrypoint."""

    _MAX_RECENT_PATROLS = 8

    def __init__(
        self,
        *,
        unattended_service: UnattendedServiceLike,
        root_dir: str | Path = "runtime/unattended_runner",
        sleep_func: Callable[[float], None] | None = None,
        clock_func: Callable[[], datetime] | None = None,
    ) -> None:
        self._unattended_service = unattended_service
        self._root_dir = Path(root_dir)
        self._sleep_func = sleep_func or time.sleep
        self._clock_func = clock_func or utcnow

    def run(
        self,
        *,
        interval_seconds: int = 60,
        max_iterations: int = 0,
        task_id: str = "",
        force: bool = False,
        requested_by: str = "automation",
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ) -> UnattendedPatrolRunnerResult:
        interval_seconds = max(1, int(interval_seconds or 60))
        max_iterations = max(0, int(max_iterations or 0))
        started_at = self._clock_func()
        paths = self._runner_paths()
        self._acquire_lock(paths, interval_seconds=interval_seconds, started_at=started_at)
        patrols: list[UnattendedPatrolRunnerCycle] = []
        recent_patrols: list[dict[str, Any]] = []
        latest_daily_report: dict[str, Any] = {}
        daily_report_paths: dict[str, str] = {}
        latest_weekly_report: dict[str, Any] = {}
        weekly_report_paths: dict[str, str] = {}
        stopped_reason = "completed"
        failure_exc: Exception | None = None

        try:
            self._write_heartbeat(
                paths,
                status="running",
                started_at=started_at,
                interval_seconds=interval_seconds,
                max_iterations=max_iterations,
                task_id=task_id,
                force=force,
                cycle_count=0,
                recent_patrols=recent_patrols,
            )
            while True:
                cycle_started_at = self._clock_func()
                self._write_heartbeat(
                    paths,
                    status="running",
                    started_at=started_at,
                    interval_seconds=interval_seconds,
                    max_iterations=max_iterations,
                    task_id=task_id,
                    force=force,
                    cycle_count=len(patrols),
                    active_cycle_index=len(patrols) + 1,
                    recent_patrols=recent_patrols,
                )
                patrol = self._unattended_service.run_due_tasks(
                    task_id=task_id,
                    force=force,
                    requested_by=requested_by,
                    persist_monitoring=persist_monitoring,
                    collect_snapshot=collect_snapshot,
                    stop_on_failure=stop_on_failure,
                    max_concurrency=max_concurrency,
                    retry_count=retry_count,
                )
                cycle_finished_at = self._clock_func()
                patrols.append(
                    UnattendedPatrolRunnerCycle(
                        cycle_index=len(patrols) + 1,
                        started_at=cycle_started_at,
                        finished_at=cycle_finished_at,
                        patrol=patrol,
                    )
                )
                patrol_summary = self._patrol_summary_payload(
                    patrol,
                    cycle_index=len(patrols),
                    started_at=cycle_started_at,
                    finished_at=cycle_finished_at,
                )
                recent_patrols.append(patrol_summary)
                recent_patrols = recent_patrols[-self._MAX_RECENT_PATROLS :]
                daily_report = self._unattended_service.build_daily_report(task_id=task_id)
                latest_daily_report = self._daily_report_payload(daily_report)
                daily_report_paths = self._write_daily_report(paths, latest_daily_report)
                weekly_report = self._unattended_service.build_weekly_report(task_id=task_id)
                latest_weekly_report = self._weekly_report_payload(weekly_report)
                weekly_report_paths = self._write_weekly_report(paths, latest_weekly_report)
                self._write_heartbeat(
                    paths,
                    status="running",
                    started_at=started_at,
                    interval_seconds=interval_seconds,
                    max_iterations=max_iterations,
                    task_id=task_id,
                    force=force,
                    cycle_count=len(patrols),
                    last_patrol=patrol_summary,
                    recent_patrols=recent_patrols,
                    latest_daily_report=latest_daily_report,
                    daily_report_paths=daily_report_paths,
                    latest_weekly_report=latest_weekly_report,
                    weekly_report_paths=weekly_report_paths,
                )
                if max_iterations > 0 and len(patrols) >= max_iterations:
                    stopped_reason = "max_iterations_reached"
                    break
                self._sleep_func(float(interval_seconds))
        except KeyboardInterrupt:
            stopped_reason = "interrupted"
        except Exception as exc:
            stopped_reason = "failed"
            failure_exc = exc
        finally:
            finished_at = self._clock_func()
            self._write_heartbeat(
                paths,
                status="failed" if stopped_reason == "failed" else "stopped",
                started_at=started_at,
                interval_seconds=interval_seconds,
                max_iterations=max_iterations,
                task_id=task_id,
                force=force,
                cycle_count=len(patrols),
                stopped_reason=stopped_reason,
                finished_at=finished_at,
                last_patrol=recent_patrols[-1] if recent_patrols else {},
                recent_patrols=recent_patrols,
                latest_daily_report=latest_daily_report,
                daily_report_paths=daily_report_paths,
                latest_weekly_report=latest_weekly_report,
                weekly_report_paths=weekly_report_paths,
            )
            self._release_lock(paths)
        if failure_exc is not None:
            raise failure_exc

        return UnattendedPatrolRunnerResult(
            started_at=started_at,
            finished_at=finished_at,
            interval_seconds=interval_seconds,
            max_iterations=max_iterations,
            cycle_count=len(patrols),
            stopped_reason=stopped_reason,
            task_id=task_id,
            force=force,
            paths=paths,
            latest_daily_report=dict(latest_daily_report),
            daily_report_paths=dict(daily_report_paths),
            latest_weekly_report=dict(latest_weekly_report),
            weekly_report_paths=dict(weekly_report_paths),
            patrols=tuple(patrols),
        )

    def _runner_paths(self) -> UnattendedPatrolRunnerPaths:
        return UnattendedPatrolRunnerPaths(
            root_dir=str(self._root_dir),
            lock_path=str(self._root_dir / "runner.lock"),
            heartbeat_path=str(self._root_dir / "runner_status.json"),
            daily_reports_dir=str(self._root_dir / "daily_reports"),
            weekly_reports_dir=str(self._root_dir / "weekly_reports"),
        )

    def show_status(self) -> UnattendedPatrolRunnerStatus:
        observed_at = self._clock_func()
        paths = self._runner_paths()
        lock_path = Path(paths.lock_path)
        heartbeat = self._read_heartbeat(paths)
        lock_payload = self._read_json_payload(lock_path) if lock_path.exists() else {}
        heartbeat_present = bool(heartbeat)
        status = str(heartbeat.get("status", "") or "missing")
        interval_seconds = max(0, int(heartbeat.get("interval_seconds", 0) or 0))
        last_heartbeat_at = self._parse_datetime(heartbeat.get("last_heartbeat_at"))
        stale_after_seconds = max(interval_seconds * 3, 300) if interval_seconds > 0 else 300
        heartbeat_age_seconds: int | None = None
        if last_heartbeat_at is not None:
            heartbeat_age_seconds = max(0, int((observed_at - last_heartbeat_at).total_seconds()))
        is_stale = False
        if lock_path.exists():
            if not heartbeat_present:
                is_stale = True
            elif status == "running":
                is_stale = heartbeat_age_seconds is None or heartbeat_age_seconds > stale_after_seconds
        lock_state = "released"
        if lock_path.exists():
            lock_state = "stale" if is_stale else "active"
        pid = self._coerce_int(heartbeat.get("pid"))
        if pid is None:
            pid = self._coerce_int(lock_payload.get("pid"))
        started_at = self._parse_datetime(heartbeat.get("started_at")) or self._parse_datetime(
            lock_payload.get("started_at")
        )
        return UnattendedPatrolRunnerStatus(
            observed_at=observed_at,
            root_dir=paths.root_dir,
            lock_path=paths.lock_path,
            heartbeat_path=paths.heartbeat_path,
            lock_present=lock_path.exists(),
            heartbeat_present=heartbeat_present,
            lock_state=lock_state,
            status=status,
            pid=pid,
            started_at=started_at,
            finished_at=self._parse_datetime(heartbeat.get("finished_at")),
            last_heartbeat_at=last_heartbeat_at,
            heartbeat_age_seconds=heartbeat_age_seconds,
            stale_after_seconds=stale_after_seconds,
            is_stale=is_stale,
            interval_seconds=interval_seconds,
            max_iterations=max(0, int(heartbeat.get("max_iterations", 0) or 0)),
            task_id=str(heartbeat.get("task_id", "") or ""),
            force=bool(heartbeat.get("force", False)),
            cycle_count=max(0, int(heartbeat.get("cycle_count", 0) or 0)),
            active_cycle_index=max(0, int(heartbeat.get("active_cycle_index", 0) or 0)),
            stopped_reason=str(heartbeat.get("stopped_reason", "") or ""),
            latest_daily_report=dict(heartbeat.get("latest_daily_report", {}) or {}),
            daily_report_paths=dict(heartbeat.get("daily_report_paths", {}) or {}),
            latest_weekly_report=dict(heartbeat.get("latest_weekly_report", {}) or {}),
            weekly_report_paths=dict(heartbeat.get("weekly_report_paths", {}) or {}),
            last_patrol=dict(heartbeat.get("last_patrol", {}) or {}),
            recent_patrols=tuple(
                dict(item)
                for item in list(heartbeat.get("recent_patrols", []) or [])
                if isinstance(item, dict)
            ),
        )

    def _acquire_lock(
        self,
        paths: UnattendedPatrolRunnerPaths,
        *,
        interval_seconds: int,
        started_at: datetime,
    ) -> None:
        root_dir = Path(paths.root_dir)
        root_dir.mkdir(parents=True, exist_ok=True)
        lock_path = Path(paths.lock_path)
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if self._is_stale_lock(paths, interval_seconds=interval_seconds, occurred_at=started_at):
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                raise UnattendedPatrolRunnerAlreadyRunning(
                    f"Another unattended patrol runner already holds {paths.lock_path}."
                ) from None
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "started_at": started_at.isoformat(),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

    def _release_lock(self, paths: UnattendedPatrolRunnerPaths) -> None:
        try:
            Path(paths.lock_path).unlink()
        except FileNotFoundError:
            return

    def _is_stale_lock(
        self,
        paths: UnattendedPatrolRunnerPaths,
        *,
        interval_seconds: int,
        occurred_at: datetime,
    ) -> bool:
        heartbeat = self._read_heartbeat(paths)
        if not heartbeat:
            return True
        if str(heartbeat.get("status", "")) != "running":
            return True
        heartbeat_at = self._parse_datetime(heartbeat.get("last_heartbeat_at"))
        if heartbeat_at is None:
            return True
        stale_after_seconds = max(interval_seconds * 3, 300)
        return (occurred_at - heartbeat_at).total_seconds() > stale_after_seconds

    def _write_heartbeat(
        self,
        paths: UnattendedPatrolRunnerPaths,
        *,
        status: str,
        started_at: datetime,
        interval_seconds: int,
        max_iterations: int,
        task_id: str,
        force: bool,
        cycle_count: int,
        active_cycle_index: int = 0,
        stopped_reason: str = "",
        finished_at: datetime | None = None,
        last_patrol: dict[str, Any] | None = None,
        recent_patrols: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
        latest_daily_report: dict[str, Any] | None = None,
        daily_report_paths: dict[str, str] | None = None,
        latest_weekly_report: dict[str, Any] | None = None,
        weekly_report_paths: dict[str, str] | None = None,
    ) -> None:
        payload = {
            "pid": os.getpid(),
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat() if isinstance(finished_at, datetime) else None,
            "last_heartbeat_at": self._clock_func().isoformat(),
            "interval_seconds": interval_seconds,
            "max_iterations": max_iterations,
            "task_id": task_id,
            "force": force,
            "cycle_count": cycle_count,
            "active_cycle_index": active_cycle_index,
            "stopped_reason": stopped_reason,
            "last_patrol": dict(last_patrol or {}),
            "recent_patrols": [dict(item) for item in list(recent_patrols or [])],
            "latest_daily_report": dict(latest_daily_report or {}),
            "daily_report_paths": dict(daily_report_paths or {}),
            "latest_weekly_report": dict(latest_weekly_report or {}),
            "weekly_report_paths": dict(weekly_report_paths or {}),
            "lock_path": paths.lock_path,
        }
        heartbeat_path = Path(paths.heartbeat_path)
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        heartbeat_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _read_heartbeat(paths: UnattendedPatrolRunnerPaths) -> dict[str, Any]:
        heartbeat_path = Path(paths.heartbeat_path)
        if not heartbeat_path.exists():
            return {}
        try:
            return json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _read_json_payload(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _patrol_summary_payload(
        patrol: object,
        *,
        cycle_index: int = 0,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> dict[str, Any]:
        if patrol is None:
            return {}
        return {
            "cycle_index": int(cycle_index or 0),
            "started_at": _isoformat(started_at),
            "finished_at": _isoformat(finished_at),
            "generated_at": _isoformat(getattr(patrol, "generated_at", None)),
            "task_count": int(getattr(patrol, "task_count", 0) or 0),
            "due_task_count": int(getattr(patrol, "due_task_count", 0) or 0),
            "executed_task_count": int(getattr(patrol, "executed_task_count", 0) or 0),
            "skipped_task_count": int(getattr(patrol, "skipped_task_count", 0) or 0),
            "failed_rate": float(getattr(patrol, "failed_rate", 0.0) or 0.0),
            "offline_rate": float(getattr(patrol, "offline_rate", 0.0) or 0.0),
            "recovery_success_rate": float(getattr(patrol, "recovery_success_rate", 0.0) or 0.0),
            "quarantined_device_count": int(getattr(patrol, "quarantined_device_count", 0) or 0),
            "quarantine_probe_attempt_count": int(getattr(patrol, "quarantine_probe_attempt_count", 0) or 0),
            "quarantine_probe_recovered_count": int(getattr(patrol, "quarantine_probe_recovered_count", 0) or 0),
        }

    def _write_daily_report(
        self,
        paths: UnattendedPatrolRunnerPaths,
        report_payload: dict[str, Any],
    ) -> dict[str, str]:
        report_date = str(report_payload.get("report_date", "") or "").strip()
        if not report_date:
            return {}
        report_root = Path(paths.daily_reports_dir) / report_date
        report_root.mkdir(parents=True, exist_ok=True)
        json_path = report_root / "report.json"
        markdown_path = report_root / "summary.md"
        json_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self._daily_report_markdown(report_payload),
            encoding="utf-8",
        )
        return {
            "report_json_path": str(json_path),
            "summary_markdown_path": str(markdown_path),
        }

    def _write_weekly_report(
        self,
        paths: UnattendedPatrolRunnerPaths,
        report_payload: dict[str, Any],
    ) -> dict[str, str]:
        week_key = str(report_payload.get("week_key", "") or "").strip()
        if not week_key:
            return {}
        report_root = Path(paths.weekly_reports_dir) / week_key
        report_root.mkdir(parents=True, exist_ok=True)
        json_path = report_root / "report.json"
        markdown_path = report_root / "summary.md"
        json_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self._weekly_report_markdown(report_payload),
            encoding="utf-8",
        )
        return {
            "report_json_path": str(json_path),
            "summary_markdown_path": str(markdown_path),
        }

    @staticmethod
    def _daily_report_payload(report: object) -> dict[str, Any]:
        if report is None:
            return {}
        return {
            "report_date": str(getattr(report, "report_date", "") or ""),
            "generated_at": _isoformat(getattr(report, "generated_at", None)),
            "task_count": int(getattr(report, "task_count", 0) or 0),
            "active_task_count": int(getattr(report, "active_task_count", 0) or 0),
            "round_count": int(getattr(report, "round_count", 0) or 0),
            "executed_round_count": int(getattr(report, "executed_round_count", 0) or 0),
            "skipped_round_count": int(getattr(report, "skipped_round_count", 0) or 0),
            "failed_round_count": int(getattr(report, "failed_round_count", 0) or 0),
            "total_runtime_seconds": int(getattr(report, "total_runtime_seconds", 0) or 0),
            "total_runtime_hours": float(getattr(report, "total_runtime_hours", 0.0) or 0.0),
            "device_online_rate": float(getattr(report, "device_online_rate", 0.0) or 0.0),
            "failed_rate": float(getattr(report, "failed_rate", 0.0) or 0.0),
            "offline_rate": float(getattr(report, "offline_rate", 0.0) or 0.0),
            "recovery_success_rate": float(getattr(report, "recovery_success_rate", 0.0) or 0.0),
            "quarantined_device_count": int(getattr(report, "quarantined_device_count", 0) or 0),
            "quarantined_device_ids": list(getattr(report, "quarantined_device_ids", ()) or ()),
            "issue_type_distribution": dict(getattr(report, "issue_type_distribution", {}) or {}),
            "top_issue_types": [dict(item) for item in (getattr(report, "top_issue_types", ()) or ())],
            "interruption_rounds": [dict(item) for item in (getattr(report, "interruption_rounds", ()) or ())],
            "task_summaries": [dict(item) for item in (getattr(report, "task_summaries", ()) or ())],
            "metrics": dict(getattr(report, "metrics", {}) or {}),
        }

    @staticmethod
    def _weekly_report_payload(report: object) -> dict[str, Any]:
        if report is None:
            return {}
        return {
            "week_key": str(getattr(report, "week_key", "") or ""),
            "anchor_date": str(getattr(report, "anchor_date", "") or ""),
            "week_start_date": str(getattr(report, "week_start_date", "") or ""),
            "week_end_date": str(getattr(report, "week_end_date", "") or ""),
            "generated_at": _isoformat(getattr(report, "generated_at", None)),
            "task_count": int(getattr(report, "task_count", 0) or 0),
            "active_task_count": int(getattr(report, "active_task_count", 0) or 0),
            "active_day_count": int(getattr(report, "active_day_count", 0) or 0),
            "round_count": int(getattr(report, "round_count", 0) or 0),
            "executed_round_count": int(getattr(report, "executed_round_count", 0) or 0),
            "skipped_round_count": int(getattr(report, "skipped_round_count", 0) or 0),
            "failed_round_count": int(getattr(report, "failed_round_count", 0) or 0),
            "total_runtime_seconds": int(getattr(report, "total_runtime_seconds", 0) or 0),
            "total_runtime_hours": float(getattr(report, "total_runtime_hours", 0.0) or 0.0),
            "device_online_rate": float(getattr(report, "device_online_rate", 0.0) or 0.0),
            "failed_rate": float(getattr(report, "failed_rate", 0.0) or 0.0),
            "offline_rate": float(getattr(report, "offline_rate", 0.0) or 0.0),
            "recovery_success_rate": float(getattr(report, "recovery_success_rate", 0.0) or 0.0),
            "quarantined_device_count": int(getattr(report, "quarantined_device_count", 0) or 0),
            "quarantined_device_ids": list(getattr(report, "quarantined_device_ids", ()) or ()),
            "issue_type_distribution": dict(getattr(report, "issue_type_distribution", {}) or {}),
            "top_issue_types": [dict(item) for item in (getattr(report, "top_issue_types", ()) or ())],
            "interruption_rounds": [dict(item) for item in (getattr(report, "interruption_rounds", ()) or ())],
            "task_summaries": [dict(item) for item in (getattr(report, "task_summaries", ()) or ())],
            "daily_summaries": [dict(item) for item in (getattr(report, "daily_summaries", ()) or ())],
            "metrics": dict(getattr(report, "metrics", {}) or {}),
        }

    @staticmethod
    def _daily_report_markdown(report_payload: dict[str, Any]) -> str:
        lines = [
            "# Unattended Daily Report",
            "",
            f"- Date: {report_payload.get('report_date', '')}",
            f"- Generated At: {report_payload.get('generated_at', '')}",
            f"- Task Count: {report_payload.get('task_count', 0)}",
            f"- Active Task Count: {report_payload.get('active_task_count', 0)}",
            f"- Round Count: {report_payload.get('round_count', 0)}",
            f"- Executed Rounds: {report_payload.get('executed_round_count', 0)}",
            f"- Failed Rounds: {report_payload.get('failed_round_count', 0)}",
            f"- Device Online Rate: {report_payload.get('device_online_rate', 0.0):.3f}",
            f"- Failed Rate: {report_payload.get('failed_rate', 0.0):.3f}",
            f"- Offline Rate: {report_payload.get('offline_rate', 0.0):.3f}",
            f"- Recovery Success Rate: {report_payload.get('recovery_success_rate', 0.0):.3f}",
            f"- Quarantined Device Count: {report_payload.get('quarantined_device_count', 0)}",
        ]
        top_issue_types = list(report_payload.get("top_issue_types", []) or [])
        if top_issue_types:
            lines.extend(["", "## Top Issue Types", ""])
            for item in top_issue_types:
                lines.append(f"- {item.get('issue_type', '')}: {item.get('count', 0)}")
        interruption_rounds = list(report_payload.get("interruption_rounds", []) or [])
        if interruption_rounds:
            lines.extend(["", "## Interruption Rounds", ""])
            for item in interruption_rounds:
                lines.append(
                    f"- {item.get('task_id', '')}/{item.get('round_id', '')}: {item.get('status', '')}"
                )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _weekly_report_markdown(report_payload: dict[str, Any]) -> str:
        lines = [
            "# Unattended Weekly Report",
            "",
            f"- Week Key: {report_payload.get('week_key', '')}",
            f"- Anchor Date: {report_payload.get('anchor_date', '')}",
            f"- Week Start: {report_payload.get('week_start_date', '')}",
            f"- Week End: {report_payload.get('week_end_date', '')}",
            f"- Generated At: {report_payload.get('generated_at', '')}",
            f"- Task Count: {report_payload.get('task_count', 0)}",
            f"- Active Task Count: {report_payload.get('active_task_count', 0)}",
            f"- Active Day Count: {report_payload.get('active_day_count', 0)}",
            f"- Round Count: {report_payload.get('round_count', 0)}",
            f"- Executed Rounds: {report_payload.get('executed_round_count', 0)}",
            f"- Failed Rounds: {report_payload.get('failed_round_count', 0)}",
            f"- Device Online Rate: {report_payload.get('device_online_rate', 0.0):.3f}",
            f"- Failed Rate: {report_payload.get('failed_rate', 0.0):.3f}",
            f"- Offline Rate: {report_payload.get('offline_rate', 0.0):.3f}",
            f"- Recovery Success Rate: {report_payload.get('recovery_success_rate', 0.0):.3f}",
            f"- Quarantined Device Count: {report_payload.get('quarantined_device_count', 0)}",
        ]
        daily_summaries = list(report_payload.get("daily_summaries", []) or [])
        if daily_summaries:
            lines.extend(["", "## Daily Summaries", ""])
            for item in daily_summaries:
                lines.append(
                    "- "
                    f"{item.get('report_date', '')}: rounds={item.get('round_count', 0)} "
                    f"failed={item.get('failed_round_count', 0)} offline={item.get('offline_event_count', 0)}"
                )
        top_issue_types = list(report_payload.get("top_issue_types", []) or [])
        if top_issue_types:
            lines.extend(["", "## Top Issue Types", ""])
            for item in top_issue_types:
                lines.append(f"- {item.get('issue_type', '')}: {item.get('count', 0)}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is not None:
                    return parsed.astimezone(timezone.utc).replace(tzinfo=None)
                return parsed
            except ValueError:
                return None
        return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def _isoformat(value: datetime | None) -> str | None:
    from stability.time_utils import format_beijing_datetime

    return format_beijing_datetime(value)
