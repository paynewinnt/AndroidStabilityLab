from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.time_utils import now_beijing_string, serialize_datetime_or_original


@dataclass(frozen=True)
class PlatformHealthComponent:
    """One continuously observed platform health area."""

    name: str
    category: str
    status: str
    summary: str
    metrics: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    recommended_action: str = ""


@dataclass(frozen=True)
class PlatformHealthSnapshot:
    """Persisted platform self-monitoring snapshot."""

    contract_version: str
    generated_at: str
    ok: bool
    status: str
    severity: str
    summary: Mapping[str, Any]
    checks: Sequence[PlatformHealthComponent]
    readiness: Mapping[str, Any]
    trends: Mapping[str, Any] = field(default_factory=dict)
    links: Mapping[str, str] = field(default_factory=dict)


class PlatformHealthService:
    """Aggregate continuous self-monitoring signals and persist health snapshots."""

    CONTRACT_VERSION = "asl.platform_health.v1"
    SNAPSHOT_FILE = "snapshots.json"

    def __init__(
        self,
        *,
        root_dir: str | Path,
        device_service: Any | None = None,
        task_repository: Any | None = None,
        run_repository: Any | None = None,
        instance_repository: Any | None = None,
        unattended_runner_service: Any | None = None,
        integration_outbox_service: Any | None = None,
        history_limit: int = 48,
    ) -> None:
        self._root_dir = Path(root_dir)
        self._device_service = device_service
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._unattended_runner_service = unattended_runner_service
        self._integration_outbox_service = integration_outbox_service
        self._history_limit = max(1, int(history_limit or 48))

    @property
    def snapshot_path(self) -> Path:
        return self._root_dir / self.SNAPSHOT_FILE

    def snapshot(self, *, record: bool = True) -> PlatformHealthSnapshot:
        checks = [
            self._scheduler_check(),
            self._device_adb_check(),
            self._execution_check(),
            self._artifact_report_check(),
            self._outbox_check(),
        ]
        status_counts: dict[str, int] = {}
        for check in checks:
            status_counts[check.status] = status_counts.get(check.status, 0) + 1
        fail_count = status_counts.get("fail", 0)
        warn_count = status_counts.get("warn", 0)
        skipped_count = status_counts.get("skipped", 0)
        severity = "fail" if fail_count else "warn" if warn_count or skipped_count else "ok"
        status = "blocked" if fail_count else "degraded" if warn_count or skipped_count else "ready"
        operational_ok = fail_count == 0 and skipped_count < len(checks)
        readiness = {
            "ok": operational_ok,
            "required_checks": [item.category for item in checks if item.status != "skipped"],
            "failed_checks": [item.category for item in checks if item.status == "fail"],
            "warning_checks": [item.category for item in checks if item.status == "warn"],
            "skipped_checks": [item.category for item in checks if item.status == "skipped"],
        }
        snapshot = PlatformHealthSnapshot(
            contract_version=self.CONTRACT_VERSION,
            generated_at=now_beijing_string(),
            ok=operational_ok,
            status=status,
            severity=severity,
            summary={
                "status": status,
                "severity": severity,
                "ok_count": status_counts.get("ok", 0),
                "warn_count": warn_count,
                "fail_count": fail_count,
                "skipped_count": skipped_count,
                "check_count": len(checks),
            },
            checks=checks,
            readiness=readiness,
            trends=self._trend_payload(),
            links={
                "api": "/api/platform-health",
                "doctor": "/doctor",
                "runner": "/runner",
                "ready": "/ready",
                "health": "/health",
            },
        )
        if record:
            self._record(snapshot)
        return snapshot

    def latest(self) -> dict[str, Any] | None:
        history = self.history()
        return history[-1] if history else None

    def history(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        path = self.snapshot_path
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = list(data.get("snapshots", []) if isinstance(data, dict) else [])
        if limit is not None and limit >= 0:
            return items[-limit:]
        return items

    def snapshot_payload(self, snapshot: PlatformHealthSnapshot) -> dict[str, Any]:
        return {
            "contract_version": snapshot.contract_version,
            "generated_at": snapshot.generated_at,
            "ok": snapshot.ok,
            "status": snapshot.status,
            "severity": snapshot.severity,
            "summary": dict(snapshot.summary),
            "checks": [self._component_payload(item) for item in snapshot.checks],
            "readiness": dict(snapshot.readiness),
            "trends": dict(snapshot.trends),
            "links": dict(snapshot.links),
            "history": self.history(limit=12),
            "storage": {"snapshot_path": str(self.snapshot_path)},
        }

    def _record(self, snapshot: PlatformHealthSnapshot) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        history = self.history()
        history.append(self.snapshot_payload(snapshot) | {"history": []})
        payload = {
            "contract_version": self.CONTRACT_VERSION,
            "updated_at": snapshot.generated_at,
            "snapshots": history[-self._history_limit :],
        }
        self.snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _component_payload(component: PlatformHealthComponent) -> dict[str, Any]:
        return {
            "name": component.name,
            "category": component.category,
            "status": component.status,
            "summary": component.summary,
            "metrics": PlatformHealthService._jsonable(component.metrics),
            "details": PlatformHealthService._jsonable(component.details),
            "recommended_action": component.recommended_action,
        }

    @staticmethod
    def _jsonable(value: Any) -> Any:
        serialized = serialize_datetime_or_original(value)
        if serialized is not None and not isinstance(value, (int, float, bool)):
            return serialized
        if isinstance(value, Mapping):
            return {str(key): PlatformHealthService._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [PlatformHealthService._jsonable(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _scheduler_check(self) -> PlatformHealthComponent:
        service = self._unattended_runner_service
        if service is None or not hasattr(service, "show_status"):
            return self._skipped("调度器心跳", "scheduler", "未配置 unattended runner service。")
        try:
            status = service.show_status()
        except Exception as exc:
            return self._failed("调度器心跳", "scheduler", f"读取 runner 状态失败：{exc}")
        heartbeat_age = getattr(status, "heartbeat_age_seconds", None)
        stale = bool(getattr(status, "is_stale", False))
        running = str(getattr(status, "status", "") or "") == "running"
        last_patrol = dict(getattr(status, "last_patrol", {}) or {})
        component_status = "fail" if stale else "ok" if running else "warn"
        summary = "runner 心跳正常。" if component_status == "ok" else "runner 未运行或心跳不可用。"
        return PlatformHealthComponent(
            name="调度器心跳",
            category="scheduler",
            status=component_status,
            summary=summary,
            metrics={
                "runner_status": getattr(status, "status", "missing"),
                "heartbeat_age_seconds": heartbeat_age,
                "cycle_count": int(getattr(status, "cycle_count", 0) or 0),
                "failed_rate": float(last_patrol.get("failed_rate", 0.0) or 0.0),
                "offline_rate": float(last_patrol.get("offline_rate", 0.0) or 0.0),
                "quarantined_device_count": int(last_patrol.get("quarantined_device_count", 0) or 0),
            },
            details={
                "last_heartbeat_at": getattr(status, "last_heartbeat_at", ""),
                "started_at": getattr(status, "started_at", ""),
                "stopped_reason": getattr(status, "stopped_reason", ""),
                "lock_state": getattr(status, "lock_state", ""),
            },
            recommended_action="如心跳 stale，先确认旧 runner 进程是否仍存活，再重启后台巡检。",
        )

    def _device_adb_check(self) -> PlatformHealthComponent:
        service = self._device_service
        if service is None or not hasattr(service, "list_devices"):
            return self._skipped("ADB 与设备池", "device_adb", "未配置 device service。")
        try:
            devices = list(service.list_devices())
        except Exception as exc:
            return self._failed("ADB 与设备池", "device_adb", f"读取设备池失败：{exc}")
        total = len(devices)
        online = sum(1 for item in devices if self._call_bool(item, "is_online"))
        schedulable = sum(1 for item in devices if self._call_bool(item, "is_schedulable"))
        quarantined = sum(1 for item in devices if self._value(getattr(item, "availability_state", "")) == "quarantined")
        online_rate = self._rate(online, total)
        schedulable_rate = self._rate(schedulable, total)
        if total == 0:
            status = "warn"
            summary = "设备池为空，任务无法自动调度。"
        elif schedulable == 0:
            status = "fail"
            summary = "当前没有可调度设备。"
        elif online_rate < 0.5:
            status = "warn"
            summary = "设备在线率偏低。"
        else:
            status = "ok"
            summary = "设备池可调度。"
        return PlatformHealthComponent(
            name="ADB 与设备池",
            category="device_adb",
            status=status,
            summary=summary,
            metrics={
                "device_count": total,
                "online_device_count": online,
                "schedulable_device_count": schedulable,
                "quarantined_device_count": quarantined,
                "device_online_rate": online_rate,
                "device_schedulable_rate": schedulable_rate,
            },
            details={"device_ids": [str(getattr(item, "device_id", "") or "") for item in devices[:20]]},
            recommended_action="无可调度设备时，先在设备池刷新 ADB 或重新连接无线调试设备。",
        )

    def _execution_check(self) -> PlatformHealthComponent:
        if self._run_repository is None:
            return self._skipped("任务与 Run 失败率", "execution", "未配置 run repository。")
        try:
            runs = self._safe_list(self._run_repository)
            tasks = self._safe_list(self._task_repository)
            instances = self._instances_for_runs(runs)
        except Exception as exc:
            return self._failed("任务与 Run 失败率", "execution", f"读取任务执行数据失败：{exc}")
        run_failed = sum(1 for item in runs if self._value(getattr(item, "status", "")) in {"failed", "partial_failed"})
        terminal = sum(
            1
            for item in runs
            if self._value(getattr(item, "status", "")) in {"success", "failed", "partial_failed", "cancelled"}
        )
        instance_failed = sum(1 for item in instances if self._value(getattr(item, "status", "")) in {"failed", "precheck_failed"})
        adb_failed = sum(1 for item in instances if "offline" in self._value(getattr(item, "exit_reason", "")))
        run_failure_rate = self._rate(run_failed, terminal)
        instance_failure_rate = self._rate(instance_failed, len(instances))
        adb_failure_rate = self._rate(adb_failed, len(instances))
        status = "fail" if run_failure_rate >= 0.5 and terminal else "warn" if run_failure_rate > 0.0 else "ok"
        return PlatformHealthComponent(
            name="任务与 Run 失败率",
            category="execution",
            status=status,
            summary="最近执行失败率正常。" if status == "ok" else "最近执行存在失败，需要查看 Run 详情。",
            metrics={
                "task_count": len(tasks),
                "run_count": len(runs),
                "terminal_run_count": terminal,
                "failed_run_count": run_failed,
                "run_failure_rate": run_failure_rate,
                "instance_count": len(instances),
                "failed_instance_count": instance_failed,
                "instance_failure_rate": instance_failure_rate,
                "adb_failure_count": adb_failed,
                "adb_failure_rate": adb_failure_rate,
            },
            recommended_action="失败率升高时，先按 Run 详情确认是设备离线、模板失败还是应用问题。",
        )

    def _artifact_report_check(self) -> PlatformHealthComponent:
        if self._run_repository is None or self._instance_repository is None:
            return self._skipped("证据与报告抓取", "artifact_report", "未配置 instance repository。")
        try:
            instances = self._instances_for_runs(self._safe_list(self._run_repository))
        except Exception as exc:
            return self._failed("证据与报告抓取", "artifact_report", f"读取实例产物失败：{exc}")
        artifact_count = 0
        artifact_failed = 0
        report_missing = 0
        for instance in instances:
            artifacts = list(getattr(instance, "artifacts", ()) or ())
            artifact_count += len(artifacts)
            artifact_failed += sum(1 for item in artifacts if self._value(getattr(item, "capture_status", "")) == "failed")
            summary = self._summary_mapping(getattr(instance, "summary", {}) or {})
            analysis_ready = dict(summary.get("analysis_ready", {}) or {})
            report = dict(analysis_ready.get("report", {}) or {})
            if self._value(getattr(instance, "status", "")) == "success" and not report:
                report_missing += 1
        artifact_failure_rate = self._rate(artifact_failed, artifact_count)
        report_missing_rate = self._rate(report_missing, len(instances))
        status = "warn" if artifact_failed or report_missing else "ok"
        return PlatformHealthComponent(
            name="证据与报告抓取",
            category="artifact_report",
            status=status,
            summary="证据与报告链路正常。" if status == "ok" else "存在证据抓取失败或报告缺失。",
            metrics={
                "instance_count": len(instances),
                "artifact_count": artifact_count,
                "artifact_failed_count": artifact_failed,
                "artifact_failure_rate": artifact_failure_rate,
                "report_missing_count": report_missing,
                "report_missing_rate": report_missing_rate,
            },
            recommended_action="报告缺失时优先查看 instance summary 和 artifact capture errors。",
        )

    def _outbox_check(self) -> PlatformHealthComponent:
        service = self._integration_outbox_service
        if service is None or not hasattr(service, "list_events"):
            return self._skipped("集成 Outbox", "outbox", "未配置 integration outbox service。")
        try:
            events = list(service.list_events(limit=200))
            worker_status = service.get_worker_status() if hasattr(service, "get_worker_status") else None
        except Exception as exc:
            return self._failed("集成 Outbox", "outbox", f"读取 outbox 失败：{exc}")
        counts: dict[str, int] = {}
        for event in events:
            status = self._value(getattr(event, "delivery_status", "") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        dead_letter = counts.get("dead_letter", 0) + sum(1 for event in events if getattr(event, "dead_lettered_at", None))
        retrying = counts.get("retry_pending", 0) + counts.get("failed", 0)
        status = "fail" if dead_letter else "warn" if retrying else "ok"
        return PlatformHealthComponent(
            name="集成 Outbox",
            category="outbox",
            status=status,
            summary="outbox 投递健康。" if status == "ok" else "outbox 存在重试或死信事件。",
            metrics={
                "event_count": len(events),
                "pending_count": counts.get("pending", 0),
                "retrying_count": retrying,
                "delivered_count": counts.get("delivered", 0),
                "dead_letter_count": dead_letter,
                "worker_status": self._value(getattr(worker_status, "status", "") or "unknown") if worker_status else "unknown",
                "worker_failed_count": int(getattr(worker_status, "failed_count", 0) or 0) if worker_status else 0,
            },
            details={"delivery_status_counts": counts},
            recommended_action="死信不应静默堆积；先查看 /integration 的 dead-letter 和 worker 日志。",
        )

    def _trend_payload(self) -> dict[str, Any]:
        latest = self.latest()
        if not latest:
            return {"history_count": 0}
        return {
            "history_count": len(self.history(limit=self._history_limit)),
            "last_status": latest.get("status"),
            "last_generated_at": latest.get("generated_at"),
        }

    def _instances_for_runs(self, runs: Sequence[Any]) -> list[Any]:
        repository = self._instance_repository
        if repository is None:
            return []
        instances: list[Any] = []
        if hasattr(repository, "list"):
            return self._safe_list(repository)
        for run in runs[:100]:
            run_id = str(getattr(run, "run_id", "") or "")
            if not run_id or not hasattr(repository, "list_by_run"):
                continue
            instances.extend(list(repository.list_by_run(run_id)))
        return instances

    @staticmethod
    def _safe_list(repository: Any | None) -> list[Any]:
        if repository is None or not hasattr(repository, "list"):
            return []
        return list(repository.list())

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round(float(numerator) / float(denominator), 4) if denominator else 0.0

    @staticmethod
    def _summary_mapping(summary: Any) -> dict[str, Any]:
        if isinstance(summary, Mapping):
            return dict(summary)
        metadata = getattr(summary, "metadata", None)
        if isinstance(metadata, Mapping):
            return dict(metadata)
        return {}

    @staticmethod
    def _value(value: Any) -> str:
        return str(getattr(value, "value", value) or "").lower()

    @staticmethod
    def _call_bool(item: Any, name: str) -> bool:
        value = getattr(item, name, False)
        return bool(value() if callable(value) else value)

    @staticmethod
    def _skipped(name: str, category: str, summary: str) -> PlatformHealthComponent:
        return PlatformHealthComponent(name=name, category=category, status="skipped", summary=summary)

    @staticmethod
    def _failed(name: str, category: str, summary: str) -> PlatformHealthComponent:
        return PlatformHealthComponent(name=name, category=category, status="fail", summary=summary)
