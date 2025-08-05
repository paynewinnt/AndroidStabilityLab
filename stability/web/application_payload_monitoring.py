from __future__ import annotations

from .application_common import *
from stability.time_utils import format_beijing_datetime_or_original


class ApplicationPayloadMonitoringMixin:
    def _decorate_runs_with_monitoring(self, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        service = getattr(self._bundle, "run_history_service", None)
        if service is None or not hasattr(service, "get_run_detail"):
            return [{**dict(item), "detail_path": f"/runs/{quote(str(item.get('run_id', '') or ''), safe='')}"} for item in runs]
        decorated: list[dict[str, Any]] = []
        for item in runs:
            run_payload = dict(item or {})
            run_id = str(run_payload.get("run_id", "") or "").strip()
            monitoring_summary: dict[str, Any] = {
                "sample_count": 0,
                "trace_count": 0,
                "backend_counts": {},
                "latest_sample_at": "",
                "summary_line": "未发现监控快照",
            }
            if run_id:
                try:
                    detail = dict(service.get_run_detail(run_id))
                    instances = self._decorate_run_detail_instances(list(detail.get("instances", []) or ()))
                    monitoring_summary = self._run_monitoring_summary(instances)
                except Exception:
                    monitoring_summary = {
                        "sample_count": 0,
                        "trace_count": 0,
                        "backend_counts": {},
                        "latest_sample_at": "",
                        "summary_line": "监控详情暂不可用",
                    }
            run_payload["detail_path"] = f"/runs/{quote(run_id, safe='')}" if run_id else ""
            run_payload["api_path"] = f"/api/runs/{quote(run_id, safe='')}" if run_id else ""
            run_payload["monitoring_summary"] = monitoring_summary
            decorated.append(run_payload)
        return decorated

    def _decorate_run_detail_instances(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for item in instances:
            instance = dict(item or {})
            inferred_snapshot_path, inferred_trace_path = self._infer_monitoring_paths(instance)
            snapshot_path = str(instance.get("monitoring_snapshot_path", "") or inferred_snapshot_path or "").strip()
            snapshot_payload = self._safe_json_file(snapshot_path)
            samples_path = str(Path(snapshot_path).with_name("samples.json")) if snapshot_path else ""
            sample_payloads = self._safe_json_list(samples_path)
            if not sample_payloads and snapshot_payload:
                sample_payloads = [snapshot_payload]
            backend = self._resolve_monitoring_backend(instance=instance, snapshot_payload=snapshot_payload)
            metrics = self._monitoring_metrics(snapshot_payload)
            app_packages = self._monitoring_app_packages(snapshot_payload)
            trace_path = str(instance.get("monitoring_trace_path", "") or inferred_trace_path or "").strip()
            captured_at = format_beijing_datetime_or_original(dict(snapshot_payload).get("timestamp", "")) or "" if snapshot_payload else ""
            samples = []
            for index, sample_payload in enumerate(sample_payloads):
                sample_backend = self._resolve_monitoring_backend(instance=instance, snapshot_payload=sample_payload)
                sample_metrics = self._monitoring_metrics(sample_payload)
                samples.append(
                    {
                        "sample_index": index,
                        "backend": sample_backend,
                        "captured_at": format_beijing_datetime_or_original(dict(sample_payload).get("timestamp", "")) or "",
                        "metrics": sample_metrics,
                        "summary_line": self._monitoring_summary_line(
                            backend=sample_backend,
                            metrics=sample_metrics,
                            trace_path=trace_path,
                        ),
                    }
                )
            instance["monitoring"] = {
                "backend": backend,
                "profile": str(instance.get("monitoring_profile", "") or ""),
                "snapshot_path": snapshot_path,
                "samples_path": samples_path,
                "trace_path": trace_path,
                "session_id": str(instance.get("monitoring_session_id", "") or ""),
                "snapshot_available": bool(snapshot_payload),
                "sample_count": len(samples),
                "samples": samples,
                "trace_available": bool(trace_path),
                "captured_at": captured_at,
                "metrics": metrics,
                "app_packages": app_packages,
                "summary_line": self._monitoring_summary_line(
                    backend=backend,
                    metrics=metrics,
                    trace_path=trace_path,
                ),
            }
            payloads.append(instance)
        return payloads

    @staticmethod
    def _infer_monitoring_paths(instance: Mapping[str, Any]) -> tuple[str, str]:
        snapshot_path = ""
        trace_path = ""
        for key in ("report_path", "html_report_path", "execution_log_path"):
            raw = str(instance.get(key, "") or "").strip()
            if not raw:
                continue
            target = Path(raw)
            device_root = target.parent.parent if len(target.parents) >= 2 else None
            if device_root is None:
                continue
            monitoring_dir = device_root / "monitoring"
            if not snapshot_path:
                candidate_snapshot = monitoring_dir / "snapshot.json"
                if candidate_snapshot.exists():
                    snapshot_path = str(candidate_snapshot)
            if not trace_path and monitoring_dir.exists():
                trace_candidates = sorted(monitoring_dir.glob("*.perfetto-trace"))
                if trace_candidates:
                    trace_path = str(trace_candidates[0])
            if snapshot_path and trace_path:
                break
        return snapshot_path, trace_path

    def _recent_monitoring_snapshot(self, *, run_limit: int, entry_limit: int) -> dict[str, Any]:
        service = getattr(self._bundle, "run_history_service", None)
        if service is None or not hasattr(service, "list_runs") or not hasattr(service, "get_run_detail"):
            return {
                "summary": {
                    "sample_count": 0,
                    "monitored_run_count": 0,
                    "trace_count": 0,
                    "backend_counts": {},
                    "latest_sample_at": "",
                },
                "entries": [],
            }
        runs = list(service.list_runs(limit=run_limit))
        entries: list[dict[str, Any]] = []
        monitored_run_ids: set[str] = set()
        for run in runs:
            run_id = str(dict(run or {}).get("run_id", "") or "").strip()
            if not run_id:
                continue
            try:
                detail = dict(service.get_run_detail(run_id))
            except Exception:
                continue
            task = dict(detail.get("task", {}) or {})
            instances = self._decorate_run_detail_instances(list(detail.get("instances", []) or ()))
            for instance in instances:
                monitoring = dict(instance.get("monitoring", {}) or {})
                if not bool(monitoring.get("snapshot_available")):
                    continue
                monitored_run_ids.add(run_id)
                samples = list(monitoring.get("samples", []) or [])
                if not samples:
                    samples = [
                        {
                            "sample_index": 0,
                            "backend": str(monitoring.get("backend", "") or "unknown"),
                            "captured_at": str(monitoring.get("captured_at", "") or ""),
                            "metrics": dict(monitoring.get("metrics", {}) or {}),
                            "summary_line": str(monitoring.get("summary_line", "") or ""),
                        }
                    ]
                for sample in samples:
                    sample_payload = dict(sample or {})
                    backend = str(sample_payload.get("backend", "") or monitoring.get("backend", "") or "unknown")
                    entries.append(
                        {
                            "run_id": run_id,
                            "run_status": str(detail.get("run_status", "") or ""),
                            "run_created_at": str(detail.get("created_at", "") or ""),
                            "run_detail_path": f"/runs/{quote(run_id, safe='')}",
                            "run_api_path": f"/api/runs/{quote(run_id, safe='')}",
                            "task_id": str(detail.get("task_id", "") or ""),
                            "task_name": str(detail.get("task_name", task.get("task_name", "")) or ""),
                            "template_type": str(task.get("template_type", "") or ""),
                            "package_name": str(task.get("package_name", "") or ""),
                            "instance_id": str(instance.get("instance_id", "") or ""),
                            "device_id": str(instance.get("device_id", "") or ""),
                            "instance_status": str(instance.get("status", "") or ""),
                            "backend": backend,
                            "captured_at": str(sample_payload.get("captured_at", "") or ""),
                            "metrics": dict(sample_payload.get("metrics", {}) or {}),
                            "summary_line": str(sample_payload.get("summary_line", "") or ""),
                            "sample_index": int(sample_payload.get("sample_index", 0) or 0),
                            "samples_path": str(monitoring.get("samples_path", "") or ""),
                            "snapshot_path": str(monitoring.get("snapshot_path", "") or ""),
                            "trace_path": str(monitoring.get("trace_path", "") or ""),
                            "trace_available": bool(monitoring.get("trace_available", False)),
                            "app_packages": list(monitoring.get("app_packages", []) or []),
                        }
                    )
        entries.sort(key=lambda item: (str(item.get("captured_at", "") or ""), str(item.get("run_created_at", "") or "")), reverse=True)
        limited_entries = entries[: max(0, int(entry_limit))]
        backend_counts: dict[str, int] = {}
        trace_count = 0
        for entry in limited_entries:
            backend = str(entry.get("backend", "") or "unknown")
            backend_counts[backend] = backend_counts.get(backend, 0) + 1
            if bool(entry.get("trace_available", False)):
                trace_count += 1
        latest_sample_at = str(limited_entries[0].get("captured_at", "") or "") if limited_entries else ""
        return {
            "summary": {
                "sample_count": len(limited_entries),
                "monitored_run_count": len(monitored_run_ids),
                "trace_count": trace_count,
                "backend_counts": backend_counts,
                "latest_sample_at": latest_sample_at,
            },
            "entries": limited_entries,
        }

    @staticmethod
    def _safe_json_file(path: str) -> dict[str, Any]:
        raw = str(path or "").strip()
        if not raw:
            return {}
        target = Path(raw)
        if not target.exists() or not target.is_file():
            return {}
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    @staticmethod
    def _safe_json_list(path: str) -> list[dict[str, Any]]:
        raw = str(path or "").strip()
        if not raw:
            return []
        target = Path(raw)
        if not target.exists() or not target.is_file():
            return []
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    @staticmethod
    def _resolve_monitoring_backend(*, instance: Mapping[str, Any], snapshot_payload: Mapping[str, Any]) -> str:
        metadata = dict(snapshot_payload.get("metadata", {}) or {})
        explicit = str(metadata.get("backend", "") or instance.get("monitoring_backend", "") or "").strip().lower()
        if explicit:
            return explicit
        profile = str(instance.get("monitoring_profile", "") or "").strip().lower()
        if profile:
            return profile
        if str(instance.get("monitoring_trace_path", "") or "").strip():
            return "perfetto"
        if snapshot_payload:
            return "adb_collector"
        return "unknown"

    @staticmethod
    def _monitoring_app_packages(snapshot_payload: Mapping[str, Any]) -> list[str]:
        packages: list[str] = []
        for item in list(snapshot_payload.get("apps", []) or []):
            if not isinstance(item, Mapping):
                continue
            package_name = str(item.get("app_package", "") or dict(item.get("app_info", {}) or {}).get("package_name", "") or "").strip()
            if package_name and package_name not in packages:
                packages.append(package_name)
        return packages

    @staticmethod
    def _monitoring_metrics(snapshot_payload: Mapping[str, Any]) -> dict[str, Any]:
        system = dict(snapshot_payload.get("system", {}) or {})
        apps = list(snapshot_payload.get("apps", []) or [])
        primary_app = dict(apps[0]) if apps and isinstance(apps[0], Mapping) else {}

        def _pick(*values: Any) -> Any:
            for value in values:
                if value not in ("", None):
                    return value
            return None

        return {
            "cpu_usage": _pick(primary_app.get("cpu_usage"), primary_app.get("top_cpu_usage"), system.get("cpu_usage")),
            "memory_pss": _pick(primary_app.get("memory_pss"), system.get("memory_pss")),
            "fps": _pick(primary_app.get("fps"), system.get("fps")),
            "gpu_usage": _pick(primary_app.get("gpu_usage"), system.get("gpu_usage")),
            "gpu_p95_ms": _pick(primary_app.get("gpu_p95_ms"), system.get("gpu_p95_ms")),
            "gpu_p99_ms": _pick(primary_app.get("gpu_p99_ms"), system.get("gpu_p99_ms")),
            "jank_frames": _pick(primary_app.get("jank_frames"), system.get("jank_frames")),
            "jank_percent": _pick(primary_app.get("jank_percent"), system.get("jank_percent")),
            "frame_count": _pick(primary_app.get("frame_count"), system.get("frame_count")),
            "battery_level": _pick(system.get("battery_level")),
            "power_usage": _pick(primary_app.get("power_usage"), primary_app.get("power_consumption"), system.get("power_usage")),
            "rx_bytes": _pick(primary_app.get("rx_bytes"), system.get("network_rx_total"), system.get("network_rx")),
            "tx_bytes": _pick(primary_app.get("tx_bytes"), system.get("network_tx_total"), system.get("network_tx")),
        }

    @staticmethod
    def _monitoring_summary_line(*, backend: str, metrics: Mapping[str, Any], trace_path: str) -> str:
        parts = [f"backend={backend or 'unknown'}"]
        ordered = (
            ("cpu", metrics.get("cpu_usage")),
            ("mem_pss", metrics.get("memory_pss")),
            ("fps", metrics.get("fps")),
            ("gpu", metrics.get("gpu_usage")),
            ("gpu_p95_ms", metrics.get("gpu_p95_ms")),
            ("jank", metrics.get("jank_percent")),
            ("battery", metrics.get("battery_level")),
        )
        for label, value in ordered:
            if value not in ("", None):
                parts.append(f"{label}={value}")
        if str(trace_path or "").strip():
            parts.append("trace=yes")
        return " / ".join(parts)

    def _run_monitoring_summary(self, instances: list[dict[str, Any]]) -> dict[str, Any]:
        backend_counts: dict[str, int] = {}
        trace_count = 0
        sample_count = 0
        latest_sample_at = ""
        latest_line = ""
        for item in instances:
            monitoring = dict(item.get("monitoring", {}) or {})
            if not bool(monitoring.get("snapshot_available")):
                continue
            sample_count += 1
            backend = str(monitoring.get("backend", "") or "unknown")
            backend_counts[backend] = backend_counts.get(backend, 0) + 1
            if bool(monitoring.get("trace_available")):
                trace_count += 1
            captured_at = str(monitoring.get("captured_at", "") or "")
            if captured_at >= latest_sample_at:
                latest_sample_at = captured_at
                latest_line = str(monitoring.get("summary_line", "") or "")
        summary_line = (
            latest_line
            if latest_line
            else ("未发现监控快照" if sample_count == 0 else f"samples={sample_count}")
        )
        return {
            "sample_count": sample_count,
            "trace_count": trace_count,
            "backend_counts": backend_counts,
            "latest_sample_at": latest_sample_at,
            "summary_line": summary_line,
        }
