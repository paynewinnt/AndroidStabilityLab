from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..execution_service import ExecutionInstanceLike, TaskDefinitionLike, TaskRunLike


class MetadataReportMixin:
    """Analysis-ready metadata, logging, and report rendering helpers."""

    @classmethod
    def _build_analysis_ready_metadata(
        cls,
        *,
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instance: "ExecutionInstanceLike",
        scenario_result,
        report_path: Path,
        html_report_path: Path,
        log_path: Path,
        monitoring_enabled: bool,
        snapshot_payload: Dict[str, Any] | None,
        exception: Exception | None = None,
    ) -> Dict[str, Any]:
        """Build a stable summary payload for downstream issue/artifact/report analysis."""
        issues = list(getattr(instance, "issues", []) or [])
        artifacts = list(getattr(instance, "artifacts", []) or [])
        target_app = getattr(task, "target_app", None)
        task_params = getattr(task, "task_params", {}) or {}
        scenario_metadata = dict(getattr(scenario_result, "metadata", {}) or {}) if scenario_result is not None else {}

        return {
            "schema_version": "v1",
            "instance": {
                "task_id": getattr(task, "task_id", "") or "",
                "run_id": getattr(run, "run_id", "") or "",
                "instance_id": getattr(instance, "instance_id", "") or "",
                "device_id": getattr(instance, "device_id", "") or "",
                "template_type": cls._enum_value(getattr(task, "template_type", "")),
                "package_name": getattr(target_app, "package_name", "") if target_app is not None else "",
                "launch_activity": getattr(target_app, "launch_activity", "") if target_app is not None else "",
                "task_param_keys": sorted(str(key) for key in task_params.keys()),
            },
            "scenario": {
                "success": bool(getattr(scenario_result, "success", False)) if scenario_result is not None else False,
                "exit_reason": cls._enum_value(getattr(scenario_result, "exit_reason", "")),
                "result_level": cls._enum_value(getattr(scenario_result, "result_level", "")),
                "note": str(getattr(scenario_result, "note", "") or ""),
                "highlights": list(getattr(scenario_result, "highlights", ()) or ()),
                "metadata_keys": sorted(str(key) for key in scenario_metadata.keys()),
                "template_type": str(scenario_metadata.get("template_type", "") or ""),
                "startup_failure_kind": str(scenario_metadata.get("startup_failure_kind", "") or ""),
                "startup_failure_loop": scenario_metadata.get("startup_failure_loop"),
            },
            "issues": {
                "count": len(issues),
                "types": sorted({issue.issue_type.value for issue in issues}),
                "blocking_count": sum(1 for issue in issues if issue.is_blocking()),
                "items": [
                    {
                        "issue_id": issue.issue_id,
                        "type": issue.issue_type.value,
                        "severity": issue.severity.value,
                        "title": issue.issue_title,
                        "source": issue.source,
                        "raw_key": issue.raw_key,
                        "process_name": issue.process_name,
                        "package_name": issue.package_name,
                        "pid": issue.pid,
                        "summary": issue.summary,
                        "metadata_keys": sorted(str(key) for key in (issue.metadata or {}).keys()),
                    }
                    for issue in issues
                ],
            },
            "artifacts": {
                "count": len(artifacts),
                "types": sorted({artifact.artifact_type.value for artifact in artifacts}),
                "items": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "artifact_type": artifact.artifact_type.value,
                        "issue_id": artifact.issue_id,
                        "capture_status": artifact.capture_status.value,
                        "capture_reason": artifact.capture_reason,
                        "file_path": artifact.file_path,
                        "size_bytes": artifact.size_bytes,
                        "metadata_keys": sorted(str(key) for key in (artifact.metadata or {}).keys()),
                    }
                    for artifact in artifacts
                ],
            },
            "report": {
                "markdown_path": str(report_path),
                "html_path": str(html_report_path),
                "execution_log_path": str(log_path),
                "formats": ["markdown", "html"],
                "monitoring_enabled": monitoring_enabled,
                "monitoring_snapshot_available": bool(snapshot_payload),
                "monitoring_backend": str(
                    dict((snapshot_payload or {}).get("metadata", {}) or {}).get("backend", "") or ""
                ),
                "monitoring_trace_path": cls._monitoring_trace_path(snapshot_payload),
            },
            "exception": {
                "type": exception.__class__.__name__,
                "message": str(exception),
            }
            if exception is not None
            else {},
        }

    @staticmethod
    def _enum_value(value: Any) -> Any:
        """Convert domain enums to plain strings while preserving primitive values."""
        return getattr(value, "value", value)

    @staticmethod
    def _append_log(path: Path, lines: Sequence[str]) -> None:
        """Append plain-text execution log lines to the instance log file."""
        text = "\n".join(lines).strip()
        if not text:
            return
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")

    def _write_reports(
        self,
        *,
        report_path: Path,
        html_report_path: Path,
        task: "TaskDefinitionLike",
        run: "TaskRunLike",
        instance: "ExecutionInstanceLike",
        monitoring_error: str,
        snapshot_payload: Dict[str, Any] | None,
        scenario_result,
    ) -> None:
        """Delegate report rendering to the shared report service."""
        self._report_service.write_instance_reports(
            markdown_path=report_path,
            html_path=html_report_path,
            task=task,
            run=run,
            instance=instance,
            monitoring_error=monitoring_error,
            snapshot_payload=snapshot_payload,
            scenario_result=scenario_result,
        )

