from __future__ import annotations

from stability.application import (
    CreateRunCommand,
    CreateTaskCommand,
    ExecuteRunCommand,
    StopRunCommand,
    create_run as run_create_use_case,
    create_task as task_create_use_case,
    execute_run as run_execute_use_case,
    stop_run as run_stop_use_case,
)
from stability.app import ConfigProvider

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote


class TasksActionsMixin:
    def _managed_apk_dir(self) -> Path:
        root = ConfigProvider().runtime_paths().apks
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _managed_apks_payload(self) -> list[dict[str, str]]:
        root = self._managed_apk_dir()
        items = []
        for path in sorted(root.glob("*.apk")):
            if path.is_file():
                items.append({"name": path.name, "path": str(path)})
        return items

    def _handle_apk_upload(self, *, body: bytes, content_type: str) -> dict[str, Any]:
        file_name, file_body = self._multipart_file(body=body, content_type=content_type, field_name="apk_file")
        if not file_name or not file_body:
            raise ValueError("请选择要上传的 APK。")
        safe_name = self._safe_apk_name(file_name)
        target = self._unique_apk_target(safe_name)
        target.write_bytes(file_body)
        return {
            "storage_mode": "local_apk_store",
            "apk": {"name": target.name, "path": str(target)},
            "apks": self._managed_apks_payload(),
        }

    def _handle_apk_delete(self, payload: Mapping[str, list[str]]) -> dict[str, Any]:
        apk_path = Path(self._required_form_value(dict(payload), "apk_path"))
        root = self._managed_apk_dir().resolve()
        target = apk_path if apk_path.is_absolute() else root / apk_path.name
        target = target.resolve()
        if root not in target.parents or target.suffix.lower() != ".apk":
            raise ValueError("只能删除应用管理目录中的 APK。")
        deleted = False
        if target.exists() and target.is_file():
            target.unlink()
            deleted = True
        return {
            "storage_mode": "local_apk_store",
            "deleted": deleted,
            "apk_path": str(target),
            "apks": self._managed_apks_payload(),
        }

    @staticmethod
    def _safe_apk_name(file_name: str) -> str:
        name = Path(str(file_name or "app.apk")).name.strip() or "app.apk"
        stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
        if not stem.lower().endswith(".apk"):
            stem += ".apk"
        return stem

    def _unique_apk_target(self, file_name: str) -> Path:
        root = self._managed_apk_dir()
        candidate = root / file_name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix or ".apk"
        index = 2
        while True:
            next_candidate = root / f"{stem}_{index}{suffix}"
            if not next_candidate.exists():
                return next_candidate
            index += 1

    @staticmethod
    def _multipart_file(*, body: bytes, content_type: str, field_name: str) -> tuple[str, bytes]:
        marker = "boundary="
        if marker not in content_type:
            return "", b""
        boundary = content_type.split(marker, 1)[1].split(";", 1)[0].strip().strip('"')
        if not boundary:
            return "", b""
        delimiter = ("--" + boundary).encode("utf-8")
        for raw_part in body.split(delimiter):
            part = raw_part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            header_blob, sep, content = part.partition(b"\r\n\r\n")
            if not sep:
                continue
            header_text = header_blob.decode("utf-8", errors="ignore")
            if f'name="{field_name}"' not in header_text:
                continue
            filename = ""
            for header_line in header_text.splitlines():
                if not header_line.lower().startswith("content-disposition:"):
                    continue
                for chunk in header_line.split(";"):
                    chunk = chunk.strip()
                    if chunk.startswith("filename="):
                        filename = chunk.split("=", 1)[1].strip().strip('"')
                        break
            return filename, content.rstrip(b"\r\n")
        return "", b""

    def _handle_task_create(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        actor = dict(request_context.get("current_actor", {}) or {})
        template_type_raw = self._required_form_value(dict(payload), "template_type")
        task_params = self._json_form_object(dict(payload), "task_params")
        metadata = self._json_form_object(dict(payload), "metadata")
        if self._form_bool(payload, "configure_unattended", default=False):
            metadata = self._long_run_task_metadata(payload, metadata)
            task_params = self._long_run_task_params(payload, task_params)
        response = task_create_use_case(
            self._bundle,
            CreateTaskCommand(
                task_name=self._required_form_value(dict(payload), "task_name"),
                template_type=template_type_raw,
                package_name=self._required_form_value(dict(payload), "package_name"),
                task_params=task_params,
                selected_device_ids=self._expand_form_values(payload, "devices")
                or self._expand_form_values(payload, "device"),
                sampling_interval=self._form_int(payload, "sampling_interval", default=5),
                enabled_metrics=self._expand_form_values(payload, "metrics"),
                created_by=str(actor.get("actor_id", "") or "web"),
                notes=self._form_value(dict(payload), "note"),
                metadata=metadata,
            ),
        )
        if self._form_bool(payload, "configure_unattended", default=False):
            response.update(self._configure_unattended_for_created_task(payload, task_id=response["task_id"]))
        return response

    def _handle_task_archive(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        task_service = getattr(self._bundle, "task_service", None)
        if task_service is None or not hasattr(task_service, "archive_task"):
            raise ValueError("Task archive is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        task_id = self._required_form_value(dict(payload), "task_id")
        reason = self._form_value(dict(payload), "reason") or "用户从 Web 任务大厅执行归档/隐藏。"
        result = task_service.archive_task(
            task_id,
            actor_id=str(actor.get("actor_id", "") or "web"),
            reason=reason,
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        task = getattr(result, "task", None)
        return {
            "storage_mode": "persistent",
            "action": "archive_task",
            "task_id": task_id,
            "task_name": str(getattr(task, "task_name", "") or ""),
            "archived": True,
            "hidden": True,
            "archived_at": self._isoformat_or_none(getattr(result, "archived_at", None)),
            "audit_event": dict(getattr(result, "audit_event", {}) or {}),
            "message": "任务已归档并从默认列表隐藏；运行记录和产物未物理删除。",
        }

    def _long_run_task_metadata(
        self,
        payload: Mapping[str, list[str]],
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        runtime_hours = max(self._form_int(payload, "runtime_hours", default=12), 1)
        interval_minutes = max(self._form_int(payload, "interval_minutes", default=60), 1)
        max_rounds = max(1, (runtime_hours * 60 + interval_minutes - 1) // interval_minutes)
        monitoring_backend = self._form_value(dict(payload), "monitoring_backend") or "default"
        outputs = self._expand_form_values(payload, "outputs")
        retry_count = max(self._form_int(payload, "retry_count", default=0), 0)
        long_run = {
            "source": "web_tasks_long_run",
            "runtime_hours": runtime_hours,
            "interval_minutes": interval_minutes,
            "estimated_max_rounds": max_rounds,
            "retry_count": retry_count,
            "auto_backfill": self._form_bool(payload, "auto_backfill", default=True),
            "desired_device_count": max(self._form_int(payload, "desired_device_count", default=1), 1),
            "failure_threshold": max(self._form_int(payload, "failure_threshold", default=3), 1),
            "rotation_strategy": self._form_value(dict(payload), "rotation_strategy") or "round_robin",
            "rotation_advance_policy": self._form_value(dict(payload), "rotation_advance_policy") or "every_round",
            "monitoring_backend": monitoring_backend,
            "outputs": outputs,
            "output_note": self._form_value(dict(payload), "output_note"),
            "runner_path": "/runner",
            "unattended_detail_path": "",
        }
        template_key = self._form_value(dict(payload), "long_run_template_key")
        template_name = self._form_value(dict(payload), "long_run_template_name")
        if template_key:
            long_run["template_key"] = template_key
        if template_name:
            long_run["template_name"] = template_name
        merged = dict(metadata or {})
        merged.setdefault("source", "web")
        if template_key:
            merged["long_run_template_id"] = template_key
        if template_name:
            merged["long_run_template_name"] = template_name
        merged["monitoring_backend"] = monitoring_backend
        merged["long_run"] = long_run
        tags = list(merged.get("tags", []) or []) if isinstance(merged.get("tags", []), list) else []
        for tag in ("long_run", "unattended"):
            if tag not in tags:
                tags.append(tag)
        merged["tags"] = tags
        return merged

    def _long_run_task_params(
        self,
        payload: Mapping[str, list[str]],
        task_params: Mapping[str, Any],
    ) -> dict[str, Any]:
        runtime_hours = max(self._form_int(payload, "runtime_hours", default=12), 1)
        interval_minutes = max(self._form_int(payload, "interval_minutes", default=60), 1)
        max_rounds = max(1, (runtime_hours * 60 + interval_minutes - 1) // interval_minutes)
        merged = dict(task_params or {})
        merged.setdefault("long_run_runtime_hours", runtime_hours)
        merged.setdefault("long_run_interval_minutes", interval_minutes)
        merged.setdefault("long_run_estimated_max_rounds", max_rounds)
        merged.setdefault("retry_count", max(self._form_int(payload, "retry_count", default=0), 0))
        return merged

    def _configure_unattended_for_created_task(
        self,
        payload: Mapping[str, list[str]],
        *,
        task_id: str,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "unattended_service", None)
        if service is None or not hasattr(service, "configure_task"):
            return {
                "unattended_configured": False,
                "unattended_warning": "Unattended service is unavailable; task was created only.",
                "runner_path": "/runner",
            }
        runtime_hours = max(self._form_int(payload, "runtime_hours", default=12), 1)
        interval_minutes = max(self._form_int(payload, "interval_minutes", default=60), 1)
        max_rounds = max(1, (runtime_hours * 60 + interval_minutes - 1) // interval_minutes)
        record = service.configure_task(
            task_id=task_id,
            interval_minutes=interval_minutes,
            desired_device_count=max(self._form_int(payload, "desired_device_count", default=1), 1),
            primary_device_ids=self._expand_form_values(payload, "devices"),
            backup_device_ids=self._expand_form_values(payload, "backup_devices")
            if self._form_bool(payload, "auto_backfill", default=True)
            else (),
            failure_threshold=max(self._form_int(payload, "failure_threshold", default=3), 1),
            max_round_history=max(max_rounds, 10),
            rotation_strategy=self._form_value(dict(payload), "rotation_strategy") or "round_robin",
            rotation_advance_policy=self._form_value(dict(payload), "rotation_advance_policy") or "every_round",
            max_device_window_history=max(max_rounds, 10),
            enabled=not self._form_bool(payload, "disabled", default=False),
            start_now=self._form_bool(payload, "start_now", default=True),
        )
        task_payload = self._unattended_task_payload(record)
        return {
            "unattended_configured": True,
            "runner_path": "/runner",
            "unattended_detail_path": f"/runner/unattended/{quote(task_id, safe='')}",
            "unattended_task": task_payload,
        }

    def _handle_run_create(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        task_id = self._required_form_value(dict(payload), "task_id")
        requested_devices = self._expand_form_values(payload, "devices") or self._expand_form_values(payload, "device")
        if not requested_devices:
            raise ValueError("Creating a Run requires at least one target device.")
        metadata = self._json_form_object(dict(payload), "metadata")
        actor = dict(request_context.get("current_actor", {}) or {})
        return run_create_use_case(
            self._bundle,
            CreateRunCommand(
                task_id=task_id,
                requested_device_ids=requested_devices,
                requested_by=str(actor.get("actor_id", "") or "web"),
                metadata=metadata,
            ),
        )

    def _handle_run_execute(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        service = getattr(self._bundle, "run_execution_service", None)
        if service is None or not hasattr(service, "execute_run"):
            raise ValueError("Run execution service is unavailable.")
        monitoring_backend = self._form_value(dict(payload), "monitoring_backend") or getattr(
            self._bundle,
            "monitoring_backend",
            None,
        )
        service, resolved_monitoring_backend = self._run_execution_service_for_backend(
            service,
            monitoring_backend,
        )
        return run_execute_use_case(
            service,
            ExecuteRunCommand(
                run_id=self._required_form_value(dict(payload), "run_id"),
                persist_monitoring=not self._form_bool(payload, "no_persist_monitoring", default=False),
                collect_snapshot=not self._form_bool(payload, "skip_monitoring", default=False),
                stop_on_failure=self._form_bool(payload, "stop_on_failure", default=False),
                max_concurrency=max(self._form_int(payload, "max_concurrency", default=1), 1),
                retry_count=max(self._form_int(payload, "retry_count", default=0), 0),
                monitoring_backend=resolved_monitoring_backend or monitoring_backend,
                requested_monitoring_backend=monitoring_backend or "",
            ),
        )

    def _handle_run_stop(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "run_execution_service", None)
        if service is None or not hasattr(service, "stop_run"):
            raise ValueError("Run stop service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        return run_stop_use_case(
            service,
            StopRunCommand(
                run_id=self._required_form_value(dict(payload), "run_id"),
                requested_by=str(actor.get("actor_id", "") or "web"),
                reason=self._form_value(dict(payload), "reason") or "user_stopped",
            ),
        )

    def _run_execution_service_for_backend(
        self,
        service: Any,
        requested_backend: object,
    ) -> tuple[Any, str]:
        backend = str(requested_backend or "").strip()
        if not backend or backend.lower() == "default":
            return service, str(getattr(self._bundle, "monitoring_backend", "") or "")
        try:
            from stability.app import RunExecutionService
            from stability.infrastructure import build_monitoring_adapter

            provider = ConfigProvider()
            adapter, resolved_backend = build_monitoring_adapter(
                requested_backend=backend,
                settings=provider.monitoring_settings(),
            )
            required_attrs = (
                "_task_repository",
                "_run_repository",
                "_instance_repository",
                "_execution_service",
            )
            if any(not hasattr(service, attr) for attr in required_attrs):
                return service, resolved_backend
            return (
                RunExecutionService(
                    task_repository=getattr(service, "_task_repository"),
                    run_repository=getattr(service, "_run_repository"),
                    instance_repository=getattr(service, "_instance_repository"),
                    execution_service=getattr(service, "_execution_service"),
                    monitoring_adapter=adapter,
                    artifact_path_planner=getattr(service, "_artifact_planner", None),
                    scenario_runners=getattr(service, "_scenario_runners", None),
                    artifact_collector=getattr(service, "_artifact_collector", None),
                    host_command_runner=getattr(service, "_host_command_runner", None),
                    report_service=getattr(service, "_report_service", None),
                ),
                resolved_backend,
            )
        except Exception:
            return service, backend


__all__ = ["TasksActionsMixin"]
