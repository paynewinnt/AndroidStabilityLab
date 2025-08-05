from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import ReleaseSubmissionRecord, TaskDefinition, TaskTargetApp, TaskTemplateType
from stability.domain.value_objects import SamplingConfig, new_id, utcnow


class ReleaseSubmissionRecordNotFound(LookupError):
    """Raised when one release submission record does not exist."""


class ReleaseSubmissionService:
    """Persist and orchestrate one minimal release-submission intake plus callback flow."""

    _default_template_type = "cold_start_loop"
    _default_sampling_interval = 5

    def __init__(
        self,
        *,
        task_service,
        execution_service,
        run_execution_service=None,
        admission_case_service=None,
        outbox_service=None,
        root_dir: str | Path = "runtime/release_submissions",
        monitoring_backend: str | None = None,
    ) -> None:
        self._task_service = task_service
        self._execution_service = execution_service
        self._run_execution_service = run_execution_service
        self._admission_case_service = admission_case_service
        self._outbox_service = outbox_service
        self._root_dir = Path(root_dir)
        self._submissions_path = self._root_dir / "submissions.json"
        self._monitoring_backend = str(monitoring_backend or "").strip()

    def list_submissions(self, *, limit: int = 50) -> tuple[ReleaseSubmissionRecord, ...]:
        items = [self._record_from_payload(item) for item in self._load_registry()]
        items.sort(
            key=lambda item: (
                item.created_at.isoformat() if item.created_at else "",
                item.submission_id,
            ),
            reverse=True,
        )
        if limit > 0:
            items = items[:limit]
        return tuple(items)

    def get_submission(self, submission_id: str) -> ReleaseSubmissionRecord:
        key = str(submission_id or "").strip()
        if not key:
            raise ReleaseSubmissionRecordNotFound("submission_id is required.")
        for item in self.list_submissions(limit=0):
            if item.submission_id == key:
                return item
        raise ReleaseSubmissionRecordNotFound(f"Release submission '{key}' was not found.")

    def create_submission(
        self,
        *,
        source_platform: str,
        source_request_id: str,
        package_name: str,
        version_name: str = "",
        version_code: str = "",
        build_id: str = "",
        release_channel: str = "",
        owner_team: str = "",
        submission_title: str = "",
        template_type: str = "",
        selected_device_ids: Sequence[str] = (),
        enabled_metrics: Sequence[str] = (),
        sampling_interval_seconds: int = _default_sampling_interval,
        monitoring_backend: str = "",
        execute_immediately: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
        created_by: str = "",
        metadata: Mapping[str, Any] | None = None,
        task_params: Mapping[str, Any] | None = None,
    ) -> ReleaseSubmissionRecord:
        normalized_source = str(source_platform or "").strip()
        normalized_request_id = str(source_request_id or "").strip()
        normalized_package = str(package_name or "").strip()
        if not normalized_source:
            raise ValueError("source_platform is required.")
        if not normalized_request_id:
            raise ValueError("source_request_id is required.")
        if not normalized_package:
            raise ValueError("package_name is required.")

        current_time = utcnow()
        submission_id = new_id("release_submission")
        normalized_template = str(template_type or self._default_template_type).strip() or self._default_template_type
        normalized_metrics = tuple(str(item).strip() for item in enabled_metrics if str(item).strip())
        normalized_metadata = dict(metadata or {})
        normalized_task_params = dict(task_params or {})
        normalized_created_by = str(created_by or "").strip() or normalized_source
        normalized_title = self._submission_title(
            package_name=normalized_package,
            version_name=version_name,
            build_id=build_id,
            explicit_title=submission_title,
        )
        task = TaskDefinition(
            task_name=normalized_title,
            template_type=TaskTemplateType(normalized_template),
            target_app=TaskTargetApp(
                package_name=normalized_package,
                version_name=str(version_name or "").strip(),
                version_code=str(version_code or "").strip(),
            ),
            task_params=normalized_task_params,
            selected_device_ids=list(selected_device_ids or ()),
            sampling_config=SamplingConfig(
                interval_seconds=max(int(sampling_interval_seconds or self._default_sampling_interval), 0),
                enabled_metrics=list(normalized_metrics),
                metadata={"release_submission_id": submission_id},
            ),
            created_by=normalized_created_by,
            notes=f"release_submission:{normalized_source}:{normalized_request_id}",
            metadata={
                **normalized_metadata,
                "release_submission": {
                    "submission_id": submission_id,
                    "source_platform": normalized_source,
                    "source_request_id": normalized_request_id,
                    "release_channel": str(release_channel or "").strip(),
                    "owner_team": str(owner_team or "").strip(),
                    "build_id": str(build_id or "").strip(),
                },
            },
        )
        task_result = self._task_service.create_task(task)
        batch = self._execution_service.create_run(
            task_result.task,
            requested_devices=tuple(selected_device_ids or ()),
            requested_by=normalized_created_by,
            metadata={
                "submission_id": submission_id,
                "source_platform": normalized_source,
                "source_request_id": normalized_request_id,
            },
        )

        run_status = str(getattr(batch.run, "run_status", "") or "")
        report_paths: dict[str, str] = {}
        execution_error = ""
        normalized_monitoring_backend = str(monitoring_backend or self._monitoring_backend or "").strip()
        if execute_immediately and self._run_execution_service is not None:
            try:
                executed = self._run_execution_service.execute_run(
                    batch.run.run_id,
                    max_concurrency=max(int(max_concurrency or 1), 1),
                    retry_count=max(int(retry_count or 0), 0),
                )
                run_status = str(getattr(executed.run, "run_status", run_status) or run_status)
                report_paths = {
                    str(key): str(value)
                    for key, value in dict(getattr(executed, "report_paths", {}) or {}).items()
                    if str(key).strip() and str(value).strip()
                }
            except Exception as exc:
                # 提测入口更看重“记录不能丢”，执行失败要沉淀到 submission 状态里而不是整条链直接中断。
                execution_error = str(exc)
                run_status = "failed"

        record = ReleaseSubmissionRecord(
            submission_id=submission_id,
            source_platform=normalized_source,
            source_request_id=normalized_request_id,
            package_name=normalized_package,
            version_name=str(version_name or "").strip(),
            version_code=str(version_code or "").strip(),
            build_id=str(build_id or "").strip(),
            release_channel=str(release_channel or "").strip(),
            owner_team=str(owner_team or "").strip(),
            submission_title=normalized_title,
            template_type=normalized_template,
            selected_device_ids=tuple(str(item).strip() for item in selected_device_ids if str(item).strip()),
            enabled_metrics=normalized_metrics,
            sampling_interval_seconds=max(int(sampling_interval_seconds or self._default_sampling_interval), 0),
            monitoring_backend=normalized_monitoring_backend,
            execute_immediately=bool(execute_immediately),
            submission_status=self._submission_status(
                execute_immediately=bool(execute_immediately),
                run_status=run_status,
                has_admission=False,
            ),
            task_id=str(getattr(task_result.task, "task_id", "") or ""),
            task_name=str(getattr(task_result.task, "task_name", "") or ""),
            run_id=str(getattr(batch.run, "run_id", "") or ""),
            run_status=run_status,
            report_paths=report_paths,
            created_at=current_time,
            created_by=normalized_created_by,
            updated_at=current_time,
            updated_by=normalized_created_by,
            metadata={
                **normalized_metadata,
                "task_params": normalized_task_params,
                "execution_error": execution_error,
            },
        )
        self._save_record(record)
        self._publish_event(
            event_type="release_submission.created",
            created_by=normalized_created_by,
            payload=self._event_payload(record),
        )
        self._publish_event(
            event_type="release_submission.execution_updated",
            created_by=normalized_created_by,
            payload=self._event_payload(record),
        )
        return record

    def sync_admission_result(
        self,
        *,
        submission_id: str,
        baseline_key: str,
        synced_by: str,
    ) -> ReleaseSubmissionRecord:
        if self._admission_case_service is None:
            raise ValueError("Admission case service is unavailable.")
        record = self.get_submission(submission_id)
        case = self._admission_case_service.get_case(str(baseline_key or "").strip())
        final_decision = str(getattr(case, "final_decision", "") or "")
        if not final_decision:
            quality_gate = getattr(case, "quality_gate", None)
            final_decision = str(getattr(quality_gate, "final_decision", "") or "")
        updated = replace(
            record,
            baseline_key=str(getattr(case, "baseline_key", "") or baseline_key).strip(),
            admission_case_id=str(getattr(case, "case_id", "") or ""),
            admission_status=str(getattr(case, "status", "") or ""),
            admission_final_decision=final_decision,
            admission_error_code=str(getattr(case, "error_code", "") or ""),
            submission_status=self._submission_status(
                execute_immediately=record.execute_immediately,
                run_status=record.run_status,
                has_admission=True,
            ),
            updated_at=utcnow(),
            updated_by=str(synced_by or "").strip() or "system",
        )
        self._save_record(updated)
        self._publish_event(
            event_type="release_submission.admission_synced",
            created_by=updated.updated_by,
            payload=self._event_payload(updated),
        )
        return updated

    @staticmethod
    def _submission_title(
        *,
        package_name: str,
        version_name: str,
        build_id: str,
        explicit_title: str,
    ) -> str:
        label = str(explicit_title or "").strip()
        if label:
            return label
        suffix = str(version_name or "").strip() or str(build_id or "").strip() or "submission"
        return f"Release Submission {package_name} {suffix}".strip()

    @staticmethod
    def _submission_status(
        *,
        execute_immediately: bool,
        run_status: str,
        has_admission: bool,
    ) -> str:
        normalized_run_status = str(run_status or "").strip().lower()
        if has_admission:
            return "admission_synced"
        if execute_immediately and normalized_run_status in {"success", "failed", "cancelled"}:
            return "executed"
        if normalized_run_status in {"queued", "pending", "running"}:
            return "run_created"
        return "received"

    def _publish_event(
        self,
        *,
        event_type: str,
        created_by: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self._outbox_service is None:
            return
        self._outbox_service.publish_event(
            event_type=event_type,
            target_type="release_submission",
            target_id=str(payload.get("submission_id", "") or ""),
            created_by=str(created_by or "").strip() or "system",
            payload=payload,
        )

    @staticmethod
    def _event_payload(record: ReleaseSubmissionRecord) -> dict[str, Any]:
        return {
            "submission_id": record.submission_id,
            "source_platform": record.source_platform,
            "source_request_id": record.source_request_id,
            "package_name": record.package_name,
            "version_name": record.version_name,
            "version_code": record.version_code,
            "build_id": record.build_id,
            "release_channel": record.release_channel,
            "owner_team": record.owner_team,
            "submission_title": record.submission_title,
            "template_type": record.template_type,
            "selected_device_ids": list(record.selected_device_ids),
            "enabled_metrics": list(record.enabled_metrics),
            "sampling_interval_seconds": int(record.sampling_interval_seconds),
            "monitoring_backend": record.monitoring_backend,
            "execute_immediately": bool(record.execute_immediately),
            "submission_status": record.submission_status,
            "task_id": record.task_id,
            "task_name": record.task_name,
            "run_id": record.run_id,
            "run_status": record.run_status,
            "report_paths": dict(record.report_paths or {}),
            "baseline_key": record.baseline_key,
            "admission_case_id": record.admission_case_id,
            "admission_status": record.admission_status,
            "admission_final_decision": record.admission_final_decision,
            "admission_error_code": record.admission_error_code,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "created_by": record.created_by,
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
            "updated_by": record.updated_by,
            "metadata": dict(record.metadata or {}),
        }

    def _save_record(self, record: ReleaseSubmissionRecord) -> None:
        registry = [item for item in self._load_registry() if str(item.get("submission_id", "") or "") != record.submission_id]
        registry.append(self._payload_from_record(record))
        self._save_registry(registry)

    def _load_registry(self) -> list[dict[str, Any]]:
        if not self._submissions_path.exists():
            return []
        try:
            payload = json.loads(self._submissions_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _save_registry(self, payload: list[dict[str, Any]]) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._submissions_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _payload_from_record(record: ReleaseSubmissionRecord) -> dict[str, Any]:
        return {
            "submission_id": record.submission_id,
            "source_platform": record.source_platform,
            "source_request_id": record.source_request_id,
            "package_name": record.package_name,
            "version_name": record.version_name,
            "version_code": record.version_code,
            "build_id": record.build_id,
            "release_channel": record.release_channel,
            "owner_team": record.owner_team,
            "submission_title": record.submission_title,
            "template_type": record.template_type,
            "selected_device_ids": list(record.selected_device_ids),
            "enabled_metrics": list(record.enabled_metrics),
            "sampling_interval_seconds": int(record.sampling_interval_seconds),
            "monitoring_backend": record.monitoring_backend,
            "execute_immediately": bool(record.execute_immediately),
            "submission_status": record.submission_status,
            "task_id": record.task_id,
            "task_name": record.task_name,
            "run_id": record.run_id,
            "run_status": record.run_status,
            "report_paths": dict(record.report_paths or {}),
            "baseline_key": record.baseline_key,
            "admission_case_id": record.admission_case_id,
            "admission_status": record.admission_status,
            "admission_final_decision": record.admission_final_decision,
            "admission_error_code": record.admission_error_code,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "created_by": record.created_by,
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
            "updated_by": record.updated_by,
            "metadata": dict(record.metadata or {}),
        }

    @staticmethod
    def _record_from_payload(payload: Mapping[str, Any]) -> ReleaseSubmissionRecord:
        def _parse_datetime(value: object) -> Any:
            raw = str(value or "").strip()
            if not raw:
                return None
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                return None

        from datetime import datetime

        return ReleaseSubmissionRecord(
            submission_id=str(payload.get("submission_id", "") or ""),
            source_platform=str(payload.get("source_platform", "") or ""),
            source_request_id=str(payload.get("source_request_id", "") or ""),
            package_name=str(payload.get("package_name", "") or ""),
            version_name=str(payload.get("version_name", "") or ""),
            version_code=str(payload.get("version_code", "") or ""),
            build_id=str(payload.get("build_id", "") or ""),
            release_channel=str(payload.get("release_channel", "") or ""),
            owner_team=str(payload.get("owner_team", "") or ""),
            submission_title=str(payload.get("submission_title", "") or ""),
            template_type=str(payload.get("template_type", "") or ReleaseSubmissionService._default_template_type),
            selected_device_ids=tuple(payload.get("selected_device_ids", []) or ()),
            enabled_metrics=tuple(payload.get("enabled_metrics", []) or ()),
            sampling_interval_seconds=int(payload.get("sampling_interval_seconds", ReleaseSubmissionService._default_sampling_interval) or ReleaseSubmissionService._default_sampling_interval),
            monitoring_backend=str(payload.get("monitoring_backend", "") or ""),
            execute_immediately=bool(payload.get("execute_immediately", False)),
            submission_status=str(payload.get("submission_status", "") or "received"),
            task_id=str(payload.get("task_id", "") or ""),
            task_name=str(payload.get("task_name", "") or ""),
            run_id=str(payload.get("run_id", "") or ""),
            run_status=str(payload.get("run_status", "") or ""),
            report_paths=dict(payload.get("report_paths", {}) or {}),
            baseline_key=str(payload.get("baseline_key", "") or ""),
            admission_case_id=str(payload.get("admission_case_id", "") or ""),
            admission_status=str(payload.get("admission_status", "") or ""),
            admission_final_decision=str(payload.get("admission_final_decision", "") or ""),
            admission_error_code=str(payload.get("admission_error_code", "") or ""),
            created_at=_parse_datetime(payload.get("created_at")),
            created_by=str(payload.get("created_by", "") or ""),
            updated_at=_parse_datetime(payload.get("updated_at")),
            updated_by=str(payload.get("updated_by", "") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
