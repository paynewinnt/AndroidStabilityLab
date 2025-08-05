from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

from stability.domain import (
    AnalysisSnapshotRecord,
    QualityGateRiskItem,
    RuleReviewFamilySummary,
    RuleReviewReportBaselineAuditEvent,
    RuleReviewReportBaselineAuditRecord,
    RuleReviewReportBaselineAuditVersionRecord,
    RuleReviewReportBaselineAuditView,
    RuleReviewReportBaselineHistoryEntry,
    RuleReviewReportBaselineRecord,
    RuleReviewReportBaselinePromotionResult,
    RuleReviewReportBaselineRollbackResult,
    RuleReviewReportComparisonFamily,
    RuleReviewReportComparisonRecord,
    RuleReviewReportEntry,
    RuleReviewReportRecord,
)
from stability.domain.value_objects import new_id, utcnow
from stability.time_utils import format_beijing_datetime


class RuleReviewReportRendererMixin:
    @classmethod
    def _render_markdown(cls, item: RuleReviewReportRecord) -> str:
        golden_summary = cls._golden_suite_summary_from_report_summary(item.summary)
        lines = [
            f"# {item.name}",
            "",
            f"- report_id: {item.report_id}",
            f"- created_at: {_display_datetime(item.created_at)}",
            f"- created_by: {item.created_by}",
            "",
            "## Summary",
            "",
            "```json",
            json.dumps(item.summary, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Golden Suite",
            "",
            "```json",
            json.dumps(golden_summary, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Filters",
            "",
            "```json",
            json.dumps(item.filters, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Review Snapshots",
            "",
        ]
        for entry in item.entries:
            lines.extend(
                [
                    f"- [{entry.decision}] {entry.snapshot_id} | {entry.name}",
                    f"  - created_at: {_display_datetime(entry.created_at)}",
                    f"  - policy_version: {entry.policy_version or 'n/a'}",
                    f"  - changed_family_count: {entry.changed_family_count}",
                    f"  - finding_count: {entry.finding_count}",
                    "  - golden_suite: {status} | cases={case_count} | failed={failed_count} | version={version}".format(
                        status=(
                            "pass"
                            if entry.golden_suite_passed is True
                            else "fail"
                            if entry.golden_suite_passed is False
                            else "n/a"
                        ),
                        case_count=entry.golden_suite_case_count,
                        failed_count=entry.golden_suite_failed_case_count,
                        version=entry.golden_suite_version or "n/a",
                    ),
                    f"  - candidate_path: {entry.candidate_path or 'n/a'}",
                    f"  - detail_path: {entry.detail_path}",
                ]
            )
        lines.extend(["", "## High Risk Families", ""])
        for item_family in item.high_risk_families:
            lines.append(
                "- [{highest_decision}] {change_type} | {issue_type} | {title} | snapshots={snapshot_count} | total_occurrences={total_occurrence_count}".format(
                    highest_decision=item_family.highest_decision,
                    change_type=item_family.change_type,
                    issue_type=item_family.issue_type or "unknown",
                    title=item_family.title or "untitled",
                    snapshot_count=item_family.snapshot_count,
                    total_occurrence_count=item_family.total_occurrence_count,
                )
            )
        return "\n".join(lines) + "\n"

    @classmethod
    def _render_comparison_markdown(cls, item: RuleReviewReportComparisonRecord) -> str:
        left_golden_suite = dict(item.summary.get("left_golden_suite", {}) or {})
        right_golden_suite = dict(item.summary.get("right_golden_suite", {}) or {})
        lines = [
            f"# {item.name}",
            "",
            f"- comparison_id: {item.comparison_id}",
            f"- created_at: {_display_datetime(item.created_at)}",
            f"- created_by: {item.created_by}",
            f"- left_report: {item.left_report_id} | {item.left_report_name}",
            f"- right_report: {item.right_report_id} | {item.right_report_name}",
            "",
            "## Summary",
            "",
            "```json",
            json.dumps(item.summary, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Golden Suite",
            "",
            "### Left",
            "",
            "```json",
            json.dumps(left_golden_suite, ensure_ascii=False, indent=2),
            "```",
            "",
            "### Right",
            "",
            "```json",
            json.dumps(right_golden_suite, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Family Diffs",
            "",
        ]
        for family in item.family_diffs:
            lines.append(
                "- [{delta_status}] {change_type} | {issue_type} | {title} | left_occurrences={left_count} | right_occurrences={right_count}".format(
                    delta_status=family.delta_status,
                    change_type=family.change_type or "unknown",
                    issue_type=family.issue_type or "unknown",
                    title=family.title or "untitled",
                    left_count=family.left_total_occurrence_count,
                    right_count=family.right_total_occurrence_count,
                )
            )
        return "\n".join(lines) + "\n"

    @classmethod
    def _render_html(cls, item: RuleReviewReportRecord) -> str:
        summary_json = escape(json.dumps(item.summary, ensure_ascii=False, indent=2))
        golden_summary_json = escape(
            json.dumps(cls._golden_suite_summary_from_report_summary(item.summary), ensure_ascii=False, indent=2)
        )
        filters_json = escape(json.dumps(item.filters, ensure_ascii=False, indent=2))
        entry_rows = "\n".join(
            (
                "<tr>"
                f"<td>{escape(entry.snapshot_id)}</td>"
                f"<td>{escape(entry.decision)}</td>"
                f"<td>{escape(entry.policy_version)}</td>"
                f"<td>{entry.changed_family_count}</td>"
                f"<td>{entry.finding_count}</td>"
                f"<td>{escape('pass' if entry.golden_suite_passed is True else 'fail' if entry.golden_suite_passed is False else 'n/a')}</td>"
                f"<td>{entry.golden_suite_failed_case_count}/{entry.golden_suite_case_count}</td>"
                f"<td>{escape(entry.candidate_path)}</td>"
                "</tr>"
            )
            for entry in item.entries
        )
        family_rows = "\n".join(
            (
                "<tr>"
                f"<td>{escape(entry.highest_decision)}</td>"
                f"<td>{escape(entry.change_type)}</td>"
                f"<td>{escape(entry.issue_type)}</td>"
                f"<td>{escape(entry.title)}</td>"
                f"<td>{entry.snapshot_count}</td>"
                f"<td>{entry.total_occurrence_count}</td>"
                "</tr>"
            )
            for entry in item.high_risk_families
        )
        return f"""<!DOCTYPE html>
    <html lang="en">
      <head>
    <meta charset="utf-8" />
    <title>{escape(item.name)}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #1f2937; }}
      pre {{ background: #f3f4f6; padding: 12px; border-radius: 8px; overflow-x: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
      th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
      th {{ background: #f9fafb; }}
    </style>
      </head>
      <body>
    <h1>{escape(item.name)}</h1>
    <p>report_id: {escape(item.report_id)}</p>
    <p>created_at: {escape(_display_datetime(item.created_at))}</p>
    <p>created_by: {escape(item.created_by)}</p>
    <h2>Summary</h2>
    <pre>{summary_json}</pre>
    <h2>Golden Suite</h2>
    <pre>{golden_summary_json}</pre>
    <h2>Filters</h2>
    <pre>{filters_json}</pre>
    <h2>Review Snapshots</h2>
    <table>
      <thead>
        <tr><th>snapshot_id</th><th>decision</th><th>policy_version</th><th>changed_families</th><th>findings</th><th>golden_suite</th><th>golden_failed/cases</th><th>candidate_path</th></tr>
      </thead>
      <tbody>
        {entry_rows}
      </tbody>
    </table>
    <h2>High Risk Families</h2>
    <table>
      <thead>
        <tr><th>highest_decision</th><th>change_type</th><th>issue_type</th><th>title</th><th>snapshots</th><th>total_occurrences</th></tr>
      </thead>
      <tbody>
        {family_rows}
      </tbody>
    </table>
      </body>
    </html>
    """

    @classmethod
    def _render_comparison_html(cls, item: RuleReviewReportComparisonRecord) -> str:
        summary_json = escape(json.dumps(item.summary, ensure_ascii=False, indent=2))
        left_golden_suite_json = escape(
            json.dumps(dict(item.summary.get("left_golden_suite", {}) or {}), ensure_ascii=False, indent=2)
        )
        right_golden_suite_json = escape(
            json.dumps(dict(item.summary.get("right_golden_suite", {}) or {}), ensure_ascii=False, indent=2)
        )
        family_rows = "\n".join(
            (
                "<tr>"
                f"<td>{escape(entry.delta_status)}</td>"
                f"<td>{escape(entry.change_type)}</td>"
                f"<td>{escape(entry.issue_type)}</td>"
                f"<td>{escape(entry.title)}</td>"
                f"<td>{entry.left_total_occurrence_count}</td>"
                f"<td>{entry.right_total_occurrence_count}</td>"
                f"<td>{escape(entry.left_highest_decision)}</td>"
                f"<td>{escape(entry.right_highest_decision)}</td>"
                "</tr>"
            )
            for entry in item.family_diffs
        )
        return f"""<!DOCTYPE html>
    <html lang="en">
      <head>
    <meta charset="utf-8" />
    <title>{escape(item.name)}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #1f2937; }}
      pre {{ background: #f3f4f6; padding: 12px; border-radius: 8px; overflow-x: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
      th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
      th {{ background: #f9fafb; }}
    </style>
      </head>
      <body>
    <h1>{escape(item.name)}</h1>
    <p>comparison_id: {escape(item.comparison_id)}</p>
    <p>left_report: {escape(item.left_report_id)} | {escape(item.left_report_name)}</p>
    <p>right_report: {escape(item.right_report_id)} | {escape(item.right_report_name)}</p>
    <h2>Summary</h2>
    <pre>{summary_json}</pre>
    <h2>Golden Suite</h2>
    <h3>Left</h3>
    <pre>{left_golden_suite_json}</pre>
    <h3>Right</h3>
    <pre>{right_golden_suite_json}</pre>
    <h2>Family Diffs</h2>
    <table>
      <thead>
        <tr><th>delta_status</th><th>change_type</th><th>issue_type</th><th>title</th><th>left_occurrences</th><th>right_occurrences</th><th>left_decision</th><th>right_decision</th></tr>
      </thead>
      <tbody>
        {family_rows}
      </tbody>
    </table>
      </body>
    </html>
    """

    @classmethod
    def _render_baseline_audit_markdown(cls, item: RuleReviewReportBaselineAuditRecord) -> str:
        current_golden_suite = dict(item.summary.get("current_report_golden_suite", {}) or {})
        lines = [
            f"# {item.name}",
            "",
            f"- audit_id: {item.audit_id}",
            f"- baseline_key: {item.baseline_key}",
            f"- created_at: {_display_datetime(item.created_at)}",
            f"- created_by: {item.created_by}",
            f"- current_report: {item.current_report_id} | {item.current_report_name}",
            "",
            "## Summary",
            "",
            "```json",
            json.dumps(item.summary, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Current Report Golden Suite",
            "",
            "```json",
            json.dumps(current_golden_suite, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Timeline",
            "",
        ]
        for event in item.events:
            lines.extend(
                [
                    f"- [{event.action}] {_display_datetime(event.changed_at) if event.changed_at else 'n/a'} | {event.changed_by or 'unknown'}",
                    f"  - from: {event.from_report_id or 'n/a'} | {event.from_report_name or 'n/a'}",
                    f"  - to: {event.to_report_id or 'n/a'} | {event.to_report_name or 'n/a'}",
                    f"  - reason: {event.reason_summary or 'n/a'}",
                    f"  - comparison_id: {event.comparison_id or 'n/a'}",
                    f"  - policy_version: {event.policy_version or 'n/a'}",
                ]
            )
        return "\n".join(lines) + "\n"

    @classmethod
    def _render_baseline_audit_html(cls, item: RuleReviewReportBaselineAuditRecord) -> str:
        summary_json = escape(json.dumps(item.summary, ensure_ascii=False, indent=2))
        current_golden_suite_json = escape(
            json.dumps(dict(item.summary.get("current_report_golden_suite", {}) or {}), ensure_ascii=False, indent=2)
        )
        event_rows = "\n".join(
            (
                "<tr>"
                f"<td>{escape(entry.action)}</td>"
                f"<td>{escape(_display_datetime(entry.changed_at) if entry.changed_at else '')}</td>"
                f"<td>{escape(entry.changed_by)}</td>"
                f"<td>{escape(entry.from_report_id)}</td>"
                f"<td>{escape(entry.to_report_id)}</td>"
                f"<td>{escape(entry.reason_summary)}</td>"
                f"<td>{escape(entry.comparison_id)}</td>"
                f"<td>{escape(entry.policy_version)}</td>"
                "</tr>"
            )
            for entry in item.events
        )
        return f"""<!DOCTYPE html>
    <html lang="en">
      <head>
    <meta charset="utf-8" />
    <title>{escape(item.name)}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #1f2937; }}
      pre {{ background: #f3f4f6; padding: 12px; border-radius: 8px; overflow-x: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
      th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
      th {{ background: #f9fafb; }}
    </style>
      </head>
      <body>
    <h1>{escape(item.name)}</h1>
    <p>audit_id: {escape(item.audit_id)}</p>
    <p>baseline_key: {escape(item.baseline_key)}</p>
    <p>current_report: {escape(item.current_report_id)} | {escape(item.current_report_name)}</p>
    <h2>Summary</h2>
    <pre>{summary_json}</pre>
    <h2>Current Report Golden Suite</h2>
    <pre>{current_golden_suite_json}</pre>
    <h2>Timeline</h2>
    <table>
      <thead>
        <tr><th>action</th><th>changed_at</th><th>changed_by</th><th>from_report</th><th>to_report</th><th>reason</th><th>comparison_id</th><th>policy_version</th></tr>
      </thead>
      <tbody>
        {event_rows}
      </tbody>
    </table>
      </body>
    </html>
    """


def _display_datetime(value: object) -> str:
    return format_beijing_datetime(value) or ""
