from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
from typing import Any, Dict

from .execution_service import ExecutionInstanceLike, TaskDefinitionLike, TaskRunLike


@dataclass(frozen=True)
class ReportPaths:
    """Resolved output paths for one instance report bundle."""

    markdown_path: str
    html_path: str


class ReportService:
    """Render one instance execution report into Markdown and HTML."""

    def write_instance_reports(
        self,
        *,
        markdown_path: Path,
        html_path: Path,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        monitoring_error: str,
        snapshot_payload: Dict[str, Any] | None,
        scenario_result,
    ) -> ReportPaths:
        """Write both Markdown and HTML reports for one executed instance."""
        report_data = self._build_report_data(
            task=task,
            run=run,
            instance=instance,
            monitoring_error=monitoring_error,
            snapshot_payload=snapshot_payload,
            scenario_result=scenario_result,
        )
        markdown_path.write_text(self._render_markdown(report_data), encoding="utf-8")
        html_path.write_text(self._render_html(report_data), encoding="utf-8")
        return ReportPaths(markdown_path=str(markdown_path), html_path=str(html_path))

    def _build_report_data(
        self,
        *,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        monitoring_error: str,
        snapshot_payload: Dict[str, Any] | None,
        scenario_result,
    ) -> Dict[str, Any]:
        issues = list(getattr(instance, "issues", []) or [])
        artifacts = list(getattr(instance, "artifacts", []) or [])
        scenario_metadata = getattr(scenario_result, "metadata", None)
        execution_summary_metadata = (
            getattr(instance, "summary", None).metadata if getattr(instance, "summary", None) is not None else {}
        )
        startup_summary = scenario_metadata.get("startup_summary") if isinstance(scenario_metadata, dict) else None
        artifact_capture_errors = execution_summary_metadata.get("artifact_capture_errors", [])

        summary_items = [
            ("task_id", getattr(task, "task_id", "")),
            ("task_name", getattr(task, "task_name", "")),
            ("run_id", getattr(run, "run_id", "")),
            ("instance_id", getattr(instance, "instance_id", "")),
            ("device_id", getattr(instance, "device_id", "")),
            ("status", getattr(instance, "instance_status", "")),
            ("monitoring_error", monitoring_error or "none"),
        ]
        if scenario_result is not None:
            summary_items.append(("scenario_note", getattr(scenario_result, "note", "") or "none"))
        if issues:
            summary_items.append(("issue_count", len(issues)))
        if artifacts:
            summary_items.append(("artifact_count", len(artifacts)))

        return {
            "summary_items": summary_items,
            "snapshot_payload": snapshot_payload,
            "startup_summary": startup_summary if isinstance(startup_summary, dict) else None,
            "execution_attempts": list(execution_summary_metadata.get("execution_attempts", []) or []),
            "cleanup_events": list(execution_summary_metadata.get("cleanup_events", []) or []),
            "retry_policy": dict(execution_summary_metadata.get("retry_policy", {}) or {}),
            "issues": issues,
            "artifacts": artifacts,
            "artifact_capture_errors": list(artifact_capture_errors or []),
            "scenario_metadata": scenario_metadata if isinstance(scenario_metadata, dict) else None,
        }

    def _render_markdown(self, report_data: Dict[str, Any]) -> str:
        content = ["# Execution Summary", ""]
        for key, value in report_data["summary_items"]:
            content.append(f"- {key}: {value}")

        snapshot_payload = report_data["snapshot_payload"]
        if snapshot_payload:
            content.extend(
                [
                    "",
                    "## Monitoring Snapshot",
                    "",
                    "```json",
                    json.dumps(snapshot_payload, ensure_ascii=False, indent=2),
                    "```",
                ]
            )

        startup_summary = report_data["startup_summary"]
        if startup_summary:
            content.extend(
                [
                    "",
                    "## Startup Summary",
                    "",
                    f"- configured_loops: {startup_summary.get('configured_loops', 0)}",
                    f"- completed_loops: {startup_summary.get('completed_loops', 0)}",
                    f"- successful_loops: {startup_summary.get('successful_loops', 0)}",
                    f"- average_wait_time_ms: {startup_summary.get('average_wait_time_ms', 'n/a')}",
                    f"- min_wait_time_ms: {startup_summary.get('min_wait_time_ms', 'n/a')}",
                    f"- max_wait_time_ms: {startup_summary.get('max_wait_time_ms', 'n/a')}",
                    f"- startup_timeout_ms: {startup_summary.get('startup_timeout_ms', 'n/a')}",
                    f"- launch_target: {startup_summary.get('launch_target', 'n/a')}",
                ]
            )
            for item in startup_summary.get("iterations", []) or []:
                content.append(
                    "- iteration {iteration}: status={status}, wait_time_ms={wait_time_ms}, "
                    "total_time_ms={total_time_ms}, this_time_ms={this_time_ms}".format(
                        iteration=item.get("iteration", "n/a"),
                        status=item.get("status", "unknown"),
                        wait_time_ms=item.get("wait_time_ms", "n/a"),
                        total_time_ms=item.get("total_time_ms", "n/a"),
                        this_time_ms=item.get("this_time_ms", "n/a"),
                    )
                )

        execution_attempts = report_data["execution_attempts"]
        retry_policy = report_data["retry_policy"]
        if execution_attempts:
            content.extend(
                [
                    "",
                    "## Execution Attempts",
                    "",
                    f"- retry_count: {retry_policy.get('retry_count', 0)}",
                    f"- max_attempts: {retry_policy.get('max_attempts', len(execution_attempts))}",
                    f"- strategy: {retry_policy.get('strategy', 'legacy')}",
                ]
            )
            for item in execution_attempts:
                content.append(
                    "- attempt {attempt}: status={status}, exit_reason={exit_reason}, retryable={retryable}, "
                    "retry_category={retry_category}, note={note}".format(
                        attempt=item.get("attempt", "n/a"),
                        status=item.get("status", "unknown"),
                        exit_reason=item.get("exit_reason", item.get("exception_type", "n/a")),
                        retryable=item.get("retryable", False),
                        retry_category=item.get("retry_category", "n/a"),
                        note=item.get("note", "none"),
                    )
                )

        cleanup_events = report_data["cleanup_events"]
        if cleanup_events:
            content.extend(["", "## Cleanup", ""])
            for item in cleanup_events:
                content.append(
                    "- action={action}, reason={reason}, return_code={return_code}, timed_out={timed_out}".format(
                        action=item.get("action", "unknown"),
                        reason=item.get("reason", "none"),
                        return_code=item.get("return_code", "n/a"),
                        timed_out=item.get("timed_out", False),
                    )
                )

        issues = report_data["issues"]
        if issues:
            content.extend(["", "## Issues", ""])
            for issue in issues:
                content.extend(
                    [
                        f"- [{issue.issue_type.value}] {issue.issue_title} ({issue.severity.value})",
                        f"  - summary: {issue.summary or 'none'}",
                    ]
                )

        artifacts = report_data["artifacts"]
        if artifacts:
            content.extend(["", "## Artifacts", ""])
            for artifact in artifacts:
                metadata_items = self._artifact_metadata_items(artifact)
                content.extend(
                    [
                        f"- [{artifact.artifact_type.value}] {artifact.file_path}",
                        f"  - issue_id: {artifact.issue_id or 'none'}",
                        f"  - capture_status: {artifact.capture_status.value}",
                        f"  - size_bytes: {artifact.size_bytes or 0}",
                    ]
                )
                if metadata_items:
                    content.append(f"  - metadata: {'; '.join(metadata_items)}")

        if report_data["artifact_capture_errors"]:
            content.extend(["", "## Artifact Capture Notes", ""])
            for note in report_data["artifact_capture_errors"]:
                content.append(f"- {note}")

        scenario_metadata = report_data["scenario_metadata"]
        if scenario_metadata:
            content.extend(
                [
                    "",
                    "## Scenario Result",
                    "",
                    "```json",
                    json.dumps(scenario_metadata, ensure_ascii=False, indent=2),
                    "```",
                ]
            )

        return "\n".join(content) + "\n"

    def _render_html(self, report_data: Dict[str, Any]) -> str:
        parts = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>Execution Summary</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #1f2328; }",
            "h1, h2 { margin-bottom: 12px; }",
            "section { margin-top: 24px; }",
            "ul { padding-left: 20px; }",
            "li { margin: 6px 0; }",
            "pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow-x: auto; }",
            "code { font-family: 'SFMono-Regular', Menlo, monospace; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Execution Summary</h1>",
            self._render_html_key_value_list(report_data["summary_items"]),
        ]

        snapshot_payload = report_data["snapshot_payload"]
        if snapshot_payload:
            parts.extend(
                [
                    "<section>",
                    "<h2>Monitoring Snapshot</h2>",
                    self._render_html_pre(json.dumps(snapshot_payload, ensure_ascii=False, indent=2)),
                    "</section>",
                ]
            )

        startup_summary = report_data["startup_summary"]
        if startup_summary:
            startup_items = [
                ("configured_loops", startup_summary.get("configured_loops", 0)),
                ("completed_loops", startup_summary.get("completed_loops", 0)),
                ("successful_loops", startup_summary.get("successful_loops", 0)),
                ("average_wait_time_ms", startup_summary.get("average_wait_time_ms", "n/a")),
                ("min_wait_time_ms", startup_summary.get("min_wait_time_ms", "n/a")),
                ("max_wait_time_ms", startup_summary.get("max_wait_time_ms", "n/a")),
                ("startup_timeout_ms", startup_summary.get("startup_timeout_ms", "n/a")),
                ("launch_target", startup_summary.get("launch_target", "n/a")),
            ]
            iteration_items = [
                (
                    "iteration {iteration}: status={status}, wait_time_ms={wait_time_ms}, "
                    "total_time_ms={total_time_ms}, this_time_ms={this_time_ms}".format(
                        iteration=item.get("iteration", "n/a"),
                        status=item.get("status", "unknown"),
                        wait_time_ms=item.get("wait_time_ms", "n/a"),
                        total_time_ms=item.get("total_time_ms", "n/a"),
                        this_time_ms=item.get("this_time_ms", "n/a"),
                    )
                )
                for item in startup_summary.get("iterations", []) or []
            ]
            parts.extend(
                [
                    "<section>",
                    "<h2>Startup Summary</h2>",
                    self._render_html_key_value_list(startup_items),
                    self._render_html_lines(iteration_items),
                    "</section>",
                ]
            )

        execution_attempts = report_data["execution_attempts"]
        retry_policy = report_data["retry_policy"]
        if execution_attempts:
            attempt_items = [
                ("retry_count", retry_policy.get("retry_count", 0)),
                ("max_attempts", retry_policy.get("max_attempts", len(execution_attempts))),
                ("strategy", retry_policy.get("strategy", "legacy")),
            ]
            attempt_lines = [
                (
                    "attempt {attempt}: status={status}, exit_reason={exit_reason}, retryable={retryable}, "
                    "retry_category={retry_category}, note={note}".format(
                        attempt=item.get("attempt", "n/a"),
                        status=item.get("status", "unknown"),
                        exit_reason=item.get("exit_reason", item.get("exception_type", "n/a")),
                        retryable=item.get("retryable", False),
                        retry_category=item.get("retry_category", "n/a"),
                        note=item.get("note", "none"),
                    )
                )
                for item in execution_attempts
            ]
            parts.extend(
                [
                    "<section>",
                    "<h2>Execution Attempts</h2>",
                    self._render_html_key_value_list(attempt_items),
                    self._render_html_lines(attempt_lines),
                    "</section>",
                ]
            )

        cleanup_events = report_data["cleanup_events"]
        if cleanup_events:
            parts.extend(
                [
                    "<section>",
                    "<h2>Cleanup</h2>",
                    self._render_html_lines(
                        [
                            "action={action}, reason={reason}, return_code={return_code}, timed_out={timed_out}".format(
                                action=item.get("action", "unknown"),
                                reason=item.get("reason", "none"),
                                return_code=item.get("return_code", "n/a"),
                                timed_out=item.get("timed_out", False),
                            )
                            for item in cleanup_events
                        ]
                    ),
                    "</section>",
                ]
            )

        issues = report_data["issues"]
        if issues:
            parts.extend(
                [
                    "<section>",
                    "<h2>Issues</h2>",
                    self._render_html_lines(
                        [
                            f"[{issue.issue_type.value}] {issue.issue_title} ({issue.severity.value}) | summary: {issue.summary or 'none'}"
                            for issue in issues
                        ]
                    ),
                    "</section>",
                ]
            )

        artifacts = report_data["artifacts"]
        if artifacts:
            artifact_lines = []
            for artifact in artifacts:
                metadata_items = self._artifact_metadata_items(artifact)
                line = (
                    f"[{artifact.artifact_type.value}] {artifact.file_path} | issue_id: {artifact.issue_id or 'none'} | "
                    f"capture_status: {artifact.capture_status.value} | size_bytes: {artifact.size_bytes or 0}"
                )
                if metadata_items:
                    line = f"{line} | metadata: {'; '.join(metadata_items)}"
                artifact_lines.append(line)
            parts.extend(
                [
                    "<section>",
                    "<h2>Artifacts</h2>",
                    self._render_html_lines(artifact_lines),
                    "</section>",
                ]
            )

        if report_data["artifact_capture_errors"]:
            parts.extend(
                [
                    "<section>",
                    "<h2>Artifact Capture Notes</h2>",
                    self._render_html_lines(report_data["artifact_capture_errors"]),
                    "</section>",
                ]
            )

        scenario_metadata = report_data["scenario_metadata"]
        if scenario_metadata:
            parts.extend(
                [
                    "<section>",
                    "<h2>Scenario Result</h2>",
                    self._render_html_pre(json.dumps(scenario_metadata, ensure_ascii=False, indent=2)),
                    "</section>",
                ]
            )

        parts.extend(["</body>", "</html>"])
        return "\n".join(parts) + "\n"

    @staticmethod
    def _artifact_metadata_items(artifact) -> list[str]:
        metadata = dict(getattr(artifact, "metadata", {}) or {})
        items = []
        for key in ("remote_path", "issue_process_name", "issue_pid", "captures", "candidate_count"):
            value = metadata.get(key)
            if value in (None, "", [], {}):
                continue
            items.append(f"{key}={value}")
        return items

    @staticmethod
    def _render_html_key_value_list(items) -> str:
        rendered = [f"<li><strong>{escape(str(key))}:</strong> {escape(str(value))}</li>" for key, value in items]
        return "<ul>\n" + "\n".join(rendered) + "\n</ul>"

    @staticmethod
    def _render_html_lines(lines) -> str:
        if not lines:
            return "<ul></ul>"
        rendered = [f"<li>{escape(str(line))}</li>" for line in lines]
        return "<ul>\n" + "\n".join(rendered) + "\n</ul>"

    @staticmethod
    def _render_html_pre(content: str) -> str:
        return f"<pre><code>{escape(content)}</code></pre>"
