from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from stability.scenario.base import ScenarioExecutionResult

from .execution_service import ExecutionInstanceLike, TaskDefinitionLike, TaskRunLike


@dataclass(frozen=True)
class ReportPaths:
    """Resolved output paths for one instance report bundle."""

    markdown_path: str
    html_path: str


# ---------------------------------------------------------------------------
# Intermediate section representation — each section has a title, optional
# key-value pairs, optional line items, and an optional JSON blob.
# Rendering to Markdown or HTML is a short switch on these three fields.
# ---------------------------------------------------------------------------


@dataclass
class _Section:
    """One report section, independent of output format."""

    title: str
    key_values: List[Tuple[str, Any]] = field(default_factory=list)
    lines: List[str] = field(default_factory=list)
    json_data: Dict[str, Any] | None = None


class ReportService:
    """Render one instance execution report into Markdown and HTML."""

    # ── helpers for formatting per-artifact metadata ──────────────────────

    @staticmethod
    def _artifact_metadata_items(artifact) -> List[str]:
        metadata = dict(getattr(artifact, "metadata", {}) or {})
        items: List[str] = []
        for key in ("remote_path", "issue_process_name", "issue_pid", "captures", "candidate_count"):
            value = metadata.get(key)
            if value in (None, "", [], {}):
                continue
            items.append(f"{key}={value}")
        return items

    @staticmethod
    def _artifact_line(artifact) -> str:
        """One-line descriptor for an artifact (used by both MD & HTML)."""
        metadata_items = ReportService._artifact_metadata_items(artifact)
        line = (
            f"[{artifact.artifact_type.value}] {artifact.file_path} | "
            f"issue_id: {artifact.issue_id or 'none'} | "
            f"capture_status: {artifact.capture_status.value} | "
            f"size_bytes: {artifact.size_bytes or 0}"
        )
        if metadata_items:
            line = f"{line} | metadata: {'; '.join(metadata_items)}"
        return line

    @staticmethod
    def _issue_line(issue) -> str:
        """One-line descriptor for an issue (used by both MD & HTML)."""
        return (
            f"[{issue.issue_type.value}] {issue.issue_title} "
            f"({issue.severity.value}) | summary: {issue.summary or 'none'}"
        )

    @staticmethod
    def _format_iteration_line(item: dict) -> str:
        return (
            "iteration {iteration}: status={status}, wait_time_ms={wait_time_ms}, "
            "total_time_ms={total_time_ms}, this_time_ms={this_time_ms}".format(
                iteration=item.get("iteration", "n/a"),
                status=item.get("status", "unknown"),
                wait_time_ms=item.get("wait_time_ms", "n/a"),
                total_time_ms=item.get("total_time_ms", "n/a"),
                this_time_ms=item.get("this_time_ms", "n/a"),
            )
        )

    @staticmethod
    def _format_attempt_line(item: dict) -> str:
        return (
            "attempt {attempt}: status={status}, exit_reason={exit_reason}, "
            "retryable={retryable}, retry_category={retry_category}, note={note}".format(
                attempt=item.get("attempt", "n/a"),
                status=item.get("status", "unknown"),
                exit_reason=item.get("exit_reason", item.get("exception_type", "n/a")),
                retryable=item.get("retryable", False),
                retry_category=item.get("retry_category", "n/a"),
                note=item.get("note", "none"),
            )
        )

    @staticmethod
    def _format_cleanup_line(item: dict) -> str:
        return (
            "action={action}, reason={reason}, return_code={return_code}, "
            "timed_out={timed_out}".format(
                action=item.get("action", "unknown"),
                reason=item.get("reason", "none"),
                return_code=item.get("return_code", "n/a"),
                timed_out=item.get("timed_out", False),
            )
        )

    # ── top-level public entry point ──────────────────────────────────────

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
        scenario_result: ScenarioExecutionResult | None,
    ) -> ReportPaths:
        """Write both Markdown and HTML reports for one executed instance."""
        sections = self._build_sections(
            task=task,
            run=run,
            instance=instance,
            monitoring_error=monitoring_error,
            snapshot_payload=snapshot_payload,
            scenario_result=scenario_result,
        )
        markdown_path.write_text(self._render_markdown(sections), encoding="utf-8")
        html_path.write_text(self._render_html(sections), encoding="utf-8")
        return ReportPaths(markdown_path=str(markdown_path), html_path=str(html_path))

    # ── build sections (the ONE place that knows what data to include) ────

    def _build_sections(
        self,
        *,
        task: TaskDefinitionLike,
        run: TaskRunLike,
        instance: ExecutionInstanceLike,
        monitoring_error: str,
        snapshot_payload: Dict[str, Any] | None,
        scenario_result: ScenarioExecutionResult | None,
    ) -> List[_Section]:
        """Build report sections from raw instance data."""
        issues = list(instance.issues or [])
        artifacts = list(instance.artifacts or [])
        scenario_metadata = scenario_result.metadata if scenario_result is not None else None
        execution_summary_metadata = (
            instance.summary.metadata if instance.summary is not None else {}
        )
        startup_summary = scenario_metadata.get("startup_summary") if isinstance(scenario_metadata, dict) else None
        artifact_capture_errors = list(execution_summary_metadata.get("artifact_capture_errors", []) or [])
        execution_attempts = list(execution_summary_metadata.get("execution_attempts", []) or [])
        retry_policy = dict(execution_summary_metadata.get("retry_policy", {}) or {})
        cleanup_events = list(execution_summary_metadata.get("cleanup_events", []) or [])

        sections: List[_Section] = []

        # -- Summary (key-value pairs, always present) --
        summary_items: List[Tuple[str, Any]] = [
            ("task_id", task.task_id or ""),
            ("task_name", task.task_name),
            ("run_id", run.run_id or ""),
            ("instance_id", instance.instance_id or ""),
            ("device_id", instance.device_id),
            ("status", instance.instance_status or ""),
            ("monitoring_error", monitoring_error or "none"),
        ]
        if scenario_result is not None:
            summary_items.append(("scenario_note", scenario_result.note or "none"))
        if issues:
            summary_items.append(("issue_count", len(issues)))
        if artifacts:
            summary_items.append(("artifact_count", len(artifacts)))

        sections.append(_Section(title="Execution Summary (key_values)", key_values=summary_items))

        # -- Monitoring Snapshot --
        if snapshot_payload:
            sections.append(_Section(title="Monitoring Snapshot", json_data=snapshot_payload))

        # -- Startup Summary --
        if startup_summary:
            startup_items: List[Tuple[str, Any]] = [
                ("configured_loops", startup_summary.get("configured_loops", 0)),
                ("completed_loops", startup_summary.get("completed_loops", 0)),
                ("successful_loops", startup_summary.get("successful_loops", 0)),
                ("average_wait_time_ms", startup_summary.get("average_wait_time_ms", "n/a")),
                ("min_wait_time_ms", startup_summary.get("min_wait_time_ms", "n/a")),
                ("max_wait_time_ms", startup_summary.get("max_wait_time_ms", "n/a")),
                ("startup_timeout_ms", startup_summary.get("startup_timeout_ms", "n/a")),
                ("launch_target", startup_summary.get("launch_target", "n/a")),
            ]
            iteration_lines = [
                self._format_iteration_line(item)
                for item in startup_summary.get("iterations", []) or []
            ]
            sections.append(_Section(title="Startup Summary", key_values=startup_items, lines=iteration_lines))

        # -- Execution Attempts --
        if execution_attempts:
            attempt_items: List[Tuple[str, Any]] = [
                ("retry_count", retry_policy.get("retry_count", 0)),
                ("max_attempts", retry_policy.get("max_attempts", len(execution_attempts))),
                ("strategy", retry_policy.get("strategy", "legacy")),
            ]
            attempt_lines = [self._format_attempt_line(item) for item in execution_attempts]
            sections.append(_Section(title="Execution Attempts", key_values=attempt_items, lines=attempt_lines))

        # -- Cleanup --
        if cleanup_events:
            cleanup_lines = [self._format_cleanup_line(item) for item in cleanup_events]
            sections.append(_Section(title="Cleanup", lines=cleanup_lines))

        # -- Issues --
        if issues:
            issue_lines = [self._issue_line(issue) for issue in issues]
            sections.append(_Section(title="Issues", lines=issue_lines))

        # -- Artifacts --
        if artifacts:
            artifact_lines = [self._artifact_line(artifact) for artifact in artifacts]
            sections.append(_Section(title="Artifacts", lines=artifact_lines))

        # -- Artifact Capture Notes --
        if artifact_capture_errors:
            sections.append(_Section(title="Artifact Capture Notes", lines=list(artifact_capture_errors)))

        # -- Scenario Result --
        scenario_dict = scenario_metadata if isinstance(scenario_metadata, dict) else None
        if scenario_dict:
            sections.append(_Section(title="Scenario Result", json_data=scenario_dict))

        return sections

    # ── render to Markdown (tiny — only knows format, not data) ───────────

    @staticmethod
    def _render_markdown(sections: List[_Section]) -> str:
        lines: List[str] = []
        for section in sections:
            if section.title == "Execution Summary (key_values)":
                # First section — h1, not h2, no blank-line prefix
                lines.append("# Execution Summary")
                lines.append("")
                for key, value in section.key_values:
                    lines.append(f"- {key}: {value}")
                continue

            lines.append("")
            lines.append(f"## {section.title}")
            lines.append("")

            if section.key_values:
                for key, value in section.key_values:
                    lines.append(f"- {key}: {value}")

            if section.lines:
                for line_text in section.lines:
                    lines.append(f"- {line_text}")

            if section.json_data is not None:
                lines.append("```json")
                lines.append(json.dumps(section.json_data, ensure_ascii=False, indent=2))
                lines.append("```")

        return "\n".join(lines) + "\n"

    # ── render to HTML (tiny — only knows format, not data) ───────────────

    @staticmethod
    def _render_html(sections: List[_Section]) -> str:
        parts = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>Execution Summary</title>",
            "<style>"
            "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;color:#1f2328}"
            "h1,h2{margin-bottom:12px}"
            "section{margin-top:24px}"
            "ul{padding-left:20px}"
            "li{margin:6px 0}"
            "pre{background:#f6f8fa;padding:12px;border-radius:6px;overflow-x:auto}"
            "code{font-family:'SFMono-Regular',Menlo,monospace}"
            "</style>",
            "</head>",
            "<body>",
        ]

        for section in sections:
            html_section = ReportService._render_html_section(section)
            parts.append(html_section)

        parts.extend(["</body>", "</html>"])
        return "\n".join(parts) + "\n"

    @staticmethod
    def _render_html_section(section: _Section) -> str:
        """Render a single _Section as an HTML block."""
        buf: List[str] = []

        if section.title == "Execution Summary (key_values)":
            buf.append("<h1>Execution Summary</h1>")
            buf.append(ReportService._kv_list(section.key_values))
            return "\n".join(buf)

        buf.append("<section>")
        buf.append(f"<h2>{escape(section.title)}</h2>")

        if section.key_values:
            buf.append(ReportService._kv_list(section.key_values))

        if section.lines:
            buf.append(ReportService._html_lines(section.lines))

        if section.json_data is not None:
            buf.append(
                f"<pre><code>{escape(json.dumps(section.json_data, ensure_ascii=False, indent=2))}</code></pre>"
            )

        buf.append("</section>")
        return "\n".join(buf)

    # ── tiny HTML helpers ─────────────────────────────────────────────────

    @staticmethod
    def _kv_list(items: List[Tuple[str, Any]]) -> str:
        rendered = [f"<li><strong>{escape(str(k))}:</strong> {escape(str(v))}</li>" for k, v in items]
        return "<ul>\n" + "\n".join(rendered) + "\n</ul>"

    @staticmethod
    def _html_lines(lines: List[str]) -> str:
        if not lines:
            return "<ul></ul>"
        rendered = [f"<li>{escape(str(line))}</li>" for line in lines]
        return "<ul>\n" + "\n".join(rendered) + "\n</ul>"
